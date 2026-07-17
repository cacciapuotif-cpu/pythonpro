"""Store condiviso per lo stato del polling IMAP (worker ARQ <-> backend API).

NEW-007: /email-inbox/status leggeva un dict in-process del modulo worker,
ma il polling reale gira nel processo ARQ: il backend rispondeva sempre con
uno stato mai aggiornato. Qui lo stato vive su Redis, con fallback in-memory
quando Redis non e' raggiungibile (test/dev).

Backoff su errori di login IMAP: base 5 minuti, raddoppio a ogni tentativo
fallito, cap 6 ore. `should_skip()` dice al polling di saltare finche'
now < next_retry_at; un login riuscito azzera il backoff.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

STATUS_KEY = "pythonpro:email_inbox:status"

BACKOFF_BASE_SECONDS = 300
BACKOFF_MULTIPLIER = 2
BACKOFF_CAP_SECONDS = 6 * 3600

_DEFAULT_STATUS: dict[str, Any] = {
    "state": "unknown",
    "last_error": None,
    "failed_attempts": 0,
    "next_retry_at": None,
    "last_success_at": None,
    "last_poll_at": None,
}

_lock = threading.RLock()
_memory_status: dict[str, Any] = dict(_DEFAULT_STATUS)
_redis_client = None
_redis_checked = False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_redis():
    global _redis_client, _redis_checked
    with _lock:
        if _redis_checked:
            return _redis_client
        _redis_checked = True
        try:
            import redis

            client = redis.Redis(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", "6379")),
                db=int(os.getenv("REDIS_DB", "0")),
                password=os.getenv("REDIS_PASSWORD") or None,
                socket_connect_timeout=2,
                socket_timeout=2,
                decode_responses=True,
            )
            client.ping()
            _redis_client = client
            logger.info("inbox_status_store: stato condiviso su Redis")
        except Exception as exc:
            _redis_client = None
            logger.info(
                "inbox_status_store: Redis non raggiungibile, fallback in-memory: %s", exc
            )
        return _redis_client


def reset_for_tests(*, force_memory: bool = True) -> None:
    """Riporta lo store allo stato iniziale senza toccare la rete."""
    global _redis_client, _redis_checked
    with _lock:
        if force_memory:
            _redis_client = None
            _redis_checked = True
        else:
            _redis_client = None
            _redis_checked = False
        _memory_status.clear()
        _memory_status.update(_DEFAULT_STATUS)


def get_status() -> dict[str, Any]:
    client = _get_redis()
    if client is not None:
        try:
            raw = client.get(STATUS_KEY)
            if raw:
                return {**_DEFAULT_STATUS, **json.loads(raw)}
            return dict(_DEFAULT_STATUS)
        except Exception as exc:
            logger.warning("inbox_status_store: lettura Redis fallita: %s", exc)
    with _lock:
        return dict(_memory_status)


def _save(status: dict[str, Any]) -> None:
    client = _get_redis()
    if client is not None:
        try:
            client.set(STATUS_KEY, json.dumps(status))
            return
        except Exception as exc:
            logger.warning("inbox_status_store: scrittura Redis fallita: %s", exc)
    with _lock:
        _memory_status.clear()
        _memory_status.update(status)


def backoff_delay_seconds(failed_attempts: int) -> int:
    """Delay per il tentativo numero `failed_attempts` (1-based)."""
    if failed_attempts <= 0:
        return 0
    delay = BACKOFF_BASE_SECONDS * (BACKOFF_MULTIPLIER ** (failed_attempts - 1))
    return min(delay, BACKOFF_CAP_SECONDS)


def record_success() -> dict[str, Any]:
    status = get_status()
    now_iso = _now().isoformat()
    status.update(
        {
            "state": "connected",
            "last_error": None,
            "failed_attempts": 0,
            "next_retry_at": None,
            "last_success_at": now_iso,
            "last_poll_at": now_iso,
        }
    )
    _save(status)
    return status


def record_failure(error: str, *, kind: str = "error") -> dict[str, Any]:
    if kind not in ("auth_failed", "error"):
        kind = "error"
    status = get_status()
    attempts = int(status.get("failed_attempts") or 0) + 1
    delay = backoff_delay_seconds(attempts)
    status.update(
        {
            "state": kind,
            "last_error": str(error),
            "failed_attempts": attempts,
            "next_retry_at": (_now() + timedelta(seconds=delay)).isoformat(),
            "last_poll_at": _now().isoformat(),
        }
    )
    _save(status)
    return status


def record_disabled(reason: str) -> dict[str, Any]:
    status = get_status()
    status.update(
        {
            "state": "disabled",
            "last_error": reason,
            "next_retry_at": None,
        }
    )
    _save(status)
    return status


def should_skip() -> tuple[bool, Optional[str]]:
    """True se il polling deve saltare perche' il backoff e' ancora attivo."""
    status = get_status()
    next_retry_at = status.get("next_retry_at")
    if not next_retry_at:
        return False, None
    try:
        retry_dt = datetime.fromisoformat(next_retry_at)
    except (TypeError, ValueError):
        return False, None
    if retry_dt.tzinfo is None:
        retry_dt = retry_dt.replace(tzinfo=timezone.utc)
    if _now() < retry_dt:
        return True, next_retry_at
    return False, None


def status_message(status: dict[str, Any]) -> str:
    state = status.get("state")
    if state == "connected":
        return "Inbox: connessa"
    if state == "auth_failed":
        return "Inbox: disconnessa — credenziali non valide"
    if state == "disabled":
        return f"Inbox: disconnessa — {status.get('last_error') or 'polling disabilitato'}"
    if state == "error":
        return f"Inbox: errore — {status.get('last_error') or 'errore sconosciuto'}"
    return "Inbox: stato sconosciuto"
