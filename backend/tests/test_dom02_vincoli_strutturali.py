"""DOM-02 / DOM-19 — vincoli strutturali della catena operativa."""

from datetime import datetime
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

from auth import get_current_user
from database import Base, get_db
from main import app
import crud
import models
import schemas


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'dom02.db'}",
        connect_args={"check_same_thread": False},
    )
    session_factory = sessionmaker(
        autocommit=False, autoflush=False, expire_on_commit=False, bind=engine
    )
    Base.metadata.create_all(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    def override_get_current_user():
        return type("User", (), {"id": 1, "role": "admin", "is_active": True})()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def base(db_session):
    collaborator = models.Collaborator(
        first_name="Ada",
        last_name="Rossi",
        email="ada.rossi@example.com",
        fiscal_code="RSSDAA80A01H501Q",
        phone="3331234567",
        position="Docente",
    )
    project = models.Project(
        name="DOM-02",
        description="Vincoli strutturali",
        status="active",
        start_date=datetime(2026, 7, 1),
        end_date=datetime(2026, 7, 31),
    )
    db_session.add_all([collaborator, project])
    db_session.commit()
    assignment = crud.create_assignment(
        db_session,
        schemas.AssignmentCreate(
            collaborator_id=collaborator.id,
            project_id=project.id,
            role="Docenza",
            assigned_hours=20,
            start_date=project.start_date,
            end_date=project.end_date,
            hourly_rate=50,
        ),
    )
    return collaborator, project, assignment


def attendance_payload(collaborator, project, assignment, day=10):
    return schemas.AttendanceCreate(
        collaborator_id=collaborator.id,
        project_id=project.id,
        assignment_id=assignment.id if assignment else None,
        date=datetime(2026, 7, day),
        start_time=datetime(2026, 7, day, 9),
        end_time=datetime(2026, 7, day, 13),
        hours=4,
    )


class TestVincoliPresenzaProgetto:
    def test_create_fuori_date_progetto_bloccata(self, db_session, base):
        collaborator, project, assignment = base
        payload = attendance_payload(collaborator, project, assignment)
        payload.date = datetime(2026, 8, 1)
        payload.start_time = datetime(2026, 8, 1, 9)
        payload.end_time = datetime(2026, 8, 1, 13)
        assignment.end_date = datetime(2026, 8, 2)  # isola il limite progetto
        db_session.commit()

        with pytest.raises(ValueError, match="periodo del progetto"):
            crud.create_attendance(db_session, payload)
        assert db_session.query(models.Attendance).count() == 0

    def test_update_fuori_date_progetto_bloccata(self, db_session, base):
        collaborator, project, assignment = base
        attendance = crud.create_attendance(
            db_session, attendance_payload(collaborator, project, assignment)
        )
        assignment.end_date = datetime(2026, 8, 2)
        db_session.commit()

        with pytest.raises(ValueError, match="periodo del progetto"):
            crud.update_attendance(
                db_session,
                attendance.id,
                schemas.AttendanceUpdate(
                    date=datetime(2026, 8, 1),
                    start_time=datetime(2026, 8, 1, 9),
                    end_time=datetime(2026, 8, 1, 13),
                ),
            )

    @pytest.mark.parametrize("missing", ["start_date", "end_date"])
    def test_date_progetto_obbligatorie(self, db_session, base, missing):
        collaborator, project, assignment = base
        setattr(project, missing, None)
        db_session.commit()
        with pytest.raises(ValueError, match="date di inizio e fine"):
            crud.create_attendance(
                db_session, attendance_payload(collaborator, project, assignment)
            )

    @pytest.mark.parametrize("status", ["paused", "completed", "cancelled"])
    def test_progetto_non_active_blocca_presenza(self, db_session, base, status):
        collaborator, project, assignment = base
        project.status = status
        db_session.commit()
        with pytest.raises(ValueError, match="non è attivo"):
            crud.create_attendance(
                db_session, attendance_payload(collaborator, project, assignment)
            )


    def test_progetto_non_active_blocca_anche_update(self, db_session, base):
        collaborator, project, assignment = base
        attendance = crud.create_attendance(
            db_session, attendance_payload(collaborator, project, assignment)
        )
        project.status = "cancelled"
        db_session.commit()

        with pytest.raises(ValueError, match="non è attivo"):
            crud.update_attendance(
                db_session, attendance.id, schemas.AttendanceUpdate(hours=3)
            )


class TestAssignmentIntegrity:
    def test_riduzione_ore_sotto_completate_restituisce_422(
        self, client, db_session, base
    ):
        collaborator, project, assignment = base
        crud.create_attendance(
            db_session, attendance_payload(collaborator, project, assignment)
        )
        response = client.patch(
            f"/api/v1/assignments/{assignment.id}", json={"assigned_hours": 3}
        )
        assert response.status_code == 422, response.text
        db_session.expire_all()
        assert float(crud.get_assignment(db_session, assignment.id).assigned_hours) == 20

    def test_ore_totali_progetto_seguono_create_e_update_assignment(
        self, db_session, base
    ):
        collaborator, project, assignment = base
        db_session.refresh(project)
        assert float(project.ore_totali) == 20

        crud.update_assignment(
            db_session,
            assignment.id,
            schemas.AssignmentUpdate(assigned_hours=30),
        )
        db_session.refresh(project)
        assert float(project.ore_totali) == 30
    def test_ore_totali_progetto_seguono_delete_assignment(self, db_session, base):
        collaborator, project, assignment = base
        db_session.refresh(project)
        assert float(project.ore_totali) == 20

        crud.delete_assignment(db_session, assignment.id)
        db_session.refresh(project)
        assert float(project.ore_totali) == 0
