"""Store condiviso per preview FAPI — usa Redis se disponibile, fallback dict."""
import json
import logging
import os
from threading import Lock

logger = logging.getLogger(__name__)

_TTL = 600  # 10 minuti

# ── Redis ─────────────────────────────────────────────────────────────────────
_redis = None
try:
    import redis as redis_lib
    _redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    _redis = redis_lib.from_url(_redis_url, decode_responses=True, socket_timeout=2)
    _redis.ping()
    logger.info("fapi_preview_store: usa Redis")
except Exception as exc:
    logger.warning("fapi_preview_store: Redis non disponibile (%s), uso dict locale", exc)
    _redis = None

# ── Fallback in-memory ────────────────────────────────────────────────────────
_local: dict = {}
_local_lock = Lock()


def store(token: str, data: dict) -> None:
    if _redis:
        try:
            _redis.setex(f"fapi_preview:{token}", _TTL, json.dumps(data, default=str))
            return
        except Exception as exc:
            logger.warning("Redis store failed: %s", exc)
    with _local_lock:
        _local[token] = data


def get(token: str) -> dict | None:
    """Legge una preview senza consumarla.

    Serve per validare destinazione e conflitti prima del ``pop`` atomico:
    un errore correggibile non deve obbligare l'operatore a ricaricare il PDF.
    """
    if _redis:
        try:
            raw = _redis.get(f"fapi_preview:{token}")
            return json.loads(raw) if raw else None
        except Exception as exc:
            logger.warning("Redis get failed: %s", exc)
    with _local_lock:
        return _local.get(token)


def pop(token: str) -> dict | None:
    if _redis:
        try:
            key = f"fapi_preview:{token}"
            # Redis >= 6.2: lettura e cancellazione in un'unica operazione.
            # Un GET seguito da DELETE consentiva due conferme concorrenti.
            raw = _redis.getdel(key)
            return json.loads(raw) if raw else None
        except Exception as exc:
            logger.warning("Redis pop failed: %s", exc)
    with _local_lock:
        return _local.pop(token, None)
