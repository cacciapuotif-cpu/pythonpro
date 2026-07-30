import logging
import smtplib

from auth import SecurityUtils, User
from services.email_sender import EmailSender
from services.password_reset import build_password_reset_url, issue_password_reset_token


def test_placeholder_sender_falls_back_to_authenticated_smtp_user(monkeypatch):
    monkeypatch.setenv("SMTP_USER", "relay@azienda.it")
    monkeypatch.setenv("SMTP_FROM", "no-reply@gestionale.local")

    sender = EmailSender()

    assert sender.smtp_from == "relay@azienda.it"


def test_real_authorized_sender_is_preserved(monkeypatch):
    monkeypatch.setenv("SMTP_USER", "relay@azienda.it")
    monkeypatch.setenv("SMTP_FROM", "noreply@azienda.it")

    sender = EmailSender()

    assert sender.smtp_from == "noreply@azienda.it"


def test_reset_link_keeps_token_out_of_http_query(monkeypatch):
    monkeypatch.setenv(
        "PASSWORD_RESET_URL_BASE",
        "https://gestionale.azienda.it/reset-password",
    )
    user = User(
        username="mario",
        email="mario@azienda.it",
        hashed_password=SecurityUtils.hash_password("CurrentPassword123!"),
        role="operatore",
        is_active=True,
    )

    token = issue_password_reset_token(user)
    reset_url = build_password_reset_url(token)

    assert "?token=" not in reset_url
    assert "#token=" in reset_url
    assert token not in reset_url.split("#", 1)[0]


def test_smtp_recipient_failure_does_not_log_recipient(monkeypatch, caplog):
    recipient = "private-admin@example.net"

    class RefusingSMTP:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def ehlo(self):
            pass

        def starttls(self):
            pass

        def login(self, username, password):
            pass

        def send_message(self, message):
            raise smtplib.SMTPRecipientsRefused({recipient: (550, b"recipient rejected")})

    monkeypatch.setenv("SMTP_HOST", "smtp.example.net")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_TEST_MODE", "false")
    monkeypatch.setattr(smtplib, "SMTP", RefusingSMTP)

    with caplog.at_level(logging.ERROR):
        sent = EmailSender().send_email(
            to=recipient,
            subject="Recupero password",
            body_html="<p>Test</p>",
        )

    assert sent is False
    rendered_logs = "\n".join(record.getMessage() for record in caplog.records)
    assert recipient not in rendered_logs
    assert "recipient rejected" not in rendered_logs
    assert "Errore invio email" in rendered_logs
