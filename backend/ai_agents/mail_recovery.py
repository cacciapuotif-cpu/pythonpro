from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

import models
from .llm import generate_mail_recovery_copy, get_agent_llm_config


def _build_suggestion(
    *,
    collaborator: models.Collaborator,
    suggestion_type: str,
    severity: str,
    title: str,
    description: str,
    subject: str,
    body: str,
    missing_fields: Optional[list[str]] = None,
    days_to_expiry: Optional[int] = None,
    confidence: float = 0.95,
) -> dict[str, Any]:
    return {
        "entity_type": "collaborator",
        "entity_id": collaborator.id,
        "suggestion_type": suggestion_type,
        "severity": severity,
        "title": title,
        "description": description,
        "confidence": confidence,
        "payload": {
            "recipient_type": "collaborator",
            "recipient_id": collaborator.id,
            "recipient_email": collaborator.email,
            "recipient_name": collaborator.full_name,
            "subject": subject,
            "body": body,
            "missing_fields": missing_fields or [],
            "days_to_expiry": days_to_expiry,
        },
    }


def _greeting(collaborator: models.Collaborator) -> str:
    return collaborator.first_name or collaborator.full_name or "Ciao"


def _missing_data_body(collaborator: models.Collaborator, missing_fields: list[str]) -> tuple[str, str]:
    pretty_fields = ", ".join(missing_fields)
    subject = "Aggiornamento dati collaboratore richiesto"
    body = (
        f"Ciao {_greeting(collaborator)},\n\n"
        "per completare la tua anagrafica operativa abbiamo bisogno di un aggiornamento su alcuni dati mancanti.\n\n"
        f"Campi da integrare: {pretty_fields}.\n\n"
        "Ti chiediamo di rispondere a questa comunicazione inviando le informazioni mancanti o i documenti necessari.\n\n"
        "Grazie."
    )
    return subject, body


def _document_expiry_body(collaborator: models.Collaborator, days_to_expiry: Optional[int]) -> tuple[str, str]:
    if days_to_expiry is None:
        timing = "risulta mancante o senza data di scadenza registrata"
    elif days_to_expiry < 0:
        timing = f"risulta scaduto da {abs(days_to_expiry)} giorni"
    else:
        timing = f"scade tra {days_to_expiry} giorni"

    subject = "Aggiornamento documento di identita richiesto"
    body = (
        f"Ciao {_greeting(collaborator)},\n\n"
        f"il documento di identita associato al tuo profilo {timing}.\n\n"
        "Per mantenere attiva la documentazione amministrativa ti chiediamo di inviare un documento valido aggiornato, "
        "indicando anche la relativa data di scadenza se non presente.\n\n"
        "Grazie."
    )
    return subject, body


def run_mail_recovery_agent(db, *, entity_type: Optional[str] = None, entity_id: Optional[int] = None, limit: int = 25) -> dict[str, Any]:
    normalized_entity_type = (entity_type or "").strip().lower() or "collaborator"
    if normalized_entity_type not in ("collaborator", "collaborators"):
        raise ValueError("Mail Recovery Agent supporta al momento solo il perimetro collaborator")

    query = db.query(models.Collaborator).filter(
        models.Collaborator.is_active == True,
        models.Collaborator.email.isnot(None),
    ).order_by(models.Collaborator.id.desc())

    if entity_id is not None:
        query = query.filter(models.Collaborator.id == entity_id)
    else:
        query = query.limit(limit)

    now = datetime.utcnow()
    near_expiry_threshold = now + timedelta(days=30)
    suggestions: list[dict[str, Any]] = []
    llm_config = get_agent_llm_config()
    llm_generated_count = 0

    for collaborator in query.all():
        missing_fields = []
        if not collaborator.phone:
            missing_fields.append("telefono")
        if not collaborator.city:
            missing_fields.append("citta")
        if not collaborator.address:
            missing_fields.append("indirizzo")
        if not collaborator.profilo_professionale:
            missing_fields.append("profilo_professionale")
        if not collaborator.curriculum_path:
            missing_fields.append("curriculum")
        if not collaborator.partita_iva:
            missing_fields.append("partita_iva")

        if missing_fields:
            subject, body = _missing_data_body(collaborator, missing_fields)
            llm_copy = generate_mail_recovery_copy(
                collaborator_name=collaborator.full_name,
                collaborator_email=collaborator.email,
                context_label="missing_collaborator_data",
                requested_tone="professionale e operativo",
                fallback_subject=subject,
                fallback_body=body,
                missing_fields=missing_fields,
            )
            if llm_copy:
                subject = llm_copy.subject
                body = llm_copy.body
                llm_generated_count += 1
            suggestions.append(_build_suggestion(
                collaborator=collaborator,
                suggestion_type="email_missing_collaborator_data",
                severity="medium",
                title=f"Bozza email recupero dati per collaboratore #{collaborator.id}",
                description=(
                    f"Preparata bozza email verso {collaborator.full_name} per richiedere i dati mancanti: "
                    f"{', '.join(missing_fields)}."
                ),
                subject=subject,
                body=body,
                missing_fields=missing_fields,
                confidence=0.94,
            ))
            suggestions[-1]["payload"]["copy_provider"] = llm_copy.provider if llm_copy else "deterministic"
            suggestions[-1]["payload"]["copy_model"] = llm_copy.model if llm_copy else None

        expiry_date = collaborator.documento_identita_scadenza
        if not collaborator.documento_identita_path or not expiry_date or expiry_date <= near_expiry_threshold:
            days_to_expiry = None
            if expiry_date:
                days_to_expiry = (expiry_date.date() - now.date()).days
            subject, body = _document_expiry_body(collaborator, days_to_expiry)
            llm_copy = generate_mail_recovery_copy(
                collaborator_name=collaborator.full_name,
                collaborator_email=collaborator.email,
                context_label="identity_document_followup",
                requested_tone="amministrativo, chiaro e sintetico",
                fallback_subject=subject,
                fallback_body=body,
                days_to_expiry=days_to_expiry,
            )
            if llm_copy:
                subject = llm_copy.subject
                body = llm_copy.body
                llm_generated_count += 1
            suggestions.append(_build_suggestion(
                collaborator=collaborator,
                suggestion_type="email_identity_document_followup",
                severity="high" if not expiry_date or (days_to_expiry is not None and days_to_expiry <= 7) else "medium",
                title=f"Bozza email documento identita per collaboratore #{collaborator.id}",
                description=(
                    f"Preparata bozza email verso {collaborator.full_name} per documento identita "
                    "mancante, senza scadenza o in scadenza."
                ),
                subject=subject,
                body=body,
                days_to_expiry=days_to_expiry,
                confidence=0.97,
            ))
            suggestions[-1]["payload"]["copy_provider"] = llm_copy.provider if llm_copy else "deterministic"
            suggestions[-1]["payload"]["copy_model"] = llm_copy.model if llm_copy else None

    summary = {
        "checked_entity_type": "collaborator",
        "checked_entity_id": entity_id,
        "suggestions_found": len(suggestions),
        "draftable_emails": len(suggestions),
        "llm_provider": llm_config.provider,
        "llm_enabled": llm_config.enabled,
        "llm_generated_count": llm_generated_count,
    }
    return {"summary": summary, "suggestions": suggestions}
