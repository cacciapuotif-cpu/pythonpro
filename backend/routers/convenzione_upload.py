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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["fapi-convenzione"])

UPLOAD_DIR = os.path.join(os.getenv("UPLOADS_DIR", "/app/uploads"), "convenzioni")
os.makedirs(UPLOAD_DIR, exist_ok=True)


class ConfirmConvenzioneRequest(BaseModel):
    preview_token: str


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


@router.post("/upload-convenzione")
async def upload_convenzione(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File deve essere un PDF")

    # salva su disco
    token = str(uuid.uuid4())
    dest = os.path.join(UPLOAD_DIR, f"{token}.pdf")
    try:
        with open(dest, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Errore salvataggio file: {exc}")

    # parsing
    try:
        from services.parsers.fapi.convenzione_parser import parse_convenzione
        result = parse_convenzione(dest)
    except Exception as exc:
        os.remove(dest)
        raise HTTPException(status_code=500, detail=f"Errore parsing PDF: {exc}")

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
    )
    db.add(project)
    db.flush()

    aziende_create = 0
    aziende_associate = 0
    suggestions_create = 0

    for az_data in preview["aziende_beneficiarie"]:
        # trova o crea azienda
        db_az = None
        if az_data.get("id"):
            db_az = db.query(models.AziendaCliente).filter(
                models.AziendaCliente.id == az_data["id"]
            ).first()

        if not db_az:
            db_az = _find_azienda_in_db(db, az_data.get("partita_iva"), az_data.get("ragione_sociale"))

        if not db_az:
            # crea nuova
            try:
                db_az = models.AziendaCliente(
                    ragione_sociale=az_data.get("ragione_sociale") or f"Azienda {az_data.get('partita_iva', 'sconosciuta')}",
                    partita_iva=az_data.get("partita_iva"),
                    codice_fiscale=az_data.get("codice_fiscale"),
                    attivo=True,
                )
                db.add(db_az)
                db.flush()
                aziende_create += 1

                # crea agent_suggestion per documenti mancanti
                run = models.AgentRun(
                    agent_type="fapi_document_request",
                    status="completed",
                    entity_type="azienda_cliente",
                    entity_id=db_az.id,
                    requested_by_user_id=current_user.id,
                )
                db.add(run)
                db.flush()

                for tipo_doc in ["visura_camerale", "durc", "autocertificazione_antimafia"]:
                    suggestion = models.AgentSuggestion(
                        run_id=run.id,
                        entity_type="azienda_cliente",
                        entity_id=db_az.id,
                        suggestion_type="documento_mancante",
                        severity="high",
                        status="pending",
                        title=f"Richiedi {tipo_doc.replace('_', ' ')} — {db_az.ragione_sociale}",
                        description=(
                            f"Azienda beneficiaria creata da convenzione FAPI {codice_fapi}. "
                            f"Documento obbligatorio: {tipo_doc.replace('_', ' ')}."
                        ),
                        priority="high",
                    )
                    db.add(suggestion)
                    suggestions_create += 1

            except Exception as exc:
                logger.warning("Errore creazione azienda %s: %s", az_data, exc)
                db.rollback()
                continue
        else:
            aziende_associate += 1

        # associa al progetto
        try:
            existing_link = db.query(models.AziendaClienteProjectLink).filter(
                models.AziendaClienteProjectLink.azienda_cliente_id == db_az.id,
                models.AziendaClienteProjectLink.project_id == project.id,
            ).first()
            if not existing_link:
                link = models.AziendaClienteProjectLink(
                    azienda_cliente_id=db_az.id,
                    project_id=project.id,
                )
                db.add(link)
        except Exception as exc:
            logger.warning("Errore link azienda-progetto: %s", exc)

    db.commit()

    return {
        "project_id": project.id,
        "codice_fapi": codice_fapi,
        "aziende_create": aziende_create,
        "aziende_associate": aziende_associate,
        "suggestions_create": suggestions_create,
    }
