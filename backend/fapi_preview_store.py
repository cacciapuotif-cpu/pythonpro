"""Store condiviso per preview FAPI — usa Redis se disponibile, fallback dict."""
import json
import logging
import os

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


def store(token: str, data: dict) -> None:
    if _redis:
        try:
            _redis.setex(f"fapi_preview:{token}", _TTL, json.dumps(data, default=str))
            return
        except Exception as exc:
            logger.warning("Redis store failed: %s", exc)
    _local[token] = data


def pop(token: str) -> dict | None:
    if _redis:
        try:
            key = f"fapi_preview:{token}"
            raw = _redis.get(key)
            if raw:
                _redis.delete(key)
                return json.loads(raw)
            return None
        except Exception as exc:
            logger.warning("Redis pop failed: %s", exc)
    return _local.pop(token, None)
