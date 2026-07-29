"""Correttezza e tempo di risposta di get_attendances_calendar con dataset
generato (migliaia di righe), non dati di produzione reali."""
import time
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import crud
import models
from database import Base

N_COLLABORATORS = 30
N_PROJECTS = 10
N_ATTENDANCES = 3000


@pytest.fixture(scope="module")
def seeded_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    collaborators = []
    for i in range(N_COLLABORATORS):
        c = models.Collaborator(
            first_name=f"Nome{i}", last_name=f"Cognome{i}", email=f"c{i}@test.it",
            fiscal_code=f"FSC{i:013d}",
        )
        db.add(c)
        collaborators.append(c)
    db.commit()

    projects = []
    for i in range(N_PROJECTS):
        p = models.Project(name=f"Progetto {i}", status="active", is_active=True)
        db.add(p)
        projects.append(p)
    db.commit()

    base_date = datetime(2026, 1, 1, 9, 0)
    for i in range(N_ATTENDANCES):
        collaborator = collaborators[i % N_COLLABORATORS]
        project = projects[i % N_PROJECTS]
        when = base_date + timedelta(hours=i)
        db.add(models.Attendance(
            collaborator_id=collaborator.id, project_id=project.id,
            date=when, start_time=when, end_time=when + timedelta(hours=1), hours=1,
        ))
    db.commit()

    yield db, collaborators, projects
    db.close()
    engine.dispose()


def test_conteggio_corretto_su_dataset_ampio_con_filtro_multi(seeded_db):
    db, collaborators, projects = seeded_db
    target_collaborators = [collaborators[0].id, collaborators[1].id]

    items, total = crud.get_attendances_calendar(
        db,
        collaborator_ids=target_collaborators,
        start_date=datetime(2026, 1, 1),
        end_date=datetime(2027, 1, 1),
        limit=50,
    )

    expected_total = sum(
        1 for i in range(N_ATTENDANCES)
        if collaborators[i % N_COLLABORATORS].id in target_collaborators
    )
    assert total == expected_total
    assert len(items) == 50


def test_tempo_risposta_ragionevole_su_dataset_ampio(seeded_db):
    db, _, _ = seeded_db
    start = time.monotonic()
    items, total = crud.get_attendances_calendar(
        db, start_date=datetime(2026, 1, 1), end_date=datetime(2027, 1, 1), limit=100,
    )
    elapsed = time.monotonic() - start

    assert total == N_ATTENDANCES
    assert elapsed < 2.0, f"Query troppo lenta su {N_ATTENDANCES} righe: {elapsed:.2f}s"
