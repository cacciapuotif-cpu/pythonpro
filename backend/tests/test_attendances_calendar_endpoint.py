"""GET /api/v1/attendances/calendar: filtri multi-selezione, only_mine, RBAC."""
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from database import Base, get_db
import auth
from auth import User, UserRole, SecurityUtils, get_current_user
import models  # noqa: F401


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(db_session, monkeypatch):
    monkeypatch.setattr(auth, "RBAC_ENFORCE", True)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    original_startup = list(app.router.on_startup)
    app.router.on_startup.clear()
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.router.on_startup[:] = original_startup
        app.dependency_overrides.clear()


def _user(db, role, collaborator_id=None):
    u = User(
        username=f"u_{role}_{collaborator_id}",
        email=f"u_{role}_{collaborator_id}@example.com",
        hashed_password=SecurityUtils.hash_password("Password123!Test"),
        role=role,
        is_active=True,
        collaborator_id=collaborator_id,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _collaborator(db):
    unique = id(object())
    c = models.Collaborator(
        first_name="Mario", last_name="Rossi", email=f"m{unique}@x.it",
        fiscal_code=f"FSC{unique % 10**13:013d}"[:16],
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _project(db, is_active=True):
    p = models.Project(name="P", status="active" if is_active else "completed", is_active=is_active)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _attendance(db, collaborator_id, project_id, when):
    a = models.Attendance(
        collaborator_id=collaborator_id, project_id=project_id,
        date=when, start_time=when, end_time=when + timedelta(hours=1), hours=1,
    )
    db.add(a)
    db.commit()
    return a


def test_filtro_multi_collaboratore_e_progetto_via_query_string(client, db_session):
    import models
    admin = _user(db_session, UserRole.ADMIN.value)
    c1, c2 = _collaborator(db_session), _collaborator(db_session)
    p1 = _project(db_session)
    now = datetime(2026, 7, 1, 9, 0)
    _attendance(db_session, c1.id, p1.id, now)
    _attendance(db_session, c2.id, p1.id, now)
    app.dependency_overrides[get_current_user] = lambda: admin

    resp = client.get(
        "/api/v1/attendances/calendar",
        params={
            "collaborator_ids": f"{c1.id}",
            "start_date": "2026-06-01T00:00:00",
            "end_date": "2026-08-01T00:00:00",
        },
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["collaborator_id"] == c1.id


def test_only_mine_ignora_collaborator_ids_esplicito(client, db_session):
    c_mio, c_altro = _collaborator(db_session), _collaborator(db_session)
    p1 = _project(db_session)
    now = datetime(2026, 7, 1, 9, 0)
    _attendance(db_session, c_mio.id, p1.id, now)
    _attendance(db_session, c_altro.id, p1.id, now)
    consultazione = _user(db_session, UserRole.CONSULTAZIONE.value, collaborator_id=c_mio.id)
    app.dependency_overrides[get_current_user] = lambda: consultazione

    resp = client.get(
        "/api/v1/attendances/calendar",
        params={
            "collaborator_ids": f"{c_altro.id}",
            "only_mine": "true",
            "start_date": "2026-06-01T00:00:00",
            "end_date": "2026-08-01T00:00:00",
        },
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["collaborator_id"] == c_mio.id


def test_consultazione_non_puo_scrivere_ma_legge(client, db_session):
    consultazione = _user(db_session, UserRole.CONSULTAZIONE.value)
    app.dependency_overrides[get_current_user] = lambda: consultazione

    resp = client.get(
        "/api/v1/attendances/calendar",
        params={"start_date": "2026-06-01T00:00:00", "end_date": "2026-08-01T00:00:00"},
    )
    assert resp.status_code == 200

    resp_post = client.post(
        "/api/v1/attendances/",
        json={
            "collaborator_id": 1, "project_id": 1,
            "date": "2026-07-01T09:00:00", "start_time": "2026-07-01T09:00:00",
            "end_time": "2026-07-01T10:00:00", "hours": 1,
        },
    )
    assert resp_post.status_code == 403
