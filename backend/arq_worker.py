from __future__ import annotations

from time_utils import utc_now
import logging
import os
from datetime import datetime, timedelta
from typing import Any

import httpx
from arq.connections import RedisSettings
from arq.cron import cron

from agent_workflows import promote_due_followups, _send_email
from ai_agents.control import agent_enabled, agents_enabled, disabled_reason
from database import SessionLocal

# AGENT-06: registra User (auth.py) nella metadata della Base condivisa.
# AgentReviewAction.reviewed_by_user_id ha FK verso users.id: senza questo
# import il processo ARQ non ha la tabella users nella metadata e ogni flush
# di AgentReviewAction fallisce con NoReferencedTableError.
import auth  # noqa: F401  isort: skip

logger = logging.getLogger(__name__)


async def process_entity_change_event(ctx: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Worker ARQ: registra evento dominio per integrazioni esterne/agenti."""
    logger.info(
        "Entity change event queued: entity=%s action=%s entity_id=%s",
        payload.get("entity"),
        payload.get("action"),
        payload.get("entity_id"),
    )
    return {
        "status": "processed",
        "processed_at": utc_now().isoformat(),
        "payload": payload,
    }


async def send_outbound_webhook(ctx: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Worker ARQ: invia webhook outbound verso endpoint esterno preconfigurato."""
    webhook_url = payload.get("webhook_url")
    if not webhook_url:
        return {"status": "skipped", "reason": "missing_webhook_url"}

    body = {
        "event_type": payload.get("event_type"),
        "occurred_at": utc_now().isoformat(),
        "data": payload.get("body", {}),
    }

    timeout = httpx.Timeout(10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(webhook_url, json=body)

    return {
        "status": "sent",
        "status_code": response.status_code,
        "webhook_url": webhook_url,
    }


async def promote_agent_followups(ctx: dict[str, Any]) -> dict[str, Any]:
    """Worker ARQ: promuove a follow-up le pratiche inviate da oltre 7 giorni."""
    db = SessionLocal()
    try:
        promoted = promote_due_followups(db)
        logger.info("Agent follow-up sweep completed: promoted=%s", promoted)
        return {
            "status": "completed",
            "promoted": promoted,
            "processed_at": utc_now().isoformat(),
        }
    finally:
        db.close()


async def poll_email_inbox(ctx: dict[str, Any]) -> dict[str, Any]:
    """Worker ARQ: polling IMAP email in arrivo per documenti allegati.

    Runs in the single arq_worker process — no duplication across gunicorn workers.
    Interval: every 5 minutes (matches INBOX_POLL_INTERVAL_SECONDS default of 300s).
    """
    import asyncio

    if not agent_enabled("email_intake"):
        return {"status": "skipped", "reason": disabled_reason("email_intake")}

    imap_user = os.getenv("GMAIL_IMAP_USER", "")
    if not imap_user:
        logger.debug("poll_email_inbox: GMAIL_IMAP_USER non configurato, skip")
        return {"status": "skipped", "reason": "no_imap_user"}

    from services.email_inbox_worker import EmailInboxWorker

    worker = EmailInboxWorker()
    db = SessionLocal()
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, worker._run_poll_cycle, db)
        logger.info("poll_email_inbox: ciclo completato")
        return {"status": "completed", "processed_at": utc_now().isoformat()}
    except Exception as exc:
        logger.exception("poll_email_inbox: errore: %s", exc)
        return {"status": "error", "error": str(exc)}
    finally:
        db.close()


async def run_mail_recovery_cron(ctx: dict[str, Any]) -> dict[str, Any]:
    if not agent_enabled("mail_recovery"):
        return {"status": "skipped", "reason": disabled_reason("mail_recovery")}
    db = SessionLocal()
    try:
        from ai_agents.mail_recovery import run_mail_recovery_agent

        result = run_mail_recovery_agent(db)
        logger.info("mail_recovery_agent cron completed: %s", result)
        return {"status": "completed", "agent": "mail_recovery_agent", "result": result}
    except Exception as exc:
        logger.exception("mail_recovery_agent cron error: %s", exc)
        return {"status": "error", "agent": "mail_recovery_agent", "error": str(exc)}
    finally:
        db.close()


async def run_contract_agent_cron(ctx: dict[str, Any]) -> dict[str, Any]:
    if not agent_enabled("contract_agent"):
        return {"status": "skipped", "reason": disabled_reason("contract_agent")}
    db = SessionLocal()
    try:
        from ai_agents.contract_agent import run_contract_agent

        result = run_contract_agent(db)
        logger.info("contract_agent cron completed: %s", result)
        return {"status": "completed", "agent": "contract_agent", "result": result}
    except Exception as exc:
        logger.exception("contract_agent cron error: %s", exc)
        return {"status": "error", "agent": "contract_agent", "error": str(exc)}
    finally:
        db.close()


async def run_certification_agent_cron(ctx: dict[str, Any]) -> dict[str, Any]:
    if not agent_enabled("certification"):
        return {"status": "skipped", "reason": disabled_reason("certification")}
    db = SessionLocal()
    try:
        from ai_agents.certification_agent import run_certification_agent

        result = run_certification_agent(db)
        logger.info("certification_agent cron completed: %s", result)
        return {"status": "completed", "agent": "certification_agent", "result": result}
    except Exception as exc:
        logger.exception("certification_agent cron error: %s", exc)
        return {"status": "error", "agent": "certification_agent", "error": str(exc)}
    finally:
        db.close()


async def data_retention_cleanup(ctx: dict[str, Any]) -> dict[str, Any]:
    """Anonimizza collaboratori non attivi oltre 5 anni dalla fine ultimo rapporto."""
    if not agents_enabled():
        return {"status": "skipped", "reason": disabled_reason("data_retention")}
    db = SessionLocal()
    try:
        import models
        from services.gdpr_service import anonymize_collaborator

        cutoff = utc_now() - timedelta(days=5 * 365)
        candidates = (
            db.query(models.Collaborator)
            .filter(models.Collaborator.anonimizzato.is_(False))
            .all()
        )
        anonymized = 0
        for collaborator in candidates:
            last_assignment_end = (
                db.query(models.Assignment.end_date)
                .filter(models.Assignment.collaborator_id == collaborator.id)
                .order_by(models.Assignment.end_date.desc())
                .first()
            )
            if not last_assignment_end or not last_assignment_end[0] or last_assignment_end[0] > cutoff:
                continue
            anonymize_collaborator(db, collaborator, user_id=None)
            anonymized += 1
        db.commit()
        admin_email = os.getenv("DATA_RETENTION_REPORT_EMAIL") or os.getenv("SMTP_FROM")
        if admin_email and anonymized:
            _send_email(
                recipient_email=admin_email,
                subject="Report data retention PythonPro",
                body=f"Anonimizzati {anonymized} collaboratori oltre retention quinquennale.",
            )
        return {"status": "completed", "anonymized": anonymized, "processed_at": utc_now().isoformat()}
    except Exception as exc:
        db.rollback()
        logger.exception("data_retention_cleanup error: %s", exc)
        return {"status": "error", "error": str(exc)}
    finally:
        db.close()


async def startup(ctx: dict[str, Any]) -> None:
    logger.info(
        "ARQ cron loaded: email_inbox_poll=5m, mail_recovery_agent=6h, "
        "contract_agent=2h, certification_agent=09:00 daily"
    )


class WorkerSettings:
    functions = [
        process_entity_change_event,
        send_outbound_webhook,
        promote_agent_followups,
        poll_email_inbox,
        run_mail_recovery_cron,
        run_contract_agent_cron,
        run_certification_agent_cron,
        data_retention_cleanup,
    ]
    redis_settings = RedisSettings(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        database=int(os.getenv("REDIS_DB", "0")),
        password=os.getenv("REDIS_PASSWORD"),
    )
    cron_jobs = [
        cron(promote_agent_followups, minute={5, 35}),
        # Email IMAP polling ogni 5 minuti (INBOX_POLL_INTERVAL_SECONDS default=300).
        # Centralizzato qui per evitare duplicazione su più worker uvicorn.
        cron(poll_email_inbox, minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}),
        cron(run_mail_recovery_cron, hour={0, 6, 12, 18}, minute=10),
        cron(run_contract_agent_cron, hour={0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22}, minute=20),
        cron(run_certification_agent_cron, hour=9, minute=0),
        cron(data_retention_cleanup, weekday=6, hour=3, minute=0),
    ]
    on_startup = startup
    max_tries = 3
