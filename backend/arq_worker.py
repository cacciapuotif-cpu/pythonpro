from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any

import httpx
from arq.connections import RedisSettings
from arq.cron import cron

from agent_workflows import promote_due_followups
from database import SessionLocal

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
        "processed_at": datetime.utcnow().isoformat(),
        "payload": payload,
    }


async def send_outbound_webhook(ctx: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Worker ARQ: invia webhook outbound verso endpoint esterno preconfigurato."""
    webhook_url = payload.get("webhook_url")
    if not webhook_url:
        return {"status": "skipped", "reason": "missing_webhook_url"}

    body = {
        "event_type": payload.get("event_type"),
        "occurred_at": datetime.utcnow().isoformat(),
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
            "processed_at": datetime.utcnow().isoformat(),
        }
    finally:
        db.close()


class WorkerSettings:
    functions = [process_entity_change_event, send_outbound_webhook, promote_agent_followups]
    redis_settings = RedisSettings(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        database=int(os.getenv("REDIS_DB", "0")),
        password=os.getenv("REDIS_PASSWORD"),
    )
    cron_jobs = [
        cron(promote_agent_followups, minute={5, 35}),
    ]
    max_tries = 3
