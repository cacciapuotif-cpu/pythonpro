"""Dispatcher sicuro degli auto-fix agentici revisionati."""
from __future__ import annotations

import json
from datetime import timedelta
from typing import Optional

import models
from time_utils import utc_now

RETENTION_KIND = "data_retention_anonymization"
AVVISO_ESTRAZIONE_KIND = "avviso_estrazione"
SECURITY_AUDIT_RETENTION_KIND = "security_audit_log_retention_cleanup"
ATTIVITA_PIANO_KIND = "attivita_piano"
PLAYBOOK_VOCE_KIND = "playbook_voce"
# Guardia timesheet: le suggestion sono informative (warning) e non mutano il
# DB. L'apply e' un no-op documentato: marca la presa in carico senza scrivere
# nulla. Predisposto per un futuro "verificato" ma qui non muta stato.
TIMESHEET_VERIFICA_KIND = "timesheet_verifica"


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


def apply_avviso_extraction_suggestion(db, suggestion, *, user_id: Optional[int] = None) -> dict:
    if not user_id:
        raise ValueError("Revisore umano obbligatorio per materializzare dati avviso")
    import crud_avvisi
    import schemas_avvisi as avvisi_schemas

    payload = json.loads(suggestion.auto_fix_payload or "")
    target = payload.get("target")
    revision_id = payload.get("revision_id") or suggestion.entity_id
    proposal_data = dict(payload.get("proposal") or {})
    proposal_data["origin_suggestion_id"] = suggestion.id
    if target == "regola":
        proposal = avvisi_schemas.AvvisoRegolaProposal.model_validate(proposal_data)
        rule = crud_avvisi.create_rule_proposal(db, revision_id, proposal, commit=False)
        db.commit()
        crud_avvisi.review_rule(db, rule.id, action="approva", reviewer_user_id=user_id)
        return {"applied": [f"avviso_regola:{rule.id}"], "skipped": []}
    if target == "scadenza":
        proposal = avvisi_schemas.AvvisoScadenzaProposal.model_validate(proposal_data)
        deadline = crud_avvisi.create_deadline_proposal(db, revision_id, proposal)
        crud_avvisi.review_deadline(db, deadline.id, action="approva", reviewer_user_id=user_id)
        return {"applied": [f"avviso_scadenza:{deadline.id}"], "skipped": []}
    raise ValueError(f"Target estrazione avviso non supportato: {target}")


def apply_suggestion(db, suggestion, *, user_id: Optional[int] = None) -> dict:
    try:
        payload = json.loads(suggestion.auto_fix_payload or "")
    except (json.JSONDecodeError, TypeError):
        payload = None
    kind = payload.get("kind") if isinstance(payload, dict) else None
    if kind == RETENTION_KIND:
        return apply_data_retention_suggestion(db, suggestion, user_id=user_id)
    if kind == AVVISO_ESTRAZIONE_KIND:
        return apply_avviso_extraction_suggestion(db, suggestion, user_id=user_id)
    if kind == SECURITY_AUDIT_RETENTION_KIND:
        from services.security_audit_retention import apply_security_audit_retention_suggestion

        return apply_security_audit_retention_suggestion(
            db, suggestion, user_id=user_id
        )
    if kind == ATTIVITA_PIANO_KIND:
        from services.attivita import apply_piano_attivita
        counts = apply_piano_attivita(db, suggestion, user_id=user_id)
        return {
            "applied": ([f"attivita_create:{counts['create']}"] if counts["create"] else []),
            "skipped": ([{"reason": "gia_esistenti", "count": counts["esistenti"]}]
                        if counts["esistenti"] else []),
            "counts": counts,
        }
    if kind == PLAYBOOK_VOCE_KIND:
        from services.playbook import apply_voce_suggestion
        return apply_voce_suggestion(db, suggestion, user_id=user_id)
    if kind == TIMESHEET_VERIFICA_KIND:
        # No-op documentato: la guardia timesheet e' proposal-only e non muta
        # il DB in B5.2. L'apply conferma la presa in carico senza scrivere.
        return {"applied": [], "skipped": [{"reason": "informativa_nessuna_mutazione"}]}
    from services.agent_apply_service import PAYLOAD_KIND, apply_field_update_suggestion
    if kind == PAYLOAD_KIND:
        return apply_field_update_suggestion(db, suggestion, user_id=user_id)
    raise ValueError("Auto-fix senza payload strutturato applicabile")
