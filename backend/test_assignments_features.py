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


def test_assignment_features_flow(client):
    now = datetime.now().replace(microsecond=0, second=0, minute=0)

    collaborator_payload = {
        "first_name": "Mario",
        "last_name": "Rossi",
        "email": "mario.rossi.features@gmail.com",
        "phone": "1234567890",
        "position": "Sviluppatore",
        "fiscal_code": "RSSMRA80A01H501Z",
    }
    response = client.post("/api/v1/collaborators/", json=collaborator_payload)
    assert response.status_code == 200, response.text
    collaborator_id = response.json()["id"]

    project_payload = {
        "name": "Progetto Feature Assignment",
        "description": "Progetto per testare le nuove funzionalita",
        "start_date": now.isoformat(),
        "end_date": (now + timedelta(days=90)).isoformat(),
        "status": "active",
        "cup": "CUPTEST00000001",
        "ente_erogatore": "Test Entity",
    }
    response = client.post("/api/v1/projects/", json=project_payload)
    assert response.status_code == 200, response.text
    project_id = response.json()["id"]

    assignment_payload = {
        "collaborator_id": collaborator_id,
        "project_id": project_id,
        "role": "docente",
        "assigned_hours": 50.0,
        "start_date": now.isoformat(),
        "end_date": (now + timedelta(days=60)).isoformat(),
        "hourly_rate": 35.0,
        "contract_type": "professionale",
    }
    response = client.post("/api/v1/assignments/", json=assignment_payload)
    assert response.status_code == 200, response.text
    assignment_id = response.json()["id"]
    assert response.json()["completed_hours"] == 0.0

    first_day = now + timedelta(days=1)
    attendance_payload = {
        "collaborator_id": collaborator_id,
        "project_id": project_id,
        "assignment_id": assignment_id,
        "date": first_day.isoformat(),
        "start_time": first_day.replace(hour=9).isoformat(),
        "end_time": first_day.replace(hour=14).isoformat(),
        "hours": 5.0,
        "notes": "Test presenza con mansione collegata",
    }
    response = client.post("/api/v1/attendances/", json=attendance_payload)
    assert response.status_code == 200, response.text
    attendance = response.json()
    assert attendance["assignment_id"] == assignment_id

    response = client.get(f"/api/v1/assignments/{assignment_id}")
    assert response.status_code == 200
    assert response.json()["completed_hours"] == 5.0

    for day_offset in [2, 3, 4]:
        day = now + timedelta(days=day_offset)
        attendance_payload = {
            "collaborator_id": collaborator_id,
            "project_id": project_id,
            "assignment_id": assignment_id,
            "date": day.isoformat(),
            "start_time": day.replace(hour=9).isoformat(),
            "end_time": day.replace(hour=13).isoformat(),
            "hours": 4.0,
            "notes": f"Presenza giorno {day_offset}",
        }
        response = client.post("/api/v1/attendances/", json=attendance_payload)
        assert response.status_code == 200, response.text

    response = client.get(f"/api/v1/assignments/{assignment_id}")
    assert response.status_code == 200
    assert response.json()["completed_hours"] == 17.0
