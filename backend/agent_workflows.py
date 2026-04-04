from __future__ import annotations

import json
import logging
import os
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage
from typing import Any, Optional

from sqlalchemy.orm import Session

import models
from ai_agents import get_agent_definition, run_registered_agent

logger = logging.getLogger(__name__)

OPEN_SUGGESTION_STATUSES = {"pending", "waiting", "approved", "sent", "followup_due"}
FOLLOWUP_ELIGIBLE_STATUSES = {"sent"}


def _json_dumps(value: Any) -> Optional[str]:
    if value is None:
        return None
    return json.dumps(value, default=str)


def create_audit_log(
    db: Session,
    *,
    entity: str,
    action: str,
    old_value: Optional[dict],
    new_value: Optional[dict],
    user_id: Optional[int] = None,
) -> None:
    db.add(models.AuditLog(
        entity=entity,
        action=action,
        old_value=_json_dumps(old_value),
        new_value=_json_dumps(new_value),
        user_id=user_id,
    ))


def _parse_json_payload(value: Optional[str]) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _is_email_enabled() -> bool:
    return os.getenv("ENABLE_EMAIL", "false").strip().lower() in {"1", "true", "yes", "on"}


def _send_email(*, recipient_email: str, subject: str, body: str) -> tuple[bool, str]:
    if not _is_email_enabled():
        return False, "Invio email non abilitato"

    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = int(os.getenv("SMTP_PORT", "0") or "0")
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    email_from = os.getenv("EMAIL_FROM", "no-reply@gestionale.local")

    if not smtp_server or not smtp_port:
        return False, "Configurazione SMTP incompleta"

    message = EmailMessage()
    message["From"] = email_from
    message["To"] = recipient_email
    message["Subject"] = subject
    message.set_content(body)

    try:
        with smtplib.SMTP(smtp_server, smtp_port, timeout=15) as server:
            server.ehlo()
            try:
                server.starttls()
                server.ehlo()
            except Exception:
                logger.info("SMTP STARTTLS non disponibile, proseguo senza TLS")
            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)
            server.send_message(message)
        return True, "Email inviata"
    except Exception as exc:
        logger.warning("Invio email fallito verso %s: %s", recipient_email, exc)
        return False, str(exc)


def _review_log(
    db: Session,
    *,
    suggestion_id: int,
    action: str,
    notes: Optional[str],
    reviewed_by_user_id: Optional[int],
) -> None:
    db.add(models.AgentReviewAction(
        suggestion_id=suggestion_id,
        action=action,
        notes=notes,
        reviewed_by_user_id=reviewed_by_user_id,
    ))


def _draft_copy_for_suggestion(
    suggestion: models.AgentSuggestion,
    collaborator: models.Collaborator,
) -> tuple[str, str]:
    payload = _parse_json_payload(suggestion.payload)
    missing_fields = payload.get("missing_fields") or []
    full_name = collaborator.full_name

    if suggestion.suggestion_type == "missing_identity_document":
        subject = "Documentazione identità da completare"
        body = (
            f"Ciao {full_name},\n\n"
            "per completare il tuo profilo nel gestionale ci serve il documento di identità "
            "completo della relativa data di scadenza.\n\n"
            "Puoi rispondere a questa email inviando il documento aggiornato oppure comunicando "
            "la data di scadenza corretta.\n\n"
            "Grazie."
        )
        return subject, body

    if suggestion.suggestion_type == "missing_curriculum":
        subject = "Curriculum da caricare sul profilo"
        body = (
            f"Ciao {full_name},\n\n"
            "nel tuo profilo collaboratore manca ancora il curriculum aggiornato.\n\n"
            "Ti chiediamo di inviarlo in risposta a questa email così possiamo completare "
            "la tua anagrafica operativa.\n\n"
            "Grazie."
        )
        return subject, body

    missing_fields_text = ", ".join(missing_fields) if missing_fields else "alcuni dati di profilo"
    subject = "Completamento dati profilo collaboratore"
    body = (
        f"Ciao {full_name},\n\n"
        "durante il controllo qualità del tuo profilo risultano ancora mancanti o incompleti "
        f"i seguenti dati: {missing_fields_text}.\n\n"
        "Ti chiediamo di inviarci queste informazioni così possiamo completare la tua anagrafica.\n\n"
        "Grazie."
    )
    return subject, body


def _whatsapp_copy_for_suggestion(
    suggestion: models.AgentSuggestion,
    collaborator: models.Collaborator,
) -> tuple[str, str]:
    payload = _parse_json_payload(suggestion.payload)
    missing_fields = payload.get("missing_fields") or []
    first_name = collaborator.first_name or collaborator.full_name

    if suggestion.suggestion_type == "missing_identity_document":
        return (
            "Richiesta documento identita",
            f"Ciao {first_name}, ci serve il documento di identita aggiornato con la data di scadenza per completare il tuo profilo. Puoi inviarcelo appena possibile?",
        )

    if suggestion.suggestion_type == "missing_curriculum":
        return (
            "Richiesta curriculum",
            f"Ciao {first_name}, nel tuo profilo manca ancora il curriculum aggiornato. Puoi inviarcelo appena possibile?",
        )

    fields_text = ", ".join(missing_fields) if missing_fields else "alcuni dati di profilo"
    return (
        "Completamento profilo",
        f"Ciao {first_name}, nel tuo profilo mancano ancora questi dati: {fields_text}. Puoi inviarceli appena possibile?",
    )


def _ensure_collaborator_draft(
    db: Session,
    *,
    run_id: Optional[int],
    suggestion: models.AgentSuggestion,
    channel: str,
    requested_by_user_id: Optional[int] = None,
) -> Optional[models.AgentCommunicationDraft]:
    if suggestion.entity_type != "collaborator" or suggestion.entity_id is None:
        return None

    collaborator = db.query(models.Collaborator).filter(models.Collaborator.id == suggestion.entity_id).first()
    if collaborator is None or not collaborator.email:
        return None

    draft = db.query(models.AgentCommunicationDraft).filter(
        models.AgentCommunicationDraft.suggestion_id == suggestion.id,
        models.AgentCommunicationDraft.channel == channel,
    ).first()

    if channel == "whatsapp":
        if not collaborator.phone:
            return None
        subject, body = _whatsapp_copy_for_suggestion(suggestion, collaborator)
        recipient_address = collaborator.phone
    else:
        subject, body = _draft_copy_for_suggestion(suggestion, collaborator)
        recipient_address = collaborator.email

    meta_payload = {
        "delivery_mode": "operator_approved",
        "suggestion_type": suggestion.suggestion_type,
        "collaborator_id": collaborator.id,
        "collaborator_name": collaborator.full_name,
        "channel": channel,
    }

    if draft is None:
        draft = models.AgentCommunicationDraft(
            run_id=run_id,
            suggestion_id=suggestion.id,
            agent_name=suggestion.agent_name,
            channel=channel,
            recipient_type="collaborator",
            recipient_id=collaborator.id,
            recipient_email=recipient_address,
            recipient_name=collaborator.full_name,
            subject=subject,
            body=body,
            status="draft",
            meta_payload=_json_dumps(meta_payload),
            created_by_user_id=requested_by_user_id,
        )
        db.add(draft)
        db.flush()
        return draft

    if draft.status in {"draft", "approved", "waiting", "followup_due"}:
        draft.subject = subject
        draft.body = body
        draft.recipient_email = recipient_address
        draft.meta_payload = _json_dumps(meta_payload)
    return draft


def _ensure_all_collaborator_drafts(
    db: Session,
    *,
    run_id: Optional[int],
    suggestion: models.AgentSuggestion,
    requested_by_user_id: Optional[int] = None,
) -> list[models.AgentCommunicationDraft]:
    drafts: list[models.AgentCommunicationDraft] = []
    email_draft = _ensure_collaborator_draft(
        db,
        run_id=run_id,
        suggestion=suggestion,
        channel="email",
        requested_by_user_id=requested_by_user_id,
    )
    if email_draft:
        drafts.append(email_draft)

    whatsapp_draft = _ensure_collaborator_draft(
        db,
        run_id=run_id,
        suggestion=suggestion,
        channel="whatsapp",
        requested_by_user_id=requested_by_user_id,
    )
    if whatsapp_draft:
        drafts.append(whatsapp_draft)

    return drafts


def _mark_suggestion_resolved(
    db: Session,
    suggestion: models.AgentSuggestion,
    *,
    notes: str,
) -> None:
    if suggestion.status == "completed":
        return
    old_status = suggestion.status
    suggestion.status = "completed"
    suggestion.reviewed_at = datetime.utcnow()
    _review_log(db, suggestion_id=suggestion.id, action="auto_resolved", notes=notes, reviewed_by_user_id=None)
    create_audit_log(
        db,
        entity="agent_suggestion",
        action="auto_resolved",
        old_value={"suggestion_id": suggestion.id, "status": old_status},
        new_value={"suggestion_id": suggestion.id, "status": suggestion.status},
        user_id=None,
    )
    drafts = db.query(models.AgentCommunicationDraft).filter(
        models.AgentCommunicationDraft.suggestion_id == suggestion.id
    ).all()
    for draft in drafts:
        if draft.status not in {"completed", "cancelled"}:
            draft.status = "completed"


def run_agent_workflow(
    db: Session,
    *,
    agent_name: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    requested_by_user_id: Optional[int] = None,
    input_payload: Optional[dict[str, Any]] = None,
    auto_mode: bool = False,
) -> models.AgentRun:
    definition = get_agent_definition(agent_name)
    if not definition:
        raise ValueError("Agente non supportato")

    supported_entity_types = definition.get("supported_entity_types") or []
    if entity_type and entity_type not in supported_entity_types:
        raise ValueError(
            f"Tipo entita non supportato per {definition['name']}: {entity_type}. "
            f"Supportati: {', '.join(supported_entity_types)}"
        )

    payload = dict(input_payload or {})
    if auto_mode:
        payload["trigger_mode"] = "automatic"

    run = models.AgentRun(
        agent_name=definition["name"],
        status="running",
        entity_type=entity_type,
        entity_id=entity_id,
        requested_by_user_id=requested_by_user_id,
        input_payload=_json_dumps(payload),
    )
    db.add(run)
    db.flush()

    result = run_registered_agent(
        db,
        agent_name=agent_name,
        entity_type=entity_type,
        entity_id=entity_id,
        input_payload=payload,
    )

    created_suggestions: list[models.AgentSuggestion] = []
    for item in result.get("suggestions", []):
        suggestion = models.AgentSuggestion(
            run_id=run.id,
            agent_name=definition["name"],
            entity_type=item["entity_type"],
            entity_id=item.get("entity_id"),
            suggestion_type=item["suggestion_type"],
            severity=item["severity"],
            status="pending",
            title=item["title"],
            description=item["description"],
            payload=_json_dumps(item.get("payload")),
            confidence=item.get("confidence"),
        )
        db.add(suggestion)
        db.flush()
        created_suggestions.append(suggestion)

        payload_dict = item.get("payload") or {}
        if (
            definition["name"] == "mail_recovery"
            and payload_dict.get("recipient_email")
            and payload_dict.get("subject")
            and payload_dict.get("body")
        ):
            db.add(models.AgentCommunicationDraft(
                run_id=run.id,
                suggestion_id=suggestion.id,
                agent_name=definition["name"],
                channel="email",
                recipient_type=payload_dict.get("recipient_type") or item["entity_type"],
                recipient_id=payload_dict.get("recipient_id"),
                recipient_email=payload_dict["recipient_email"],
                recipient_name=payload_dict.get("recipient_name"),
                subject=payload_dict["subject"],
                body=payload_dict["body"],
                status="draft",
                meta_payload=_json_dumps(payload_dict),
                created_by_user_id=requested_by_user_id,
            ))

    summary = result.get("summary", {})
    run.status = "completed"
    run.completed_at = datetime.utcnow()
    run.suggestions_count = len(created_suggestions)
    run.result_summary = _json_dumps(summary)

    create_audit_log(
        db,
        entity="agent_run",
        action="created",
        old_value=None,
        new_value={
            "run_id": run.id,
            "agent_name": run.agent_name,
            "entity_type": run.entity_type,
            "entity_id": run.entity_id,
            "suggestions_count": run.suggestions_count,
            "auto_mode": auto_mode,
        },
        user_id=requested_by_user_id,
    )

    db.commit()
    db.refresh(run)
    return run


def sync_collaborator_data_quality(
    db: Session,
    *,
    collaborator_id: int,
    requested_by_user_id: Optional[int] = None,
    trigger_source: str = "collaborator_update",
) -> Optional[models.AgentRun]:
    collaborator = db.query(models.Collaborator).filter(models.Collaborator.id == collaborator_id).first()
    if collaborator is None or not collaborator.is_active:
        return None

    run = run_agent_workflow(
        db,
        agent_name="data_quality",
        entity_type="collaborator",
        entity_id=collaborator_id,
        requested_by_user_id=requested_by_user_id,
        input_payload={"limit": 1, "trigger_source": trigger_source},
        auto_mode=True,
    )

    open_suggestions = db.query(models.AgentSuggestion).filter(
        models.AgentSuggestion.agent_name == "data_quality",
        models.AgentSuggestion.entity_type == "collaborator",
        models.AgentSuggestion.entity_id == collaborator_id,
        models.AgentSuggestion.status.in_(tuple(OPEN_SUGGESTION_STATUSES)),
    ).all()

    latest_suggestions = [item for item in open_suggestions if item.run_id == run.id]
    latest_by_type = {item.suggestion_type: item for item in latest_suggestions}

    existing_open = [
        item for item in open_suggestions
        if item.run_id != run.id
    ]

    for suggestion in existing_open:
        refreshed = latest_by_type.get(suggestion.suggestion_type)
        if refreshed is None:
            _mark_suggestion_resolved(
                db,
                suggestion,
                notes=f"Risolto automaticamente dopo nuovo controllo {trigger_source}",
            )
            continue

        old_status = suggestion.status
        suggestion.run_id = run.id
        suggestion.title = refreshed.title
        suggestion.description = refreshed.description
        suggestion.payload = refreshed.payload
        suggestion.severity = refreshed.severity
        suggestion.confidence = refreshed.confidence

        if suggestion.status == "completed":
            suggestion.status = "pending"
        refreshed.status = "completed"

        if old_status != suggestion.status:
            _review_log(
                db,
                suggestion_id=suggestion.id,
                action="reopened",
                notes="Issue ancora aperta dopo nuovo controllo automatico",
                reviewed_by_user_id=None,
            )
        create_audit_log(
            db,
            entity="agent_suggestion",
            action="refreshed",
            old_value={"suggestion_id": suggestion.id, "status": old_status},
            new_value={"suggestion_id": suggestion.id, "status": suggestion.status, "run_id": run.id},
            user_id=requested_by_user_id,
        )

    active_suggestions = db.query(models.AgentSuggestion).filter(
        models.AgentSuggestion.agent_name == "data_quality",
        models.AgentSuggestion.entity_type == "collaborator",
        models.AgentSuggestion.entity_id == collaborator_id,
        models.AgentSuggestion.status.in_(tuple(OPEN_SUGGESTION_STATUSES)),
    ).all()

    for suggestion in active_suggestions:
        _ensure_all_collaborator_drafts(db, run_id=run.id, suggestion=suggestion, requested_by_user_id=requested_by_user_id)

    db.commit()
    return run


def promote_due_followups(db: Session) -> int:
    threshold = datetime.utcnow() - timedelta(days=7)
    due_count = 0
    drafts = db.query(models.AgentCommunicationDraft).filter(
        models.AgentCommunicationDraft.status == "sent",
        models.AgentCommunicationDraft.sent_at.isnot(None),
        models.AgentCommunicationDraft.sent_at <= threshold,
    ).all()

    for draft in drafts:
        suggestion = None
        if draft.suggestion_id:
            suggestion = db.query(models.AgentSuggestion).filter(
                models.AgentSuggestion.id == draft.suggestion_id
            ).first()

        if draft.status != "sent":
            continue
        draft.status = "followup_due"
        due_count += 1
        if suggestion and suggestion.status in FOLLOWUP_ELIGIBLE_STATUSES:
            old_status = suggestion.status
            suggestion.status = "followup_due"
            _review_log(
                db,
                suggestion_id=suggestion.id,
                action="followup_due",
                notes="Nessuna risposta registrata entro 7 giorni dall'invio",
                reviewed_by_user_id=None,
            )
            create_audit_log(
                db,
                entity="agent_suggestion",
                action="followup_due",
                old_value={"suggestion_id": suggestion.id, "status": old_status},
                new_value={"suggestion_id": suggestion.id, "status": suggestion.status},
                user_id=None,
            )

    if due_count:
        db.commit()
    return due_count


def apply_workflow_action(
    db: Session,
    *,
    suggestion_id: int,
    action: str,
    reviewed_by_user_id: Optional[int],
    notes: Optional[str] = None,
) -> models.AgentSuggestion:
    promote_due_followups(db)

    suggestion = db.query(models.AgentSuggestion).filter(models.AgentSuggestion.id == suggestion_id).first()
    if suggestion is None:
        raise ValueError("Suggerimento non trovato")

    selected_channel = "email"
    normalized_action = action
    if action.endswith("_email"):
        normalized_action = action.replace("_email", "")
        selected_channel = "email"
    elif action.endswith("_whatsapp"):
        normalized_action = action.replace("_whatsapp", "")
        selected_channel = "whatsapp"

    draft = db.query(models.AgentCommunicationDraft).filter(
        models.AgentCommunicationDraft.suggestion_id == suggestion.id,
        models.AgentCommunicationDraft.channel == selected_channel,
    ).first()
    if draft is None:
        _ensure_all_collaborator_drafts(db, run_id=suggestion.run_id, suggestion=suggestion, requested_by_user_id=reviewed_by_user_id)
        draft = db.query(models.AgentCommunicationDraft).filter(
            models.AgentCommunicationDraft.suggestion_id == suggestion.id,
            models.AgentCommunicationDraft.channel == selected_channel,
        ).first()

    old_status = suggestion.status

    if normalized_action in {"approve", "remind"}:
        if draft is None:
            raise ValueError(f"Nessuna comunicazione {selected_channel} disponibile per questo suggerimento")
        sent_ok = False
        detail = "Bozza pronta per invio manuale"
        if draft.channel == "email":
            sent_ok, detail = _send_email(
                recipient_email=draft.recipient_email,
                subject=draft.subject,
                body=draft.body,
            )
        meta = _parse_json_payload(draft.meta_payload)
        meta["last_delivery_attempt_at"] = datetime.utcnow().isoformat()
        meta["last_delivery_detail"] = detail
        meta["delivery_attempts"] = int(meta.get("delivery_attempts") or 0) + 1
        draft.meta_payload = _json_dumps(meta)
        draft.reviewed_by_user_id = reviewed_by_user_id
        if sent_ok:
            draft.status = "sent"
            draft.sent_at = datetime.utcnow()
            suggestion.status = "sent"
        else:
            draft.status = "approved"
            suggestion.status = "approved"
        suggestion.reviewed_at = datetime.utcnow()
        suggestion.reviewed_by_user_id = reviewed_by_user_id
        review_action = f"{normalized_action}_{draft.channel}"
        if normalized_action == "remind" and sent_ok:
            review_action = f"reminder_sent_{draft.channel}"
        _review_log(db, suggestion_id=suggestion.id, action=review_action, notes=notes or detail, reviewed_by_user_id=reviewed_by_user_id)
    elif normalized_action == "wait":
        suggestion.status = "waiting"
        suggestion.reviewed_at = datetime.utcnow()
        suggestion.reviewed_by_user_id = reviewed_by_user_id
        drafts = db.query(models.AgentCommunicationDraft).filter(
            models.AgentCommunicationDraft.suggestion_id == suggestion.id
        ).all()
        for item in drafts:
            if item.status in {"draft", "approved", "followup_due"}:
                item.status = "waiting"
                item.reviewed_by_user_id = reviewed_by_user_id
        _review_log(db, suggestion_id=suggestion.id, action="waiting", notes=notes, reviewed_by_user_id=reviewed_by_user_id)
    elif normalized_action == "close":
        suggestion.status = "completed"
        suggestion.reviewed_at = datetime.utcnow()
        suggestion.reviewed_by_user_id = reviewed_by_user_id
        drafts = db.query(models.AgentCommunicationDraft).filter(
            models.AgentCommunicationDraft.suggestion_id == suggestion.id
        ).all()
        for item in drafts:
            if item.status not in {"sent", "completed"}:
                item.status = "completed"
                item.reviewed_by_user_id = reviewed_by_user_id
        _review_log(db, suggestion_id=suggestion.id, action="completed", notes=notes, reviewed_by_user_id=reviewed_by_user_id)
    else:
        raise ValueError("Azione workflow non supportata")

    create_audit_log(
        db,
        entity="agent_suggestion",
        action=f"workflow_{action}",
        old_value={"suggestion_id": suggestion.id, "status": old_status},
        new_value={"suggestion_id": suggestion.id, "status": suggestion.status, "notes": notes},
        user_id=reviewed_by_user_id,
    )
    db.commit()
    db.refresh(suggestion)
    return suggestion
