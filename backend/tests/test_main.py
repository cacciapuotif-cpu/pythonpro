# =================================================================
# FILE: test_main.py
# =================================================================
# SCOPO: smoke test minimi per hardening produzione
# =================================================================

import json
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import models  # noqa: F401  # registra metadata SQLAlchemy
import auth
from auth import LoginAttempt, SecurityUtils, User, UserRole, create_user
from database import get_db
from main import app
import routers.auth as auth_router


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
def client(db_session, monkeypatch):
    # I limiter applicativi non devono condividere Redis o contatori fra test.
    monkeypatch.setattr(auth, "redis_client", None)
    auth._memory_store.clear()
    auth._memory_token_blacklist.clear()

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
        email="admin.smoke@example.com",
        password=ADMIN_PASSWORD,
        full_name="Admin Smoke",
        role=UserRole.ADMIN,
    )


@pytest.fixture
def auth_headers(client, admin_user):
    token = SecurityUtils.generate_token(
        {
            "sub": admin_user.username,
            "type": "access",
            "role": admin_user.role,
            "credential_marker": SecurityUtils.credential_marker(admin_user.hashed_password),
        }
    )
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


def test_authenticated_user_updates_only_own_profile(client, auth_headers, admin_user, db_session):
    response = client.patch(
        "/api/v1/auth/me",
        headers=auth_headers,
        json={
            "full_name": "  Nome   Aggiornato  ",
            "email": "NUOVA@example.com",
            "current_password": ADMIN_PASSWORD,
        },
    )

    assert response.status_code == 200
    assert response.json()["full_name"] == "Nome Aggiornato"
    assert response.json()["email"] == "nuova@example.com"
    assert response.json()["username"] == ADMIN_USERNAME
    db_session.refresh(admin_user)
    assert admin_user.full_name == "Nome Aggiornato"
    audit_entry = db_session.query(models.SecurityAuditLog).filter_by(
        azione="auth_profile_updated",
    ).one()
    assert json.loads(audit_entry.dati_dopo) == {
        "changed_fields": ["full_name", "email"],
    }
    assert "Nome Aggiornato" not in audit_entry.dati_dopo
    assert "nuova@example.com" not in audit_entry.dati_dopo


def test_authenticated_user_completes_name_phone_and_profile(client, auth_headers, admin_user, db_session):
    response = client.patch(
        "/api/v1/auth/me",
        headers=auth_headers,
        json={
            "first_name": "Mario",
            "last_name": "Rossi",
            "phone": "+39 333 123 4567",
            "email": admin_user.email,
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["first_name"] == "Mario"
    assert body["last_name"] == "Rossi"
    assert body["full_name"] == "Mario Rossi"
    assert body["phone"] == "+39 333 123 4567"
    assert body["has_avatar"] is False
    db_session.refresh(admin_user)
    assert admin_user.first_name == "Mario"
    assert admin_user.last_name == "Rossi"
    assert admin_user.phone == "+39 333 123 4567"


def test_authenticated_user_manages_own_avatar(
    client,
    auth_headers,
    admin_user,
    tmp_path,
    monkeypatch,
):
    avatar_dir = tmp_path / "user-avatars"
    monkeypatch.setattr(auth_router, "AVATAR_DIR", avatar_dir)
    png_content = b"\x89PNG\r\n\x1a\n" + b"profile-image"

    uploaded = client.post(
        "/api/v1/auth/me/avatar",
        headers=auth_headers,
        files={"file": ("profilo.png", png_content, "image/png")},
    )
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()["has_avatar"] is True
    assert admin_user.avatar_path
    assert Path(admin_user.avatar_path).parent == avatar_dir

    downloaded = client.get("/api/v1/auth/me/avatar", headers=auth_headers)
    assert downloaded.status_code == 200
    assert downloaded.headers["content-type"].startswith("image/png")
    assert downloaded.content == png_content

    deleted = client.delete("/api/v1/auth/me/avatar", headers=auth_headers)
    assert deleted.status_code == 204
    assert not list(avatar_dir.glob("user-*"))


def test_profile_update_noop_does_not_create_audit_noise(client, auth_headers, admin_user, db_session):
    response = client.patch(
        "/api/v1/auth/me",
        headers=auth_headers,
        json={"full_name": admin_user.full_name, "email": admin_user.email},
    )

    assert response.status_code == 200
    assert db_session.query(models.SecurityAuditLog).filter_by(
        azione="auth_profile_updated",
    ).count() == 0


def test_profile_name_only_update_does_not_require_current_password(
    client,
    auth_headers,
    admin_user,
):
    response = client.patch(
        "/api/v1/auth/me",
        headers=auth_headers,
        json={"full_name": "Solo Nome Nuovo", "email": admin_user.email},
    )

    assert response.status_code == 200
    assert response.json()["full_name"] == "Solo Nome Nuovo"
    assert response.json()["email"] == admin_user.email


def test_stolen_bearer_cannot_change_email_without_current_password(
    client,
    auth_headers,
    admin_user,
    db_session,
):
    original_email = admin_user.email
    response = client.patch(
        "/api/v1/auth/me",
        headers=auth_headers,
        json={
            "full_name": admin_user.full_name,
            "email": "attacker@example.com",
            "current_password": "WrongPassword123!",
        },
    )

    assert response.status_code == 400
    db_session.refresh(admin_user)
    assert admin_user.email == original_email
    assert db_session.query(models.SecurityAuditLog).filter_by(
        azione="auth_profile_updated",
    ).count() == 0
    failure = db_session.query(models.SecurityAuditLog).filter_by(
        azione="auth_profile_update_failed",
    ).one()
    assert failure.esito == "failure"
    assert "WrongPassword123!" not in (failure.dati_dopo or "")


def test_profile_update_rejects_email_owned_by_another_user(client, auth_headers, admin_user, db_session):
    create_user(
        db=db_session,
        username="other_user",
        email="other@example.com",
        password="OtherUser123!",
        full_name="Other User",
        role=UserRole.OPERATORE,
    )

    response = client.patch(
        "/api/v1/auth/me",
        headers=auth_headers,
        json={
            "full_name": admin_user.full_name,
            "email": "OTHER@example.com",
            "current_password": ADMIN_PASSWORD,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Questa email è già associata a un altro account"


def test_profile_update_rejects_email_longer_than_database_column(client, auth_headers, admin_user):
    # Local part e singole label restano RFC-validi; fallisce solo il limite DB di 100.
    email_over_100 = f"{'a' * 64}@{'b' * 30}.examplecomxx"
    response = client.patch(
        "/api/v1/auth/me",
        headers=auth_headers,
        json={
            "full_name": admin_user.full_name,
            "email": email_over_100,
            "current_password": ADMIN_PASSWORD,
        },
    )

    assert response.status_code == 422


def test_password_change_requires_current_password(client, auth_headers, admin_user, db_session):
    response = client.post(
        "/api/v1/auth/change-password",
        headers=auth_headers,
        json={
            "current_password": "WrongPassword123!",
            "new_password": "NewPassword456!",
            "confirm_password": "NewPassword456!",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "La password attuale non è corretta"
    audit_entry = db_session.query(models.SecurityAuditLog).filter_by(
        azione="auth_password_change_failed",
    ).one()
    assert audit_entry.esito == "failure"
    assert json.loads(audit_entry.dati_dopo) == {
        "reason": "current_password_mismatch",
    }
    assert "WrongPassword123!" not in audit_entry.dati_dopo


def test_password_change_handles_current_password_over_bcrypt_limit(client, auth_headers, admin_user):
    response = client.post(
        "/api/v1/auth/change-password",
        headers=auth_headers,
        json={
            "current_password": "è" * 40,
            "new_password": "NewPassword456!",
            "confirm_password": "NewPassword456!",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "La password attuale non è corretta"


def test_password_change_rejects_weak_or_mismatched_password(client, auth_headers, admin_user):
    weak = client.post(
        "/api/v1/auth/change-password",
        headers=auth_headers,
        json={
            "current_password": ADMIN_PASSWORD,
            "new_password": "tuttaminuscola1!",
            "confirm_password": "tuttaminuscola1!",
        },
    )
    mismatch = client.post(
        "/api/v1/auth/change-password",
        headers=auth_headers,
        json={
            "current_password": ADMIN_PASSWORD,
            "new_password": "NewPassword456!",
            "confirm_password": "DifferentPass456!",
        },
    )

    assert weak.status_code == 422
    assert mismatch.status_code == 422


def test_password_change_invalidates_old_access_and_refresh_tokens(client, admin_user, db_session):
    login = client.post(
        "/api/v1/auth/login",
        data={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )
    old_access = login.json()["access_token"]
    old_refresh = login.json()["refresh_token"]
    headers = {"Authorization": f"Bearer {old_access}"}

    changed = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={
            "current_password": ADMIN_PASSWORD,
            "new_password": "NewPassword456!",
            "confirm_password": "NewPassword456!",
        },
    )

    assert changed.status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    assert client.post(
        "/api/v1/auth/refresh",
        data={"refresh_token": old_refresh},
    ).status_code == 401
    assert client.post(
        "/api/v1/auth/login",
        data={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    ).status_code == 401
    assert client.post(
        "/api/v1/auth/login",
        data={"username": ADMIN_USERNAME, "password": "NewPassword456!"},
    ).status_code == 200
    audit_entry = db_session.query(models.SecurityAuditLog).filter_by(
        azione="auth_password_changed",
    ).one()
    assert json.loads(audit_entry.dati_dopo) == {
        "all_previous_tokens_invalidated": True,
    }
    assert ADMIN_PASSWORD not in audit_entry.dati_dopo
    assert "NewPassword456!" not in audit_entry.dati_dopo


def test_access_token_cannot_be_exchanged_at_refresh_endpoint(client, admin_user):
    login = client.post(
        "/api/v1/auth/login",
        data={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )

    response = client.post(
        "/api/v1/auth/refresh",
        data={"refresh_token": login.json()["access_token"]},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Token non è un refresh token"


def test_forgot_password_is_anti_enumeration_and_queues_only_known_account(
    client,
    admin_user,
    db_session,
    monkeypatch,
):
    sent_messages = []
    monkeypatch.setenv(
        "PASSWORD_RESET_URL_BASE",
        "https://gestionale.example.com/reset-password",
    )
    monkeypatch.setattr(
        auth_router,
        "send_password_reset_email",
        lambda **kwargs: sent_messages.append(kwargs),
    )

    known = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "ADMIN.SMOKE@example.com"},
    )
    unknown = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "nobody@example.com"},
    )

    assert known.status_code == 200
    assert unknown.status_code == 200
    assert known.json() == unknown.json()
    assert known.json()["status"] == "accepted"
    assert len(sent_messages) == 1
    assert sent_messages[0]["recipient"] == admin_user.email
    assert sent_messages[0]["reset_url"].startswith(
        "https://gestionale.example.com/reset-password#token=",
    )
    assert "admin.smoke@example.com" not in known.text
    audit_entries = db_session.query(models.SecurityAuditLog).filter_by(
        azione="auth_password_reset_requested",
    ).all()
    assert len(audit_entries) == 2
    assert all("admin.smoke@example.com" not in (entry.dati_dopo or "") for entry in audit_entries)
    assert all("#token=" not in (entry.dati_dopo or "") for entry in audit_entries)


def test_password_reset_link_is_one_use_and_invalidates_existing_sessions(
    client,
    admin_user,
    db_session,
    monkeypatch,
):
    sent_messages = []
    monkeypatch.setenv(
        "PASSWORD_RESET_URL_BASE",
        "https://gestionale.example.com/reset-password",
    )
    monkeypatch.setattr(
        auth_router,
        "send_password_reset_email",
        lambda **kwargs: sent_messages.append(kwargs),
    )
    login = client.post(
        "/api/v1/auth/login",
        data={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )
    old_access = login.json()["access_token"]
    old_refresh = login.json()["refresh_token"]
    client.post(
        "/api/v1/auth/forgot-password",
        json={"email": admin_user.email},
    )
    fragment = urlsplit(sent_messages[0]["reset_url"]).fragment
    reset_token = parse_qs(fragment)["token"][0]
    payload = {
        "token": reset_token,
        "new_password": "RecoveredPassword789!",
        "confirm_password": "RecoveredPassword789!",
    }

    reset = client.post("/api/v1/auth/reset-password", json=payload)
    reused = client.post("/api/v1/auth/reset-password", json=payload)

    assert reset.status_code == 200
    assert reused.status_code == 400
    assert client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {old_access}"},
    ).status_code == 401
    assert client.post(
        "/api/v1/auth/refresh",
        data={"refresh_token": old_refresh},
    ).status_code == 401
    assert client.post(
        "/api/v1/auth/login",
        data={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    ).status_code == 401
    assert client.post(
        "/api/v1/auth/login",
        data={"username": ADMIN_USERNAME, "password": "RecoveredPassword789!"},
    ).status_code == 200
    audit_entry = db_session.query(models.SecurityAuditLog).filter_by(
        azione="auth_password_reset_completed",
    ).one()
    assert json.loads(audit_entry.dati_dopo) == {
        "all_previous_tokens_invalidated": True,
    }
    assert reset_token not in audit_entry.dati_dopo
    assert "RecoveredPassword789!" not in audit_entry.dati_dopo


def test_access_refresh_and_expired_tokens_cannot_reset_password(client, admin_user):
    login = client.post(
        "/api/v1/auth/login",
        data={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )
    expired = SecurityUtils.generate_token(
        {
            "sub": admin_user.username,
            "type": "password_reset",
            "credential_marker": SecurityUtils.credential_marker(admin_user.hashed_password),
        },
        expires_delta=timedelta(seconds=-1),
    )
    password_payload = {
        "new_password": "RecoveredPassword789!",
        "confirm_password": "RecoveredPassword789!",
    }

    for token in (login.json()["access_token"], login.json()["refresh_token"], expired):
        response = client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, **password_payload},
        )
        assert response.status_code == 400


def test_forgot_password_does_not_fail_closed_when_mail_config_is_missing(
    client,
    admin_user,
    monkeypatch,
):
    monkeypatch.delenv("PASSWORD_RESET_URL_BASE", raising=False)
    sent = []
    monkeypatch.setattr(
        auth_router,
        "send_password_reset_email",
        lambda **kwargs: sent.append(kwargs),
    )

    response = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": admin_user.email},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert sent == []


def test_refresh_token_cannot_authenticate_protected_profile_endpoints(client, admin_user):
    login = client.post(
        "/api/v1/auth/login",
        data={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )
    refresh_headers = {"Authorization": f"Bearer {login.json()['refresh_token']}"}

    assert client.get("/api/v1/auth/me", headers=refresh_headers).status_code == 401
    assert client.patch(
        "/api/v1/auth/me",
        headers=refresh_headers,
        json={"full_name": "Refresh Intruder", "email": "intruder@example.com"},
    ).status_code == 401
    assert client.post(
        "/api/v1/auth/change-password",
        headers=refresh_headers,
        json={
            "current_password": ADMIN_PASSWORD,
            "new_password": "NewPassword456!",
            "confirm_password": "NewPassword456!",
        },
    ).status_code == 401


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
