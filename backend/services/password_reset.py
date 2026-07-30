"""Recupero password con token JWT breve, monouso e legato alle credenziali."""

from datetime import timedelta
import hmac
import logging
import os
from urllib.parse import quote

from fastapi import HTTPException
from sqlalchemy.orm import Session

from auth import SecurityUtils, User, is_token_revoked
from services.email_sender import EmailSender

logger = logging.getLogger(__name__)

PASSWORD_RESET_EXPIRE_MINUTES = 30


class PasswordResetTokenError(ValueError):
    """Il token di recupero non è utilizzabile."""


def issue_password_reset_token(user: User) -> str:
    return SecurityUtils.generate_token(
        data={
            "sub": user.username,
            "type": "password_reset",
            "credential_marker": SecurityUtils.credential_marker(user.hashed_password),
        },
        expires_delta=timedelta(minutes=PASSWORD_RESET_EXPIRE_MINUTES),
    )


def build_password_reset_url(token: str) -> str:
    """Costruisce un link con token nel fragment, escluso quindi dai log HTTP."""
    base_url = os.getenv("PASSWORD_RESET_URL_BASE", "").strip().rstrip("#")
    if not base_url or not base_url.startswith(("http://", "https://")):
        raise RuntimeError("PASSWORD_RESET_URL_BASE non configurato correttamente")
    return f"{base_url}#token={quote(token, safe='')}"


def send_password_reset_email(
    *,
    recipient: str,
    full_name: str,
    reset_url: str,
) -> None:
    sent = EmailSender().send_template_email(
        to=recipient,
        template_name="password_reset",
        context={
            "subject": "Reimposta la password di PythonPro",
            "full_name": full_name,
            "reset_url": reset_url,
            "expires_minutes": PASSWORD_RESET_EXPIRE_MINUTES,
        },
    )
    if not sent:
        logger.error("Invio email recupero password fallito")


def validate_password_reset_token(token: str, db: Session) -> tuple[dict, User]:
    try:
        payload = SecurityUtils.verify_token(token)
    except HTTPException as exc:
        raise PasswordResetTokenError("Token non valido o scaduto") from exc

    if payload.get("type") != "password_reset" or is_token_revoked(payload.get("jti")):
        raise PasswordResetTokenError("Token non valido o scaduto")

    username = payload.get("sub")
    user = db.query(User).filter(User.username == username).first() if username else None
    if not user or not user.is_active:
        raise PasswordResetTokenError("Token non valido o scaduto")

    if not hmac.compare_digest(
        str(payload.get("credential_marker") or ""),
        SecurityUtils.credential_marker(user.hashed_password),
    ):
        raise PasswordResetTokenError("Token non valido o già utilizzato")

    return payload, user


def replace_password_atomically(
    *,
    db: Session,
    user: User,
    new_password: str,
) -> bool:
    """Evita che due richieste concorrenti consumino lo stesso token."""
    previous_hash = user.hashed_password
    new_hash = SecurityUtils.hash_password(new_password)
    updated = (
        db.query(User)
        .filter(User.id == user.id, User.hashed_password == previous_hash)
        .update({User.hashed_password: new_hash}, synchronize_session=False)
    )
    return updated == 1


__all__ = [
    "PASSWORD_RESET_EXPIRE_MINUTES",
    "PasswordResetTokenError",
    "build_password_reset_url",
    "issue_password_reset_token",
    "replace_password_atomically",
    "send_password_reset_email",
    "validate_password_reset_token",
]
