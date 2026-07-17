"""Collector GDPR retention: propone, non anonimizza."""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Optional

import models
from time_utils import utc_now

RETENTION_DAYS = 5 * 365
SUGGESTION_TYPE = "data_retention_anonymization"
PAYLOAD_KIND = "data_retention_anonymization"


def collect_data_retention_suggestions(db, *, collaborator_id: Optional[int] = None) -> dict[str, Any]:
    """Trova collaboratori oltre retention senza modificare dati o inviare email."""
    cutoff = utc_now() - timedelta(days=RETENTION_DAYS)
    query = db.query(models.Collaborator).filter(models.Collaborator.anonimizzato.is_(False))
    if collaborator_id is not None:
        query = query.filter(models.Collaborator.id == collaborator_id)
    suggestions = []
    scanned = 0
    for collaborator in query.all():
        scanned += 1
        row = (db.query(models.Assignment.end_date)
               .filter(models.Assignment.collaborator_id == collaborator.id)
               .order_by(models.Assignment.end_date.desc()).first())
        last_end = row[0] if row else None
        if last_end is None or last_end > cutoff.replace(tzinfo=None):
            continue
        payload = {"kind": PAYLOAD_KIND, "collaborator_id": collaborator.id,
                   "last_assignment_end": last_end.isoformat(), "retention_days": RETENTION_DAYS,
                   "cutoff_at_collection": cutoff.isoformat()}
        suggestions.append({
            "entity_type": "collaborator", "entity_id": collaborator.id,
            "suggestion_type": SUGGESTION_TYPE, "severity": "high",
            "title": f"Anonimizzazione GDPR proposta — {collaborator.full_name}",
            "description": f"Ultimo rapporto terminato il {last_end.date().isoformat()}; verificare e approvare l'anonimizzazione.",
            "payload": payload, "auto_fix_available": True,
            "auto_fix_payload": payload, "confidence_score": 1.0,
        })
    return {"summary": {"items_processed": scanned, "items_with_issues": len(suggestions),
                         "candidates": len(suggestions)}, "suggestions": suggestions}
