"""Router per upload formulario FAPI."""
import os
import uuid
import shutil
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

import models
from database import get_db
from auth import get_current_user, User
import fapi_preview_store as _preview_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["fapi-formulario"])

UPLOAD_DIR = os.path.join(os.getenv("UPLOADS_DIR", "/app/uploads"), "formulari")
os.makedirs(UPLOAD_DIR, exist_ok=True)


class ConfirmFormularioRequest(BaseModel):
    preview_token: str


def _is_empty(value) -> bool:
    return value is None or value == ""


def _set_if_empty(obj, attr: str, value) -> bool:
    if value in (None, "") or not hasattr(obj, attr) or not _is_empty(getattr(obj, attr)):
        return False
    setattr(obj, attr, value)
    return True


def _find_azienda_cliente(db: Session, az_form: dict):
    ragione = (az_form.get("ragione_sociale") or "").strip()
    piva = az_form.get("partita_iva")
    cf = az_form.get("codice_fiscale")

    filters = []
    if piva:
        filters.append(models.AziendaCliente.partita_iva == piva)
    if cf:
        filters.append(models.AziendaCliente.codice_fiscale == cf)
    if ragione:
        filters.append(models.AziendaCliente.ragione_sociale.ilike(f"%{ragione}%"))
        if len(ragione) > 20:
            filters.append(models.AziendaCliente.ragione_sociale.ilike(f"%{ragione[:20]}%"))

    if not filters:
        return None
    return db.query(models.AziendaCliente).filter(or_(*filters)).first()


@router.post("/{project_id}/upload-formulario")
async def upload_formulario(
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
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(UPLOAD_DIR, f"{project_id}_{timestamp}_{token}.pdf")

    try:
        with open(dest, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Errore salvataggio: {exc}")

    try:
        from services.parsers.fapi.formulario_parser import parse_formulario
        result = parse_formulario(dest)
    except Exception as exc:
        os.remove(dest)
        raise HTTPException(status_code=500, detail=f"Errore parsing PDF: {exc}")

    _preview_store.store(token, {
        "project_id": project_id,
        "file_path": dest,
        **result,
    })

    return {
        "preview_token": token,
        "project_id": project_id,
        "codice_fapi": project.codice_fapi,
        **result,
    }


@router.post("/{project_id}/confirm-formulario")
def confirm_formulario(
    project_id: int,
    body: ConfirmFormularioRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Progetto non trovato")

    preview = _preview_store.pop(body.preview_token)
    if not preview:
        raise HTTPException(status_code=404, detail="Preview token non trovato o scaduto")

    if preview["project_id"] != project_id:
        raise HTTPException(status_code=400, detail="Token non appartiene a questo progetto")

    # ── Aggiorna nome progetto se estratto dal formulario ───────────────────
    titolo_piano = preview.get("titolo_piano")
    if titolo_piano and (not project.name or project.name.startswith("Piano FAPI")):
        project.name = titolo_piano

    # ── Arricchisci aziende beneficiarie con dati anagrafici dal formulario ─
    aziende_arricchite = 0
    regimi_aiuto_impostati = 0
    for az_form in preview.get("aziende_beneficiarie", []):
        ragione = az_form.get("ragione_sociale", "")
        if not ragione:
            continue
        db_az = _find_azienda_cliente(db, az_form)
        if db_az:
            changed = False
            field_map = {
                "partita_iva": "partita_iva",
                "codice_fiscale": "codice_fiscale",
                "natura_giuridica": "natura_giuridica",
                "settore_codice": "settore_codice",
                "settore_descrizione": "settore_descrizione",
                "sede_legale_indirizzo": "sede_legale_indirizzo",
                "sede_legale_cap": "sede_legale_cap",
                "sede_legale_comune": "sede_legale_comune",
                "sede_legale_provincia": "sede_legale_provincia",
                "sede_operativa_indirizzo": "sede_operativa_indirizzo",
                "sede_operativa_cap": "sede_operativa_cap",
                "sede_operativa_comune": "sede_operativa_comune",
                "sede_operativa_provincia": "sede_operativa_provincia",
                "legale_rappresentante_nome": "legale_rappresentante_nome",
                "legale_rappresentante_cf": "legale_rappresentante_codice_fiscale",
                "legale_rappresentante_telefono": "legale_rappresentante_telefono",
                "legale_rappresentante_email": "legale_rappresentante_email",
                "matricola_inps": "matricola_inps",
                "anno_adesione": "anno_adesione",
                "num_dipendenti": "num_dipendenti",
                "ccnl_prevalente": "ccnl_prevalente",
            }
            for source, target in field_map.items():
                try:
                    changed = _set_if_empty(db_az, target, az_form.get(source)) or changed
                except Exception as exc:
                    logger.warning(
                        "Campo azienda %s non aggiornato per %s: %s",
                        target,
                        ragione,
                        exc,
                    )

            changed = _set_if_empty(db_az, "telefono", az_form.get("legale_rappresentante_telefono")) or changed
            changed = _set_if_empty(db_az, "email", az_form.get("legale_rappresentante_email")) or changed
            changed = _set_if_empty(db_az, "indirizzo", az_form.get("sede_legale_indirizzo")) or changed
            changed = _set_if_empty(db_az, "cap", az_form.get("sede_legale_cap")) or changed
            changed = _set_if_empty(db_az, "citta", az_form.get("sede_legale_comune")) or changed
            changed = _set_if_empty(db_az, "regime_aiuto_default", az_form.get("regime_aiuto")) or changed

            if changed:
                aziende_arricchite += 1

            regime_aiuto = az_form.get("regime_aiuto")
            if regime_aiuto:
                link = db.query(models.AziendaClienteProjectLink).filter(
                    models.AziendaClienteProjectLink.azienda_cliente_id == db_az.id,
                    models.AziendaClienteProjectLink.project_id == project_id,
                ).first()
                if not link:
                    link = models.AziendaClienteProjectLink(
                        azienda_cliente_id=db_az.id,
                        project_id=project_id,
                    )
                    db.add(link)
                link.regime_aiuto = regime_aiuto
                regimi_aiuto_impostati += 1

    # ── Crea moduli formativi ─────────────────────────────────────────────────
    moduli_creati = 0
    for m in preview.get("tutti_moduli", []):
        try:
            modulo = models.ModuloFormativo(
                project_id=project_id,
                codice_progetto_fapi=m.get("codice_progetto_fapi"),
                titolo_modulo=m.get("titolo_modulo", ""),
                materia=m.get("materia"),
                modalita_erogazione=m.get("modalita_erogazione"),
                tipo_attivita=m.get("tipo_attivita", "formativa"),
                ore_previste=m.get("ore_previste"),
                obiettivo=m.get("obiettivo"),
            )
            db.add(modulo)
            moduli_creati += 1
        except Exception as exc:
            logger.warning("Errore creazione modulo %s: %s", m, exc)

    db.commit()

    return {
        "project_id": project_id,
        "moduli_creati": moduli_creati,
        "aziende_arricchite": aziende_arricchite,
        "regimi_aiuto_impostati": regimi_aiuto_impostati,
        "nome_progetto": project.name,
    }
