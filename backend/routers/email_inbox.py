"""Router per audit trail email in arrivo e controllo worker IMAP."""
from __future__ import annotations

import logging
from typing import Optional
from types import SimpleNamespace
from mimetypes import guess_type

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

import models
import schemas
from agent_workflows import create_audit_log, sync_collaborator_data_quality
from auth import get_current_user
from database import get_db
from services.document_intake_agent import DocumentIntakeAgent

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


@router.get("/items/{item_id}/attachment")
def download_item_attachment(
    item_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from file_upload import get_file_path

    item = db.query(models.EmailInboxItem).filter(models.EmailInboxItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item non trovato")
    if not item.attachment_path:
        raise HTTPException(status_code=404, detail="Nessun allegato disponibile su questo item")

    file_path = get_file_path(item.attachment_path)
    media_type = guess_type(item.attachment_name or str(file_path))[0] or "application/octet-stream"
    return FileResponse(
        path=file_path,
        filename=item.attachment_name,
        media_type=media_type,
    )


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


def _resolve_related_mail_recovery_suggestions(
    db: Session,
    *,
    collaborator_id: int,
    doc_type: str,
    reviewed_by_user_id: Optional[int],
) -> list[int]:
    suggestion_types = {
        "documento_identita": {"email_identity_document_followup"},
        "curriculum": {"email_missing_collaborator_data"},
    }.get(doc_type, set())

    if not suggestion_types:
        return []

    suggestions = (
        db.query(models.AgentSuggestion)
        .join(models.AgentRun, models.AgentSuggestion.run_id == models.AgentRun.id)
        .filter(
            models.AgentRun.agent_type == "mail_recovery",
            models.AgentSuggestion.entity_type == "collaborator",
            models.AgentSuggestion.entity_id == collaborator_id,
            models.AgentSuggestion.suggestion_type.in_(tuple(suggestion_types)),
            models.AgentSuggestion.status.in_(("pending", "waiting", "approved", "sent", "followup_due")),
        ).all()
    )

    resolved_ids: list[int] = []
    for suggestion in suggestions:
        suggestion.status = "completed"
        suggestion.reviewed_by_user_id = reviewed_by_user_id
        drafts = db.query(models.AgentCommunicationDraft).filter(
            models.AgentCommunicationDraft.suggestion_id == suggestion.id
        ).all()
        for draft in drafts:
            if draft.status != "completed":
                draft.status = "completed"
                draft.reviewed_by_user_id = reviewed_by_user_id
        resolved_ids.append(suggestion.id)
    return resolved_ids


@router.post("/items/{item_id}/assign", response_model=schemas.EmailInboxAssignResponse)
def assign_item_to_collaborator_document(
    item_id: int,
    payload: schemas.EmailInboxAssignPayload,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    item = db.query(models.EmailInboxItem).filter(models.EmailInboxItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item non trovato")
    if item.entity_type != "collaborator" or not item.entity_id:
        raise HTTPException(status_code=400, detail="Email non associata a un collaboratore")
    if not item.attachment_path:
        raise HTTPException(status_code=400, detail="Nessun allegato disponibile su questo item")

    normalized_doc_type = (payload.doc_type or "").strip().lower()
    if normalized_doc_type not in {"documento_identita", "curriculum"}:
        raise HTTPException(status_code=400, detail="Tipo documento non supportato")

    intake = DocumentIntakeAgent()
    fake_result = SimpleNamespace(
        doc_type=normalized_doc_type,
        valid=True,
        issues=[],
        extracted_data={"data_scadenza": payload.expiry_date.isoformat() if payload.expiry_date else None},
    )
    outcome = intake.apply_document_result(
        db,
        entity_type=item.entity_type,
        entity_id=item.entity_id,
        attachment_path=item.attachment_path,
        attachment_name=item.attachment_name,
        result=fake_result,
        expected_doc_type=normalized_doc_type,
    )

    item.processing_status = "valid"
    item.error_message = None
    item.llm_result = f"manual_assignment:{normalized_doc_type}"

    resolved_suggestion_ids = _resolve_related_mail_recovery_suggestions(
        db,
        collaborator_id=item.entity_id,
        doc_type=normalized_doc_type,
        reviewed_by_user_id=payload.reviewed_by_user_id or getattr(current_user, "id", None),
    )

    create_audit_log(
        db,
        entity="email_inbox_item",
        action="manual_document_assignment",
        old_value={"item_id": item.id, "processing_status": "manual_review"},
        new_value={
            "item_id": item.id,
            "processing_status": item.processing_status,
            "doc_type": normalized_doc_type,
            "resolved_suggestion_ids": resolved_suggestion_ids,
        },
        user_id=payload.reviewed_by_user_id or getattr(current_user, "id", None),
    )

    db.add(item)
    db.commit()
    db.refresh(item)

    try:
        sync_collaborator_data_quality(
            db,
            collaborator_id=item.entity_id,
            requested_by_user_id=payload.reviewed_by_user_id or getattr(current_user, "id", None),
            trigger_source="email_inbox_manual_assignment",
        )
    except Exception as exc:
        logger.warning("sync_collaborator_data_quality failed after inbox assignment %s: %s", item.id, exc)

    return schemas.EmailInboxAssignResponse(
        item=item,
        collaborator_updated_fields=outcome.collaborator_updated_fields,
        resolved_suggestion_ids=resolved_suggestion_ids,
        documento_richiesto_id=outcome.documento_richiesto_id,
    )
