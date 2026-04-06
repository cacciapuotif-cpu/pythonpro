"""
Test per la validazione overlap nelle assegnazioni collaboratori.

Verifica:
1. Assegnazioni su date diverse → OK
2. Assegnazioni sovrapposte su progetti diversi → ValueError
3. Assegnazioni sovrapposte sullo STESSO progetto → OK (ruoli diversi permessi)
4. Presenza fuori dal range dell'assegnazione → ValueError
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base
import models
import crud
import schemas

# Database SQLite in memoria per i test
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db_with_data():
    """Crea database in memoria con 1 collaboratore e 2 progetti."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    collaborator = models.Collaborator(
        first_name="Mario",
        last_name="Rossi",
        email="mario.rossi@test.com",
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
    """Helper: crea un'assegnazione direttamente nel DB senza passare per crud."""
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


def test_no_overlap_different_dates(db_with_data):
    """Assegnazioni su periodi non sovrapposti su progetti diversi → non solleva eccezione."""
    db, collaborator, project1, project2 = db_with_data

    # Prima assegnazione: gennaio
    _make_assignment(
        db, collaborator.id, project1.id,
        start=datetime(2024, 1, 1),
        end=datetime(2024, 1, 31),
    )

    # Seconda assegnazione: febbraio (diverso progetto, date non sovrapposte)
    result = crud.check_assignment_overlap(
        db,
        collaborator_id=collaborator.id,
        start_date=datetime(2024, 2, 1),
        end_date=datetime(2024, 2, 28),
        project_id=project2.id,
    )

    assert result is None


def test_overlap_different_projects_blocked(db_with_data):
    """Assegnazioni sovrapposte su progetti diversi → ValueError al momento della creazione."""
    db, collaborator, project1, project2 = db_with_data

    # Prima assegnazione: 1 gennaio – 28 febbraio su project1
    _make_assignment(
        db, collaborator.id, project1.id,
        start=datetime(2024, 1, 1),
        end=datetime(2024, 2, 28),
    )

    # Tentativo di creare assegnazione sovrapposta su project2
    assignment_data = schemas.AssignmentCreate(
        collaborator_id=collaborator.id,
        project_id=project2.id,
        role="Tutor",
        start_date=datetime(2024, 2, 1),
        end_date=datetime(2024, 3, 31),
        hourly_rate=40.0,
        assigned_hours=30.0,
    )

    with pytest.raises(ValueError) as exc_info:
        crud.create_assignment(db, assignment_data)

    assert "già un'assegnazione attiva" in str(exc_info.value)


def test_overlap_same_project_allowed(db_with_data):
    """Assegnazioni sovrapposte sullo STESSO progetto (ruoli diversi) → permesse."""
    db, collaborator, project1, _ = db_with_data

    # Prima assegnazione sullo stesso progetto
    _make_assignment(
        db, collaborator.id, project1.id,
        start=datetime(2024, 1, 1),
        end=datetime(2024, 3, 31),
        role="Docente",
    )

    # check_assignment_overlap non deve segnalare nulla per lo stesso progetto
    result = crud.check_assignment_overlap(
        db,
        collaborator_id=collaborator.id,
        start_date=datetime(2024, 2, 1),
        end_date=datetime(2024, 4, 30),
        project_id=project1.id,
    )

    assert result is None


def test_attendance_outside_assignment_range(db_with_data):
    """Presenza con data fuori dal periodo dell'assegnazione → ValueError."""
    db, collaborator, project1, _ = db_with_data

    assignment = _make_assignment(
        db, collaborator.id, project1.id,
        start=datetime(2024, 3, 1),
        end=datetime(2024, 3, 31),
    )

    # Data fuori range (aprile, mentre l'assegnazione è solo a marzo)
    with pytest.raises(ValueError) as exc_info:
        crud.validate_attendance_in_assignment_range(
            db,
            attendance_date=datetime(2024, 4, 15),
            assignment_id=assignment.id,
        )

    assert "non rientra nel periodo" in str(exc_info.value)
