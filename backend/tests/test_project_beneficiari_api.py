"""
Test F2-002: endpoint beneficiari progetto.

Il frontend (ProjectManager via apiService) chiama
GET /api/v1/projects/{id}/beneficiari e
PATCH /api/v1/projects/{id}/beneficiari/{azienda_id}/regime,
ma gli endpoint non esistevano a runtime (404).
"""

from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app
from database import Base, get_db
from auth import UserRole, get_current_user, rbac_decision_for
import models  # noqa: F401  # assicura registrazione metadata


@pytest.fixture(scope="function")
def db_session(tmp_path):
    """Fornisce una sessione DB isolata per ogni test."""
    db_path = tmp_path / "test_beneficiari.db"
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
    """Override di get_db per usare il DB temporaneo del test."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def override_get_current_user():
        return type(
            "TestUser",
            (),
            {
                "id": 1,
                "username": "test-admin",
                "email": "test-admin@example.com",
                "role": "admin",
                "is_active": True,
            },
        )()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def progetto_con_beneficiario(db_session):
    """Crea progetto + azienda cliente + link beneficiario."""
    project = models.Project(name="Progetto FAPI Test")
    azienda = models.AziendaCliente(ragione_sociale="ACME Srl")
    db_session.add_all([project, azienda])
    db_session.commit()
    db_session.refresh(project)
    db_session.refresh(azienda)

    link = models.AziendaClienteProjectLink(
        azienda_cliente_id=azienda.id,
        project_id=project.id,
        regime_aiuto=None,
        plafond_dichiarato=None,
    )
    db_session.add(link)
    db_session.commit()
    return project, azienda, link


class TestGetBeneficiari:
    def test_progetto_inesistente_404(self, client):
        response = client.get("/api/v1/projects/999999/beneficiari")
        assert response.status_code == 404

    def test_progetto_senza_beneficiari(self, client, db_session):
        project = models.Project(name="Progetto Vuoto")
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)

        response = client.get(f"/api/v1/projects/{project.id}/beneficiari")
        assert response.status_code == 200
        assert response.json() == {"beneficiari": []}

    def test_lista_beneficiari(self, client, progetto_con_beneficiario):
        project, azienda, _ = progetto_con_beneficiario
        response = client.get(f"/api/v1/projects/{project.id}/beneficiari")
        assert response.status_code == 200
        beneficiari = response.json()["beneficiari"]
        assert len(beneficiari) == 1
        b = beneficiari[0]
        assert b["azienda_id"] == azienda.id
        assert b["ragione_sociale"] == "ACME Srl"
        assert b["regime_aiuto"] is None
        assert b["plafond_dichiarato"] is None


class TestPatchRegime:
    def test_aggiorna_regime_e_plafond(self, client, db_session, progetto_con_beneficiario):
        project, azienda, link = progetto_con_beneficiario
        response = client.patch(
            f"/api/v1/projects/{project.id}/beneficiari/{azienda.id}/regime",
            json={"regime_aiuto": "de_minimis", "plafond_dichiarato": 200000.0},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["regime_aiuto"] == "de_minimis"
        assert data["plafond_dichiarato"] == 200000.0

        db_session.refresh(link)
        assert link.regime_aiuto == "de_minimis"
        assert link.plafond_dichiarato == 200000.0

    def test_regime_non_definito_azzera(self, client, db_session, progetto_con_beneficiario):
        project, azienda, link = progetto_con_beneficiario
        link.regime_aiuto = "de_minimis"
        db_session.commit()

        response = client.patch(
            f"/api/v1/projects/{project.id}/beneficiari/{azienda.id}/regime",
            json={"regime_aiuto": "non_definito"},
        )
        assert response.status_code == 200
        assert response.json()["regime_aiuto"] is None

        db_session.refresh(link)
        assert link.regime_aiuto is None

    def test_regime_non_valido_422(self, client, progetto_con_beneficiario):
        project, azienda, _ = progetto_con_beneficiario
        response = client.patch(
            f"/api/v1/projects/{project.id}/beneficiari/{azienda.id}/regime",
            json={"regime_aiuto": "regime-inventato"},
        )
        assert response.status_code == 422

    def test_azienda_non_collegata_404(self, client, db_session, progetto_con_beneficiario):
        project, _, _ = progetto_con_beneficiario
        altra_azienda = models.AziendaCliente(ragione_sociale="Estranea Srl")
        db_session.add(altra_azienda)
        db_session.commit()
        db_session.refresh(altra_azienda)

        response = client.patch(
            f"/api/v1/projects/{project.id}/beneficiari/{altra_azienda.id}/regime",
            json={"regime_aiuto": "esenzione"},
        )
        assert response.status_code == 404

    def test_progetto_inesistente_404(self, client):
        response = client.patch(
            "/api/v1/projects/999999/beneficiari/1/regime",
            json={"regime_aiuto": "de_minimis"},
        )
        assert response.status_code == 404


class TestBeneficiariRbacMatrix:
    """RBAC: /api/v1/projects e' prefisso operativo gia' coperto da require_role."""

    @pytest.mark.parametrize(
        "method,path,expected_by_role",
        [
            ("GET", "/api/v1/projects/1/beneficiari", {"admin": 200, "operatore": 200, "consultazione": 200}),
            ("PATCH", "/api/v1/projects/1/beneficiari/1/regime", {"admin": 200, "operatore": 200, "consultazione": 403}),
        ],
    )
    @pytest.mark.parametrize(
        "role",
        [UserRole.ADMIN.value, UserRole.OPERATORE.value, UserRole.CONSULTAZIONE.value],
    )
    def test_rbac_beneficiari(self, method, path, expected_by_role, role):
        decision = rbac_decision_for(method, path, role)
        assert decision["would_status"] == expected_by_role[role]
