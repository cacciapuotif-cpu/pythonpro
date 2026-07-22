"""NEW-029 — la colonna relitto ``piani_finanziari.legacy_template_id`` e' stata
migrata (valore preservato in ``audit_logs``) e droppata dalla migration 062.

Qui si verifica il contratto del modello:
- ``PianoFinanziario`` non espone piu' ``legacy_template_id`` (ne' colonna ne' attr);
- la creazione di un piano funziona senza il campo (regressione).
"""

from datetime import datetime
from pathlib import Path
import sys

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from database import Base


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine(
        "sqlite:///{}".format(tmp_path / "new029.db"),
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_connection, _record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_piano_finanziario_model_has_no_legacy_template_id():
    columns = set(models.PianoFinanziario.__table__.columns.keys())
    assert "legacy_template_id" not in columns
    assert not hasattr(models.PianoFinanziario, "legacy_template_id")


def test_create_piano_without_legacy_template_id(db_session):
    project = models.Project(name="Progetto NEW-029")
    db_session.add(project)
    db_session.commit()

    piano = models.PianoFinanziario(
        progetto_id=project.id,
        anno=2026,
        nome="Piano NEW-029",
        ente_erogatore="Formazienda",
        data_inizio=datetime(2026, 7, 1),
        data_fine=datetime(2026, 7, 31),
    )
    db_session.add(piano)
    db_session.commit()

    assert piano.id is not None
