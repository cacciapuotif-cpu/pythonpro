import logging
import json
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload, selectinload

import crud
import models
import schemas
from agent_workflows import AgentWorkflowExecutionError, apply_workflow_action, run_agent_workflow
from ai_agents import list_agent_definitions
from ai_agents.llm import probe_agent_llm_health
from auth import User, UserRole, get_current_user, normalize_role
from database import get_db

router = APIRouter(prefix="/api/v1/agents", tags=["Agents"])
suggestion_actions_router = APIRouter(prefix="/api/v1/agent-suggestions", tags=["Agent Suggestions"])
logger = logging.getLogger(__name__)


# Matrice A5a (GATE confermato 2026-07-15):
# - execute (run manuale agenti, strumenti tecnici): solo ADMIN
# - write (review/approve/reject/send/apply-fix, comunicazioni): OPERATORE e ADMIN
def require_agents_execute(current_user: User = Depends(get_current_user)) -> User:
    if normalize_role(current_user.role) != UserRole.ADMIN.value:
        raise HTTPException(status_code=403, detail="Esecuzione agenti riservata agli amministratori")
    return current_user


def require_agents_write(current_user: User = Depends(get_current_user)) -> User:
    if normalize_role(current_user.role) not in {UserRole.ADMIN.value, UserRole.OPERATORE.value}:
        raise HTTPException(status_code=403, detail="Permesso operatore richiesto per le azioni agenti")
    return current_user


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


class SendEmailPayload(BaseModel):
    reviewed_by_user_id: Optional[int] = None
    notes: Optional[str] = None


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


def _catalog_entry(definition: dict) -> dict:
    return {
        "name": definition["name"],
        "label": definition["name"].replace("_", " ").title(),
        "description": definition.get("description") or "",
        "supported_entity_types": definition.get("supported_entity_types") or [],
        "agent_type": definition["name"],
        "version": definition.get("version", "1.0"),
        "triggers": definition.get("triggers") or [],
        "kill_switch_env": definition.get("kill_switch_env"),
        "allowed_roles": definition.get("allowed_roles") or [],
    }


@router.get("/")
def list_registered_agents(current_user: User = Depends(get_current_user)):
    # AGENT-09: catalogo dal solo registry unico dichiarativo (ai_agents).
    return [_catalog_entry(definition) for definition in list_agent_definitions()]


@router.get("/{agent_type}/info")
def get_agent_info(agent_type: str, current_user: User = Depends(get_current_user)):
    for definition in list_agent_definitions():
        if definition["name"] == agent_type:
            return _catalog_entry(definition)
    raise HTTPException(status_code=404, detail=f"Agente non registrato: {agent_type}")


@router.get("/llm/health", response_model=schemas.AgentLlmHealth)
def get_llm_health(current_user: User = Depends(get_current_user)):
    return probe_agent_llm_health()


# Schedulazioni cron ARQ (allineate a arq_worker.WorkerSettings.cron_jobs).
_AGENT_CRON_SCHEDULES = {
    "mail_recovery": "ogni 6h (00/06/12/18 al minuto 10)",
    "contract_agent": "ogni 2h (minuto 20)",
    "certification": "ogni giorno alle 09:00",
    "email_intake": "polling IMAP ogni 5 minuti",
    "data_quality": "su evento (aggiornamento collaboratore) e manuale",
}


def _last_run_snapshot(db: Session, agent_type: str) -> Optional[dict]:
    run = (
        db.query(models.AgentRun)
        .filter(models.AgentRun.agent_type == agent_type)
        .order_by(models.AgentRun.id.desc())
        .first()
    )
    if not run:
        return None
    return {
        "run_id": run.id,
        "status": run.status,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "error_message": run.error_message,
        "suggestions_count": run.suggestions_count,
    }


def _arq_queue_health() -> dict:
    import os

    try:
        import redis

        client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=int(os.getenv("REDIS_DB", "0")),
            password=os.getenv("REDIS_PASSWORD") or None,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        client.ping()
        queue_key = "arq:queue"
        try:
            depth = int(client.zcard(queue_key))
        except Exception:
            try:
                depth = int(client.llen(queue_key))
            except Exception:
                depth = None
        return {"reachable": True, "queue_depth": depth, "detail": "Redis raggiungibile"}
    except Exception as exc:
        return {"reachable": False, "queue_depth": None, "detail": f"Redis non raggiungibile: {exc.__class__.__name__}"}


@router.get("/system-health")
def get_agents_system_health(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """A5b: stato operativo piattaforma agenti — per agente ultimo run/esito e
    schedulazione, stato inbox IMAP (store condiviso), LLM health, coda ARQ."""
    from dataclasses import asdict

    from ai_agents.control import agent_enabled, agents_enabled
    from services.email_inbox_worker import get_worker_status

    agents = []
    for definition in list_agent_definitions():
        name = definition["name"]
        agents.append({
            "name": name,
            "enabled": agent_enabled(name),
            "kill_switch_env": definition.get("kill_switch_env"),
            "triggers": definition.get("triggers") or [],
            "schedule": _AGENT_CRON_SCHEDULES.get(name),
            "last_run": _last_run_snapshot(db, name),
        })
    # email_intake non e' nel registry (non eseguibile manualmente) ma ha run propri.
    agents.append({
        "name": "email_intake",
        "enabled": agent_enabled("email_intake"),
        "kill_switch_env": "AGENT_EMAIL_INTAKE_ENABLED",
        "triggers": ["cron:polling IMAP", "event:email"],
        "schedule": _AGENT_CRON_SCHEDULES.get("email_intake"),
        "last_run": _last_run_snapshot(db, "email_intake"),
    })

    return {
        "agents_enabled": agents_enabled(),
        "agents": agents,
        "inbox": get_worker_status(),
        "llm": asdict(probe_agent_llm_health()),
        "arq": _arq_queue_health(),
    }


@router.post("/run", response_model=schemas.AgentRun)
def run_agent_via_workflow(payload: schemas.AgentRunRequest, db: Session = Depends(get_db), current_user: User = Depends(require_agents_execute)):
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
    except AgentWorkflowExecutionError as exc:
        raise HTTPException(status_code=500, detail=f"Esecuzione agente fallita: {exc}")
    return crud.get_agent_run(db, run.id)


@router.post("/{agent_type}/run", response_model=schemas.AgentRun)
def run_agent_manually(agent_type: str, db: Session = Depends(get_db), current_user: User = Depends(require_agents_execute)):
    try:
        run = run_agent_workflow(
            db,
            agent_type=agent_type,
            entity_type=None,
            entity_id=None,
            requested_by_user_id=None,
            input_payload={},
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except AgentWorkflowExecutionError as exc:
        raise HTTPException(status_code=500, detail=f"Esecuzione agente fallita: {exc}")
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
    current_user: User = Depends(get_current_user),
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
def get_run_detail(run_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
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
    current_user: User = Depends(get_current_user),
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
def list_pending_suggestions(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return crud.get_pending_suggestions(db)


@router.get("/suggestions/{suggestion_id}", response_model=schemas.AgentSuggestionWithDetails)
def get_suggestion_detail(suggestion_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    suggestion = crud.get_suggestion(db, suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggerimento non trovato")
    return suggestion


@router.post("/suggestions/{suggestion_id}/review", response_model=schemas.AgentSuggestionWithDetails)
def review_suggestion(
    suggestion_id: int,
    payload: SuggestionReviewPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_agents_write),
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
    current_user: User = Depends(require_agents_write),
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
    current_user: User = Depends(require_agents_write),
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
    current_user: User = Depends(require_agents_write),
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
def apply_suggestion_fix(suggestion_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_agents_write)):
    from services.suggestion_apply import apply_suggestion

    suggestion = crud.get_suggestion(db, suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggerimento non trovato")
    if not suggestion.auto_fix_available:
        raise HTTPException(status_code=400, detail="Auto-fix non disponibile per questo suggerimento")
    if suggestion.status not in ("pending", "approved"):
        raise HTTPException(status_code=400, detail=f"Suggerimento in stato '{suggestion.status}', non applicabile")

    reviewer_id = getattr(current_user, "id", None)
    try:
        apply_result = apply_suggestion(db, suggestion, user_id=reviewer_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    applied = apply_result["applied"]
    crud.create_review_action(
        db=db,
        suggestion_id=suggestion_id,
        action="implemented" if applied else "apply_fix_no_changes",
        reviewed_by_user_id=reviewer_id,
        notes="Applicazione auto-fix",
        auto_fix_applied=bool(applied),
        result_success=bool(applied),
        result_message=json.dumps(apply_result, ensure_ascii=True),
    )
    if applied:
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
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(require_agents_write),
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
    current_user: User = Depends(require_agents_write),
):
    draft = db.query(models.AgentCommunicationDraft).filter(models.AgentCommunicationDraft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Bozza comunicazione non trovata")

    draft.status = payload.status
    draft.reviewed_by_user_id = payload.reviewed_by_user_id
    if payload.status == "sent" and draft.sent_at is None:
        draft.sent_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(draft)
    return draft


@suggestion_actions_router.post("/{suggestion_id}/send-email", response_model=schemas.AgentSuggestionWithDetails)
def send_suggestion_email(
    suggestion_id: int,
    payload: SendEmailPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_agents_write),
):
    try:
        return apply_workflow_action(
            db,
            suggestion_id=suggestion_id,
            action="approve_email",
            reviewed_by_user_id=payload.reviewed_by_user_id,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except AgentWorkflowExecutionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/suggestions/bulk-review", response_model=List[schemas.AgentSuggestion])
def bulk_review_suggestions(payload: BulkReviewPayload, db: Session = Depends(get_db), current_user: User = Depends(require_agents_write)):
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
