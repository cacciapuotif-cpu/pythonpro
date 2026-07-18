"""Smoke HTTP reale per router attivita e dependency override FastAPI."""

from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import auth
import models
from database import get_db
from main import app as main_app
from routers import attivita as attivita_router


@pytest.fixture()
def http_context(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'attivita-http.db'}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _foreign_keys(dbapi_connection, _):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    for table in (
        models.Collaborator.__table__,
        models.ImplementingEntity.__table__,
        models.Avviso.__table__,
        models.AvvisoRevisione.__table__,
        models.AvvisoScadenza.__table__,
        auth.User.__table__,
        models.Project.__table__,
        models.AgentRun.__table__,
        models.AgentSuggestion.__table__,
        models.Playbook.__table__,
        models.PlaybookVersione.__table__,
        models.PlaybookVoce.__table__,
        models.AttivitaOperativa.__table__,
        models.AttivitaEvento.__table__,
    ):
        table.create(bind=engine, checkfirst=True)

    session = sessionmaker(
        bind=engine, autocommit=False, autoflush=False, expire_on_commit=False
    )()
    actor = auth.User(
        username="attivita-http",
        email="attivita-http@example.test",
        hashed_password="not-used",
        role="admin",
        is_active=True,
    )
    project = models.Project(name="Progetto HTTP")
    session.add_all([actor, project])
    session.flush()
    activity = models.AttivitaOperativa(
        project_id=project.id,
        fase="avvio",
        titolo="Attivita HTTP",
        created_by_user_id=actor.id,
    )
    session.add(activity)
    session.commit()

    current_user = SimpleNamespace(
        id=actor.id,
        username=actor.username,
        role="consultazione",
    )
    monkeypatch.setattr(auth, "RBAC_ENFORCE", True)
    original_startup = list(main_app.router.on_startup)
    original_overrides = dict(main_app.dependency_overrides)
    main_app.router.on_startup.clear()
    main_app.dependency_overrides[get_db] = lambda: session
    main_app.dependency_overrides[attivita_router.get_current_user] = lambda: current_user

    with TestClient(main_app) as client:
        yield SimpleNamespace(
            client=client,
            session=session,
            user=current_user,
            project=project,
            activity=activity,
        )

    main_app.router.on_startup[:] = original_startup
    main_app.dependency_overrides.clear()
    main_app.dependency_overrides.update(original_overrides)
    session.close()
    engine.dispose()


def test_consultazione_reads_checklist_but_cannot_change_state(http_context):
    response = http_context.client.get(
        f"/api/v1/attivita/projects/{http_context.project.id}"
    )
    assert response.status_code == 200, response.text
    assert [item["id"] for item in response.json()] == [http_context.activity.id]

    response = http_context.client.post(
        f"/api/v1/attivita/{http_context.activity.id}/stato",
        json={"nuovo_stato": "in_corso"},
    )
    assert response.status_code == 403, response.text


def test_operatore_reaches_state_route_and_playbook_stays_admin_only(http_context):
    http_context.user.role = "operatore"
    response = http_context.client.post(
        f"/api/v1/attivita/{http_context.activity.id}/stato",
        json={"nuovo_stato": "in_corso"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["stato"] == "in_corso"

    response = http_context.client.patch(
        f"/api/v1/attivita/{http_context.activity.id}",
        json={
            "scadenza": "2026-09-30",
            "assegnatario_user_id": http_context.user.id,
            "note": "Aggiornata via HTTP",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["scadenza"] == "2026-09-30"
    assert response.json()["assegnatario_user_id"] == http_context.user.id

    response = http_context.client.post(
        "/api/v1/attivita/playbooks",
        json={"nome": "Playbook vietato", "fondo": "fapi"},
    )
    assert response.status_code == 403, response.text


def test_admin_reaches_playbook_route(http_context):
    http_context.user.role = "admin"
    response = http_context.client.post(
        "/api/v1/attivita/playbooks",
        json={"nome": "Playbook HTTP", "fondo": "fapi"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["nome"] == "Playbook HTTP"
    assert response.json()["versione_corrente_id"] is not None

    playbook_id = response.json()["id"]
    response = http_context.client.get(
        f"/api/v1/attivita/playbooks/{playbook_id}/voci",
        params={"stato": "proposta"},
    )
    assert response.status_code == 200, response.text
    assert response.json() == []

    response = http_context.client.get(
        f"/api/v1/attivita/playbooks/{playbook_id}/voci",
        params={"stato": "inventato"},
    )
    assert response.status_code == 422, response.text
