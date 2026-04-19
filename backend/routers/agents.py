import logging
import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload, selectinload

import crud
import models
import schemas
from agent_workflows import apply_workflow_action, run_agent_workflow
from ai_agents import list_agent_definitions
from ai_agents.llm import probe_agent_llm_health
from ai_agents.registry import agent_registry
from database import get_db

router = APIRouter(prefix="/api/v1/agents", tags=["Agents"])
logger = logging.getLogger(__name__)


class SuggestionReviewPayload(BaseModel):
    action: str
    reviewed_by_user_id: Optional[int] = None
    notes: Optional[str] = None


class BulkReviewPayload(BaseModel):
    suggestion_ids: List[int]
    action: str
    reviewed_by_user_id: Optional[int] = None
    notes: Optional[str] = None


class CommunicationStatusPayload(BaseModel):
    status: str
    reviewed_by_user_id: Optional[int] = None


def _run_query(db: Session):
    return db.query(models.AgentRun)


def _suggestion_query(db: Session, include_review_actions: bool = True):
    query = db.query(models.AgentSuggestion).options(
        joinedload(models.AgentSuggestion.run),
    )
    if include_review_actions:
        query = query.options(selectinload(models.AgentSuggestion.review_actions))
    return query


def _normalize_review_action(action: str) -> str:
    normalized = (action or "").strip().lower()
    allowed = {"approve", "approved", "reject", "rejected", "implemented", "deferred"}
    if normalized not in allowed:
        raise HTTPException(status_code=400, detail="Azione review non supportata")
    return normalized


def _map_action_to_status(action: str) -> str:
    mapping = {
        "approve": "approved",
        "approved": "approved",
        "reject": "rejected",
        "rejected": "rejected",
        "implemented": "implemented",
        "deferred": "expired",
    }
    return mapping[action]


def _normalize_accept_workflow_action(action: Optional[str]) -> str:
    normalized = (action or "").strip().lower()
    if normalized in {"", "accept", "accepted", "approve", "approved"}:
        return "approve_email"
    return normalized


@router.get("/")
def list_registered_agents():
    registered = {
        item.get("agent_type"): item
        for item in agent_registry.list_agents()
        if item.get("agent_type")
    }

    catalog = []
    for definition in list_agent_definitions():
        registered_item = registered.get(definition["name"], {})
        catalog.append({
            "name": definition["name"],
            "label": definition["name"].replace("_", " ").title(),
            "description": definition.get("description") or registered_item.get("description") or "",
            "supported_entity_types": definition.get("supported_entity_types") or [],
            "agent_type": definition["name"],
            "version": registered_item.get("version", "1.0"),
        })

    for agent_type, registered_item in registered.items():
        if any(item["name"] == agent_type for item in catalog):
            continue
        catalog.append({
            "name": agent_type,
            "label": agent_type.replace("_", " ").title(),
            "description": registered_item.get("description") or "",
            "supported_entity_types": [],
            "agent_type": agent_type,
            "version": registered_item.get("version", "1.0"),
        })

    return catalog


@router.get("/{agent_type}/info")
def get_agent_info(agent_type: str):
    for definition in list_agent_definitions():
        if definition["name"] == agent_type:
            return {
                "name": definition["name"],
                "label": definition["name"].replace("_", " ").title(),
                "description": definition.get("description") or "",
                "supported_entity_types": definition.get("supported_entity_types") or [],
                "agent_type": definition["name"],
            }
    try:
        return agent_registry.get(agent_type).get_info()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/llm/health", response_model=schemas.AgentLlmHealth)
def get_llm_health():
    return probe_agent_llm_health()


@router.post("/run", response_model=schemas.AgentRun)
def run_agent_via_workflow(payload: schemas.AgentRunRequest, db: Session = Depends(get_db)):
    normalized_entity_type = payload.entity_type
    if normalized_entity_type:
        normalized_entity_type = normalized_entity_type.strip().lower()
    if normalized_entity_type in {"", "global", "all"}:
        normalized_entity_type = None

    try:
        run = run_agent_workflow(
            db,
            agent_type=payload.agent_name,
            entity_type=normalized_entity_type,
            entity_id=payload.entity_id,
            requested_by_user_id=payload.requested_by_user_id,
            input_payload=payload.input_payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return crud.get_agent_run(db, run.id)


@router.post("/{agent_type}/run", response_model=schemas.AgentRun)
def run_agent_manually(agent_type: str, db: Session = Depends(get_db)):
    try:
        run = agent_registry.run_agent(db, agent_type=agent_type, triggered_by="manual")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return crud.get_agent_run(db, run.id)


@router.get("/runs/", response_model=List[schemas.AgentRun])
def list_agent_runs(
    agent_type: Optional[str] = None,
    status: Optional[str] = None,
    start_date_from: Optional[datetime] = Query(None),
    start_date_to: Optional[datetime] = Query(None),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    try:
        query = _run_query(db)
        if agent_type:
            query = query.filter(models.AgentRun.agent_type == agent_type)
        if status:
            query = query.filter(models.AgentRun.status == status)
        if start_date_from:
            query = query.filter(models.AgentRun.started_at >= start_date_from)
        if start_date_to:
            query = query.filter(models.AgentRun.started_at <= start_date_to)
        return (
            query.order_by(models.AgentRun.started_at.desc(), models.AgentRun.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
    except Exception as exc:
        logger.exception("Failed to list agent runs: %s", exc)
        return []


@router.get("/runs/{run_id}", response_model=schemas.AgentRunWithSuggestions)
def get_run_detail(run_id: int, db: Session = Depends(get_db)):
    run = crud.get_agent_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run agente non trovato")
    return run


@router.get("/suggestions/", response_model=List[schemas.AgentSuggestion])
def list_suggestions(
    agent_type: Optional[str] = None,
    agent_name: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    entity_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    try:
        query = _suggestion_query(db, include_review_actions=False)
        effective_agent_type = agent_type or agent_name
        if effective_agent_type:
            query = query.join(models.AgentRun, models.AgentSuggestion.run_id == models.AgentRun.id)
            query = query.filter(models.AgentRun.agent_type == effective_agent_type)
        if status:
            query = query.filter(models.AgentSuggestion.status == status)
        if entity_type:
            query = query.filter(models.AgentSuggestion.entity_type == entity_type)
        return query.order_by(models.AgentSuggestion.id.desc()).offset(skip).limit(limit).all()
    except Exception as exc:
        logger.exception("Failed to list agent suggestions: %s", exc)
        return []


@router.get("/suggestions/pending", response_model=List[schemas.AgentSuggestion])
def list_pending_suggestions(db: Session = Depends(get_db)):
    return crud.get_pending_suggestions(db)


@router.get("/suggestions/{suggestion_id}", response_model=schemas.AgentSuggestionWithDetails)
def get_suggestion_detail(suggestion_id: int, db: Session = Depends(get_db)):
    suggestion = crud.get_suggestion(db, suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggerimento non trovato")
    return suggestion


@router.post("/suggestions/{suggestion_id}/review", response_model=schemas.AgentSuggestionWithDetails)
def review_suggestion(
    suggestion_id: int,
    payload: SuggestionReviewPayload,
    db: Session = Depends(get_db),
):
    suggestion = crud.get_suggestion(db, suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggerimento non trovato")

    normalized_action = _normalize_review_action(payload.action)
    next_status = _map_action_to_status(normalized_action)
    crud.create_review_action(
        db=db,
        suggestion_id=suggestion_id,
        action=normalized_action,
        reviewed_by_user_id=payload.reviewed_by_user_id,
        notes=payload.notes,
        auto_fix_applied=False,
        result_success=None,
        result_message=None,
    )
    crud.update_suggestion_status(db, suggestion_id, next_status)
    return crud.get_suggestion(db, suggestion_id)


@router.post("/suggestions/{suggestion_id}/accept", response_model=schemas.AgentSuggestionWithDetails)
def accept_suggestion(
    suggestion_id: int,
    payload: schemas.AgentWorkflowActionRequest,
    db: Session = Depends(get_db),
):
    try:
        return apply_workflow_action(
            db,
            suggestion_id=suggestion_id,
            action=_normalize_accept_workflow_action(payload.action),
            reviewed_by_user_id=payload.reviewed_by_user_id,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/suggestions/{suggestion_id}/reject", response_model=schemas.AgentSuggestionWithDetails)
def reject_suggestion(
    suggestion_id: int,
    payload: schemas.AgentWorkflowActionRequest,
    db: Session = Depends(get_db),
):
    review_payload = SuggestionReviewPayload(
        action="rejected",
        reviewed_by_user_id=payload.reviewed_by_user_id,
        notes=payload.notes,
    )
    return review_suggestion(suggestion_id, review_payload, db)


@router.post("/suggestions/{suggestion_id}/workflow", response_model=schemas.AgentSuggestionWithDetails)
def workflow_suggestion(
    suggestion_id: int,
    payload: schemas.AgentWorkflowActionRequest,
    db: Session = Depends(get_db),
):
    try:
        return apply_workflow_action(
            db,
            suggestion_id=suggestion_id,
            action=payload.action,
            reviewed_by_user_id=payload.reviewed_by_user_id,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/suggestions/{suggestion_id}/apply-fix", response_model=schemas.AgentSuggestionWithDetails)
def apply_suggestion_fix(suggestion_id: int, db: Session = Depends(get_db)):
    suggestion = crud.get_suggestion(db, suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggerimento non trovato")
    if not suggestion.auto_fix_available:
        raise HTTPException(status_code=400, detail="Auto-fix non disponibile per questo suggerimento")

    result_message = "Auto-fix applicato"
    if suggestion.auto_fix_payload:
        try:
            payload_preview = json.loads(suggestion.auto_fix_payload)
            result_message = f"Auto-fix applicato con payload: {payload_preview}"
        except json.JSONDecodeError:
            result_message = "Auto-fix applicato con payload non JSON"

    crud.create_review_action(
        db=db,
        suggestion_id=suggestion_id,
        action="implemented",
        reviewed_by_user_id=None,
        notes="Applicazione auto-fix",
        auto_fix_applied=True,
        result_success=True,
        result_message=result_message,
    )
    crud.update_suggestion_status(db, suggestion_id, "implemented")
    return crud.get_suggestion(db, suggestion_id)


@router.get("/communications", response_model=List[schemas.AgentCommunicationDraft])
def list_communications(
    agent_name: Optional[str] = None,
    recipient_type: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 200,
    db: Session = Depends(get_db),
):
    query = db.query(models.AgentCommunicationDraft)
    if agent_name:
        query = query.filter(models.AgentCommunicationDraft.agent_name == agent_name)
    if recipient_type:
        query = query.filter(models.AgentCommunicationDraft.recipient_type == recipient_type)
    if status:
        query = query.filter(models.AgentCommunicationDraft.status == status)
    return query.order_by(models.AgentCommunicationDraft.id.desc()).offset(skip).limit(limit).all()


@router.post("/communications", response_model=schemas.AgentCommunicationDraft)
def create_communication_draft(
    payload: schemas.AgentCommunicationDraftCreate,
    db: Session = Depends(get_db),
):
    draft = models.AgentCommunicationDraft(
        run_id=payload.run_id,
        suggestion_id=payload.suggestion_id,
        agent_name=payload.agent_name.strip(),
        channel=(payload.channel or "email").strip().lower(),
        recipient_type=payload.recipient_type.strip(),
        recipient_id=payload.recipient_id,
        recipient_email=payload.recipient_email.strip(),
        recipient_name=payload.recipient_name.strip() if payload.recipient_name else None,
        subject=payload.subject.strip(),
        body=payload.body.strip(),
        status=(payload.status or "draft").strip().lower(),
        meta_payload=payload.meta_payload,
        created_by_user_id=payload.created_by_user_id,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


@router.post("/communications/{draft_id}/status", response_model=schemas.AgentCommunicationDraft)
def update_communication_status(
    draft_id: int,
    payload: CommunicationStatusPayload,
    db: Session = Depends(get_db),
):
    draft = db.query(models.AgentCommunicationDraft).filter(models.AgentCommunicationDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Bozza comunicazione non trovata")

    draft.status = payload.status
    draft.reviewed_by_user_id = payload.reviewed_by_user_id
    if payload.status == "sent" and draft.sent_at is None:
        draft.sent_at = datetime.utcnow()

    db.commit()
    db.refresh(draft)
    return draft


@router.post("/suggestions/bulk-review", response_model=List[schemas.AgentSuggestion])
def bulk_review_suggestions(payload: BulkReviewPayload, db: Session = Depends(get_db)):
    normalized_action = _normalize_review_action(payload.action)
    next_status = _map_action_to_status(normalized_action)

    suggestions = []
    for suggestion_id in payload.suggestion_ids:
        suggestion = crud.get_suggestion(db, suggestion_id)
        if not suggestion:
            continue
        crud.create_review_action(
            db=db,
            suggestion_id=suggestion_id,
            action=normalized_action,
            reviewed_by_user_id=payload.reviewed_by_user_id,
            notes=payload.notes,
            auto_fix_applied=False,
            result_success=None,
            result_message=None,
        )
        suggestions.append(suggestion_id)

    return crud.bulk_update_suggestions_status(db, suggestions, next_status)
