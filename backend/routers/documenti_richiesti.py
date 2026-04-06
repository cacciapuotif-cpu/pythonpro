from datetime import datetime
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

import crud
from database import get_db
from file_upload import delete_file, save_uploaded_file

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Documenti Richiesti"])


class DocumentoRichiestoPayload(BaseModel):
    collaboratore_id: int
    tipo_documento: str
    descrizione: Optional[str] = None
    obbligatorio: bool = True
    data_scadenza: Optional[datetime] = None
    stato: Optional[str] = "richiesto"
    file_path: Optional[str] = None
    file_name: Optional[str] = None
    note_operatore: Optional[str] = None
    validato_da: Optional[str] = None
    validato_il: Optional[datetime] = None


class DocumentoRichiestoUpdatePayload(BaseModel):
    collaboratore_id: Optional[int] = None
    tipo_documento: Optional[str] = None
    descrizione: Optional[str] = None
    obbligatorio: Optional[bool] = None
    data_scadenza: Optional[datetime] = None
    data_caricamento: Optional[datetime] = None
    stato: Optional[str] = None
    file_path: Optional[str] = None
    file_name: Optional[str] = None
    note_operatore: Optional[str] = None
    validato_da: Optional[str] = None
    validato_il: Optional[datetime] = None


class DocumentoReviewPayload(BaseModel):
    validato_da: Optional[str] = None
    note: Optional[str] = None


@router.get("/api/v1/documenti-richiesti/")
def list_documenti_richiesti(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    collaboratore_id: Optional[int] = Query(None),
    stato: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    return crud.get_documenti_richiesti(
        db,
        skip=skip,
        limit=limit,
        collaboratore_id=collaboratore_id,
        stato=stato,
    )


@router.get("/api/v1/documenti-richiesti/{doc_id}")
def get_documento_richiesto(
    doc_id: int,
    db: Session = Depends(get_db),
):
    documento = crud.get_documento_richiesto(db, doc_id)
    if not documento:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento richiesto non trovato")
    return documento


@router.post("/api/v1/documenti-richiesti/", status_code=status.HTTP_201_CREATED)
def create_documento_richiesto(
    documento: DocumentoRichiestoPayload,
    db: Session = Depends(get_db),
):
    try:
        return crud.create_documento_richiesto(db, documento)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.put("/api/v1/documenti-richiesti/{doc_id}")
def update_documento_richiesto(
    doc_id: int,
    documento: DocumentoRichiestoUpdatePayload,
    db: Session = Depends(get_db),
):
    try:
        updated = crud.update_documento_richiesto(db, doc_id, documento)
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento richiesto non trovato")
        return updated
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.delete("/api/v1/documenti-richiesti/{doc_id}")
def delete_documento_richiesto(
    doc_id: int,
    db: Session = Depends(get_db),
):
    documento = crud.get_documento_richiesto(db, doc_id)
    if not documento:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento richiesto non trovato")

    if documento.file_path:
        try:
            delete_file(documento.file_path)
        except Exception:
            logger.warning("Impossibile eliminare il file associato al documento %s", doc_id)

    crud.delete_documento_richiesto(db, doc_id)
    return {"message": "Documento richiesto eliminato con successo", "doc_id": doc_id}


@router.get("/api/v1/collaborators/{collaboratore_id}/documenti")
def get_documenti_collaboratore(
    collaboratore_id: int,
    stato: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    collaboratore = crud.get_collaborator(db, collaboratore_id)
    if not collaboratore:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collaboratore non trovato")
    return crud.get_documenti_collaboratore(db, collaboratore_id, stato=stato)


@router.get("/api/v1/collaborators/{collaboratore_id}/documenti-mancanti")
def get_documenti_mancanti(
    collaboratore_id: int,
    db: Session = Depends(get_db),
):
    collaboratore = crud.get_collaborator(db, collaboratore_id)
    if not collaboratore:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collaboratore non trovato")
    return crud.get_documenti_mancanti(db, collaboratore_id)


@router.post("/api/v1/documenti-richiesti/{doc_id}/valida")
def valida_documento(
    doc_id: int,
    payload: DocumentoReviewPayload,
    db: Session = Depends(get_db),
):
    validato_da = (payload.validato_da or "").strip()
    if not validato_da:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="validato_da obbligatorio")
    documento = crud.valida_documento(db, doc_id, validato_da)
    if not documento:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento richiesto non trovato")
    return documento


@router.post("/api/v1/documenti-richiesti/{doc_id}/rifiuta")
def rifiuta_documento(
    doc_id: int,
    payload: DocumentoReviewPayload,
    db: Session = Depends(get_db),
):
    documento = crud.rifiuta_documento(db, doc_id, payload.note)
    if not documento:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento richiesto non trovato")
    return documento


@router.post("/api/v1/documenti-richiesti/{doc_id}/upload")
async def upload_documento_richiesto(
    doc_id: int,
    file: UploadFile = File(...),
    data_scadenza: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    documento = crud.get_documento_richiesto(db, doc_id)
    if not documento:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento richiesto non trovato")

    try:
        filename, filepath = await save_uploaded_file(file, documento.collaboratore_id, "documento")
        update_payload = {
            "file_name": filename,
            "file_path": filepath,
            "data_caricamento": datetime.now(),
            "stato": "caricato",
        }
        if data_scadenza:
            update_payload["data_scadenza"] = datetime.fromisoformat(data_scadenza)
        return crud.update_documento_richiesto(db, doc_id, update_payload)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        logger.error("Errore upload documento richiesto %s: %s", doc_id, exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Errore nel caricamento file")
