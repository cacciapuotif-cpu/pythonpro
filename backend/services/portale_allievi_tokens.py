"""Token firmati e a scadenza per il portale pubblico degli allievi."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass


TOKEN_VERSION = "v1"
TOKEN_TTL_SECONDS = 24 * 60 * 60
_SIGNING_CONTEXT = b"pythonpro:portale-allievi:v1"


class InvalidPortalToken(ValueError):
    """Il token non è autentico, è malformato o è scaduto."""


@dataclass(frozen=True)
class PortalTokenClaims:
    allievo_id: int
    expires_at: int


def issue_portal_token(
    allievo_id: int,
    *,
    now: int | None = None,
    ttl_seconds: int = TOKEN_TTL_SECONDS,
) -> str:
    if allievo_id <= 0:
        raise ValueError("allievo_id non valido")
    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds deve essere positivo")

    issued_at = int(time.time() if now is None else now)
    payload = {
        "sub": allievo_id,
        "exp": issued_at + ttl_seconds,
        "nonce": secrets.token_urlsafe(24),
    }
    encoded_payload = _b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signed_value = f"{TOKEN_VERSION}.{encoded_payload}"
    signature = hmac.new(_signing_key(), signed_value.encode("ascii"), hashlib.sha256).digest()
    return f"{signed_value}.{_b64encode(signature)}"


def verify_portal_token(token: str, *, now: int | None = None) -> PortalTokenClaims:
    try:
        version, encoded_payload, encoded_signature = token.split(".", 2)
        received_signature = _b64decode(encoded_signature)
    except (AttributeError, ValueError):
        raise InvalidPortalToken("token malformato") from None

    signed_value = f"{version}.{encoded_payload}"
    try:
        signed_bytes = signed_value.encode("ascii")
    except UnicodeEncodeError:
        raise InvalidPortalToken("token malformato") from None
    expected_signature = hmac.new(
        _signing_key(), signed_bytes, hashlib.sha256
    ).digest()
    if version != TOKEN_VERSION or not hmac.compare_digest(received_signature, expected_signature):
        raise InvalidPortalToken("firma non valida")

    try:
        payload = json.loads(_b64decode(encoded_payload).decode("utf-8"))
        allievo_id = int(payload["sub"])
        expires_at = int(payload["exp"])
        nonce = payload["nonce"]
    except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        raise InvalidPortalToken("payload non valido") from None

    current_time = int(time.time() if now is None else now)
    if allievo_id <= 0 or not isinstance(nonce, str) or len(nonce) < 24:
        raise InvalidPortalToken("payload non valido")
    if expires_at <= current_time:
        raise InvalidPortalToken("token scaduto")

    return PortalTokenClaims(allievo_id=allievo_id, expires_at=expires_at)


def _signing_key() -> bytes:
    secret = (
        os.getenv("PORTALE_ALLIEVI_TOKEN_SECRET")
        or os.getenv("SECRET_KEY")
        or os.getenv("JWT_SECRET_KEY")
        or ""
    ).strip()
    if len(secret) < 32:
        raise RuntimeError("Secret portale allievi non configurato o troppo corto")
    return hmac.new(secret.encode("utf-8"), _SIGNING_CONTEXT, hashlib.sha256).digest()


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    try:
        return base64.b64decode(value + padding, altchars=b"-_", validate=True)
    except (ValueError, UnicodeEncodeError):
        raise InvalidPortalToken("base64 non valido") from None
