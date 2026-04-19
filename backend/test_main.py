# =================================================================
# FILE: test_main.py
# =================================================================
# SCOPO: smoke/integration tests per endpoint API principali
# =================================================================

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app
from database import Base, get_db
import models  # noqa: F401  # assicura registrazione metadata


@pytest.fixture(scope="function")
def db_session(tmp_path):
    """Fornisce una sessione DB isolata per ogni test."""
    db_path = tmp_path / "test_main.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )

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
    """Fornisce TestClient FastAPI con DB di test."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def sample_collaborator(db_session):
    collaborator = models.Collaborator(
        first_name="Mario",
        last_name="Rossi",
        email="mario.rossi@gmail.com",
        phone="1234567890",
        position="Developer",
        fiscal_code="RSSMRA80A01H501Z",
    )
    db_session.add(collaborator)
    db_session.commit()
    db_session.refresh(collaborator)

    return {
        "id": collaborator.id,
        "first_name": collaborator.first_name,
        "last_name": collaborator.last_name,
        "email": collaborator.email,
    }


@pytest.fixture
def sample_project(db_session):
    project = models.Project(
        name="Test Project",
        description="A test project for unit tests",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        status="active",
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    return {
        "id": project.id,
        "name": project.name,
        "status": project.status,
    }


class TestCollaborators:
    def test_create_collaborator_success(self, client):
        payload = {
            "first_name": "Luigi",
            "last_name": "Verdi",
            "email": "luigi.verdi@gmail.com",
            "phone": "0987654321",
            "position": "Designer",
            "fiscal_code": "VRDLGU85B15H501W",
        }

        response = client.post("/api/v1/collaborators/", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["first_name"] == "Luigi"
        assert data["last_name"] == "Verdi"
        assert data["email"] == "luigi.verdi@gmail.com"

    def test_create_collaborator_duplicate_email(self, client, sample_collaborator):
        payload = {
            "first_name": "Mario",
            "last_name": "Bianchi",
            "email": sample_collaborator["email"],
            "phone": "1111111111",
            "position": "Manager",
            "fiscal_code": "BNCMRA85B15H501W",
        }

        response = client.post("/api/v1/collaborators/", json=payload)

        assert response.status_code == 409
        body = response.json()
        message = (body.get("detail") or body.get("error") or str(body)).lower()
        assert "email" in message

    def test_get_collaborators_empty(self, client):
        response = client.get("/api/v1/collaborators/")

        assert response.status_code == 200
        assert response.json() == []

    def test_get_collaborators_with_data(self, client, sample_collaborator):
        response = client.get("/api/v1/collaborators/")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["email"] == sample_collaborator["email"]

    def test_get_collaborator_by_id_success(self, client, sample_collaborator):
        collab_id = sample_collaborator["id"]
        response = client.get(f"/api/v1/collaborators/{collab_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == collab_id
        assert data["first_name"] == sample_collaborator["first_name"]

    def test_get_collaborator_by_id_not_found(self, client):
        response = client.get("/api/v1/collaborators/9999")

        assert response.status_code == 404
        body = response.json()
        message = (body.get("detail") or body.get("error") or str(body)).lower()
        assert "non trovato" in message

    def test_update_collaborator_success(self, client, sample_collaborator):
        collab_id = sample_collaborator["id"]
        update_payload = {
            "first_name": "Mario",
            "last_name": "Rossi Aggiornato",
            "position": "Senior Developer",
        }

        response = client.put(f"/api/v1/collaborators/{collab_id}", json=update_payload)

        assert response.status_code == 200
        data = response.json()
        assert data["last_name"] == "Rossi Aggiornato"
        assert data["position"] == "Senior Developer"

    def test_delete_collaborator_success(self, client, sample_collaborator):
        collab_id = sample_collaborator["id"]

        response = client.delete(f"/api/v1/collaborators/{collab_id}")
        assert response.status_code == 200

        get_response = client.get(f"/api/v1/collaborators/{collab_id}")
        assert get_response.status_code == 200
        assert get_response.json()["id"] == collab_id

        list_response = client.get("/api/v1/collaborators/?active_only=true")
        assert list_response.status_code == 200
        assert list_response.json() == []


class TestProjects:
    def test_create_project_success(self, client):
        payload = {
            "name": "Nuovo Progetto",
            "description": "Descrizione test",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "status": "active",
        }

        response = client.post("/api/v1/projects/", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Nuovo Progetto"
        assert data["status"] == "active"

    def test_get_projects(self, client, sample_project):
        response = client.get("/api/v1/projects/")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == sample_project["name"]


class TestSystem:
    def test_health_check(self, client):
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_root_endpoint(self, client):
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "online"


class TestValidation:
    def test_collaborator_invalid_email(self, client):
        payload = {
            "first_name": "Test",
            "last_name": "User",
            "email": "not-an-email",
            "phone": "1234567890",
            "position": "Tester",
        }

        response = client.post("/api/v1/collaborators/", json=payload)

        assert response.status_code == 422

    def test_collaborator_missing_required_field(self, client):
        payload = {
            "last_name": "User",
            "email": "test.user@gmail.com",
            "phone": "1234567890",
            "position": "Tester",
        }

        response = client.post("/api/v1/collaborators/", json=payload)

        assert response.status_code == 422
        assert "first_name" in str(response.json()).lower()


class TestIntegration:
    def test_full_crud_workflow(self, client):
        create_payload = {
            "first_name": "Integration",
            "last_name": "Test",
            "email": "integration.test@gmail.com",
            "phone": "5555555555",
            "position": "QA",
            "fiscal_code": "TSTNTG85B15H501W",
        }
        create_response = client.post("/api/v1/collaborators/", json=create_payload)
        assert create_response.status_code == 200
        collab_id = create_response.json()["id"]

        read_response = client.get(f"/api/v1/collaborators/{collab_id}")
        assert read_response.status_code == 200
        assert read_response.json()["email"] == "integration.test@gmail.com"

        update_payload = {"position": "Senior QA"}
        update_response = client.put(f"/api/v1/collaborators/{collab_id}", json=update_payload)
        assert update_response.status_code == 200
        assert update_response.json()["position"] == "Senior QA"

        delete_response = client.delete(f"/api/v1/collaborators/{collab_id}")
        assert delete_response.status_code == 200

        verify_response = client.get(f"/api/v1/collaborators/{collab_id}")
        assert verify_response.status_code == 200
        assert verify_response.json()["id"] == collab_id

        active_list_response = client.get("/api/v1/collaborators/?active_only=true")
        assert active_list_response.status_code == 200
        assert active_list_response.json() == []


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
