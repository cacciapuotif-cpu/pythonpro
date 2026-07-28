"""Router per upload e conferma documenti Fondimpresa."""
import hashlib
import logging
import os
import shutil
import uuid
from datetime import datetime, date

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

import fapi_preview_store as _preview_store
import models
from auth import User, get_current_user
from database import get_db
from services import date_progetto, documento_progetto
from services.parsers.fondimpresa.ammissione_parser import AmmissioneParser
from services.parsers.fondimpresa.riepilogo_parser import RiepilogoParser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["fondimpresa-upload"])

AMMISSIONI_DIR = os.path.join(os.getenv("UPLOADS_DIR", "/app/uploads"), "fondimpresa", "ammissioni")
RIEPILOGHI_DIR = os.path.join(os.getenv("UPLOADS_DIR", "/app/uploads"), "fondimpresa", "riepiloghi")
os.makedirs(AMMISSIONI_DIR, exist_ok=True)
os.makedirs(RIEPILOGHI_DIR, exist_ok=True)


class ConfirmPreviewRequest(BaseModel):
    preview_token: str
    data_approvazione: date | None = None
    data_avvio_piano: date | None = None
    data_termine_piano: date | None = None
    data_avvio_attivita_formative: date | None = None
    data_fine_attivita_formative: date | None = None
    data_termine_rendicontazione: date | None = None
    data_chiusura_effettiva: date | None = None


class AssociaAmmissioneRequest(BaseModel):
    """UX-6: conferma dell'associazione della lettera a un progetto esistente."""

    preview_token: str
    campi_da_applicare: list[str] = []


def _parse_date(value) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    text = str(value)
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%d 00:00:00"):
        try:
            return datetime.strptime(text[:19], fmt).date()
        except Exception:
            pass
    return None


def _safe_code(value: str | None, fallback: str) -> str:
    text = value or fallback
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in text)[:80]


def _find_ente(db: Session, ragione_sociale: str | None):
    if not ragione_sociale:
        return None
    return db.query(models.ImplementingEntity).filter(
        models.ImplementingEntity.ragione_sociale.ilike(f"%{ragione_sociale[:40]}%")
    ).first()


def _placeholder_piva(ragione_sociale: str) -> str:
    digest = hashlib.sha1(ragione_sociale.encode("utf-8")).hexdigest()
    return str(int(digest[:10], 16))[:10].zfill(10) + "0"


def _get_or_create_ente(db: Session, ragione_sociale: str | None):
    if not ragione_sociale:
        return None
    ente = _find_ente(db, ragione_sociale)
    if ente:
        return ente
    ente = models.ImplementingEntity(
        ragione_sociale=ragione_sociale,
        partita_iva=_placeholder_piva(ragione_sociale),
        note="Creato da upload Fondimpresa: P.IVA non presente nella lettera di ammissione.",
        is_active=True,
    )
    db.add(ente)
    db.flush()
    return ente


def _find_azienda(db: Session, az_data: dict):
    filters = []
    cf = az_data.get("codice_fiscale")
    piva = az_data.get("partita_iva")
    ragione = (az_data.get("ragione_sociale") or "").strip()
    if cf:
        filters.append(models.AziendaCliente.codice_fiscale == cf)
        if cf.isdigit() and len(cf) == 11:
            filters.append(models.AziendaCliente.partita_iva == cf)
    if piva:
        filters.append(models.AziendaCliente.partita_iva == piva)
    if ragione:
        filters.append(models.AziendaCliente.ragione_sociale.ilike(f"%{ragione[:40]}%"))
    if not filters:
        return None
    return db.query(models.AziendaCliente).filter(or_(*filters)).first()


def _create_document_suggestions(db: Session, azienda: models.AziendaCliente, current_user: User, codice_piano: str | None) -> int:
    run = models.AgentRun(
        agent_type="fondimpresa_document_request",
        status="completed",
        entity_type="azienda_cliente",
        entity_id=azienda.id,
        requested_by_user_id=current_user.id,
    )
    db.add(run)
    db.flush()
    count = 0
    for tipo_doc in ["visura_camerale", "durc", "autocertificazione_antimafia"]:
        db.add(models.AgentSuggestion(
            run_id=run.id,
            entity_type="azienda_cliente",
            entity_id=azienda.id,
            suggestion_type="documento_mancante",
            severity="high",
            status="pending",
            title=f"Richiedi {tipo_doc.replace('_', ' ')} - {azienda.ragione_sociale}",
            description=(
                f"Azienda beneficiaria creata da riepilogo Fondimpresa {codice_piano or ''}. "
                f"Documento obbligatorio: {tipo_doc.replace('_', ' ')}."
            ),
            priority="high",
        ))
        count += 1
    return count


def _categoria_for(voce: dict) -> str:
    combined = f"{voce.get('voce_codice') or ''} {voce.get('voce_descrizione') or ''} {voce.get('nominativo') or ''}".lower()
    if "docenz" in combined or "a1" in combined:
        return "docenza"
    if "tutor" in combined or "a2" in combined:
        return "tutoraggio"
    if "progett" in combined:
        return "progettazione"
    if "aula" in combined:
        return "aula"
    if "material" in combined:
        return "materiali_didattici"
    if "certific" in combined:
        return "certificazioni"
    if "coordin" in combined or "direzione" in combined:
        return "coordinamento"
    return "altro"


def _macrovoce(codice: str | None) -> str:
    first = (codice or "A").strip().upper()[:1]
    return first if first in {"A", "B", "C", "D"} else "A"


def _modalita(azione: dict) -> str:
    aula = float(azione.get("ore_aula") or 0)
    toj = float(azione.get("ore_toj") or 0)
    return "training_on_job" if toj > 0 and aula <= 0 else "aula"


@router.post("/fondimpresa/upload-ammissione")
async def upload_ammissione_fondimpresa(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File deve essere un PDF")

    token = str(uuid.uuid4())
    temp_path = os.path.join(AMMISSIONI_DIR, f"{token}.pdf")
    try:
        with open(temp_path, "wb") as fh:
            shutil.copyfileobj(file.file, fh)
        result = AmmissioneParser().parse(temp_path)
    except Exception as exc:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(status_code=500, detail=f"Errore parsing ammissione: {exc}")

    if result.get("codice_piano"):
        existing = db.query(models.Project).filter(models.Project.codice_fapi == result["codice_piano"]).first()
        if existing:
            result.setdefault("warnings", []).append(
                f"Esiste gia' un progetto con codice {result['codice_piano']} (id={existing.id})"
            )
            result["existing_project_id"] = existing.id

    _preview_store.store(token, {"file_path": temp_path, "original_filename": file.filename, **result})
    return {"preview_token": token, **result}


@router.post("/fondimpresa/confirm-ammissione")
def confirm_ammissione_fondimpresa(
    body: ConfirmPreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    preview = _preview_store.pop(body.preview_token)
    if not preview:
        raise HTTPException(status_code=404, detail="Preview token non trovato o scaduto")

    codice = preview.get("codice_piano")

    # UX-6: senza codice ne' titolo la lettera non identifica alcun piano.
    # Creare comunque un progetto genera solo un doppione col nome di fallback.
    if not documento_progetto.documento_riconosciuto(
        {"codice_fapi": codice, "titolo": preview.get("titolo_piano")}
    ):
        try:
            os.remove(preview.get("file_path") or "")
        except OSError:
            pass
        raise HTTPException(
            status_code=422,
            detail=(
                "Documento non riconosciuto come lettera di ammissione Fondimpresa: "
                "non e' stato estratto ne' il codice del piano ne' il titolo. Se vuoi "
                "allegarlo a un progetto esistente, caricalo dalla scheda di quel progetto."
            ),
        )

    if codice:
        existing = db.query(models.Project).filter(models.Project.codice_fapi == codice).first()
        if existing:
            raise HTTPException(status_code=409, detail=f"Progetto Fondimpresa gia' esistente (id={existing.id})")

    date_values = {
        **body.model_dump(),
        "status": "active",
        "data_approvazione": body.data_approvazione
        or _parse_date(preview.get("data_approvazione") or preview.get("determina_data")),
    }
    try:
        date_progetto.valida_date_progetto(
            date_values,
            richiedi_date_nuovo_attivo=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    file_path = preview.get("file_path")
    if file_path:
        final_path = os.path.join(AMMISSIONI_DIR, f"{_safe_code(codice, body.preview_token)}.pdf")
        try:
            shutil.move(file_path, final_path)
            file_path = final_path
        except Exception:
            pass

    ente = _get_or_create_ente(db, preview.get("soggetto_attuatore"))
    project = models.Project(
        name=preview.get("titolo_piano") or f"Piano Fondimpresa {codice or ''}".strip(),
        ente_erogatore="Fondimpresa",
        ente_attuatore_id=ente.id if ente else None,
        codice_fapi=codice,
        cup=preview.get("cup"),
        id_piano_esterno=preview.get("id_piano_esterno"),
        avviso=preview.get("avviso_numero"),
        data_approvazione=date_values["data_approvazione"],
        data_avvio_piano=body.data_avvio_piano,
        data_termine_piano=body.data_termine_piano,
        data_avvio_attivita_formative=body.data_avvio_attivita_formative,
        data_fine_attivita_formative=body.data_fine_attivita_formative,
        data_termine_rendicontazione=body.data_termine_rendicontazione,
        data_chiusura_effettiva=body.data_chiusura_effettiva,
        delibera_data=_parse_date(preview.get("determina_data")),
        costo_totale=preview.get("importo_totale"),
        contributo_ente=preview.get("contributo_ente"),
        cofinanziamento=preview.get("cofinanziamento"),
        convenzione_file_path=file_path,
        budget=preview.get("importo_totale"),
        status="active",
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return {"project_id": project.id, "codice_piano": project.codice_fapi, "nome_progetto": project.name}


@router.post("/{project_id}/fondimpresa/upload-riepilogo")
async def upload_riepilogo_fondimpresa(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Progetto non trovato")
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="File deve essere un Excel")

    token = str(uuid.uuid4())
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(RIEPILOGHI_DIR, f"{project_id}_{timestamp}_{token}.xlsx")
    try:
        with open(dest, "wb") as fh:
            shutil.copyfileobj(file.file, fh)
        result = RiepilogoParser().parse(dest)
    except Exception as exc:
        if os.path.exists(dest):
            os.remove(dest)
        raise HTTPException(status_code=500, detail=f"Errore parsing riepilogo: {exc}")

    _preview_store.store(token, {"project_id": project_id, "file_path": dest, **result})
    return {"preview_token": token, "project_id": project_id, **result}


@router.post("/{project_id}/fondimpresa/confirm-riepilogo")
def confirm_riepilogo_fondimpresa(
    project_id: int,
    body: ConfirmPreviewRequest,
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

    if preview.get("titolo_piano"):
        project.name = preview["titolo_piano"]
    project.ente_erogatore = "Fondimpresa"
    project.codice_fapi = preview.get("codice_piano") or project.codice_fapi
    project.cup = preview.get("cup") or project.cup
    project.id_piano_esterno = preview.get("id_piano_esterno") or project.id_piano_esterno
    project.avviso = preview.get("avviso_numero") or project.avviso
    project.data_approvazione = _parse_date(preview.get("data_approvazione")) or project.data_approvazione
    project.costo_totale = preview.get("importo_totale") or project.costo_totale
    project.contributo_ente = preview.get("contributo_ente") or project.contributo_ente
    project.cofinanziamento = preview.get("cofinanziamento") or project.cofinanziamento
    project.budget = preview.get("importo_totale") or project.budget

    aziende_create = 0
    aziende_associate = 0
    suggestions_create = 0
    aziende_by_name: dict[str, models.AziendaCliente] = {}

    for az_data in preview.get("aziende_beneficiarie", []):
        azienda = _find_azienda(db, az_data)
        if not azienda:
            cf = az_data.get("codice_fiscale")
            piva = az_data.get("partita_iva") or (cf if cf and cf.isdigit() and len(cf) == 11 else None)
            azienda = models.AziendaCliente(
                ragione_sociale=az_data.get("ragione_sociale") or "Azienda Fondimpresa",
                partita_iva=piva,
                codice_fiscale=cf,
                provincia=az_data.get("provincia"),
                regime_aiuto_default=az_data.get("regime_aiuto"),
                num_dipendenti=az_data.get("num_dipendenti"),
                attivo=True,
            )
            db.add(azienda)
            db.flush()
            aziende_create += 1
            suggestions_create += _create_document_suggestions(db, azienda, current_user, project.codice_fapi)
        else:
            aziende_associate += 1
            if az_data.get("regime_aiuto") and not azienda.regime_aiuto_default:
                azienda.regime_aiuto_default = az_data.get("regime_aiuto")
            if az_data.get("num_dipendenti") and not azienda.num_dipendenti:
                azienda.num_dipendenti = az_data.get("num_dipendenti")
            if az_data.get("provincia") and not azienda.provincia:
                azienda.provincia = az_data.get("provincia")

        link = db.query(models.AziendaClienteProjectLink).filter(
            models.AziendaClienteProjectLink.azienda_cliente_id == azienda.id,
            models.AziendaClienteProjectLink.project_id == project_id,
        ).first()
        if not link:
            link = models.AziendaClienteProjectLink(azienda_cliente_id=azienda.id, project_id=project_id)
            db.add(link)
        link.regime_aiuto = az_data.get("regime_aiuto") or link.regime_aiuto
        link.plafond_dichiarato = az_data.get("finanziamento") or link.plafond_dichiarato
        aziende_by_name[(azienda.ragione_sociale or "").strip().lower()] = azienda

    moduli_creati = 0
    for azione in preview.get("azioni_formative", []):
        azienda = aziende_by_name.get((azione.get("azienda_ragione_sociale") or "").strip().lower())
        modulo = models.ModuloFormativo(
            project_id=project_id,
            azienda_beneficiaria_id=azienda.id if azienda else None,
            codice_progetto_fapi=azione.get("id_azione_esterno"),
            titolo_modulo=azione.get("titolo") or "Azione Fondimpresa",
            materia=azione.get("tipologia"),
            modalita_erogazione=_modalita(azione),
            tipo_attivita="formativa",
            ore_previste=azione.get("ore_totali") or 0,
            obiettivo=(
                f"PAX: {azione.get('n_partecipanti') or 0}; "
                f"certificazione: {'si' if azione.get('certificazione') else 'no'}; "
                f"importo: {azione.get('importo') or 0}"
            ),
        )
        db.add(modulo)
        moduli_creati += 1

    anno = (project.data_approvazione or date.today()).year
    piano = db.query(models.PianoFinanziario).filter(
        models.PianoFinanziario.progetto_id == project_id,
        models.PianoFinanziario.tipo_fondo == "fondimpresa",
    ).first()
    if not piano:
        piano = models.PianoFinanziario(
            progetto_id=project_id,
            anno=anno,
            ente_erogatore="Fondimpresa",
            avviso_pf_id=getattr(project, "avviso_id", None),
            tipo_fondo="fondimpresa",
            codice_piano=project.codice_fapi,
            nome=f"Piano Finanziario Fondimpresa - {project.codice_fapi or project.name}",
            budget_totale=project.costo_totale or 0.0,
            budget_approvato=project.contributo_ente or project.costo_totale or 0.0,
            data_inizio=datetime.now(),
            data_fine=datetime(anno + 1, 12, 31),
            data_approvazione=project.data_approvazione,
            stato="bozza",
        )
        db.add(piano)
        db.flush()

    voci_piano = 0
    for voce_data in preview.get("piano_finanziario", []):
        ore = float(voce_data.get("ore_previste") or 0)
        importo = float(voce_data.get("importo_preventivo") or 0)
        tariffa = float(voce_data.get("tariffa_oraria") or 0)
        if not tariffa and ore:
            tariffa = round(importo / ore, 2)
        voce = models.VocePianoFinanziario(
            piano_id=piano.id,
            macrovoce=_macrovoce(voce_data.get("voce_codice")),
            voce_codice=(voce_data.get("voce_codice") or "A")[:10],
            categoria=_categoria_for(voce_data),
            sottocategoria=voce_data.get("voce_descrizione"),
            mansione_riferimento=voce_data.get("nominativo"),
            descrizione=voce_data.get("tipo_doc"),
            ore=ore,
            ore_previste=ore,
            tariffa_oraria=tariffa,
            importo_preventivo=importo,
            stato="previsto",
        )
        db.add(voce)
        voci_piano += 1

    db.commit()
    return {
        "project_id": project_id,
        "aziende_create": aziende_create,
        "aziende_associate": aziende_associate,
        "moduli_creati": moduli_creati,
        "voci_piano": voci_piano,
        "suggestions_create": suggestions_create,
        "piano_id": piano.id if piano else None,
    }



# ── UX-6: lettera di ammissione allegata a un progetto esistente ─────────────
# Stessa regola della convenzione FAPI: dalla scheda di un progetto il
# documento si associa, non genera un gemello.


def _estratti_progetto_fondimpresa(db: Session, preview: dict, file_path: str) -> dict:
    """Dati della lettera nei nomi dei campi di ``Project``."""
    ente = _find_ente(db, preview.get("soggetto_attuatore"))
    return {
        "codice_fapi": preview.get("codice_piano"),
        "name": preview.get("titolo_piano"),
        "cup": preview.get("cup"),
        "id_piano_esterno": preview.get("id_piano_esterno"),
        "avviso": preview.get("avviso_numero"),
        "data_approvazione": _parse_date(
            preview.get("data_approvazione") or preview.get("determina_data")
        ),
        "delibera_data": _parse_date(preview.get("determina_data")),
        "costo_totale": preview.get("importo_totale"),
        "contributo_ente": preview.get("contributo_ente"),
        "cofinanziamento": preview.get("cofinanziamento"),
        "budget": preview.get("importo_totale"),
        "ente_attuatore_id": ente.id if ente else None,
        "convenzione_file_path": file_path,
    }


@router.post("/{project_id}/fondimpresa/upload-ammissione")
async def upload_ammissione_progetto(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Progetto non trovato")
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File deve essere un PDF")

    token = str(uuid.uuid4())
    temp_path = os.path.join(AMMISSIONI_DIR, f"{token}.pdf")
    try:
        with open(temp_path, "wb") as fh:
            shutil.copyfileobj(file.file, fh)
        result = AmmissioneParser().parse(temp_path)
    except Exception as exc:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(status_code=500, detail=f"Errore parsing ammissione: {exc}")

    diff = documento_progetto.calcola_diff(
        project, _estratti_progetto_fondimpresa(db, result, temp_path)
    )

    _preview_store.store(token, {
        "project_id": project_id,
        "file_path": temp_path,
        "original_filename": file.filename,
        **result,
    })
    return {"preview_token": token, "project_id": project_id, "diff": diff, **result}


@router.post("/{project_id}/fondimpresa/confirm-ammissione")
def confirm_ammissione_progetto(
    project_id: int,
    body: AssociaAmmissioneRequest,
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

    codice = preview.get("codice_piano")
    if codice:
        altro = db.query(models.Project).filter(
            models.Project.codice_fapi == codice,
            models.Project.id != project_id,
        ).first()
        if altro:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Il codice piano {codice} appartiene gia' al progetto "
                    f"'{altro.name}' (id={altro.id}): documento non associato."
                ),
            )

    file_path = preview.get("file_path")
    if codice and file_path:
        final_path = os.path.join(AMMISSIONI_DIR, f"{_safe_code(codice, body.preview_token)}.pdf")
        try:
            shutil.move(file_path, final_path)
            file_path = final_path
        except Exception:
            pass

    project.ente_erogatore = project.ente_erogatore or "Fondimpresa"
    esito = documento_progetto.applica_estratti(
        project,
        _estratti_progetto_fondimpresa(db, preview, file_path),
        body.campi_da_applicare,
    )
    db.commit()

    return {"project_id": project.id, "codice_piano": project.codice_fapi, **esito}
