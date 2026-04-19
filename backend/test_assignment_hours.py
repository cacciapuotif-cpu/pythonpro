import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import Column, Integer, Table, create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from main import app
import models  # noqa: F401


if "users" not in Base.metadata.tables:
    Table("users", Base.metadata, Column("id", Integer, primary_key=True))


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
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_assignment_completed_hours_flow(client):
    today = datetime.now().replace(microsecond=0, second=0, minute=0)
    assignment_start = today
    assignment_end = today + timedelta(days=30)
    day1 = today + timedelta(days=1)
    day2 = today + timedelta(days=2)
    day3 = today + timedelta(days=3)

    collab_data = {
        "first_name": "Mario",
        "last_name": "Rossi",
        "email": "mario.rossi.hours@gmail.com",
        "phone": "1234567890",
        "position": "Docente",
        "fiscal_code": "RSSMRA80A01H501Z",
    }
    response = client.post("/api/v1/collaborators/", json=collab_data)
    assert response.status_code == 200, response.text
    collaborator_id = response.json()["id"]

    project_data = {
        "name": "Progetto Test Ore",
        "description": "Progetto per test mansioni",
        "status": "active",
    }
    response = client.post("/api/v1/projects/", json=project_data)
    assert response.status_code == 200, response.text
    project_id = response.json()["id"]

    assignment_data = {
        "collaborator_id": collaborator_id,
        "project_id": project_id,
        "role": "docente",
        "assigned_hours": 20.0,
        "start_date": assignment_start.isoformat(),
        "end_date": assignment_end.isoformat(),
        "hourly_rate": 25.0,
        "contract_type": "professionale",
    }
    response = client.post("/api/v1/assignments/", json=assignment_data)
    assert response.status_code == 200, response.text
    assignment_id = response.json()["id"]
    assert response.json()["completed_hours"] == 0.0

    attendance1_data = {
        "collaborator_id": collaborator_id,
        "project_id": project_id,
        "assignment_id": assignment_id,
        "date": day1.isoformat(),
        "start_time": day1.replace(hour=9).isoformat(),
        "end_time": day1.replace(hour=14).isoformat(),
        "hours": 5.0,
        "notes": "Prima presenza di test",
    }
    response = client.post("/api/v1/attendances/", json=attendance1_data)
    assert response.status_code == 200, response.text
    attendance1_id = response.json()["id"]

    response = client.get(f"/api/v1/assignments/{assignment_id}")
    assert response.status_code == 200
    assert response.json()["completed_hours"] == 5.0

    attendance2_data = {
        "collaborator_id": collaborator_id,
        "project_id": project_id,
        "assignment_id": assignment_id,
        "date": day2.isoformat(),
        "start_time": day2.replace(hour=9).isoformat(),
        "end_time": day2.replace(hour=12).isoformat(),
        "hours": 3.0,
        "notes": "Seconda presenza di test",
    }
    response = client.post("/api/v1/attendances/", json=attendance2_data)
    assert response.status_code == 200, response.text
    attendance2_id = response.json()["id"]

    response = client.get(f"/api/v1/assignments/{assignment_id}")
    assert response.status_code == 200
    assert response.json()["completed_hours"] == 8.0

    update_data = {
        "hours": 7.0,
        "end_time": day1.replace(hour=16).isoformat(),
    }
    response = client.put(f"/api/v1/attendances/{attendance1_id}", json=update_data)
    assert response.status_code == 200, response.text

    response = client.get(f"/api/v1/assignments/{assignment_id}")
    assert response.status_code == 200
    assert response.json()["completed_hours"] == 10.0

    response = client.delete(f"/api/v1/attendances/{attendance2_id}")
    assert response.status_code == 200, response.text

    response = client.get(f"/api/v1/assignments/{assignment_id}")
    assert response.status_code == 200
    assert response.json()["completed_hours"] == 7.0

    invalid_data = {
        "collaborator_id": collaborator_id,
        "project_id": project_id,
        "date": day3.isoformat(),
        "start_time": day3.replace(hour=9).isoformat(),
        "end_time": day3.replace(hour=14).isoformat(),
        "hours": 5.0,
    }
    response = client.post("/api/v1/attendances/", json=invalid_data)
    assert response.status_code == 200, response.text
