"""FASE E1 (Task E1.1) — modello PianoFinanziarioTemplate e vincoli.

Copre:
- unicità (nome, versione)
- round-trip JSON di struttura_voci
- CheckConstraint versione > 0

Il seed (services/piano_templates.py::seed_templates) è di un task successivo:
qui si verifica solo il contratto del modello.
"""

from pathlib import Path
import sys

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from database import Base


VOCI_STANDARD = [
    {"categoria": "docenza", "descrizione": "Docenza d'aula", "macrovoce": "A"},
    {"categoria": "tutoraggio", "descrizione": "Tutoraggio", "macrovoce": "A"},
    {"categoria": "coordinamento", "descrizione": "Coordinamento", "macrovoce": "B"},
    {"categoria": "materiali", "descrizione": "Materiali didattici", "macrovoce": "B"},
]


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine(
        "sqlite:///{}".format(tmp_path / "piano_templates.db"),
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def make_template(db_session, *, nome="Template FAPI generico", versione=1, commit=True, **extra):
    obj = models.PianoFinanziarioTemplate(
        nome=nome,
        tipo_fondo=extra.pop("tipo_fondo", "fapi"),
        versione=versione,
        struttura_voci=extra.pop("struttura_voci", VOCI_STANDARD),
        **extra,
    )
    db_session.add(obj)
    if commit:
        db_session.commit()
    return obj


def test_template_versionato_unico(db_session):
    make_template(db_session, nome="Template FAPI generico", versione=1)
    make_template(db_session, nome="Template FAPI generico", versione=2)  # nuova versione ok

    duplicate = models.PianoFinanziarioTemplate(
        nome="Template FAPI generico",
        tipo_fondo="fapi",
        versione=1,
        struttura_voci=VOCI_STANDARD,
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_template_struttura_voci_json_round_trip(db_session):
    created = make_template(db_session, nome="Template Formazienda", tipo_fondo="formazienda")
    db_session.expire_all()

    reloaded = (
        db_session.query(models.PianoFinanziarioTemplate)
        .filter(models.PianoFinanziarioTemplate.id == created.id)
        .one()
    )
    assert reloaded.struttura_voci == VOCI_STANDARD
    assert reloaded.struttura_voci[0]["categoria"] == "docenza"
    assert reloaded.versione == 1
    assert reloaded.is_active is True


def test_versione_zero_o_negativa_rifiutata(db_session):
    for bad in (0, -1):
        obj = models.PianoFinanziarioTemplate(
            nome=f"Template versione {bad}",
            tipo_fondo="fondimpresa",
            versione=bad,
            struttura_voci=VOCI_STANDARD,
        )
        db_session.add(obj)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()
