"""Router per upload e conferma convenzione FAPI."""
import os
import uuid
import shutil
import logging
from datetime import datetime, date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session

import models
from database import get_db
from auth import get_current_user, User
import fapi_preview_store as _preview_store
from services import date_progetto, documento_progetto

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["fapi-convenzione"])

UPLOAD_DIR = os.path.join(os.getenv("UPLOADS_DIR", "/app/uploads"), "convenzioni")
os.makedirs(UPLOAD_DIR, exist_ok=True)


class ConfirmConvenzioneRequest(BaseModel):
    preview_token: str
    data_approvazione: date | None = None
    data_avvio_piano: date | None = None
    data_termine_piano: date | None = None
    data_avvio_attivita_formative: date | None = None
    data_fine_attivita_formative: date | None = None
    data_termine_rendicontazione: date | None = None
    data_chiusura_effettiva: date | None = None


class AssociaConvenzioneRequest(BaseModel):
    """UX-6: conferma dell'associazione a un progetto esistente.

    ``campi_da_applicare`` elenca i soli campi in conflitto che l'operatore ha
    scelto di sovrascrivere. Vuoto = nessuna sovrascrittura.
    """

    preview_token: str
    campi_da_applicare: list[str] = []


def _find_ente_in_db(db: Session, piva: str | None, ragione_sociale: str | None):
    if piva:
        ente = db.query(models.ImplementingEntity).filter(
            models.ImplementingEntity.partita_iva == piva
        ).first()
        if ente:
            return ente
    if ragione_sociale:
        ente = db.query(models.ImplementingEntity).filter(
            models.ImplementingEntity.ragione_sociale.ilike(f"%{ragione_sociale[:20]}%")
        ).first()
        return ente
    return None


def _find_azienda_in_db(db: Session, piva: str | None, ragione_sociale: str | None):
    if piva:
        az = db.query(models.AziendaCliente).filter(
            models.AziendaCliente.partita_iva == piva
        ).first()
        if az:
            return az
    if ragione_sociale:
        az = db.query(models.AziendaCliente).filter(
            models.AziendaCliente.ragione_sociale.ilike(f"%{ragione_sociale[:20]}%")
        ).first()
        return az
    return None


def _parse_date_str(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def _salva_pdf(file: UploadFile, token: str) -> str:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File deve essere un PDF")
    dest = os.path.join(UPLOAD_DIR, f"{token}.pdf")
    try:
        with open(dest, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Errore salvataggio file: {exc}")
    return dest


def _parse_pdf(dest: str) -> dict:
    try:
        from services.parsers.fapi.convenzione_parser import parse_convenzione
        return parse_convenzione(dest)
    except Exception as exc:
        os.remove(dest)
        raise HTTPException(status_code=500, detail=f"Errore parsing PDF: {exc}")


def _estratti_progetto(db: Session, preview: dict, file_path: str) -> dict:
    """Dati del documento nei nomi dei campi di ``Project``.

    Il costo totale alimenta sia ``costo_totale`` sia ``budget``, come fa il
    percorso di creazione: sono lo stesso dato con due usi.
    """
    piano = preview.get("piano") or {}
    ente_info = preview.get("ente_attuatore") or {}
    ente_id = ente_info.get("id")
    if not ente_id:
        db_ente = _find_ente_in_db(db, ente_info.get("partita_iva"), ente_info.get("ragione_sociale"))
        ente_id = db_ente.id if db_ente else None
    return {
        "codice_fapi": piano.get("codice_fapi"),
        "name": piano.get("titolo"),
        "delibera_numero": piano.get("delibera_numero"),
        "delibera_data": piano.get("delibera_data"),
        "costo_totale": piano.get("costo_totale"),
        "contributo_ente": piano.get("contributo_ente"),
        "cofinanziamento": piano.get("cofinanziamento"),
        "budget": piano.get("costo_totale"),
        "ente_attuatore_id": ente_id,
        "convenzione_file_path": file_path,
    }


def _associa_aziende(
    db: Session,
    project: models.Project,
    aziende: list[dict],
    current_user: User,
    codice_fapi: str | None,
) -> dict[str, int]:
    """Collega le aziende beneficiarie al progetto, creando le mancanti.

    Condiviso fra creazione e associazione: la stessa convenzione deve
    produrre gli stessi collegamenti in entrambi i percorsi.
    """
    create = 0
    associate = 0
    suggestions = 0

    for az_data in aziende:
        db_az = None
        if az_data.get("id"):
            db_az = db.query(models.AziendaCliente).filter(
                models.AziendaCliente.id == az_data["id"]
            ).first()
        if not db_az:
            db_az = _find_azienda_in_db(db, az_data.get("partita_iva"), az_data.get("ragione_sociale"))

        if not db_az:
            try:
                db_az = models.AziendaCliente(
                    ragione_sociale=az_data.get("ragione_sociale") or f"Azienda {az_data.get('partita_iva', 'sconosciuta')}",
                    partita_iva=az_data.get("partita_iva"),
                    codice_fiscale=az_data.get("codice_fiscale"),
                    attivo=True,
                )
                db.add(db_az)
                db.flush()
                create += 1
                suggestions += _suggerisci_documenti(db, db_az, current_user, codice_fapi)
            except Exception as exc:
                logger.warning("Errore creazione azienda %s: %s", az_data, exc)
                db.rollback()
                continue
        else:
            associate += 1

        try:
            existing_link = db.query(models.AziendaClienteProjectLink).filter(
                models.AziendaClienteProjectLink.azienda_cliente_id == db_az.id,
                models.AziendaClienteProjectLink.project_id == project.id,
            ).first()
            if not existing_link:
                db.add(models.AziendaClienteProjectLink(
                    azienda_cliente_id=db_az.id,
                    project_id=project.id,
                ))
        except Exception as exc:
            logger.warning("Errore link azienda-progetto: %s", exc)

    return {
        "aziende_create": create,
        "aziende_associate": associate,
        "suggestions_create": suggestions,
    }


def _suggerisci_documenti(
    db: Session,
    azienda: models.AziendaCliente,
    current_user: User,
    codice_fapi: str | None,
) -> int:
    run = models.AgentRun(
        agent_type="fapi_document_request",
        status="completed",
        entity_type="azienda_cliente",
        entity_id=azienda.id,
        requested_by_user_id=current_user.id,
    )
    db.add(run)
    db.flush()

    creati = 0
    for tipo_doc in ["visura_camerale", "durc", "autocertificazione_antimafia"]:
        db.add(models.AgentSuggestion(
            run_id=run.id,
            entity_type="azienda_cliente",
            entity_id=azienda.id,
            suggestion_type="documento_mancante",
            severity="high",
            status="pending",
            title=f"Richiedi {tipo_doc.replace('_', ' ')} — {azienda.ragione_sociale}",
            description=(
                f"Azienda beneficiaria creata da convenzione FAPI {codice_fapi}. "
                f"Documento obbligatorio: {tipo_doc.replace('_', ' ')}."
            ),
            priority="high",
        ))
        creati += 1
    return creati


@router.post("/upload-convenzione")
async def upload_convenzione(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    token = str(uuid.uuid4())
    dest = _salva_pdf(file, token)
    result = _parse_pdf(dest)

    # check duplicato codice_fapi
    codice_fapi = result["piano"].get("codice_fapi")
    if codice_fapi:
        existing = db.query(models.Project).filter(
            models.Project.codice_fapi == codice_fapi
        ).first()
        if existing:
            result["warnings"].append(
                f"Attenzione: esiste già un progetto con codice FAPI {codice_fapi} (id={existing.id})"
            )
            result["existing_project_id"] = existing.id

    # arricchisci con info DB per ente attuatore
    ente_info = result["ente_attuatore"]
    db_ente = _find_ente_in_db(db, ente_info.get("partita_iva"), ente_info.get("ragione_sociale"))
    ente_info["exists_in_db"] = db_ente is not None
    ente_info["id"] = db_ente.id if db_ente else None
    if db_ente:
        ente_info["ragione_sociale"] = db_ente.ragione_sociale
        ente_info["partita_iva"] = db_ente.partita_iva

    # arricchisci aziende beneficiarie
    for az in result["aziende_beneficiarie"]:
        db_az = _find_azienda_in_db(db, az.get("partita_iva"), az.get("ragione_sociale"))
        az["exists_in_db"] = db_az is not None
        az["id"] = db_az.id if db_az else None

    # salva preview in store condiviso (Redis o memory)
    _preview_store.store(token, {
        "file_path": dest,
        "original_filename": file.filename,
        **result,
    })

    return {
        "preview_token": token,
        **result,
    }


@router.post("/confirm-convenzione")
def confirm_convenzione(
    body: ConfirmConvenzioneRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    preview = _preview_store.pop(body.preview_token)
    if not preview:
        raise HTTPException(status_code=404, detail="Preview token non trovato o scaduto")

    piano = preview["piano"]
    codice_fapi = piano.get("codice_fapi")

    # UX-6: senza codice ne' titolo il documento non e' identificabile come atto
    # del fondo. Creare comunque un progetto produce solo un fantasma col nome
    # di fallback, scollegato da tutto (successo in produzione il 2026-07-27).
    if not documento_progetto.documento_riconosciuto(piano):
        try:
            os.remove(preview["file_path"])
        except OSError:
            pass
        raise HTTPException(
            status_code=422,
            detail=(
                "Documento non riconosciuto come convenzione: non è stato estratto "
                "né il codice del piano né il titolo. Se vuoi allegarlo a un progetto "
                "esistente, caricalo dalla scheda di quel progetto."
            ),
        )

    # check duplicato
    if codice_fapi:
        existing = db.query(models.Project).filter(
            models.Project.codice_fapi == codice_fapi
        ).first()
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Progetto con codice FAPI {codice_fapi} già esistente (id={existing.id})",
            )

    try:
        date_progetto.valida_date_progetto(
            {**body.model_dump(), "status": "active"},
            richiedi_date_nuovo_attivo=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # rinomina file con codice piano
    file_path = preview["file_path"]
    if codice_fapi:
        final_path = os.path.join(UPLOAD_DIR, f"{codice_fapi}.pdf")
        try:
            shutil.move(file_path, final_path)
            file_path = final_path
        except Exception:
            pass

    # risolvi ente attuatore
    ente_info = preview["ente_attuatore"]
    ente_id = ente_info.get("id")
    if not ente_id:
        db_ente = _find_ente_in_db(db, ente_info.get("partita_iva"), ente_info.get("ragione_sociale"))
        ente_id = db_ente.id if db_ente else None

    # crea progetto
    project = models.Project(
        name=piano.get("titolo") or (f"Piano FAPI {codice_fapi}" if codice_fapi else "Piano FAPI"),
        ente_erogatore="FAPI",
        ente_attuatore_id=ente_id,
        codice_fapi=codice_fapi,
        delibera_numero=piano.get("delibera_numero"),
        delibera_data=_parse_date_str(piano.get("delibera_data")),
        costo_totale=piano.get("costo_totale"),
        contributo_ente=piano.get("contributo_ente"),
        cofinanziamento=piano.get("cofinanziamento"),
        convenzione_file_path=file_path,
        status="active",
        budget=piano.get("costo_totale"),
        data_approvazione=body.data_approvazione,
        data_avvio_piano=body.data_avvio_piano,
        data_termine_piano=body.data_termine_piano,
        data_avvio_attivita_formative=body.data_avvio_attivita_formative,
        data_fine_attivita_formative=body.data_fine_attivita_formative,
        data_termine_rendicontazione=body.data_termine_rendicontazione,
        data_chiusura_effettiva=body.data_chiusura_effettiva,
    )
    db.add(project)
    db.flush()

    esito = _associa_aziende(
        db, project, preview["aziende_beneficiarie"], current_user, codice_fapi
    )

    db.commit()

    return {
        "project_id": project.id,
        "codice_fapi": codice_fapi,
        **esito,
    }


# ── UX-6: associazione a un progetto esistente ───────────────────────────────
# Il percorso project-less qui sopra CREA un progetto: e' giusto solo quando si
# parte da zero. Dalla scheda di un progetto si passa da qui, e il documento
# finisce sul progetto che l'operatore sta guardando.


@router.post("/{project_id}/upload-convenzione")
async def upload_convenzione_progetto(
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
    result = _parse_pdf(dest)

    ente_info = result["ente_attuatore"]
    db_ente = _find_ente_in_db(db, ente_info.get("partita_iva"), ente_info.get("ragione_sociale"))
    ente_info["exists_in_db"] = db_ente is not None
    ente_info["id"] = db_ente.id if db_ente else None

    for az in result["aziende_beneficiarie"]:
        db_az = _find_azienda_in_db(db, az.get("partita_iva"), az.get("ragione_sociale"))
        az["exists_in_db"] = db_az is not None
        az["id"] = db_az.id if db_az else None

    estratti = _estratti_progetto(db, result, dest)
    diff = documento_progetto.calcola_diff(project, estratti)

    _preview_store.store(token, {
        "project_id": project_id,
        "file_path": dest,
        "original_filename": file.filename,
        **result,
    })

    return {
        "preview_token": token,
        "project_id": project_id,
        "diff": diff,
        **result,
    }


@router.post("/{project_id}/confirm-convenzione")
def confirm_convenzione_progetto(
    project_id: int,
    body: AssociaConvenzioneRequest,
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

    piano = preview["piano"]
    codice_fapi = piano.get("codice_fapi")

    # Il codice del piano identifica il progetto: se e' gia' di un ALTRO
    # progetto, associarlo qui creerebbe due progetti con lo stesso codice.
    if codice_fapi:
        altro = db.query(models.Project).filter(
            models.Project.codice_fapi == codice_fapi,
            models.Project.id != project_id,
        ).first()
        if altro:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Il codice piano {codice_fapi} appartiene già al progetto "
                    f"'{altro.name}' (id={altro.id}): documento non associato."
                ),
            )

    file_path = preview["file_path"]
    if codice_fapi:
        final_path = os.path.join(UPLOAD_DIR, f"{codice_fapi}.pdf")
        try:
            shutil.move(file_path, final_path)
            file_path = final_path
        except Exception:
            pass

    estratti = _estratti_progetto(db, preview, file_path)
    esito_campi = documento_progetto.applica_estratti(
        project, estratti, body.campi_da_applicare
    )
    esito_aziende = _associa_aziende(
        db, project, preview.get("aziende_beneficiarie", []), current_user, codice_fapi
    )
    db.commit()

    return {
        "project_id": project.id,
        "codice_fapi": project.codice_fapi,
        **esito_campi,
        **esito_aziende,
    }
