"""Task R1 — sweep RBAC endpoint file/export (classe di bug NEW-022).

Censimento completo degli endpoint che restituiscono file/stream/export e
verifica ruolo x endpoint contro la matrice Ondata 1:
- consultazione: solo export non sensibili (no PII completa, no dati
  economici/lavorativi individuali)
- timesheet e piano finanziario: admin + operatore
- documenti collaboratore, curriculum, export GDPR, export CSV timesheet
  massivo: solo admin (ADMIN_ONLY_PATTERNS / ADMIN_ONLY_PREFIXES)

Due livelli di verifica:
1. Matrice pura: ``rbac_decision_for`` -> would_status 200/403 esatto per
   ognuno dei 3 ruoli su ogni endpoint censito.
2. HTTP reale con ``RBAC_ENFORCE=True`` (monkeypatch, pattern
   test_e2e_catena_contratto.py): ruolo negato -> esattamente 403 dal
   router-level ``require_role``; ruolo ammesso -> mai 403/401 (tipicamente
   404 perche' gli ID usati non esistono: cosi' si prova che il gate RBAC
   lascia passare senza dover costruire su disco PDF/Excel/ZIP reali per
   ogni endpoint — setup minimo motivato, vedi Task R1 punto 3).
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from database import Base, get_db
import auth
from auth import User, UserRole, get_current_user, rbac_decision_for
import models  # noqa: F401 - registra i modelli sul Base
import routers.reporting as reporting_router

ALL_ROLES = (UserRole.ADMIN.value, UserRole.OPERATORE.value, UserRole.CONSULTAZIONE.value)

# (nome, metodo, path con ID inesistente, {ruolo: status atteso dalla matrice})
# 200 = ammesso (a livello HTTP: qualunque esito != 401/403),
# 403 = negato dal RBAC.
FILE_ENDPOINT_CASES = [
    # -- export non sensibili: consultazione ammessa --------------------
    ("preventivo-pdf", "GET", "/api/v1/preventivi/999999/pdf",
     {"admin": 200, "operatore": 200, "consultazione": 200}),
    ("entity-download-logo", "GET", "/api/v1/entities/999999/download-logo",
     {"admin": 200, "operatore": 200, "consultazione": 200}),
    # -- PII / dati individuali: admin + operatore ----------------------
    ("assignment-contract-pdf", "GET", "/api/v1/assignments/999999/contract",
     {"admin": 200, "operatore": 200, "consultazione": 403}),  # NEW-022
    ("assignment-timesheet-pdf", "GET", "/api/v1/assignments/999999/timesheet",
     {"admin": 200, "operatore": 200, "consultazione": 403}),  # NEW-024
    ("email-inbox-attachment", "GET", "/api/v1/email-inbox/items/999999/attachment",
     {"admin": 200, "operatore": 200, "consultazione": 403}),  # NEW-025
    ("piano-finanziario-export-excel", "GET", "/api/v1/piani-finanziari/999999/export-excel",
     {"admin": 200, "operatore": 200, "consultazione": 403}),
    ("rendicontazione-zip", "POST", "/api/v1/reporting/projects/999999/rendicontazione",
     {"admin": 200, "operatore": 200, "consultazione": 403}),
    # -- solo admin (ADMIN_ONLY_PATTERNS / ADMIN_ONLY_PREFIXES) ---------
    ("timesheet-export-csv-start", "POST", "/api/v1/reporting/timesheet/export",
     {"admin": 200, "operatore": 403, "consultazione": 403}),
    ("timesheet-export-csv-download", "GET", "/api/v1/reporting/timesheet/export/id-inesistente",
     {"admin": 200, "operatore": 403, "consultazione": 403}),
    ("collaborator-download-documento", "GET", "/api/v1/collaborators/999999/download-documento",
     {"admin": 200, "operatore": 403, "consultazione": 403}),
    ("collaborator-download-curriculum", "GET", "/api/v1/collaborators/999999/download-curriculum",
     {"admin": 200, "operatore": 403, "consultazione": 403}),
    ("gdpr-export", "GET", "/api/v1/gdpr/export/999999",
     {"admin": 200, "operatore": 403, "consultazione": 403}),
]


# ------------------------------------------------------------------
# Livello 1: matrice pura (nessun setup, copre l'intero censimento)
# ------------------------------------------------------------------

@pytest.mark.parametrize("case_name,method,path,expected_by_role", FILE_ENDPOINT_CASES)
@pytest.mark.parametrize("role", ALL_ROLES)
def test_matrice_rbac_endpoint_file(case_name, method, path, expected_by_role, role):
    decision = rbac_decision_for(method, path, role)
    assert decision["would_status"] == expected_by_role[role], (
        f"{case_name}: {method} {path} ruolo={role} "
        f"atteso={expected_by_role[role]} ottenuto={decision['would_status']} "
        f"(allowed_roles={decision['allowed_roles']})"
    )


# ------------------------------------------------------------------
# Livello 2: HTTP reale con enforcement attivo
# ------------------------------------------------------------------

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
def users_by_role(db_session):
    users = {}
    for role in ALL_ROLES:
        user = User(
            username=f"rbacdl_{role}",
            email=f"rbacdl_{role}@example.com",
            hashed_password="x",
            role=role,
            is_active=True,
        )
        db_session.add(user)
        users[role] = user
    db_session.commit()
    for user in users.values():
        db_session.refresh(user)
    return users


@pytest.fixture(scope="function")
def client(db_session, monkeypatch):
    # Enforcement esplicito, indipendente dall'env del container
    # (pattern M-2, vedi test_e2e_catena_contratto.py).
    monkeypatch.setattr(auth, "RBAC_ENFORCE", True)
    # Il POST /reporting/timesheet/export (admin) schedula un background task
    # che scrive un CSV in EXPORTS_DIR con una sessione DB propria: qui
    # interessa solo il gate RBAC, quindi il task viene neutralizzato.
    monkeypatch.setattr(
        reporting_router, "_generate_timesheet_export_file",
        lambda *args, **kwargs: None,
    )

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _request(client, method, path):
    if method == "GET":
        return client.get(path)
    if method == "POST":
        # Unico POST con body: filters export timesheet (tutti opzionali).
        return client.post(path, json={})
    raise AssertionError(f"Metodo non gestito: {method}")


@pytest.mark.parametrize("case_name,method,path,expected_by_role", FILE_ENDPOINT_CASES)
@pytest.mark.parametrize("role", ALL_ROLES)
def test_http_rbac_endpoint_file(client, users_by_role, case_name, method, path, expected_by_role, role):
    app.dependency_overrides[get_current_user] = lambda: users_by_role[role]
    resp = _request(client, method, path)

    if expected_by_role[role] == 403:
        assert resp.status_code == 403, (
            f"{case_name}: ruolo {role} doveva ricevere 403 su {method} {path}, "
            f"ottenuto {resp.status_code}: {resp.text[:200]}"
        )
        assert "Permessi insufficienti" in resp.text
    else:
        # Ruolo ammesso: il gate RBAC non deve scattare. Gli ID nei path non
        # esistono, quindi l'esito tipico e' 404 (o 200 per gli export
        # asincroni): l'importante e' che non sia un rifiuto auth (401/403).
        assert resp.status_code not in (401, 403), (
            f"{case_name}: ruolo {role} doveva passare il gate RBAC su "
            f"{method} {path}, ottenuto {resp.status_code}: {resp.text[:200]}"
        )


def test_suffisso_timesheet_non_concede_percorsi_admin_only():
    """Nota N-2 (review R0): la regola a suffisso e' bidirezionale — oltre a
    restringere, concede {admin, operatore}. Verifica che i suffissi sensibili
    non ribaltino percorsi admin-only reali: i pattern admin-only vincono
    perche' nessun path admin-only censito termina con un suffisso concesso,
    e i prefissi admin (/admin, /gdpr) sono valutati prima dei suffissi."""
    # Prefissi admin-only valutati PRIMA della regola a suffisso.
    for path in (
        "/api/v1/gdpr/export/1/contract",
        "/api/v1/admin/qualcosa/export-excel",
    ):
        assert rbac_decision_for("GET", path, "operatore")["would_status"] == 403, path
    # Nessun endpoint reale admin-only termina con /contract, /timesheet o
    # /export-excel: i pattern ADMIN_ONLY restano effettivi sui loro path.
    for path in (
        "/api/v1/collaborators/1/download-documento",
        "/api/v1/collaborators/1/download-curriculum",
        "/api/v1/reporting/timesheet/export/abc",
    ):
        assert rbac_decision_for("GET", path, "operatore")["would_status"] == 403, path
