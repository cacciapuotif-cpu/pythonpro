from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class WhatsAppSendResult:
    ok: bool
    detail: str
    provider: str
    provider_message_id: Optional[str] = None
    raw_response: Optional[str] = None


def _is_enabled() -> bool:
    return os.getenv("ENABLE_WHATSAPP", "false").strip().lower() in {"1", "true", "yes", "on"}


def _provider_name() -> str:
    return (os.getenv("WHATSAPP_PROVIDER", "generic") or "generic").strip().lower()


def send_whatsapp_message(
    *,
    recipient_phone: str,
    body: str,
    subject: Optional[str] = None,
) -> WhatsAppSendResult:
    if not _is_enabled():
        return WhatsAppSendResult(
            ok=False,
            detail="Invio WhatsApp non abilitato",
            provider=_provider_name(),
        )

    provider = _provider_name()
    try:
        if provider in {"meta", "meta_cloud_api"}:
            return _send_via_meta_cloud_api(
                recipient_phone=recipient_phone,
                body=body,
                subject=subject,
            )
        return _send_via_generic_provider(
            recipient_phone=recipient_phone,
            body=body,
            subject=subject,
        )
    except Exception as exc:
        logger.warning("Invio WhatsApp fallito verso %s: %s", recipient_phone, exc)
        return WhatsAppSendResult(
            ok=False,
            detail=str(exc),
            provider=provider,
        )


def _send_via_meta_cloud_api(
    *,
    recipient_phone: str,
    body: str,
    subject: Optional[str],
) -> WhatsAppSendResult:
    token = (os.getenv("WHATSAPP_API_TOKEN", "") or "").strip()
    phone_number_id = (os.getenv("WHATSAPP_META_PHONE_NUMBER_ID", "") or "").strip()
    graph_version = (os.getenv("WHATSAPP_META_GRAPH_VERSION", "v17.0") or "v17.0").strip()
    base_url = (os.getenv("WHATSAPP_META_BASE_URL", "https://graph.facebook.com") or "https://graph.facebook.com").rstrip("/")
    timeout_seconds = float(os.getenv("WHATSAPP_TIMEOUT_SECONDS", "15") or "15")

    if not token:
        return WhatsAppSendResult(
            ok=False,
            detail="Configurazione Meta incompleta: WHATSAPP_API_TOKEN mancante",
            provider=_provider_name(),
        )
    if not phone_number_id:
        return WhatsAppSendResult(
            ok=False,
            detail="Configurazione Meta incompleta: WHATSAPP_META_PHONE_NUMBER_ID mancante",
            provider=_provider_name(),
        )

    message_body = body.strip()
    if subject and subject.strip():
        message_body = f"{subject.strip()}\n\n{message_body}"

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": _normalize_phone(recipient_phone),
        "type": "text",
        "text": {
            "preview_url": False,
            "body": message_body,
        },
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    target_url = f"{base_url}/{graph_version}/{phone_number_id}/messages"

    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.post(target_url, json=payload, headers=headers)
        raw_text = response.text
        response.raise_for_status()
        message_id = _extract_message_id(response)

    return WhatsAppSendResult(
        ok=True,
        detail="Messaggio WhatsApp inviato via Meta Cloud API",
        provider="meta",
        provider_message_id=message_id,
        raw_response=raw_text[:2000] if raw_text else None,
    )


def _send_via_generic_provider(
    *,
    recipient_phone: str,
    body: str,
    subject: Optional[str],
) -> WhatsAppSendResult:
    provider_url = (os.getenv("WHATSAPP_PROVIDER_URL", "") or "").strip()
    if not provider_url:
        return WhatsAppSendResult(
            ok=False,
            detail="Configurazione WhatsApp incompleta: WHATSAPP_PROVIDER_URL mancante",
            provider=_provider_name(),
        )

    token = (os.getenv("WHATSAPP_API_TOKEN", "") or "").strip()
    sender_id = (os.getenv("WHATSAPP_SENDER_ID", "") or "").strip()
    timeout_seconds = float(os.getenv("WHATSAPP_TIMEOUT_SECONDS", "15") or "15")
    payload = {
        "to": _normalize_phone(recipient_phone),
        "body": body,
        "subject": subject,
        "channel": "whatsapp",
        "sender_id": sender_id or None,
    }
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.post(provider_url, json=payload, headers=headers)
        raw_text = response.text
        response.raise_for_status()
        message_id = _extract_message_id(response)

    return WhatsAppSendResult(
        ok=True,
        detail="Messaggio WhatsApp inviato",
        provider=_provider_name(),
        provider_message_id=message_id,
        raw_response=raw_text[:2000] if raw_text else None,
    )


def _normalize_phone(raw_phone: str) -> str:
    value = (raw_phone or "").strip().replace(" ", "")
    if not value:
        return value
    if value.startswith("+"):
        return "+" + "".join(ch for ch in value[1:] if ch.isdigit())
    return "".join(ch for ch in value if ch.isdigit() or ch == "+")


def _extract_message_id(response: httpx.Response) -> Optional[str]:
    try:
        data = response.json()
    except Exception:
        return None

    if isinstance(data, dict):
        candidates = [
            data.get("message_id"),
            data.get("id"),
            ((data.get("data") or {}).get("message_id") if isinstance(data.get("data"), dict) else None),
            ((data.get("data") or {}).get("id") if isinstance(data.get("data"), dict) else None),
        ]
        for candidate in candidates:
            if candidate:
                return str(candidate)

        messages = data.get("messages")
        if isinstance(messages, list) and messages:
            first = messages[0]
            if isinstance(first, dict):
                candidate = first.get("id") or first.get("message_id")
                if candidate:
                    return str(candidate)

    return None
