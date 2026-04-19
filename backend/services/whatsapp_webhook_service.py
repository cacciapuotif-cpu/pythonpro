from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

import models

logger = logging.getLogger(__name__)


def verify_meta_webhook(*, mode: Optional[str], verify_token: Optional[str], challenge: Optional[str]) -> Optional[str]:
    expected = (os.getenv("WHATSAPP_META_WEBHOOK_VERIFY_TOKEN", "") or "").strip()
    if not expected:
        return None
    if mode == "subscribe" and verify_token == expected and challenge is not None:
        return challenge
    return None


def process_meta_webhook(db, payload: dict[str, Any]) -> dict[str, Any]:
    summary = {
        "object": payload.get("object"),
        "processed_statuses": 0,
        "matched_statuses": 0,
        "processed_messages": 0,
        "logged_inbound_messages": 0,
    }

    if payload.get("object") != "whatsapp_business_account":
        return summary

    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            value = change.get("value") or {}
            metadata = value.get("metadata") or {}

            for status_item in value.get("statuses") or []:
                summary["processed_statuses"] += 1
                if _apply_status_update(db, status_item, metadata):
                    summary["matched_statuses"] += 1

            for message_item in value.get("messages") or []:
                summary["processed_messages"] += 1
                if _log_inbound_message(db, message_item, value):
                    summary["logged_inbound_messages"] += 1

    db.commit()
    return summary


def _apply_status_update(db, status_item: dict[str, Any], metadata: dict[str, Any]) -> bool:
    provider_message_id = status_item.get("id")
    if not provider_message_id:
        return False

    draft = _find_draft_by_provider_message_id(db, provider_message_id)
    if draft is None:
        return False

    previous_status = draft.status
    status_value = (status_item.get("status") or "").strip().lower() or "unknown"
    meta = _parse_json(draft.meta_payload)

    status_timestamp = _parse_meta_timestamp(status_item.get("timestamp"))
    meta.update({
        "delivery_channel": "whatsapp",
        "delivery_provider": "meta",
        "provider_message_id": provider_message_id,
        "delivery_status": status_value,
        "recipient_wa_id": status_item.get("recipient_id"),
        "last_status_at": status_timestamp.isoformat() if status_timestamp else None,
        "meta_phone_number_id": metadata.get("phone_number_id"),
        "meta_display_phone_number": metadata.get("display_phone_number"),
    })

    conversation = status_item.get("conversation") or {}
    if isinstance(conversation, dict):
        if conversation.get("id"):
            meta["conversation_id"] = conversation.get("id")
        origin = conversation.get("origin") or {}
        if isinstance(origin, dict) and origin.get("type"):
            meta["conversation_origin_type"] = origin.get("type")

    pricing = status_item.get("pricing")
    if pricing is not None:
        meta["pricing"] = pricing

    errors = status_item.get("errors")
    if errors is not None:
        meta["errors"] = errors

    if status_value in {"sent", "delivered", "read"}:
        draft.status = status_value if status_value != "sent" else "sent"
        if draft.sent_at is None:
            draft.sent_at = status_timestamp or datetime.now(timezone.utc)
    elif status_value == "failed":
        draft.status = "failed"
        if draft.suggestion is not None:
            draft.suggestion.status = "approved"
            draft.suggestion.reviewed_at = datetime.utcnow()

    draft.meta_payload = json.dumps({key: value for key, value in meta.items() if value is not None}, default=str)
    draft.updated_at = datetime.utcnow()

    _append_audit_log(
        db,
        entity="agent_communication_draft",
        action="meta_webhook_status",
        old_value={"draft_id": draft.id, "status": previous_status},
        new_value={"draft_id": draft.id, "status": draft.status, "provider_message_id": provider_message_id},
    )
    return True


def _log_inbound_message(db, message_item: dict[str, Any], value: dict[str, Any]) -> bool:
    from_phone = (message_item.get("from") or "").strip()
    message_id = message_item.get("id")
    message_type = message_item.get("type")

    if not from_phone and not message_id:
        return False

    text_body = None
    if isinstance(message_item.get("text"), dict):
        text_body = message_item["text"].get("body")

    contacts = value.get("contacts") or []
    contact_name = None
    if contacts and isinstance(contacts[0], dict):
        profile = contacts[0].get("profile") or {}
        if isinstance(profile, dict):
            contact_name = profile.get("name")

    context = message_item.get("context") or {}
    linked_provider_message_id = context.get("id") if isinstance(context, dict) else None
    if linked_provider_message_id:
        draft = _find_draft_by_provider_message_id(db, linked_provider_message_id)
        if draft is not None:
            meta = _parse_json(draft.meta_payload)
            meta["last_inbound_message_id"] = message_id
            meta["last_inbound_from"] = from_phone
            if text_body:
                meta["last_inbound_text"] = text_body[:1000]
            draft.meta_payload = json.dumps(meta, default=str)

    _append_audit_log(
        db,
        entity="whatsapp_inbound_message",
        action="received",
        old_value=None,
        new_value={
            "message_id": message_id,
            "from": from_phone,
            "profile_name": contact_name,
            "type": message_type,
            "text": text_body,
            "linked_provider_message_id": linked_provider_message_id,
        },
    )
    return True


def _find_draft_by_provider_message_id(db, provider_message_id: str) -> Optional[models.AgentCommunicationDraft]:
    candidates = (
        db.query(models.AgentCommunicationDraft)
        .filter(models.AgentCommunicationDraft.channel == "whatsapp")
        .all()
    )
    for draft in candidates:
        meta = _parse_json(draft.meta_payload)
        if meta.get("provider_message_id") == provider_message_id:
            return draft
    return None


def _parse_json(raw_value: Optional[str]) -> dict[str, Any]:
    if not raw_value:
        return {}
    try:
        parsed = json.loads(raw_value)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _parse_meta_timestamp(raw_value: Any) -> Optional[datetime]:
    if raw_value is None:
        return None
    try:
        return datetime.fromtimestamp(int(raw_value), tz=timezone.utc)
    except Exception:
        return None


def _append_audit_log(db, *, entity: str, action: str, old_value: Optional[dict[str, Any]], new_value: Optional[dict[str, Any]]) -> None:
    db.add(models.AuditLog(
        entity=entity,
        action=action,
        old_value=json.dumps(old_value, default=str) if old_value is not None else None,
        new_value=json.dumps(new_value, default=str) if new_value is not None else None,
        user_id=None,
    ))
