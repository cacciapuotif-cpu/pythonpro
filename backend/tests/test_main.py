# =================================================================
# FILE: test_main.py
# =================================================================
# SCOPO: smoke test minimi per hardening produzione
# =================================================================

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import models  # noqa: F401  # registra metadata SQLAlchemy
from auth import LoginAttempt, User, UserRole, create_user
from database import get_db
from main import app


ADMIN_USERNAME = "admin_smoke"
ADMIN_PASSWORD = "AdminSmoke123!"

SMOKE_TABLES = [
    models.Collaborator.__table__,
    models.ImplementingEntity.__table__,
    models.Project.__table__,
    models.Assignment.__table__,
    models.Attendance.__table__,
    models.SecurityAuditLog.__table__,
    User.__table__,
    LoginAttempt.__table__,
]


@pytest.fixture(scope="function")
def db_session(tmp_path):
    db_path = tmp_path / "pythonpro_smoke.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    for table in SMOKE_TABLES:
        table.create(bind=engine, checkfirst=True)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        for table in reversed(SMOKE_TABLES):
            table.drop(bind=engine, checkfirst=True)
        engine.dispose()


@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    original_startup = list(app.router.on_startup)
    app.router.on_startup.clear()

    with TestClient(app) as test_client:
        yield test_client

    app.router.on_startup[:] = original_startup
    app.dependency_overrides.clear()


@pytest.fixture
def admin_user(db_session):
    return create_user(
        db=db_session,
        username=ADMIN_USERNAME,
        email="admin.smoke@example.test",
        password=ADMIN_PASSWORD,
        full_name="Admin Smoke",
        role=UserRole.ADMIN,
    )


@pytest.fixture
def auth_headers(client, admin_user):
    response = client.post(
        "/api/v1/auth/login",
        data={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_health_check_public(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_login_success_returns_access_and_refresh_tokens(client, admin_user):
    response = client.post(
        "/api/v1/auth/login",
        data={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]
    assert data["refresh_token"]
    assert data["role"] == UserRole.ADMIN.value


def test_login_failure_returns_401(client, admin_user):
    response = client.post(
        "/api/v1/auth/login",
        data={"username": ADMIN_USERNAME, "password": "wrong-password"},
    )

    assert response.status_code == 401


def test_protected_endpoint_without_token_is_rejected(client):
    response = client.get("/api/v1/reporting/summary")

    assert response.status_code in {401, 403}


def test_reporting_summary_authenticated(client, auth_headers):
    response = client.get("/api/v1/reporting/summary", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert "kpi_generali" in data
    assert data["kpi_generali"]["totale_collaboratori"] == 0
    assert data["kpi_generali"]["totale_progetti"] == 0
    assert data["kpi_generali"]["totale_ore_lavorate"] == 0


def test_agents_list_authenticated(client, auth_headers):
    response = client.get("/api/v1/agents/", headers=auth_headers)

    assert response.status_code == 200
    assert isinstance(response.json(), list)
