import logging
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Optional

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape

logger = logging.getLogger(__name__)


class _FallbackSettings:
    SMTP_HOST = None
    SMTP_PORT = 587
    SMTP_USER = None
    SMTP_PASSWORD = None
    SMTP_FROM = "no-reply@gestionale.local"
    SMTP_TEST_MODE = True
    SMTP_USE_TLS = True
    SMTP_SERVER = None
    EMAIL_FROM = "no-reply@gestionale.local"


def _load_settings():
    try:
        from app.core.settings import get_settings
        return get_settings()
    except Exception:
        try:
            from backend.app.core.settings import get_settings
            return get_settings()
        except Exception:
            logger.warning("Settings applicative non disponibili, uso fallback da env per EmailSender")
            return _FallbackSettings()


class EmailSender:
    def __init__(self) -> None:
        settings = _load_settings()
        self.smtp_host = os.getenv("SMTP_HOST") or settings.SMTP_HOST or settings.SMTP_SERVER
        self.smtp_port = int(os.getenv("SMTP_PORT") or settings.SMTP_PORT or 587)
        self.smtp_user = os.getenv("SMTP_USER") or settings.SMTP_USER
        self.smtp_password = os.getenv("SMTP_PASSWORD") or settings.SMTP_PASSWORD
        self.smtp_from = (
            os.getenv("SMTP_FROM")
            or getattr(settings, "SMTP_FROM", None)
            or settings.EMAIL_FROM
        )
        self.test_mode = str(
            os.getenv("SMTP_TEST_MODE", str(getattr(settings, "SMTP_TEST_MODE", True)))
        ).strip().lower() in {"1", "true", "yes", "on"}
        self.use_tls = str(
            os.getenv("SMTP_USE_TLS", str(getattr(settings, "SMTP_USE_TLS", True)))
        ).strip().lower() in {"1", "true", "yes", "on"}
        self.templates_dir = Path(__file__).resolve().parent.parent / "templates" / "email"
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def send_email(
        self,
        to: str,
        subject: str,
        body_html: str,
        body_text: Optional[str] = None,
    ) -> bool:
        if not to:
            raise ValueError("Destinatario email mancante")
        if not subject:
            raise ValueError("Oggetto email mancante")
        if not body_html and not body_text:
            raise ValueError("Corpo email mancante")

        message = EmailMessage()
        message["From"] = self.smtp_from
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body_text or self._html_to_text(body_html))
        if body_html:
            message.add_alternative(body_html, subtype="html")

        if self.test_mode:
            logger.info(
                "SMTP test mode attivo: email non inviata realmente",
                extra={"to": to, "subject": subject},
            )
            return True

        if not self.smtp_host:
            logger.error("SMTP_HOST non configurato")
            return False

        try:
            if self.smtp_port == 465:
                with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=20) as server:
                    if self.smtp_user and self.smtp_password:
                        server.login(self.smtp_user, self.smtp_password)
                    server.send_message(message)
            else:
                with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=20) as server:
                    server.ehlo()
                    if self.use_tls:
                        server.starttls()
                        server.ehlo()
                    if self.smtp_user and self.smtp_password:
                        server.login(self.smtp_user, self.smtp_password)
                    server.send_message(message)
            return True
        except Exception as exc:
            logger.exception("Errore invio email verso %s: %s", to, exc)
            return False

    def send_template_email(
        self,
        to: str,
        template_name: str,
        context: dict[str, Any],
    ) -> bool:
        html_template = self._load_template(template_name, "html")
        text_template = self._load_template(template_name, "txt", required=False)
        safe_context = {key: "" if value is None else value for key, value in (context or {}).items()}
        subject = str(safe_context.get("subject") or safe_context.get("titolo") or template_name.replace("_", " ").title())
        body_html = html_template.render(**safe_context)
        body_text = text_template.render(**safe_context) if text_template else None
        return self.send_email(to=to, subject=subject, body_html=body_html, body_text=body_text)

    def _load_template(self, template_name: str, extension: str, required: bool = True):
        filename = f"{template_name}.{extension}"
        try:
            return self.jinja_env.get_template(filename)
        except TemplateNotFound:
            if required:
                raise FileNotFoundError(f"Template email non trovato: {self.templates_dir / filename}")
            return None

    @staticmethod
    def _html_to_text(html: str) -> str:
        if not html:
            return ""
        text = html.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
        for tag in ("<p>", "</p>", "<div>", "</div>", "<strong>", "</strong>", "<em>", "</em>"):
            text = text.replace(tag, "")
        return text.strip()


__all__ = ["EmailSender"]
