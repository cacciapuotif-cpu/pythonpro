"""AGENT-08: polling IMAP resiliente con stato condiviso e backoff.

- errori di login classificati (auth_failed vs error) nello store condiviso
- backoff esponenziale: base 5m, x2 per tentativo, cap 6h
- polling salta finche' now < next_retry_at; login riuscito resetta
- /email-inbox/status legge lo store; /email-inbox/imap/test (admin) prova
  il login senza mai esporre le credenziali
"""
from __future__ import annotations

import imaplib
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from auth import User, UserRole, get_admin_user, get_current_user
from services import inbox_status_store

IMAP_PASSWORD = "super-secret-app-password"


@pytest.fixture(autouse=True)
def clean_store():
    inbox_status_store.reset_for_tests()
    yield
    inbox_status_store.reset_for_tests()


def make_worker(tmp_path):
    from services.email_inbox_worker import EmailInboxWorker

    return EmailInboxWorker(
        imap_user="inbox@example.com",
        imap_password=IMAP_PASSWORD,
        upload_base_dir=tmp_path,
    )


def _auth_failing_imap_factory(calls):
    def factory(host, port):
        calls.append((host, port))
        imap = MagicMock()
        imap.login.side_effect = imaplib.IMAP4.error(
            b"[AUTHENTICATIONFAILED] Invalid credentials (Failure)"
        )
        return imap

    return factory


def _ok_imap_factory(calls):
    def factory(host, port):
        calls.append((host, port))
        imap = MagicMock()
        imap.login.return_value = ("OK", [b"Logged in"])
        imap.select.return_value = ("OK", [b"0"])
        imap.search.return_value = ("OK", [b""])
        return imap

    return factory


# --- Store: backoff -----------------------------------------------------


def test_backoff_grows_exponentially_and_caps():
    assert inbox_status_store.backoff_delay_seconds(1) == 300
    assert inbox_status_store.backoff_delay_seconds(2) == 600
    assert inbox_status_store.backoff_delay_seconds(3) == 1200
    assert inbox_status_store.backoff_delay_seconds(7) == 19200
    assert inbox_status_store.backoff_delay_seconds(8) == 21600
    assert inbox_status_store.backoff_delay_seconds(20) == 21600


def test_record_failure_increments_attempts_and_sets_retry():
    first = inbox_status_store.record_failure("boom", kind="error")
    second = inbox_status_store.record_failure("boom", kind="error")
    assert first["failed_attempts"] == 1
    assert second["failed_attempts"] == 2
    assert second["next_retry_at"] > first["next_retry_at"]
    skip, until = inbox_status_store.should_skip()
    assert skip is True
    assert until == second["next_retry_at"]


# --- Worker: classificazione, skip, reset -------------------------------


def test_auth_failure_classified_and_backoff_set(monkeypatch, tmp_path):
    import services.email_inbox_worker as worker_module

    calls = []
    monkeypatch.setattr(
        worker_module.imaplib, "IMAP4_SSL", _auth_failing_imap_factory(calls)
    )

    worker = make_worker(tmp_path)
    worker._run_poll_cycle(MagicMock())

    status = inbox_status_store.get_status()
    assert status["state"] == "auth_failed"
    assert status["failed_attempts"] == 1
    assert status["next_retry_at"] is not None
    assert len(calls) == 1


def test_poll_skipped_while_backoff_active(monkeypatch, tmp_path):
    import services.email_inbox_worker as worker_module

    calls = []
    monkeypatch.setattr(
        worker_module.imaplib, "IMAP4_SSL", _auth_failing_imap_factory(calls)
    )

    worker = make_worker(tmp_path)
    worker._run_poll_cycle(MagicMock())
    worker._run_poll_cycle(MagicMock())

    assert len(calls) == 1, "secondo ciclo doveva saltare per backoff attivo"
    status = inbox_status_store.get_status()
    assert status["failed_attempts"] == 1


def test_success_resets_backoff(monkeypatch, tmp_path):
    import services.email_inbox_worker as worker_module

    inbox_status_store.record_failure("vecchio errore", kind="auth_failed")
    # backoff scaduto: retry consentito
    status = inbox_status_store.get_status()
    status["next_retry_at"] = "2020-01-01T00:00:00+00:00"
    inbox_status_store._save(status)

    calls = []
    monkeypatch.setattr(worker_module.imaplib, "IMAP4_SSL", _ok_imap_factory(calls))

    worker = make_worker(tmp_path)
    worker._run_poll_cycle(MagicMock())

    status = inbox_status_store.get_status()
    assert status["state"] == "connected"
    assert status["failed_attempts"] == 0
    assert status["next_retry_at"] is None
    assert status["last_success_at"] is not None


def test_missing_credentials_marks_disabled(monkeypatch, tmp_path):
    from services.email_inbox_worker import EmailInboxWorker

    monkeypatch.delenv("GMAIL_IMAP_USER", raising=False)
    monkeypatch.delenv("GMAIL_IMAP_APP_PASSWORD", raising=False)
    worker = EmailInboxWorker(upload_base_dir=tmp_path)
    worker._run_poll_cycle(MagicMock())

    status = inbox_status_store.get_status()
    assert status["state"] == "disabled"


def test_generic_connection_error_classified_as_error(monkeypatch, tmp_path):
    import services.email_inbox_worker as worker_module

    def factory(host, port):
        raise OSError("connection refused")

    monkeypatch.setattr(worker_module.imaplib, "IMAP4_SSL", factory)

    worker = make_worker(tmp_path)
    worker._run_poll_cycle(MagicMock())

    status = inbox_status_store.get_status()
    assert status["state"] == "error"
    assert "connection refused" in (status["last_error"] or "")


# --- Endpoint /status e /imap/test ---------------------------------------


def _make_user(role: str) -> User:
    user = User(username=f"test-{role}", email=f"{role}@example.com", role=role)
    user.id = 1
    return user


@pytest.fixture()
def api_client():
    from main import app

    admin = _make_user(UserRole.ADMIN.value)
    app.dependency_overrides[get_current_user] = lambda: admin
    app.dependency_overrides[get_admin_user] = lambda: admin
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_status_endpoint_reads_shared_store(api_client):
    inbox_status_store.record_failure("AUTHENTICATIONFAILED", kind="auth_failed")

    response = api_client.get("/api/v1/email-inbox/status")

    assert response.status_code == 200
    data = response.json()
    assert data["state"] == "auth_failed"
    assert data["failed_attempts"] == 1
    assert data["message"] == "Inbox: disconnessa — credenziali non valide"


def test_imap_test_endpoint_does_not_expose_password(monkeypatch, api_client):
    import services.email_inbox_worker as worker_module

    monkeypatch.setenv("GMAIL_IMAP_USER", "inbox@example.com")
    monkeypatch.setenv("GMAIL_IMAP_APP_PASSWORD", IMAP_PASSWORD)

    calls = []
    monkeypatch.setattr(
        worker_module.imaplib, "IMAP4_SSL", _auth_failing_imap_factory(calls)
    )

    response = api_client.post("/api/v1/email-inbox/imap/test")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["state"] == "auth_failed"
    assert IMAP_PASSWORD not in response.text


def test_imap_test_endpoint_success_resets_state(monkeypatch, api_client):
    import services.email_inbox_worker as worker_module

    monkeypatch.setenv("GMAIL_IMAP_USER", "inbox@example.com")
    monkeypatch.setenv("GMAIL_IMAP_APP_PASSWORD", IMAP_PASSWORD)
    inbox_status_store.record_failure("vecchio errore", kind="auth_failed")

    calls = []
    monkeypatch.setattr(worker_module.imaplib, "IMAP4_SSL", _ok_imap_factory(calls))

    response = api_client.post("/api/v1/email-inbox/imap/test")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["state"] == "connected"
    status = inbox_status_store.get_status()
    assert status["failed_attempts"] == 0
