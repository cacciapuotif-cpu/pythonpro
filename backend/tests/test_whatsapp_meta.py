from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from auth import User
from database import Base, get_db
import models
from routers import whatsapp


class TestMetaWhatsAppSender:

    def test_meta_sender_uses_graph_api_messages_endpoint(self, monkeypatch):
        from services.whatsapp_sender import send_whatsapp_message

        monkeypatch.setenv("ENABLE_WHATSAPP", "true")
        monkeypatch.setenv("WHATSAPP_PROVIDER", "meta")
        monkeypatch.setenv("WHATSAPP_API_TOKEN", "token-123")
        monkeypatch.setenv("WHATSAPP_META_PHONE_NUMBER_ID", "106540352242922")
        monkeypatch.setenv("WHATSAPP_META_GRAPH_VERSION", "v17.0")
        monkeypatch.setenv("WHATSAPP_META_BASE_URL", "https://graph.facebook.com")

        response = MagicMock()
        response.text = '{"messages":[{"id":"wamid.HBgLM"}]}'
        response.json.return_value = {"messages": [{"id": "wamid.HBgLM"}]}
        response.raise_for_status.return_value = None

        with patch("services.whatsapp_sender.httpx.Client") as mocked_client:
            mocked_client.return_value.__enter__.return_value.post.return_value = response

            result = send_whatsapp_message(
                recipient_phone="+39 333 1112233",
                subject="Richiesta documento",
                body="Invia il documento aggiornato.",
            )

        assert result.ok is True
        assert result.provider == "meta"
        assert result.provider_message_id == "wamid.HBgLM"

        post_call = mocked_client.return_value.__enter__.return_value.post.call_args
        assert post_call.args[0] == "https://graph.facebook.com/v17.0/106540352242922/messages"
        assert post_call.kwargs["headers"]["Authorization"] == "Bearer token-123"
        assert post_call.kwargs["json"]["messaging_product"] == "whatsapp"
        assert post_call.kwargs["json"]["recipient_type"] == "individual"
        assert post_call.kwargs["json"]["to"] == "+393331112233"
        assert post_call.kwargs["json"]["type"] == "text"
        assert "Richiesta documento" in post_call.kwargs["json"]["text"]["body"]


@pytest.fixture(scope="function")
def whatsapp_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(
        bind=engine,
        tables=[
            models.Collaborator.__table__,
            User.__table__,
            models.AgentRun.__table__,
            models.AgentSuggestion.__table__,
            models.AgentCommunicationDraft.__table__,
            models.AgentReviewAction.__table__,
            models.AuditLog.__table__,
        ],
    )

    app = FastAPI()
    app.include_router(whatsapp.router)

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client, TestingSessionLocal

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


class TestMetaWebhookRouter:

    def test_webhook_verification_returns_challenge(self, whatsapp_client, monkeypatch):
        client, _ = whatsapp_client
        monkeypatch.setenv("WHATSAPP_META_WEBHOOK_VERIFY_TOKEN", "verify-me")

        response = client.get(
            "/api/v1/whatsapp/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "verify-me",
                "hub.challenge": "12345",
            },
        )

        assert response.status_code == 200
        assert response.text == "12345"

    def test_webhook_status_updates_matching_draft(self, whatsapp_client):
        client, SessionLocal = whatsapp_client

        db: Session = SessionLocal()
        collaborator = models.Collaborator(
            first_name="Mario",
            last_name="Rossi",
            email="mario@example.com",
            phone="+393331112233",
            fiscal_code="RSSMRA80A01H501Z",
        )
        db.add(collaborator)
        db.flush()

        run = models.AgentRun(agent_type="mail_recovery", status="completed")
        db.add(run)
        db.flush()

        suggestion = models.AgentSuggestion(
            run_id=run.id,
            entity_type="collaborator",
            entity_id=collaborator.id,
            suggestion_type="missing_curriculum",
            severity="medium",
            status="sent",
            title="Richiedi curriculum",
            description="Serve curriculum",
        )
        db.add(suggestion)
        db.flush()

        draft = models.AgentCommunicationDraft(
            run_id=run.id,
            suggestion_id=suggestion.id,
            agent_name="mail_recovery",
            channel="whatsapp",
            recipient_type="collaborator",
            recipient_id=collaborator.id,
            recipient_email=collaborator.phone,
            recipient_name=collaborator.full_name,
            subject="Richiesta curriculum",
            body="Ciao Mario",
            status="sent",
            meta_payload=json.dumps({"provider_message_id": "wamid.HBgLM"}),
        )
        db.add(draft)
        db.commit()
        draft_id = draft.id
        db.close()

        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "metadata": {
                                    "display_phone_number": "15551234567",
                                    "phone_number_id": "106540352242922",
                                },
                                "statuses": [
                                    {
                                        "id": "wamid.HBgLM",
                                        "status": "delivered",
                                        "timestamp": "1712000000",
                                        "recipient_id": "393331112233",
                                        "conversation": {
                                            "id": "conv-1",
                                            "origin": {"type": "utility"},
                                        },
                                    }
                                ],
                            },
                        }
                    ]
                }
            ],
        }

        response = client.post("/api/v1/whatsapp/webhook", json=payload)

        assert response.status_code == 200
        assert response.json()["processed_statuses"] == 1
        assert response.json()["matched_statuses"] == 1

        db = SessionLocal()
        refreshed_draft = db.query(models.AgentCommunicationDraft).filter_by(id=draft_id).first()
        assert refreshed_draft.status == "delivered"
        meta = json.loads(refreshed_draft.meta_payload)
        assert meta["provider_message_id"] == "wamid.HBgLM"
        assert meta["delivery_status"] == "delivered"
        assert meta["conversation_id"] == "conv-1"
        assert meta["conversation_origin_type"] == "utility"
        assert meta["meta_phone_number_id"] == "106540352242922"
        db.close()
