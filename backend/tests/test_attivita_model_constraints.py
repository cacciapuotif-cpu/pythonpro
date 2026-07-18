"""Vincoli DB del sottosistema attivita, verificati su SQLite con FK attive."""

from pathlib import Path
import sys

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import auth
import models


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'attivita-constraints.db'}")
    event.listen(
        engine,
        "connect",
        lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"),
    )
    for table in (
        models.Collaborator.__table__,
        models.ImplementingEntity.__table__,
        models.Avviso.__table__,
        models.AvvisoRevisione.__table__,
        models.AvvisoScadenza.__table__,
        auth.User.__table__,
        models.Project.__table__,
        models.AgentRun.__table__,
        models.AgentSuggestion.__table__,
        models.Playbook.__table__,
        models.PlaybookVersione.__table__,
        models.PlaybookVoce.__table__,
        models.AttivitaOperativa.__table__,
        models.AttivitaEvento.__table__,
    ):
        table.create(bind=engine, checkfirst=True)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _actor_and_project(db):
    actor = auth.User(
        username="vincoli-attivita",
        email="vincoli-attivita@example.test",
        hashed_password="not-used",
        role="admin",
    )
    project = models.Project(name="Progetto vincoli")
    db.add_all([actor, project])
    db.commit()
    return actor, project


@pytest.mark.parametrize(
    "fase,titolo",
    [("fase-inesistente", "Titolo"), ("avvio", "   ")],
)
def test_activity_rejects_invalid_phase_and_empty_title(db, fase, titolo):
    actor, project = _actor_and_project(db)
    db.add(
        models.AttivitaOperativa(
            project_id=project.id,
            fase=fase,
            titolo=titolo,
            created_by_user_id=actor.id,
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()


def test_completed_activity_requires_human_and_timestamp(db):
    actor, project = _actor_and_project(db)
    db.add(
        models.AttivitaOperativa(
            project_id=project.id,
            fase="avvio",
            titolo="Completamento invalido",
            stato="completata",
            created_by_user_id=actor.id,
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()


def test_event_requires_user_or_agent_actor(db):
    actor, project = _actor_and_project(db)
    activity = models.AttivitaOperativa(
        project_id=project.id,
        fase="avvio",
        titolo="Evento",
        created_by_user_id=actor.id,
    )
    db.add(activity)
    db.commit()
    db.add(
        models.AttivitaEvento(
            attivita_id=activity.id,
            tipo_evento="nota",
            payload={"nota": "senza attore"},
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()


def test_activity_title_is_unique_per_project_and_phase(db):
    actor, project = _actor_and_project(db)
    db.add_all(
        [
            models.AttivitaOperativa(
                project_id=project.id,
                fase="gestione",
                titolo="Titolo unico",
                created_by_user_id=actor.id,
            ),
            models.AttivitaOperativa(
                project_id=project.id,
                fase="gestione",
                titolo="Titolo unico",
                created_by_user_id=actor.id,
            ),
        ]
    )
    with pytest.raises(IntegrityError):
        db.commit()
