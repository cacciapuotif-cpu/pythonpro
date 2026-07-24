"""A5b: endpoint /agents/system-health — stato operativo piattaforma agenti.

A5c: l'esito dell'ultimo run (incluso error_message) e' esposto per agente.
"""
from __future__ import annotations

from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app
from database import Base, get_db
from auth import User, UserRole, get_current_user
import models  # noqa: F401


@pytest.fixture(scope="function")
def db_session(tmp_path):
    db_path = tmp_path / "test_system_health.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        yield db_session

    user = User(username="admin-test", email="admin@example.com", role=UserRole.ADMIN.value)
    user.id = 1
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_system_health_shape(client):
    response = client.get("/api/v1/agents/system-health")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["agents_enabled"], bool)
    names = {item["name"] for item in data["agents"]}
    assert names == {
        "data_quality",
        "mail_recovery",
        "contract_agent",
        "certification",
        "email_intake",
        "data_retention",
        "avviso_extractor",
        "activity_planner",
        "procedure_extractor",
        "timesheet",
    }
    for item in data["agents"]:
        assert set(item) >= {"name", "enabled", "kill_switch_env", "triggers", "schedule", "last_run"}
    assert "state" in data["inbox"]
    assert "provider" in data["llm"]
    assert "reachable" in data["arq"]


def test_system_health_exposes_last_run_error(client, db_session):
    run = models.AgentRun(
        agent_type="mail_recovery",
        status="failed",
        error_message="Connessione SMTP rifiutata",
    )
    db_session.add(run)
    db_session.commit()

    response = client.get("/api/v1/agents/system-health")

    assert response.status_code == 200
    by_name = {item["name"]: item for item in response.json()["agents"]}
    last_run = by_name["mail_recovery"]["last_run"]
    assert last_run is not None
    assert last_run["status"] == "failed"
    assert last_run["error_message"] == "Connessione SMTP rifiutata"
    assert last_run["run_id"] == run.id


def test_system_health_reflects_kill_switch(client, monkeypatch):
    monkeypatch.setenv("AGENT_CERTIFICATION_ENABLED", "false")

    response = client.get("/api/v1/agents/system-health")

    by_name = {item["name"]: item for item in response.json()["agents"]}
    assert by_name["certification"]["enabled"] is False
    assert by_name["mail_recovery"]["enabled"] is True
