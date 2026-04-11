"""Router per audit trail email in arrivo e controllo worker IMAP."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

import models
import schemas
from auth import get_current_user
from database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/email-inbox", tags=["Email Inbox"])


@router.get("/items", response_model=schemas.EmailInboxListResponse)
def list_items(
    status: Optional[str] = Query(None, description="Filtra per processing_status"),
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    q = db.query(models.EmailInboxItem)
    if status:
        q = q.filter(models.EmailInboxItem.processing_status == status)
    if entity_type:
        q = q.filter(models.EmailInboxItem.entity_type == entity_type)
    if entity_id is not None:
        q = q.filter(models.EmailInboxItem.entity_id == entity_id)
    total = q.count()
    items = q.order_by(models.EmailInboxItem.received_at.desc()).offset(skip).limit(limit).all()
    return schemas.EmailInboxListResponse(items=items, total=total)


@router.get("/items/{item_id}", response_model=schemas.EmailInboxItemOut)
def get_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    item = db.query(models.EmailInboxItem).filter(models.EmailInboxItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item non trovato")
    return item


@router.post("/trigger-poll", status_code=202)
def trigger_poll(
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
):
    """Triggera un ciclo di polling IMAP in background (fire-and-forget)."""
    def _run():
        try:
            from services.email_inbox_worker import EmailInboxWorker
            worker = EmailInboxWorker()
            from database import SessionLocal
            db = SessionLocal()
            try:
                worker._run_poll_cycle(db)
            finally:
                db.close()
        except Exception as exc:
            logger.exception("trigger-poll background fallito: %s", exc)

    background_tasks.add_task(_run)
    return {"message": "Polling avviato in background"}


@router.get("/status", response_model=schemas.EmailInboxStatusResponse)
def get_status(current_user=Depends(get_current_user)):
    from services.email_inbox_worker import get_worker_status
    return get_worker_status()
