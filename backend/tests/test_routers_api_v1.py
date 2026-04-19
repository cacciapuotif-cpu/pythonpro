"""
Test basilari per tutti i router con prefix /api/v1/

Verifica che gli endpoint principali siano raggiungibili con un DB di test
isolato, senza dipendere da file SQLite relativi al working directory.
"""

from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Importa app e dipendenze
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app
from database import Base, get_db
import models  # noqa: F401  # assicura registrazione metadata


@pytest.fixture(scope="function")
def db_session(tmp_path):
    """Fornisce una sessione DB isolata per ogni test."""
    db_path = tmp_path / "test_api_v1.db"
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

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


class TestSystemEndpoints:
    """Test endpoint di sistema"""

    def test_root_endpoint(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["status"] == "online"

    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


class TestCollaboratorsEndpoints:
    """Test endpoint collaboratori /api/v1/collaborators"""

    def test_get_collaborators(self, client):
        response = client.get("/api/v1/collaborators/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_create_collaborator(self, client):
        collab_data = {
            "first_name": "Mario",
            "last_name": "Rossi",
            "email": "mario.rossi@gmail.com",
            "fiscal_code": "RSSMRA80A01H501Z",
            "birthplace": "Roma",
            "birth_date": "1980-01-01",
            "address": "Via Test 1",
            "city": "Roma",
        }
        response = client.post("/api/v1/collaborators/", json=collab_data)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == collab_data["email"]
        assert "id" in data

    def test_get_collaborator_not_found(self, client):
        response = client.get("/api/v1/collaborators/99999")
        assert response.status_code == 404


class TestProjectsEndpoints:
    """Test endpoint progetti /api/v1/projects"""

    def test_get_projects(self, client):
        response = client.get("/api/v1/projects/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_create_project(self, client):
        project_data = {
            "name": "Progetto Test",
            "description": "Descrizione progetto test",
            "cup": "A12345678901234",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "status": "active",
        }
        response = client.post("/api/v1/projects/", json=project_data)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == project_data["name"]
        assert "id" in data

    def test_get_project_not_found(self, client):
        response = client.get("/api/v1/projects/99999")
        assert response.status_code == 404


class TestAttendancesEndpoints:
    """Test endpoint presenze /api/v1/attendances"""

    def test_get_attendances(self, client):
        response = client.get("/api/v1/attendances/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_attendance_not_found(self, client):
        response = client.get("/api/v1/attendances/99999")
        assert response.status_code == 404


class TestAssignmentsEndpoints:
    """Test endpoint assegnazioni /api/v1/assignments"""

    def test_get_assignments(self, client):
        response = client.get("/api/v1/assignments/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_assignment_not_found(self, client):
        response = client.get("/api/v1/assignments/99999")
        assert response.status_code == 404


class TestEntitiesEndpoints:
    """Test endpoint enti attuatori /api/v1/entities"""

    def test_get_entities(self, client):
        response = client.get("/api/v1/entities/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_create_entity(self, client):
        entity_data = {
            "ragione_sociale": "Ente Test SRL",
            "partita_iva": "12345678901",
            "indirizzo_completo": "Via Test 1, 00100 Roma",
            "referente_nome_completo": "Giuseppe Verdi",
            "pec": "test@pec.it",
        }
        response = client.post("/api/v1/entities/", json=entity_data)
        assert response.status_code in [200, 400]

    def test_get_entity_not_found(self, client):
        response = client.get("/api/v1/entities/99999")
        assert response.status_code == 404


class TestContractsEndpoints:
    """Test endpoint contratti /api/v1/contracts"""

    def test_get_contract_templates(self, client):
        response = client.get("/api/v1/contracts/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_contract_template_not_found(self, client):
        response = client.get("/api/v1/contracts/99999")
        assert response.status_code == 404


class TestReportingEndpoints:
    """Test endpoint reporting /api/v1/reporting"""

    def test_get_timesheet_report(self, client):
        response = client.get("/api/v1/reporting/timesheet")
        assert response.status_code == 200
        data = response.json()
        assert "periodo" in data
        assert "presenze" in data
        assert "totali" in data

    def test_get_summary_report(self, client):
        response = client.get("/api/v1/reporting/summary")
        assert response.status_code == 200
        data = response.json()
        assert "periodo" in data
        assert "kpi_generali" in data

    def test_get_timesheet_with_filters(self, client):
        response = client.get("/api/v1/reporting/timesheet?from=2025-01-01&to=2025-12-31")
        assert response.status_code == 200
        data = response.json()
        assert data["periodo"]["from"] == "2025-01-01"
        assert data["periodo"]["to"] == "2025-12-31"


class TestAdminEndpoints:
    """Test endpoint admin /api/v1/admin"""

    def test_admin_metrics_unauthorized(self, client):
        response = client.get("/api/v1/admin/metrics")
        assert response.status_code in [401, 403]


class TestIntegrationFlow:
    """Test flow completo: crea collaboratore, progetto, assegnazione"""

    def test_complete_flow(self, client):
        collab_data = {
            "first_name": "Luigi",
            "last_name": "Bianchi",
            "email": "luigi.bianchi@gmail.com",
            "fiscal_code": "BNCLGU85B15H501W",
            "birthplace": "Milano",
            "birth_date": "1985-02-15",
            "address": "Via Milano 10",
            "city": "Milano",
        }
        collab_response = client.post("/api/v1/collaborators/", json=collab_data)
        assert collab_response.status_code == 200
        collaborator_id = collab_response.json()["id"]

        project_data = {
            "name": "Progetto Integrazione",
            "description": "Test integrazione completa",
            "cup": "B98765432109876",
            "start_date": "2025-03-01",
            "end_date": "2025-09-30",
            "status": "active",
        }
        project_response = client.post("/api/v1/projects/", json=project_data)
        assert project_response.status_code == 200
        project_id = project_response.json()["id"]

        assignment_data = {
            "collaborator_id": collaborator_id,
            "project_id": project_id,
            "role": "Developer",
            "assigned_hours": 100,
            "hourly_rate": 35.0,
            "start_date": "2025-03-01",
            "end_date": "2025-09-30",
            "contract_type": "professionale",
        }
        assignment_response = client.post("/api/v1/assignments/", json=assignment_data)
        assert assignment_response.status_code == 200

        assignments = client.get("/api/v1/assignments/")
        assert assignments.status_code == 200

        stats_response = client.get(f"/api/v1/reporting/collaborator/{collaborator_id}/stats")
        assert stats_response.status_code == 200

        stats_response = client.get(f"/api/v1/reporting/project/{project_id}/stats")
        assert stats_response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
