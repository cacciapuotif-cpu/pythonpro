from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from auth import User, get_current_user
from database import Base, get_db
from main import app
import models
import routers.documenti_richiesti as documenti_router
from services.document_reminders import (
    build_document_upload_url,
    send_document_reminders,
)


class RecordingSender:
    def __init__(self, result=True):
        self.result = result
        self.calls = []

    def send_template_email(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


def _document(document_id, collaborator, *, kind="documento_identita", deadline=None):
    return SimpleNamespace(
        id=document_id,
        collaboratore_id=collaborator.id,
        collaboratore=collaborator,
        tipo_documento=kind,
        data_scadenza=deadline,
        stato="richiesto",
    )


def test_reminder_groups_documents_and_uses_server_side_email(monkeypatch):
    monkeypatch.setenv("DOCUMENT_UPLOAD_URL_BASE", "https://pythonpro.example.it")
    collaborator = SimpleNamespace(
        id=1,
        email="mario@example.it",
        full_name="ROSSI Mario",
    )
    sender = RecordingSender()

    result = send_document_reminders(
        [
            _document(10, collaborator),
            _document(11, collaborator, kind="curriculum", deadline=datetime(2026, 9, 1)),
        ],
        email_sender=sender,
    )

    assert result["sent_count"] == 1
    assert result["failed_count"] == 0
    assert len(sender.calls) == 1
    assert sender.calls[0]["to"] == "mario@example.it"
    assert sender.calls[0]["template_name"] == "sollecito_documento"
    assert sender.calls[0]["context"]["link_upload"] == (
        "https://pythonpro.example.it/collaborators/1/documents"
    )
    assert sender.calls[0]["context"]["documenti"] == [
        {"nome": "documento_identita", "scadenza": "Senza scadenza"},
        {"nome": "curriculum", "scadenza": "01/09/2026"},
    ]


def test_reminder_does_not_call_sender_without_recipient(monkeypatch):
    monkeypatch.setenv("DOCUMENT_UPLOAD_URL_BASE", "https://pythonpro.example.it")
    collaborator = SimpleNamespace(id=2, email="", full_name="BIANCHI Anna")
    sender = RecordingSender()

    result = send_document_reminders([_document(12, collaborator)], email_sender=sender)

    assert result["sent_count"] == 0
    assert result["failed_count"] == 1
    assert sender.calls == []


def test_upload_url_falls_back_to_password_reset_origin(monkeypatch):
    monkeypatch.delenv("DOCUMENT_UPLOAD_URL_BASE", raising=False)
    monkeypatch.setenv(
        "PASSWORD_RESET_URL_BASE",
        "http://192.168.2.41:3001/reset-password",
    )

    assert build_document_upload_url(7) == (
        "http://192.168.2.41:3001/collaborators/7/documents"
    )


def test_upload_url_fails_closed_when_public_url_is_missing(monkeypatch):
    monkeypatch.delenv("DOCUMENT_UPLOAD_URL_BASE", raising=False)
    monkeypatch.delenv("PASSWORD_RESET_URL_BASE", raising=False)

    with pytest.raises(RuntimeError, match="URL pubblico"):
        build_document_upload_url(1)


@pytest.fixture
def api_db(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'document-reminders.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            User.__table__,
            models.Collaborator.__table__,
            models.DocumentoRichiesto.__table__,
            models.SecurityAuditLog.__table__,
        ],
    )
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(
            bind=engine,
            tables=[
                models.SecurityAuditLog.__table__,
                models.DocumentoRichiesto.__table__,
                models.Collaborator.__table__,
                User.__table__,
            ],
        )
        engine.dispose()


def _fake_user(role="admin"):
    return SimpleNamespace(id=99, username=f"test-{role}", role=role, is_active=True)


def _seed_requested_document(db):
    collaborator = models.Collaborator(
        first_name="Francesco",
        last_name="Cacciapuoti",
        email="cacciapuotif@gmail.com",
        fiscal_code="CCCFNC80A01F839A",
    )
    db.add(collaborator)
    db.flush()
    requested = models.DocumentoRichiesto(
        collaboratore_id=collaborator.id,
        tipo_documento="documento_identita",
        stato="richiesto",
    )
    db.add(requested)
    db.commit()
    db.refresh(requested)
    return requested


def test_reminder_endpoint_sends_and_writes_audit(api_db, monkeypatch):
    requested = _seed_requested_document(api_db)

    def override_get_db():
        yield api_db

    send_calls = []

    def fake_send(documents):
        send_calls.append([document.id for document in documents])
        return {
            "sent_count": 1,
            "failed_count": 0,
            "results": [{
                "collaboratore_id": documents[0].collaboratore_id,
                "sent": True,
                "detail": "Sollecito inviato",
            }],
        }

    monkeypatch.setattr(documenti_router, "send_document_reminders", fake_send)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: _fake_user("admin")
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/documenti-richiesti/sollecita",
                json={"documento_ids": [requested.id]},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    assert response.json()["sent_count"] == 1
    assert send_calls == [[requested.id]]
    audit = api_db.query(models.SecurityAuditLog).one()
    assert audit.azione == "documenti_sollecito_email"
    assert audit.esito == "success"


def test_reminder_endpoint_rejects_consultation_role(api_db, monkeypatch):
    requested = _seed_requested_document(api_db)

    def override_get_db():
        yield api_db

    send_mock = RecordingSender()
    monkeypatch.setattr(documenti_router, "send_document_reminders", send_mock)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: _fake_user("consultazione")
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/documenti-richiesti/sollecita",
                json={"documento_ids": [requested.id]},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
