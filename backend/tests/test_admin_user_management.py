"""Modifica, disattivazione/riattivazione ed eliminazione utenti da admin.

Guardrail concordate con l'utente (2026-07-29):
- un admin non puo' mai disattivare/degradare/eliminare se stesso;
- l'ultimo admin attivo del sistema non puo' essere disattivato, degradato
  o eliminato da nessuno.
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


def _make_user(db_session, username, role, email=None, is_active=True):
    user = User(
        username=username,
        email=email or f"{username}@example.com",
        hashed_password=SecurityUtils.hash_password("Password123!Test"),
        full_name=username.replace("_", " ").title(),
        role=role,
        is_active=is_active,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def admin_user(db_session):
    return _make_user(db_session, "admin_one", UserRole.ADMIN.value)


@pytest.fixture(scope="function")
def second_admin(db_session):
    return _make_user(db_session, "admin_two", UserRole.ADMIN.value)


@pytest.fixture(scope="function")
def operatore_user(db_session):
    return _make_user(db_session, "operatore_test", UserRole.OPERATORE.value)


@pytest.fixture(scope="function")
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


# ---------------------------------------------------------------------------
# PATCH /api/v1/admin/users/{id}
# ---------------------------------------------------------------------------

def test_admin_modifica_dati_altro_utente(client, admin_user, operatore_user, db_session):
    app.dependency_overrides[get_current_user] = lambda: admin_user

    resp = client.patch(
        f"/api/v1/admin/users/{operatore_user.id}",
        json={"full_name": "Nuovo Nome", "email": "nuovo@example.com", "role": "consultazione"},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["full_name"] == "Nuovo Nome"
    assert body["email"] == "nuovo@example.com"
    assert body["role"] == "consultazione"

    db_session.refresh(operatore_user)
    assert operatore_user.role == "consultazione"


def test_non_admin_non_puo_modificare_utenti(client, operatore_user, db_session):
    altro = _make_user(db_session, "altro_operatore", UserRole.OPERATORE.value)
    app.dependency_overrides[get_current_user] = lambda: operatore_user

    resp = client.patch(f"/api/v1/admin/users/{altro.id}", json={"full_name": "X"})

    assert resp.status_code == 403


def test_ruolo_invalido_in_modifica_rifiutato(client, admin_user, operatore_user):
    app.dependency_overrides[get_current_user] = lambda: admin_user

    resp = client.patch(f"/api/v1/admin/users/{operatore_user.id}", json={"role": "superadmin"})

    assert resp.status_code == 422


def test_email_duplicata_in_modifica_rifiutata(client, admin_user, operatore_user, db_session):
    altro = _make_user(db_session, "altro_utente", UserRole.OPERATORE.value, email="occupata@example.com")
    app.dependency_overrides[get_current_user] = lambda: admin_user

    resp = client.patch(f"/api/v1/admin/users/{operatore_user.id}", json={"email": "occupata@example.com"})

    assert resp.status_code == 409


def test_admin_non_puo_disattivare_se_stesso(client, admin_user, second_admin):
    app.dependency_overrides[get_current_user] = lambda: admin_user

    resp = client.patch(f"/api/v1/admin/users/{admin_user.id}", json={"is_active": False})

    assert resp.status_code == 409
    assert "te stesso" in resp.text.lower()


def test_admin_non_puo_degradare_se_stesso(client, admin_user, second_admin):
    app.dependency_overrides[get_current_user] = lambda: admin_user

    resp = client.patch(f"/api/v1/admin/users/{admin_user.id}", json={"role": "operatore"})

    assert resp.status_code == 409
    assert "te stesso" in resp.text.lower()


def test_admin_non_puo_cambiare_la_propria_email_senza_reauth(
    client,
    admin_user,
    second_admin,
):
    app.dependency_overrides[get_current_user] = lambda: admin_user

    resp = client.patch(
        f"/api/v1/admin/users/{admin_user.id}",
        json={"email": "attaccante@example.com"},
    )

    assert resp.status_code == 409
    assert "area personale" in resp.text.lower()
    assert admin_user.email != "attaccante@example.com"


# NOTA: uno scenario HTTP "un admin diverso disattiva/degrada l'ultimo admin
# attivo rimasto" non e' costruibile end-to-end: get_current_user rifiuta gli
# utenti is_active=False con 401 prima ancora che get_admin_user valuti il
# ruolo, quindi l'attore che chiama questo endpoint e' sempre un admin attivo
# distinto dal target. Se il target e' davvero l'unico admin attivo, l'attore
# stesso lo sarebbe anche lui, cioe' target e attore coinciderebbero: e' il
# caso "self", gia' coperto sopra. La guardia _would_remove_last_active_admin
# resta comunque difesa in profondita' e va provata direttamente.
def test_would_remove_last_active_admin_true_quando_e_lultimo(db_session, admin_user):
    from routers.admin import _would_remove_last_active_admin

    assert _would_remove_last_active_admin(
        db_session, admin_user, next_role="operatore", next_is_active=True
    ) is True
    assert _would_remove_last_active_admin(
        db_session, admin_user, next_role="admin", next_is_active=False
    ) is True


def test_would_remove_last_active_admin_false_se_ne_resta_un_altro(db_session, admin_user, second_admin):
    from routers.admin import _would_remove_last_active_admin

    assert _would_remove_last_active_admin(
        db_session, admin_user, next_role="operatore", next_is_active=True
    ) is False


def test_would_remove_last_active_admin_false_per_non_admin(db_session, operatore_user):
    from routers.admin import _would_remove_last_active_admin

    assert _would_remove_last_active_admin(
        db_session, operatore_user, next_role="operatore", next_is_active=False
    ) is False


def test_admin_puo_disattivare_altro_admin_se_non_e_lultimo(client, admin_user, second_admin, db_session):
    app.dependency_overrides[get_current_user] = lambda: admin_user

    resp = client.patch(f"/api/v1/admin/users/{second_admin.id}", json={"is_active": False})

    assert resp.status_code == 200, resp.text
    db_session.refresh(second_admin)
    assert second_admin.is_active is False


def test_modifica_utente_inesistente_404(client, admin_user):
    app.dependency_overrides[get_current_user] = lambda: admin_user

    resp = client.patch("/api/v1/admin/users/999999", json={})

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/v1/admin/users/{id}
# ---------------------------------------------------------------------------

def test_admin_elimina_altro_utente(client, admin_user, operatore_user, db_session):
    app.dependency_overrides[get_current_user] = lambda: admin_user

    resp = client.delete(f"/api/v1/admin/users/{operatore_user.id}")

    assert resp.status_code == 204, resp.text
    assert db_session.query(User).filter(User.id == operatore_user.id).first() is None


def test_non_admin_non_puo_eliminare_utenti(client, operatore_user, db_session):
    altro = _make_user(db_session, "altro_operatore", UserRole.OPERATORE.value)
    app.dependency_overrides[get_current_user] = lambda: operatore_user

    resp = client.delete(f"/api/v1/admin/users/{altro.id}")

    assert resp.status_code == 403


def test_admin_non_puo_eliminare_se_stesso(client, admin_user, second_admin):
    app.dependency_overrides[get_current_user] = lambda: admin_user

    resp = client.delete(f"/api/v1/admin/users/{admin_user.id}")

    assert resp.status_code == 409
    assert "te stesso" in resp.text.lower()


# Stesso limite architetturale spiegato sopra: uno scenario HTTP con un
# attore diverso dal target che elimina l'ultimo admin attivo non e'
# costruibile (l'attore dovrebbe essere quell'admin). La guardia e' la
# stessa funzione _would_remove_last_active_admin gia' provata direttamente;
# qui verifichiamo solo che il codice dell'endpoint la richiami davvero.
def test_eliminazione_ultimo_admin_attivo_blocca_anche_se_non_self(client, admin_user, db_session, monkeypatch):
    import routers.admin as admin_router

    monkeypatch.setattr(admin_router, "_would_remove_last_active_admin", lambda *a, **k: True)
    altro_attore = _make_user(db_session, "altro_admin_attore", UserRole.ADMIN.value)
    app.dependency_overrides[get_current_user] = lambda: altro_attore

    resp = client.delete(f"/api/v1/admin/users/{admin_user.id}")

    assert resp.status_code == 409
    assert "unico amministratore attivo" in resp.text.lower()


def test_eliminazione_utente_inesistente_404(client, admin_user):
    app.dependency_overrides[get_current_user] = lambda: admin_user

    resp = client.delete("/api/v1/admin/users/999999")

    assert resp.status_code == 404
