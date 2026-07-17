"""Dispatcher sicuro degli auto-fix agentici revisionati."""
from __future__ import annotations

import json
from datetime import timedelta
from typing import Optional

import models
from time_utils import utc_now

RETENTION_KIND = "data_retention_anonymization"


def apply_data_retention_suggestion(db, suggestion, *, user_id: Optional[int] = None) -> dict:
    try:
        payload = json.loads(suggestion.auto_fix_payload or "")
    except (json.JSONDecodeError, TypeError):
        payload = None
    if not isinstance(payload, dict) or payload.get("kind") != RETENTION_KIND:
        raise ValueError("Proposta retention senza payload strutturato applicabile")
    collaborator_id = payload.get("collaborator_id") or suggestion.entity_id
    collaborator = db.query(models.Collaborator).filter(models.Collaborator.id == collaborator_id).first()
    if collaborator is None:
        raise ValueError(f"Collaboratore {collaborator_id} non trovato")
    if collaborator.anonimizzato:
        return {"applied": [], "skipped": [{"field": "anonimizzato", "reason": "gia anonimizzato"}]}
    row = (db.query(models.Assignment.end_date)
           .filter(models.Assignment.collaborator_id == collaborator_id)
           .order_by(models.Assignment.end_date.desc()).first())
    last_end = row[0] if row else None
    cutoff = utc_now() - timedelta(days=int(payload.get("retention_days") or 5 * 365))
    if last_end is None or last_end > cutoff.replace(tzinfo=None):
        return {"applied": [], "skipped": [{"field": "anonimizzato", "reason": "retention non piu soddisfatta"}]}
    from services.gdpr_service import anonymize_collaborator
    anonymize_collaborator(db, collaborator, user_id=user_id)
    db.commit()
    return {"applied": ["anonimizzato"], "skipped": []}


def apply_suggestion(db, suggestion, *, user_id: Optional[int] = None) -> dict:
    try:
        payload = json.loads(suggestion.auto_fix_payload or "")
    except (json.JSONDecodeError, TypeError):
        payload = None
    kind = payload.get("kind") if isinstance(payload, dict) else None
    if kind == RETENTION_KIND:
        return apply_data_retention_suggestion(db, suggestion, user_id=user_id)
    from services.agent_apply_service import PAYLOAD_KIND, apply_field_update_suggestion
    if kind == PAYLOAD_KIND:
        return apply_field_update_suggestion(db, suggestion, user_id=user_id)
    raise ValueError("Auto-fix senza payload strutturato applicabile")
