import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

import models
import schemas
from ai_agents import list_agent_definitions
from ai_agents.llm import probe_agent_llm_health
from agent_workflows import apply_workflow_action, promote_due_followups, run_agent_workflow
from database import get_db

router = APIRouter(prefix="/api/v1/agents", tags=["Agents"])


def _agent_run_query(db: Session):
    return db.query(models.AgentRun).options(
        selectinload(models.AgentRun.suggestions).selectinload(models.AgentSuggestion.review_actions)
    )


def _agent_suggestion_query(db: Session):
    return db.query(models.AgentSuggestion).options(
        selectinload(models.AgentSuggestion.review_actions)
    )


def _communication_draft_query(db: Session):
    return db.query(models.AgentCommunicationDraft)


@router.get("/catalog", response_model=List[schemas.AgentCatalogItem], response_model_by_alias=False)
def read_agent_catalog():
    return list_agent_definitions()


@router.get("/llm/health", response_model=schemas.AgentLlmHealth, response_model_by_alias=False)
def read_agent_llm_health():
    return probe_agent_llm_health()


@router.post("/run", response_model=schemas.AgentRun, response_model_by_alias=False)
def run_agent(payload: schemas.AgentRunRequest, db: Session = Depends(get_db)):
    try:
        run = run_agent_workflow(
            db,
            agent_name=payload.agent_name,
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
            requested_by_user_id=payload.requested_by_user_id,
            input_payload=payload.input_payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Esecuzione agente fallita: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Esecuzione agente fallita: {exc}")

    return _agent_run_query(db).filter(models.AgentRun.id == run.id).first()


@router.get("/runs", response_model=List[schemas.AgentRun], response_model_by_alias=False)
def read_agent_runs(
    agent_name: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    query = _agent_run_query(db)
    if agent_name:
        query = query.filter(models.AgentRun.agent_name == agent_name)
    if entity_type:
        query = query.filter(models.AgentRun.entity_type == entity_type)
    if entity_id is not None:
        query = query.filter(models.AgentRun.entity_id == entity_id)
    if status:
        query = query.filter(models.AgentRun.status == status)
    return query.order_by(models.AgentRun.started_at.desc()).limit(limit).all()


@router.get("/suggestions", response_model=List[schemas.AgentSuggestion], response_model_by_alias=False)
def read_agent_suggestions(
    agent_name: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    run_id: Optional[int] = None,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    promote_due_followups(db)
    query = _agent_suggestion_query(db)
    if agent_name:
        query = query.filter(models.AgentSuggestion.agent_name == agent_name)
    if entity_type:
        query = query.filter(models.AgentSuggestion.entity_type == entity_type)
    if entity_id is not None:
        query = query.filter(models.AgentSuggestion.entity_id == entity_id)
    if run_id is not None:
        query = query.filter(models.AgentSuggestion.run_id == run_id)
    if status:
        query = query.filter(models.AgentSuggestion.status == status)
    if severity:
        query = query.filter(models.AgentSuggestion.severity == severity)
    return query.order_by(models.AgentSuggestion.created_at.desc()).limit(limit).all()


@router.get("/communications", response_model=List[schemas.AgentCommunicationDraft], response_model_by_alias=False)
def read_agent_communications(
    agent_name: Optional[str] = None,
    recipient_type: Optional[str] = None,
    recipient_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    promote_due_followups(db)
    query = _communication_draft_query(db)
    if agent_name:
        query = query.filter(models.AgentCommunicationDraft.agent_name == agent_name)
    if recipient_type:
        query = query.filter(models.AgentCommunicationDraft.recipient_type == recipient_type)
    if recipient_id is not None:
        query = query.filter(models.AgentCommunicationDraft.recipient_id == recipient_id)
    if status:
        query = query.filter(models.AgentCommunicationDraft.status == status)
    return query.order_by(models.AgentCommunicationDraft.created_at.desc()).limit(limit).all()


@router.post("/communications/{draft_id}/status", response_model=schemas.AgentCommunicationDraft, response_model_by_alias=False)
def update_agent_communication_status(
    draft_id: int,
    payload: schemas.AgentCommunicationDraftStatusUpdate,
    db: Session = Depends(get_db),
):
    draft = _communication_draft_query(db).filter(models.AgentCommunicationDraft.id == draft_id).first()
    if draft is None:
        raise HTTPException(status_code=404, detail="Bozza comunicazione non trovata")

    old_status = draft.status
    draft.status = payload.status
    draft.reviewed_by_user_id = payload.reviewed_by_user_id
    if payload.status == "sent":
        draft.sent_at = datetime.utcnow()

    db.add(models.AuditLog(
        entity="agent_communication_draft",
        action="status_updated",
        old_value=json.dumps({"draft_id": draft.id, "status": old_status}),
        new_value=json.dumps({"draft_id": draft.id, "status": draft.status}),
        user_id=payload.reviewed_by_user_id,
    ))
    db.commit()
    return _communication_draft_query(db).filter(models.AgentCommunicationDraft.id == draft.id).first()


def _review_suggestion(
    db: Session,
    *,
    suggestion_id: int,
    action: str,
    payload: schemas.AgentReviewActionCreate,
):
    suggestion = _agent_suggestion_query(db).filter(models.AgentSuggestion.id == suggestion_id).first()
    if suggestion is None:
        raise HTTPException(status_code=404, detail="Suggerimento non trovato")
    if suggestion.status != "pending":
        raise HTTPException(status_code=409, detail="Suggerimento gia revisionato")

    suggestion.status = "accepted" if action == "accept" else "rejected"
    suggestion.reviewed_at = datetime.utcnow()
    suggestion.reviewed_by_user_id = payload.reviewed_by_user_id
    review_action = models.AgentReviewAction(
        suggestion_id=suggestion.id,
        action=suggestion.status,
        notes=payload.notes,
        reviewed_by_user_id=payload.reviewed_by_user_id,
    )
    db.add(review_action)
    db.add(models.AuditLog(
        entity="agent_suggestion",
        action=suggestion.status,
        old_value=json.dumps({"suggestion_id": suggestion.id, "status": "pending"}),
        new_value=json.dumps({"suggestion_id": suggestion.id, "status": suggestion.status, "notes": payload.notes}),
        user_id=payload.reviewed_by_user_id,
    ))
    db.commit()
    return _agent_suggestion_query(db).filter(models.AgentSuggestion.id == suggestion.id).first()


@router.post("/suggestions/{suggestion_id}/accept", response_model=schemas.AgentSuggestion, response_model_by_alias=False)
def accept_agent_suggestion(
    suggestion_id: int,
    payload: schemas.AgentReviewActionCreate,
    db: Session = Depends(get_db),
):
    return _review_suggestion(db, suggestion_id=suggestion_id, action="accept", payload=payload)


@router.post("/suggestions/{suggestion_id}/reject", response_model=schemas.AgentSuggestion, response_model_by_alias=False)
def reject_agent_suggestion(
    suggestion_id: int,
    payload: schemas.AgentReviewActionCreate,
    db: Session = Depends(get_db),
):
    return _review_suggestion(db, suggestion_id=suggestion_id, action="reject", payload=payload)


@router.post("/suggestions/{suggestion_id}/workflow", response_model=schemas.AgentSuggestion, response_model_by_alias=False)
def workflow_agent_suggestion(
    suggestion_id: int,
    payload: schemas.AgentWorkflowActionRequest,
    db: Session = Depends(get_db),
):
    try:
        suggestion = apply_workflow_action(
            db,
            suggestion_id=suggestion_id,
            action=payload.action,
            reviewed_by_user_id=payload.reviewed_by_user_id,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _agent_suggestion_query(db).filter(models.AgentSuggestion.id == suggestion.id).first()
