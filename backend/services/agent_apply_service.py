"""Proposte di aggiornamento campi (diff) e loro applicazione reale dopo approvazione umana.

Formato auto_fix_payload (JSON) per suggestion_type="document_field_updates":

    {
        "kind": "field_diff",
        "entity_type": "collaborator",
        "entity_id": 1,
        "changes": [
            {"field": "fiscal_code", "current": null, "proposed": "RSSMRA80A01H501Z", "confidence": 0.9}
        ],
        "source": {"doc_type": "curriculum", "documento_richiesto_id": 12}
    }

L'applicazione (`apply_field_update_suggestion`) è l'unico punto che scrive le anagrafiche:
whitelist campi per entity_type, ricontrollo del valore attuale (skip se stantio) e
audit log immutabile per ogni campo applicato.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Optional

import models
from time_utils import utc_now

logger = logging.getLogger(__name__)

PAYLOAD_KIND = "field_diff"
SUGGESTION_TYPE_FIELD_UPDATES = "document_field_updates"

# Campi applicabili per entity_type: field -> tipo valore ("text" | "datetime")
FIELD_WHITELIST: dict[str, dict[str, str]] = {
    "collaborator": {
        "fiscal_code": "text",
        "partita_iva": "text",
        "phone": "text",
        "profilo_professionale": "text",
        "competenze_principali": "text",
        "education": "text",
        "documento_identita_path": "text",
        "documento_identita_filename": "text",
        "documento_identita_scadenza": "datetime",
        "curriculum_path": "text",
        "curriculum_filename": "text",
    },
    "azienda_cliente": {
        "ragione_sociale": "text",
        "partita_iva": "text",
        "codice_fiscale": "text",
        "settore_ateco": "text",
        "indirizzo": "text",
        "citta": "text",
        "cap": "text",
        "provincia": "text",
        "pec": "text",
        "email": "text",
        "telefono": "text",
        "legale_rappresentante_nome": "text",
        "legale_rappresentante_cognome": "text",
        "legale_rappresentante_codice_fiscale": "text",
        "legale_rappresentante_email": "text",
        "legale_rappresentante_telefono": "text",
        "attivita_erogate": "text",
        "note": "text",
    },
}

# Timestamp di corredo aggiornati automaticamente quando il campo principale viene applicato.
COMPANION_TIMESTAMPS: dict[str, dict[str, str]] = {
    "collaborator": {
        "documento_identita_path": "documento_identita_uploaded_at",
        "curriculum_path": "curriculum_uploaded_at",
    },
}


def _entity_model(entity_type: str):
    return {
        "collaborator": models.Collaborator,
        "azienda_cliente": models.AziendaCliente,
    }.get(entity_type)


def serialize_value(value: Any) -> Optional[str]:
    """Serializzazione stabile per confronto stantio e payload JSON."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def build_change(field: str, current: Any, proposed: Any, confidence: Optional[float]) -> dict:
    return {
        "field": field,
        "current": serialize_value(current),
        "proposed": serialize_value(proposed),
        "confidence": confidence,
    }


def create_field_update_suggestion(
    db,
    *,
    entity_type: str,
    entity_id: int,
    entity_name: Optional[str],
    changes: list[dict],
    source: Optional[dict] = None,
    confidence: Optional[float] = None,
    triggered_by: str = "email_inbox_worker",
) -> Optional[models.AgentSuggestion]:
    """Crea AgentRun + AgentSuggestion pending con il diff proposto. Nessuna scrittura sull'entità."""
    if not changes:
        return None

    run = models.AgentRun(
        agent_type="email_intake",
        status="completed",
        entity_type=entity_type,
        entity_id=entity_id,
        triggered_by=triggered_by,
        items_processed=1,
        suggestions_created=1,
        suggestions_count=1,
    )
    db.add(run)
    db.flush()

    payload = {
        "kind": PAYLOAD_KIND,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "changes": changes,
        "source": source or {},
    }
    fields_desc = ", ".join(change["field"] for change in changes)
    display_name = entity_name or f"{entity_type} {entity_id}"
    suggestion = models.AgentSuggestion(
        run_id=run.id,
        suggestion_type=SUGGESTION_TYPE_FIELD_UPDATES,
        status="pending",
        severity="medium",
        entity_type=entity_type,
        entity_id=entity_id,
        title=f"Aggiornamento dati proposto — {display_name}",
        description=f"Campi proposti da documento/email: {fields_desc}",
        priority="medium",
        auto_fix_available=True,
        auto_fix_payload=json.dumps(payload, ensure_ascii=True),
        confidence_score=confidence,
    )
    db.add(suggestion)
    db.commit()
    db.refresh(suggestion)
    return suggestion


def parse_field_diff_payload(raw_payload: Optional[str]) -> Optional[dict]:
    """Ritorna il payload field_diff se valido, altrimenti None."""
    if not raw_payload:
        return None
    try:
        payload = json.loads(raw_payload)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(payload, dict) or payload.get("kind") != PAYLOAD_KIND:
        return None
    if not isinstance(payload.get("changes"), list):
        return None
    return payload


def apply_field_update_suggestion(db, suggestion, *, user_id: Optional[int] = None) -> dict:
    """Applica davvero il diff proposto: whitelist, ricontrollo valori attuali, audit per campo.

    Ritorna {"applied": [campo...], "skipped": [{"field", "reason"}...]}.
    Solleva ValueError su payload/entità non applicabili.
    """
    payload = parse_field_diff_payload(suggestion.auto_fix_payload)
    if payload is None:
        raise ValueError("Auto-fix senza payload strutturato applicabile")

    entity_type = payload.get("entity_type") or suggestion.entity_type
    entity_id = payload.get("entity_id") or suggestion.entity_id
    model = _entity_model(entity_type)
    whitelist = FIELD_WHITELIST.get(entity_type)
    if model is None or whitelist is None:
        raise ValueError(f"Entity type non applicabile: {entity_type}")

    entity = db.query(model).filter(model.id == entity_id).first()
    if entity is None:
        raise ValueError(f"Entità {entity_type} {entity_id} non trovata")

    companions = COMPANION_TIMESTAMPS.get(entity_type, {})
    applied: list[str] = []
    skipped: list[dict] = []

    for change in payload["changes"]:
        field = change.get("field")
        if not field or field not in whitelist:
            skipped.append({"field": field, "reason": "campo non in whitelist"})
            continue

        live_value = getattr(entity, field, None)
        if serialize_value(live_value) != change.get("current"):
            skipped.append({
                "field": field,
                "reason": "valore attuale cambiato dopo la proposta",
                "expected_current": change.get("current"),
                "actual_current": serialize_value(live_value),
            })
            continue

        proposed_raw = change.get("proposed")
        if whitelist[field] == "datetime" and proposed_raw is not None:
            try:
                new_value: Any = datetime.fromisoformat(str(proposed_raw).replace("Z", "+00:00"))
            except ValueError:
                skipped.append({"field": field, "reason": f"valore datetime non parseabile: {proposed_raw!r}"})
                continue
        else:
            new_value = proposed_raw

        setattr(entity, field, new_value)
        companion_field = companions.get(field)
        if companion_field:
            setattr(entity, companion_field, utc_now())

        db.add(models.AuditLog(
            entity=f"{entity_type}:{entity_id}",
            action="agent_apply_fix",
            old_value=json.dumps({field: serialize_value(live_value)}, ensure_ascii=True),
            new_value=json.dumps({field: proposed_raw}, ensure_ascii=True),
            user_id=user_id,
        ))
        applied.append(field)

    if applied:
        db.add(entity)
        if entity_type == "collaborator":
            _resolve_pending_data_requests(db, collaborator_id=entity_id)

    db.commit()
    logger.info(
        "agent_apply_service: suggestion %s su %s/%s — applicati %s, saltati %s",
        suggestion.id,
        entity_type,
        entity_id,
        applied,
        [item.get("field") for item in skipped],
    )
    return {"applied": applied, "skipped": skipped}


def _resolve_pending_data_requests(db, *, collaborator_id: int) -> None:
    """Chiude le richieste dati pendenti quando i dati vengono effettivamente applicati."""
    pending = (
        db.query(models.AgentSuggestion)
        .filter(
            models.AgentSuggestion.entity_type == "collaborator",
            models.AgentSuggestion.entity_id == collaborator_id,
            models.AgentSuggestion.suggestion_type == "request_missing_collaborator_data",
            models.AgentSuggestion.status == "pending",
        )
        .all()
    )
    for item in pending:
        item.status = "resolved"
        item.reviewed_at = utc_now()
