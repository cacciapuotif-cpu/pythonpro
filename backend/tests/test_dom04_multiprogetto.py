"""
DOM-04 (W1.6): sblocco multiprogetto.

Un collaboratore PUÒ avere assegnazioni su progetti diversi con periodi
sovrapposti (flusso d'ufficio comune). Restano vietati:
- overlap ORARIO delle presenze (check_attendance_overlap + constraint DB 055)
- overlap di periodo consentito anche su progetti di enti attuatori diversi
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from database import Base
import models
import crud
import schemas

TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


if "users" not in Base.metadata.tables:
    from sqlalchemy import Table

    Table("users", Base.metadata, Column("id", Integer, primary_key=True))


@pytest.fixture
def db_with_data():
    """Database in memoria con 1 collaboratore e 2 progetti (stesso ente)."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    collaborator = models.Collaborator(
        first_name="Mario",
        last_name="Rossi",
        email="mario.rossi@gmail.com",
        fiscal_code="RSSMRA80A01H501U",
        phone="3331234567",
        position="Formatore",
    )
    db.add(collaborator)

    project1 = models.Project(
        name="Corso Informatica",
        description="Progetto formativo A",
        status="active",
    )
    project2 = models.Project(
        name="Corso Management",
        description="Progetto formativo B",
        status="active",
    )
    db.add(project1)
    db.add(project2)
    db.commit()
    db.refresh(collaborator)
    db.refresh(project1)
    db.refresh(project2)

    yield db, collaborator, project1, project2

    db.close()
    Base.metadata.drop_all(bind=engine)


def _make_assignment(db, collaborator_id, project_id, start, end, role="Docente", hourly_rate=50.0, assigned_hours=40.0):
    assignment = models.Assignment(
        collaborator_id=collaborator_id,
        project_id=project_id,
        role=role,
        start_date=start,
        end_date=end,
        hourly_rate=hourly_rate,
        assigned_hours=assigned_hours,
        completed_hours=0.0,
        progress_percentage=0.0,
        is_active=True,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


def test_multiproject_period_overlap_allowed(db_with_data):
    """DOM-04: periodi sovrapposti su progetti diversi (stesso ente) → creazione OK."""
    db, collaborator, project1, project2 = db_with_data

    _make_assignment(
        db, collaborator.id, project1.id,
        start=datetime(2024, 1, 1),
        end=datetime(2024, 2, 28),
    )

    assignment_data = schemas.AssignmentCreate(
        collaborator_id=collaborator.id,
        project_id=project2.id,
        role="Tutor",
        start_date=datetime(2024, 2, 1),
        end_date=datetime(2024, 3, 31),
        hourly_rate=40.0,
        assigned_hours=30.0,
    )

    created = crud.create_assignment(db, assignment_data)

    assert created.id is not None
    assert created.project_id == project2.id


def test_multiproject_update_overlap_allowed(db_with_data):
    """DOM-04: update date che crea overlap cross-progetto (stesso ente) → OK."""
    db, collaborator, project1, project2 = db_with_data

    _make_assignment(
        db, collaborator.id, project1.id,
        start=datetime(2024, 1, 1),
        end=datetime(2024, 2, 28),
    )
    second = _make_assignment(
        db, collaborator.id, project2.id,
        start=datetime(2024, 3, 1),
        end=datetime(2024, 3, 31),
        role="Tutor",
    )

    updated = crud.update_assignment(
        db,
        second.id,
        schemas.AssignmentUpdate(start_date=datetime(2024, 2, 1)),
    )

    assert updated is not None
    assert updated.start_date == datetime(2024, 2, 1)


def test_cross_ente_overlap_allowed(db_with_data):
    """Periodi sovrapposti su enti attuatori diversi sono consentiti."""
    db, collaborator, project1, project2 = db_with_data

    project1.ente_attuatore_id = 1
    project2.ente_attuatore_id = 2
    db.commit()

    _make_assignment(
        db, collaborator.id, project1.id,
        start=datetime(2024, 1, 1),
        end=datetime(2024, 2, 28),
    )

    assignment_data = schemas.AssignmentCreate(
        collaborator_id=collaborator.id,
        project_id=project2.id,
        role="Tutor",
        start_date=datetime(2024, 2, 1),
        end_date=datetime(2024, 3, 31),
        hourly_rate=40.0,
        assigned_hours=30.0,
    )

    created = crud.create_assignment(db, assignment_data)

    assert created.id is not None
    assert created.project_id == project2.id
