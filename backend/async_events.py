from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Optional

from arq.connections import RedisSettings, create_pool

logger = logging.getLogger(__name__)


def _redis_settings() -> RedisSettings:
    return RedisSettings(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        database=int(os.getenv("REDIS_DB", "0")),
        password=os.getenv("REDIS_PASSWORD"),
    )


async def _enqueue_job_async(function_name: str, **payload: Any) -> None:
    redis = await create_pool(_redis_settings())
    try:
        await redis.enqueue_job(function_name, payload)
    finally:
        await redis.aclose()


def enqueue_job(function_name: str, **payload: Any) -> None:
    """Enqueue ARQ job from sync FastAPI CRUD paths."""
    payload.setdefault("queued_at", datetime.utcnow().isoformat())
    try:
        asyncio.run(_enqueue_job_async(function_name, **payload))
    except RuntimeError:
        # Fallback per ambienti con loop già attivo.
        loop = asyncio.get_event_loop()
        loop.create_task(_enqueue_job_async(function_name, **payload))
    except Exception as exc:
        logger.warning("ARQ enqueue failed for %s: %s", function_name, exc)


def enqueue_entity_change_event(
    entity: str,
    action: str,
    entity_id: Optional[int],
    user_id: Optional[int] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    enqueue_job(
        "process_entity_change_event",
        entity=entity,
        action=action,
        entity_id=entity_id,
        user_id=user_id,
        metadata=metadata or {},
    )


def enqueue_webhook_notification(event_type: str, payload: dict[str, Any]) -> None:
    webhook_url = os.getenv("PYTHONPRO_OUTBOUND_WEBHOOK_URL", "").strip()
    if not webhook_url:
        return
    enqueue_job(
        "send_outbound_webhook",
        event_type=event_type,
        webhook_url=webhook_url,
        body=payload,
    )


def track_entity_event(
    entity: str,
    action: str,
    entity_id_getter: Optional[Callable[[Any, tuple[Any, ...], dict[str, Any]], Optional[int]]] = None,
    metadata_getter: Optional[Callable[[Any, tuple[Any, ...], dict[str, Any]], dict[str, Any]]] = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator per tracciare modifiche alle entità chiave con emissione evento ARQ.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = func(*args, **kwargs)
            try:
                entity_id = None
                if entity_id_getter:
                    entity_id = entity_id_getter(result, args, kwargs)
                elif hasattr(result, "id"):
                    entity_id = getattr(result, "id")
                metadata = metadata_getter(result, args, kwargs) if metadata_getter else {}
                enqueue_entity_change_event(
                    entity=entity,
                    action=action,
                    entity_id=entity_id,
                    user_id=metadata.get("user_id"),
                    metadata=metadata,
                )
            except Exception as exc:
                logger.warning("Unable to emit entity event %s.%s: %s", entity, action, exc)
            return result

        return wrapper

    return decorator
