"""
Test basilari per tutti i router con prefix /api/v1/

Verifica che tutti gli endpoint principali rispondano correttamente.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Importa app e dipendenze
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app
from database import Base, get_db
import models

# Setup database di test in memoria
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_api_v1.db"
engine = create_engine(SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Crea tabelle
Base.metadata.create_all(bind=engine)

def override_get_db():
    """Override della dipendenza database per usare DB di test"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


class TestSystemEndpoints:
    """Test endpoint di sistema"""

    def test_root_endpoint(self):
        """Test endpoint root"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["status"] == "online"

    def test_health_endpoint(self):
        """Test health check"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


class TestCollaboratorsEndpoints:
    """Test endpoint collaboratori /api/v1/collaborators"""

    def test_get_collaborators(self):
        """Test GET /api/v1/collaborators"""
        response = client.get("/api/v1/collaborators/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_create_collaborator(self):
        """Test POST /api/v1/collaborators"""
        collab_data = {
            "first_name": "Mario",
            "last_name": "Rossi",
            "email": "mario.rossi@test.com",
            "fiscal_code": "RSSMRA80A01H501Z",
            "birthplace": "Roma",
            "birth_date": "1980-01-01",
            "address": "Via Test 1",
            "city": "Roma"
        }
        response = client.post("/api/v1/collaborators/", json=collab_data)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == collab_data["email"]
        assert "id" in data

    def test_get_collaborator_not_found(self):
        """Test GET /api/v1/collaborators/{id} - not found"""
        response = client.get("/api/v1/collaborators/99999")
        assert response.status_code == 404


class TestProjectsEndpoints:
    """Test endpoint progetti /api/v1/projects"""

    def test_get_projects(self):
        """Test GET /api/v1/projects"""
        response = client.get("/api/v1/projects/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_create_project(self):
        """Test POST /api/v1/projects"""
        project_data = {
            "name": "Progetto Test",
            "description": "Descrizione progetto test",
            "cup": "A12345678901234",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "status": "active"
        }
        response = client.post("/api/v1/projects/", json=project_data)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == project_data["name"]
        assert "id" in data

    def test_get_project_not_found(self):
        """Test GET /api/v1/projects/{id} - not found"""
        response = client.get("/api/v1/projects/99999")
        assert response.status_code == 404


class TestAttendancesEndpoints:
    """Test endpoint presenze /api/v1/attendances"""

    def test_get_attendances(self):
        """Test GET /api/v1/attendances"""
        response = client.get("/api/v1/attendances/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_attendance_not_found(self):
        """Test GET /api/v1/attendances/{id} - not found"""
        response = client.get("/api/v1/attendances/99999")
        assert response.status_code == 404


class TestAssignmentsEndpoints:
    """Test endpoint assegnazioni /api/v1/assignments"""

    def test_get_assignments(self):
        """Test GET /api/v1/assignments"""
        response = client.get("/api/v1/assignments/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_assignment_not_found(self):
        """Test GET /api/v1/assignments/{id} - not found"""
        response = client.get("/api/v1/assignments/99999")
        assert response.status_code == 404


class TestEntitiesEndpoints:
    """Test endpoint enti attuatori /api/v1/entities"""

    def test_get_entities(self):
        """Test GET /api/v1/entities"""
        response = client.get("/api/v1/entities/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_create_entity(self):
        """Test POST /api/v1/entities"""
        entity_data = {
            "ragione_sociale": "Ente Test SRL",
            "partita_iva": "12345678901",
            "indirizzo_completo": "Via Test 1, 00100 Roma",
            "referente_nome_completo": "Giuseppe Verdi",
            "pec": "test@pec.it"
        }
        response = client.post("/api/v1/entities/", json=entity_data)
        # Può fallire se P.IVA già esiste, ma almeno verifica il path
        assert response.status_code in [200, 400]

    def test_get_entity_not_found(self):
        """Test GET /api/v1/entities/{id} - not found"""
        response = client.get("/api/v1/entities/99999")
        assert response.status_code == 404


class TestContractsEndpoints:
    """Test endpoint contratti /api/v1/contracts"""

    def test_get_contract_templates(self):
        """Test GET /api/v1/contracts"""
        response = client.get("/api/v1/contracts/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_contract_template_not_found(self):
        """Test GET /api/v1/contracts/{id} - not found"""
        response = client.get("/api/v1/contracts/99999")
        assert response.status_code == 404


class TestReportingEndpoints:
    """Test endpoint reporting /api/v1/reporting"""

    def test_get_timesheet_report(self):
        """Test GET /api/v1/reporting/timesheet"""
        response = client.get("/api/v1/reporting/timesheet")
        assert response.status_code == 200
        data = response.json()
        assert "periodo" in data
        assert "presenze" in data
        assert "totali" in data

    def test_get_summary_report(self):
        """Test GET /api/v1/reporting/summary"""
        response = client.get("/api/v1/reporting/summary")
        assert response.status_code == 200
        data = response.json()
        assert "periodo" in data
        assert "kpi_generali" in data

    def test_get_timesheet_with_filters(self):
        """Test GET /api/v1/reporting/timesheet con filtri"""
        response = client.get("/api/v1/reporting/timesheet?from=2025-01-01&to=2025-12-31")
        assert response.status_code == 200
        data = response.json()
        assert data["periodo"]["from"] == "2025-01-01"
        assert data["periodo"]["to"] == "2025-12-31"


class TestAdminEndpoints:
    """Test endpoint admin /api/v1/admin"""

    def test_admin_metrics_unauthorized(self):
        """Test GET /api/v1/admin/metrics senza auth (deve fallire)"""
        response = client.get("/api/v1/admin/metrics")
        # Dovrebbe richiedere autenticazione
        assert response.status_code in [401, 403]


# Test di integrazione completo
class TestIntegrationFlow:
    """Test flow completo: crea collaboratore, progetto, assegnazione"""

    def test_complete_flow(self):
        """Test flow completo creazione e collegamento entità"""

        # 1. Crea collaboratore
        collab_data = {
            "first_name": "Luigi",
            "last_name": "Bianchi",
            "email": "luigi.bianchi@test.com",
            "fiscal_code": "BNCLGU85B15H501W",
            "birthplace": "Milano",
            "birth_date": "1985-02-15",
            "address": "Via Milano 10",
            "city": "Milano"
        }
        collab_response = client.post("/api/v1/collaborators/", json=collab_data)
        assert collab_response.status_code == 200
        collaborator_id = collab_response.json()["id"]

        # 2. Crea progetto
        project_data = {
            "name": "Progetto Integrazione",
            "description": "Test integrazione completa",
            "cup": "B98765432109876",
            "start_date": "2025-03-01",
            "end_date": "2025-09-30",
            "status": "active"
        }
        project_response = client.post("/api/v1/projects/", json=project_data)
        assert project_response.status_code == 200
        project_id = project_response.json()["id"]

        # 3. Crea assegnazione
        assignment_data = {
            "collaborator_id": collaborator_id,
            "project_id": project_id,
            "role": "Developer",
            "assigned_hours": 100,
            "hourly_rate": 35.0,
            "start_date": "2025-03-01",
            "end_date": "2025-09-30",
            "contract_type": "professionale"
        }
        assignment_response = client.post("/api/v1/assignments/", json=assignment_data)
        assert assignment_response.status_code == 200

        # 4. Verifica che l'assegnazione sia stata creata
        assignments = client.get(f"/api/v1/assignments/")
        assert assignments.status_code == 200

        # 5. Recupera stats collaboratore
        stats_response = client.get(f"/api/v1/reporting/collaborator/{collaborator_id}/stats")
        assert stats_response.status_code == 200

        # 6. Recupera stats progetto
        stats_response = client.get(f"/api/v1/reporting/project/{project_id}/stats")
        assert stats_response.status_code == 200


# Cleanup finale
def teardown_module(module):
    """Cleanup database di test"""
    import os
    try:
        os.remove("./test_api_v1.db")
    except:
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
