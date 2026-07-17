"""Retention revisionabile del security audit log.

Il collector non modifica dati. La pulizia avviene solo dopo approvazione
umana tramite il dispatcher delle AgentSuggestion.
"""

from __future__ import annotations

import calendar
import os
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import func

import models
from services.audit_log import write_audit_log
from time_utils import utc_now


DEFAULT_RETENTION_MONTHS = 24
DELETE_BATCH_SIZE = 1_000
SUGGESTION_TYPE = "security_audit_log_retention_cleanup"
PAYLOAD_KIND = "security_audit_log_retention_cleanup"


def get_retention_months() -> int:
    raw_value = os.getenv("AUDIT_LOG_RETENTION_MONTHS", str(DEFAULT_RETENTION_MONTHS))
    try:
        months = int(raw_value)
    except (TypeError, ValueError):
        raise ValueError("AUDIT_LOG_RETENTION_MONTHS deve essere un intero positivo") from None
    if months < 1:
        raise ValueError("AUDIT_LOG_RETENTION_MONTHS deve essere almeno 1")
    return months


def retention_cutoff(*, now: Optional[datetime] = None, months: Optional[int] = None) -> datetime:
    current = now or utc_now()
    retention_months = get_retention_months() if months is None else months
    absolute_month = current.year * 12 + current.month - 1 - retention_months
    target_year, zero_based_month = divmod(absolute_month, 12)
    target_month = zero_based_month + 1
    target_day = min(current.day, calendar.monthrange(target_year, target_month)[1])
    return current.replace(year=target_year, month=target_month, day=target_day)


def collect_security_audit_retention_suggestions(db) -> dict[str, Any]:
    months = get_retention_months()
    cutoff = retention_cutoff(months=months)
    count, oldest_id, newest_id = (
        db.query(
            func.count(models.SecurityAuditLog.id),
            func.min(models.SecurityAuditLog.id),
            func.max(models.SecurityAuditLog.id),
        )
        .filter(models.SecurityAuditLog.timestamp < cutoff)
        .one()
    )
    expired_count = int(count or 0)
    if not expired_count:
        return {
            "summary": {"items_processed": 0, "items_with_issues": 0, "candidates": 0},
            "suggestions": [],
        }

    payload = {
        "kind": PAYLOAD_KIND,
        "retention_months": months,
        "cutoff_at_collection": cutoff.isoformat(),
        "expired_count": expired_count,
        "oldest_id": int(oldest_id),
        "newest_id": int(newest_id),
        "batch_size": DELETE_BATCH_SIZE,
    }
    suggestion = {
        "entity_type": "security_audit_log",
        "entity_id": int(oldest_id),
        "suggestion_type": SUGGESTION_TYPE,
        "severity": "medium",
        "title": "Pulizia security audit log oltre retention",
        "description": (
            f"{expired_count} eventi superano la retention configurata di {months} mesi; "
            "la cancellazione richiede approvazione umana."
        ),
        "payload": payload,
        "auto_fix_available": True,
        "auto_fix_payload": payload,
        "confidence_score": 1.0,
    }
    return {
        "summary": {
            "items_processed": expired_count,
            "items_with_issues": expired_count,
            "candidates": expired_count,
        },
        "suggestions": [suggestion],
    }


def apply_security_audit_retention_suggestion(
    db,
    suggestion,
    *,
    user_id: Optional[int],
) -> dict[str, Any]:
    if not user_id:
        raise ValueError("Revisore umano obbligatorio per pulire il security audit log")

    months = get_retention_months()
    cutoff = retention_cutoff(months=months)
    expired_ids = [
        row[0]
        for row in (
            db.query(models.SecurityAuditLog.id)
            .filter(models.SecurityAuditLog.timestamp < cutoff)
            .order_by(models.SecurityAuditLog.id)
            .limit(DELETE_BATCH_SIZE)
            .all()
        )
    ]
    if not expired_ids:
        return {
            "applied": [],
            "skipped": [{"field": "audit_log", "reason": "nessun evento oltre retention"}],
        }

    deleted_count = (
        db.query(models.SecurityAuditLog)
        .filter(models.SecurityAuditLog.id.in_(expired_ids))
        .delete(synchronize_session=False)
    )
    write_audit_log(
        db,
        user_id=user_id,
        azione="security_audit_log_retention_cleanup",
        risorsa_tipo="security_audit_log",
        dati_dopo={
            "deleted_count": deleted_count,
            "first_deleted_id": min(expired_ids),
            "last_deleted_id": max(expired_ids),
            "retention_months": months,
            "cutoff": cutoff.isoformat(),
            "suggestion_id": suggestion.id,
        },
    )
    db.commit()
    return {"applied": [f"audit_logs_deleted:{deleted_count}"], "skipped": []}
