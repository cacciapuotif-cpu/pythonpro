"""
Test per i router in-memory API v1
Testa tutti i router creati in app/api/ con storage in-memory
"""

import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Setup path per importare app.main
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import app

# Crea client di test
client = TestClient(app)


class TestSystemEndpoints:
    """Test endpoint di sistema"""

    def test_root_endpoint(self):
        """Test endpoint root"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "app" in data
        assert data["status"] == "online"

    def test_health_endpoint(self):
        """Test health check"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "checks" in data

    def test_version_endpoint(self):
        """Test version info"""
        response = client.get("/version")
        assert response.status_code == 200
        data = response.json()
        assert "app_name" in data
        assert "version" in data


class TestCollaboratorsInMemory:
    """Test endpoint collaboratori in-memory"""

    def test_get_empty_collaborators(self):
        """Test GET /api/v1/collaborators - lista vuota"""
        response = client.get("/api/v1/collaborators/")
        assert response.status_code == 200
        # Nota: potrebbe avere dati dai test precedenti, quindi verifico solo che sia lista
        assert isinstance(response.json(), list)

    def test_create_collaborator(self):
        """Test POST /api/v1/collaborators"""
        collab_data = {
            "first_name": "Mario",
            "last_name": "Rossi",
            "email": f"mario.rossi.{hash('test1')}@test.com",  # Email unica
            "fiscal_code": "RSSMRA80A01H501Z"
        }
        response = client.post("/api/v1/collaborators/", json=collab_data)
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == collab_data["email"]
        assert data["first_name"] == "Mario"
        assert "id" in data
        assert "created_at" in data

    def test_create_collaborator_duplicate_email(self):
        """Test POST /api/v1/collaborators con email duplicata"""
        collab_data = {
            "first_name": "Luigi",
            "last_name": "Bianchi",
            "email": "duplicate@test.com",
            "fiscal_code": "BNCLGU85B15H501W"
        }
        # Prima creazione
        response1 = client.post("/api/v1/collaborators/", json=collab_data)
        assert response1.status_code == 201

        # Seconda creazione - deve fallire
        response2 = client.post("/api/v1/collaborators/", json=collab_data)
        assert response2.status_code == 400
        assert "già esistente" in response2.json()["detail"]

    def test_get_collaborator_search(self):
        """Test GET /api/v1/collaborators con filtro search"""
        # Crea un collaboratore
        collab_data = {
            "first_name": "Giovanni",
            "last_name": "Verdi",
            "email": f"giovanni.verdi.{hash('test2')}@test.com",
            "fiscal_code": "VRDGNN90C10H501X"
        }
        create_response = client.post("/api/v1/collaborators/", json=collab_data)
        assert create_response.status_code == 201

        # Cerca per nome
        response = client.get("/api/v1/collaborators/?search=Giovanni")
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        assert any(c["first_name"] == "Giovanni" for c in data)

    def test_get_collaborator_by_id(self):
        """Test GET /api/v1/collaborators/{id}"""
        # Crea collaboratore
        collab_data = {
            "first_name": "Test",
            "last_name": "User",
            "email": f"test.user.{hash('test3')}@test.com",
            "fiscal_code": "TSTURS95D20H501Y"
        }
        create_response = client.post("/api/v1/collaborators/", json=collab_data)
        collaborator_id = create_response.json()["id"]

        # Recupera per ID
        response = client.get(f"/api/v1/collaborators/{collaborator_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == collaborator_id
        assert data["email"] == collab_data["email"]

    def test_update_collaborator(self):
        """Test PUT /api/v1/collaborators/{id}"""
        # Crea collaboratore
        collab_data = {
            "first_name": "Update",
            "last_name": "Test",
            "email": f"update.test.{hash('test4')}@test.com",
            "fiscal_code": "UPDTST88E30H501Z"
        }
        create_response = client.post("/api/v1/collaborators/", json=collab_data)
        collaborator_id = create_response.json()["id"]

        # Aggiorna
        update_data = {"first_name": "UpdatedName"}
        response = client.put(f"/api/v1/collaborators/{collaborator_id}", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "UpdatedName"
        assert data["last_name"] == "Test"  # Non modificato

    def test_delete_collaborator(self):
        """Test DELETE /api/v1/collaborators/{id}"""
        # Crea collaboratore
        collab_data = {
            "first_name": "Delete",
            "last_name": "Me",
            "email": f"delete.me.{hash('test5')}@test.com",
            "fiscal_code": "DLTMXX91F01H501A"
        }
        create_response = client.post("/api/v1/collaborators/", json=collab_data)
        collaborator_id = create_response.json()["id"]

        # Elimina
        response = client.delete(f"/api/v1/collaborators/{collaborator_id}")
        assert response.status_code == 204

        # Verifica che non esista più
        get_response = client.get(f"/api/v1/collaborators/{collaborator_id}")
        assert get_response.status_code == 404


class TestProjectsInMemory:
    """Test endpoint progetti in-memory"""

    def test_create_project(self):
        """Test POST /api/v1/projects"""
        project_data = {
            "name": "Progetto Test In-Memory",
            "description": "Test progetto in-memory",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "status": "active"
        }
        response = client.post("/api/v1/projects/", json=project_data)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == project_data["name"]
        assert "id" in data
        assert "created_at" in data

    def test_get_projects(self):
        """Test GET /api/v1/projects"""
        response = client.get("/api/v1/projects/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_projects_with_status_filter(self):
        """Test GET /api/v1/projects con filtro status"""
        # Crea progetto active
        project_data = {
            "name": "Active Project",
            "status": "active"
        }
        client.post("/api/v1/projects/", json=project_data)

        # Filtra per status
        response = client.get("/api/v1/projects/?status=active")
        assert response.status_code == 200
        data = response.json()
        assert all(p["status"] == "active" for p in data)


class TestEntitiesInMemory:
    """Test endpoint enti attuatori in-memory"""

    def test_create_entity(self):
        """Test POST /api/v1/entities"""
        entity_data = {
            "name": "Ente Test",
            "description": "Descrizione ente test"
        }
        response = client.post("/api/v1/entities/", json=entity_data)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == entity_data["name"]
        assert "id" in data

    def test_get_entities(self):
        """Test GET /api/v1/entities"""
        response = client.get("/api/v1/entities/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_entities_with_search(self):
        """Test GET /api/v1/entities con search"""
        # Crea entità
        entity_data = {"name": "Searchable Entity", "description": "Test search"}
        client.post("/api/v1/entities/", json=entity_data)

        # Cerca
        response = client.get("/api/v1/entities/?search=Searchable")
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0


class TestAssignmentsInMemory:
    """Test endpoint assegnazioni in-memory"""

    def test_create_assignment(self):
        """Test POST /api/v1/assignments"""
        assignment_data = {
            "collaborator_id": 1,
            "project_id": 1,
            "entity_id": 1,
            "role": "Developer",
            "start_date": "2025-10-19"
        }
        response = client.post("/api/v1/assignments/", json=assignment_data)
        assert response.status_code == 201
        data = response.json()
        assert data["role"] == "Developer"
        assert "id" in data

    def test_get_assignments(self):
        """Test GET /api/v1/assignments"""
        response = client.get("/api/v1/assignments/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_assignments_with_filters(self):
        """Test GET /api/v1/assignments con filtri"""
        response = client.get("/api/v1/assignments/?project_id=1")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestAttendancesInMemory:
    """Test endpoint presenze in-memory"""

    def test_create_attendance(self):
        """Test POST /api/v1/attendances"""
        attendance_data = {
            "collaborator_id": 1,
            "project_id": 1,
            "date": "2025-10-19",
            "hours": 8.0
        }
        response = client.post("/api/v1/attendances/", json=attendance_data)
        assert response.status_code == 201
        data = response.json()
        assert data["hours"] == 8.0
        assert "id" in data

    def test_get_attendances(self):
        """Test GET /api/v1/attendances"""
        response = client.get("/api/v1/attendances/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_attendances_with_date_filter(self):
        """Test GET /api/v1/attendances con filtri date"""
        response = client.get("/api/v1/attendances/?from=2025-01-01&to=2025-12-31")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestContractsInMemory:
    """Test endpoint contratti in-memory"""

    def test_get_templates(self):
        """Test GET /api/v1/contracts/templates"""
        response = client.get("/api/v1/contracts/templates")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_create_template(self):
        """Test POST /api/v1/contracts/templates"""
        template_data = {
            "name": "Template Test",
            "template_type": "collaborazione",
            "content": "Contenuto del template"
        }
        response = client.post("/api/v1/contracts/templates", json=template_data)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Template Test"
        assert "id" in data

    def test_delete_template(self):
        """Test DELETE /api/v1/contracts/templates/{id}"""
        # Crea template
        template_data = {
            "name": "Template to Delete",
            "template_type": "subordinato",
            "content": "Test"
        }
        create_response = client.post("/api/v1/contracts/templates", json=template_data)
        template_id = create_response.json()["id"]

        # Elimina
        response = client.delete(f"/api/v1/contracts/templates/{template_id}")
        assert response.status_code == 204

    def test_generate_contract(self):
        """Test POST /api/v1/contracts/generate"""
        # Prima crea un template
        template_data = {
            "name": "Template Generate",
            "template_type": "collaborazione",
            "content": "Template content"
        }
        template_response = client.post("/api/v1/contracts/templates", json=template_data)
        template_id = template_response.json()["id"]

        # Genera contratto
        generate_data = {
            "template_id": template_id,
            "collaborator_id": 1,
            "project_id": 1,
            "entity_id": 1
        }
        response = client.post("/api/v1/contracts/generate", json=generate_data)
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["template_id"] == template_id


class TestReportingInMemory:
    """Test endpoint reporting in-memory"""

    def test_get_timesheet(self):
        """Test GET /api/v1/reporting/timesheet"""
        response = client.get("/api/v1/reporting/timesheet")
        assert response.status_code == 200
        data = response.json()
        assert "period" in data
        assert "attendances" in data
        assert "total_hours" in data

    def test_get_timesheet_with_filters(self):
        """Test GET /api/v1/reporting/timesheet con filtri"""
        response = client.get("/api/v1/reporting/timesheet?from=2025-01-01&to=2025-12-31")
        assert response.status_code == 200
        data = response.json()
        assert data["period"]["from"] == "2025-01-01"
        assert data["period"]["to"] == "2025-12-31"

    def test_get_summary(self):
        """Test GET /api/v1/reporting/summary"""
        response = client.get("/api/v1/reporting/summary")
        assert response.status_code == 200
        data = response.json()
        assert "period" in data
        assert "kpi" in data
        assert "total_collaborators" in data["kpi"]
        assert "total_projects" in data["kpi"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
