"""Router per upload e conferma dell'Atto di adesione Formazienda (Allegato E).

Stessa forma della convenzione FAPI (upload -> preview -> confirm crea/associa),
con una differenza di dominio non negoziabile: l'Allegato E non porta MAI
aziende beneficiarie. Aziende, sedi e allievi restano selezionabili a mano
nello Step Delivery (vedi crud._validate_delivery_update e
routers.projects.read_project_delivery_companies).
"""
import os
import shutil
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session

import models
import fapi_preview_store as _preview_store
from database import get_db
from auth import get_current_user, User
from services import date_progetto, documento_progetto
from services.parsers.formazienda.atto_adesione_parser import parse_atto_adesione

router = APIRouter(prefix="/api/v1/projects", tags=["formazienda-upload"])

UPLOAD_DIR = os.path.join(os.getenv("UPLOADS_DIR", "/app/uploads"), "formazienda", "atti_adesione")
os.makedirs(UPLOAD_DIR, exist_ok=True)


class ConfirmAttoAdesioneRequest(BaseModel):
    preview_token: str
    data_approvazione: date | None = None
    data_avvio_piano: date | None = None
    data_termine_piano: date | None = None
    data_avvio_attivita_formative: date | None = None
    data_fine_attivita_formative: date | None = None
    data_termine_rendicontazione: date | None = None
    data_chiusura_effettiva: date | None = None
    conferma_creazione_duplicato: bool = False


class AssociaAttoAdesioneRequest(BaseModel):
    preview_token: str
    campi_da_applicare: list[str] = []


def _salva_pdf(file: UploadFile, token: str) -> str:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File deve essere un PDF")
    dest = os.path.join(UPLOAD_DIR, f"{token}.pdf")
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return dest


def _find_ente_in_db(db: Session, piva: str | None, ragione_sociale: str | None):
    if piva:
        ente = db.query(models.ImplementingEntity).filter(
            models.ImplementingEntity.partita_iva == piva
        ).first()
        if ente:
            return ente
    if ragione_sociale:
        return db.query(models.ImplementingEntity).filter(
            models.ImplementingEntity.ragione_sociale.ilike(f"%{ragione_sociale[:20]}%")
        ).first()
    return None


def _get_or_create_ente(db: Session, ente_info: dict) -> models.ImplementingEntity | None:
    if not ente_info:
        return None
    ente = _find_ente_in_db(db, ente_info.get("partita_iva"), ente_info.get("ragione_sociale"))
    campi_ente = {
        "ragione_sociale": ente_info.get("ragione_sociale"),
        "partita_iva": ente_info.get("partita_iva"),
        "codice_fiscale": ente_info.get("codice_fiscale"),
        "indirizzo": ente_info.get("indirizzo"),
        "cap": ente_info.get("cap"),
        "citta": ente_info.get("citta"),
        "provincia": ente_info.get("provincia"),
        "legale_rappresentante_nome": ente_info.get("legale_rappresentante_nome"),
        "legale_rappresentante_cognome": ente_info.get("legale_rappresentante_cognome"),
        "legale_rappresentante_luogo_nascita": ente_info.get("legale_rappresentante_luogo_nascita"),
        "legale_rappresentante_comune_residenza": ente_info.get("legale_rappresentante_comune_residenza"),
        "legale_rappresentante_via_residenza": ente_info.get("legale_rappresentante_via_residenza"),
    }
    data_nascita = ente_info.get("legale_rappresentante_data_nascita")
    if data_nascita:
        campi_ente["legale_rappresentante_data_nascita"] = documento_progetto.parse_data(data_nascita)
    if ente is None:
        if not ente_info.get("partita_iva"):
            return None
        ente = models.ImplementingEntity(**{k: v for k, v in campi_ente.items() if v is not None})
        db.add(ente)
        db.flush()
        return ente
    # Arricchisce solo i campi vuoti: un ente gia' censito non viene ribaltato
    # da un parser, stessa regola non negoziabile di documento_progetto.
    for campo, valore in campi_ente.items():
        if valore is None:
            continue
        if not getattr(ente, campo, None):
            setattr(ente, campo, valore)
    return ente


def _estratti_progetto(preview: dict, ente, file_path: str) -> dict:
    piano = preview.get("piano") or {}
    return {
        "name": piano.get("titolo"),
        "id_piano_esterno": piano.get("id_piano_esterno"),
        "avviso": piano.get("avviso"),
        "delibera_data": piano.get("delibera_data"),
        "data_approvazione": piano.get("delibera_data"),
        "costo_totale": piano.get("costo_totale"),
        "contributo_ente": piano.get("quota_pubblica"),
        "cofinanziamento": piano.get("cofinanziamento"),
        "budget": piano.get("costo_totale"),
        "ente_attuatore_id": ente.id if ente else None,
        "convenzione_file_path": file_path,
    }


@router.post("/formazienda/upload-atto-adesione")
async def upload_atto_adesione(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    token = str(uuid.uuid4())
    dest = _salva_pdf(file, token)
    result = parse_atto_adesione(dest)

    ente_info = result.get("ente_attuatore") or {}
    db_ente = _find_ente_in_db(db, ente_info.get("partita_iva"), ente_info.get("ragione_sociale"))
    ente_info["exists_in_db"] = db_ente is not None
    ente_info["id"] = db_ente.id if db_ente else None

    _preview_store.store(token, {"file_path": dest, "original_filename": file.filename, **result})
    return {"preview_token": token, **result}


@router.post("/formazienda/confirm-atto-adesione")
def confirm_atto_adesione(
    body: ConfirmAttoAdesioneRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    preview = _preview_store.pop(body.preview_token)
    if not preview:
        raise HTTPException(status_code=404, detail="Preview token non trovato o scaduto")

    piano = preview.get("piano") or {}
    if not documento_progetto.documento_riconosciuto(
        {"codice_fapi": piano.get("id_piano_esterno"), "titolo": piano.get("titolo")}
    ):
        try:
            os.remove(preview["file_path"])
        except OSError:
            pass
        raise HTTPException(
            status_code=422,
            detail=(
                "Documento non riconosciuto come Atto di adesione: non e' stato "
                "estratto ne' l'ID del piano ne' il titolo. Se vuoi allegarlo a un "
                "progetto esistente, caricalo dalla scheda di quel progetto."
            ),
        )

    id_piano_esterno = piano.get("id_piano_esterno")
    if id_piano_esterno:
        existing = db.query(models.Project).filter(
            models.Project.id_piano_esterno == id_piano_esterno,
        ).first()
        if existing and not body.conferma_creazione_duplicato:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Progetto con ID piano {id_piano_esterno} gia' esistente "
                    f"(id={existing.id}). Per creare un secondo progetto serve "
                    "la conferma esplicita della duplicazione."
                ),
            )

    data_approvazione_effettiva = body.data_approvazione or documento_progetto.parse_data(
        piano.get("delibera_data")
    )
    try:
        date_progetto.valida_date_progetto(
            {**body.model_dump(), "status": "active", "data_approvazione": data_approvazione_effettiva},
            richiedi_date_nuovo_attivo=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    file_path = preview["file_path"]
    ente = _get_or_create_ente(db, preview.get("ente_attuatore") or {})

    project = models.Project(
        name=piano.get("titolo") or f"Piano Formazienda {id_piano_esterno or ''}".strip(),
        ente_erogatore="Formazienda",
        ente_attuatore_id=ente.id if ente else None,
        id_piano_esterno=id_piano_esterno,
        avviso=piano.get("avviso"),
        delibera_data=documento_progetto.parse_data(piano.get("delibera_data")),
        costo_totale=piano.get("costo_totale"),
        contributo_ente=piano.get("quota_pubblica"),
        cofinanziamento=piano.get("cofinanziamento"),
        convenzione_file_path=file_path,
        status="active",
        budget=piano.get("costo_totale"),
        data_approvazione=data_approvazione_effettiva,
        data_avvio_piano=body.data_avvio_piano,
        data_termine_piano=body.data_termine_piano,
        data_avvio_attivita_formative=body.data_avvio_attivita_formative,
        data_fine_attivita_formative=body.data_fine_attivita_formative,
        data_termine_rendicontazione=body.data_termine_rendicontazione,
        data_chiusura_effettiva=body.data_chiusura_effettiva,
    )
    db.add(project)
    db.flush()

    documento = documento_progetto.archivia_documento_progetto(
        db,
        project=project,
        preview=preview,
        file_path=file_path,
        tipo_documento="atto_concessione",
        current_user=current_user,
    )
    db.commit()

    return {
        "project_id": project.id,
        "id_piano_esterno": id_piano_esterno,
        "documento_id": documento.id,
        "documento_versione": documento.versione,
    }


@router.post("/{project_id}/formazienda/upload-atto-adesione")
async def upload_atto_adesione_progetto(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Progetto non trovato")

    token = str(uuid.uuid4())
    dest = _salva_pdf(file, token)
    result = parse_atto_adesione(dest)

    ente_info = result.get("ente_attuatore") or {}
    db_ente = _find_ente_in_db(db, ente_info.get("partita_iva"), ente_info.get("ragione_sociale"))
    estratti = _estratti_progetto(result, db_ente, dest)
    diff = documento_progetto.calcola_diff(project, estratti)

    _preview_store.store(token, {
        "project_id": project_id, "file_path": dest, "original_filename": file.filename, **result,
    })
    return {"preview_token": token, "project_id": project_id, "diff": diff, **result}


@router.post("/{project_id}/formazienda/confirm-atto-adesione")
def confirm_atto_adesione_progetto(
    project_id: int,
    body: AssociaAttoAdesioneRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Progetto non trovato")

    preview = _preview_store.pop(body.preview_token)
    if not preview:
        raise HTTPException(status_code=404, detail="Preview token non trovato o scaduto")
    if preview.get("project_id") != project_id:
        raise HTTPException(status_code=400, detail="Token non appartiene a questo progetto")

    file_path = preview["file_path"]
    ente = _get_or_create_ente(db, preview.get("ente_attuatore") or {})
    esito = documento_progetto.applica_estratti(
        project, _estratti_progetto(preview, ente, file_path), body.campi_da_applicare,
    )
    project.ente_erogatore = project.ente_erogatore or "Formazienda"
    documento = documento_progetto.archivia_documento_progetto(
        db, project=project, preview=preview, file_path=file_path,
        tipo_documento="atto_concessione", current_user=current_user,
    )
    db.commit()

    return {
        "project_id": project.id,
        "documento_id": documento.id,
        "documento_versione": documento.versione,
        **esito,
    }
