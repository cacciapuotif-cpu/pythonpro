"""Creazione utenti con assegnazione ruolo da parte dell'amministratore.

Pattern DB/client ripreso da test_rbac_download_endpoints.py: sqlite
in-memory, dependency_overrides su get_db/get_current_user, RBAC_ENFORCE
esplicito via monkeypatch (indipendente dall'env del container).
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from database import Base, get_db
import auth
from auth import User, UserRole, SecurityUtils, get_current_user
import models  # noqa: F401 - registra i modelli sul Base
import routers.admin as admin_router


@pytest.fixture(scope="function")
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


@pytest.fixture(scope="function")
def admin_user(db_session):
    user = User(
        username="admin_test",
        email="admin_test@example.com",
        hashed_password=SecurityUtils.hash_password("AdminPassword123!"),
        role=UserRole.ADMIN.value,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def operatore_user(db_session):
    user = User(
        username="operatore_test",
        email="operatore_test@example.com",
        hashed_password=SecurityUtils.hash_password("OperatorePassword123!"),
        role=UserRole.OPERATORE.value,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def sent_emails(monkeypatch):
    """Cattura le email di invito senza toccare SMTP reale."""
    calls = []

    def fake_send(*, recipient, full_name, reset_url):
        calls.append({"recipient": recipient, "full_name": full_name, "reset_url": reset_url})

    monkeypatch.setattr(admin_router, "send_password_reset_email", fake_send)
    return calls


@pytest.fixture(scope="function")
def client(db_session, monkeypatch):
    monkeypatch.setattr(auth, "RBAC_ENFORCE", True)
    monkeypatch.setenv("PASSWORD_RESET_URL_BASE", "https://gestionale.azienda.it/reset-password")

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


def _create_payload(**overrides):
    payload = {
        "username": "nuovo_operatore",
        "email": "nuovo.operatore@azienda.it",
        "full_name": "Nuovo Operatore",
        "role": "operatore",
    }
    payload.update(overrides)
    return payload


def test_admin_crea_utente_con_ruolo(client, admin_user, db_session, sent_emails):
    app.dependency_overrides[get_current_user] = lambda: admin_user

    resp = client.post("/api/v1/admin/users", json=_create_payload())

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["username"] == "nuovo_operatore"
    assert body["role"] == "operatore"
    assert "password" not in body
    assert "hashed_password" not in body

    created = db_session.query(User).filter(User.username == "nuovo_operatore").first()
    assert created is not None
    assert created.role == "operatore"
    assert created.is_active is True

    assert len(sent_emails) == 1
    assert sent_emails[0]["recipient"] == "nuovo.operatore@azienda.it"


def test_admin_crea_utente_senza_username_e_il_sistema_lo_genera(
    client,
    admin_user,
    db_session,
    sent_emails,
):
    app.dependency_overrides[get_current_user] = lambda: admin_user

    resp = client.post(
        "/api/v1/admin/users",
        json={
            "first_name": "Giulia",
            "last_name": "Verdi",
            "email": "giulia.verdi@azienda.it",
            "role": "consultazione",
        },
    )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["username"] == "giulia.verdi"
    assert body["first_name"] == "Giulia"
    assert body["last_name"] == "Verdi"
    assert body["full_name"] == "Giulia Verdi"
    created = db_session.query(User).filter(User.email == "giulia.verdi@azienda.it").one()
    assert created.username == "giulia.verdi"


def test_utente_creato_non_puo_accedere_prima_del_reset(client, admin_user, db_session, sent_emails):
    app.dependency_overrides[get_current_user] = lambda: admin_user
    client.post("/api/v1/admin/users", json=_create_payload())

    login_resp = client.post(
        "/api/v1/auth/login",
        data={"username": "nuovo_operatore", "password": "qualsiasi-cosa"},
    )
    assert login_resp.status_code == 401


@pytest.mark.parametrize("role", ["operatore", "consultazione"])
def test_non_admin_non_puo_creare_utenti(client, operatore_user, role, db_session):
    non_admin = operatore_user
    non_admin.role = role
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: non_admin

    resp = client.post("/api/v1/admin/users", json=_create_payload())

    assert resp.status_code == 403


def test_ruolo_non_valido_rifiutato(client, admin_user):
    app.dependency_overrides[get_current_user] = lambda: admin_user

    resp = client.post("/api/v1/admin/users", json=_create_payload(role="superadmin"))

    assert resp.status_code == 422


def test_username_duplicato_rifiutato(client, admin_user, operatore_user):
    app.dependency_overrides[get_current_user] = lambda: admin_user

    resp = client.post(
        "/api/v1/admin/users",
        json=_create_payload(username="operatore_test", email="altro@azienda.it"),
    )

    assert resp.status_code == 409


def test_email_duplicata_rifiutata_case_insensitive(client, admin_user, operatore_user):
    app.dependency_overrides[get_current_user] = lambda: admin_user

    resp = client.post(
        "/api/v1/admin/users",
        json=_create_payload(username="altro_utente", email="OPERATORE_TEST@example.com"),
    )

    assert resp.status_code == 409


def test_admin_lista_utenti(client, admin_user, operatore_user):
    app.dependency_overrides[get_current_user] = lambda: admin_user

    resp = client.get("/api/v1/admin/users")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    usernames = {item["username"] for item in body["users"]}
    assert {"admin_test", "operatore_test"} <= usernames
    for item in body["users"]:
        assert "hashed_password" not in item
        assert "password" not in item


def test_non_admin_non_puo_listare_utenti(client, operatore_user):
    app.dependency_overrides[get_current_user] = lambda: operatore_user

    resp = client.get("/api/v1/admin/users")

    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /api/v1/admin/users/{id}/resend-invite
# ---------------------------------------------------------------------------

def test_admin_reinvia_credenziali(client, admin_user, operatore_user, sent_emails):
    app.dependency_overrides[get_current_user] = lambda: admin_user

    resp = client.post(f"/api/v1/admin/users/{operatore_user.id}/resend-invite")

    assert resp.status_code == 200, resp.text
    assert resp.json() == {"status": "invite_queued", "email": operatore_user.email}
    assert len(sent_emails) == 1
    assert sent_emails[0]["recipient"] == operatore_user.email


def test_non_admin_non_puo_reinviare_credenziali(client, operatore_user, db_session):
    from auth import User as _User
    altro = _User(
        username="altro_operatore",
        email="altro_operatore@example.com",
        hashed_password=SecurityUtils.hash_password("Password123!Test"),
        role=UserRole.OPERATORE.value,
        is_active=True,
    )
    db_session.add(altro)
    db_session.commit()
    db_session.refresh(altro)
    app.dependency_overrides[get_current_user] = lambda: operatore_user

    resp = client.post(f"/api/v1/admin/users/{altro.id}/resend-invite")

    assert resp.status_code == 403


def test_reinvio_credenziali_utente_inesistente_404(client, admin_user):
    app.dependency_overrides[get_current_user] = lambda: admin_user

    resp = client.post("/api/v1/admin/users/999999/resend-invite")

    assert resp.status_code == 404


def test_reinvio_credenziali_utente_disattivato_rifiutato(client, admin_user, operatore_user, db_session):
    operatore_user.is_active = False
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: admin_user

    resp = client.post(f"/api/v1/admin/users/{operatore_user.id}/resend-invite")

    assert resp.status_code == 409
