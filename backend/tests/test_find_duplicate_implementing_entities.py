"""
find_duplicate_implementing_entities: normalizzazione + raggruppamento,
sola lettura. Il caso che l'ha motivato: "Next Group srl" (seed placeholder)
e "NEXT GROUP S.R.L." (import Formazienda) sono la stessa azienda ma con
piva diverse e forme societarie scritte diversamente - il match applicativo
in formazienda_upload.py non le accosta, questo script si'.
"""

from pathlib import Path
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import Base
import models  # noqa: F401
from scripts.find_duplicate_implementing_entities import (
    normalizza_partita_iva,
    normalizza_ragione_sociale,
    trova_gruppi_duplicati,
    genera_report,
)


@pytest.fixture()
def db_session(tmp_path):
    db_path = tmp_path / "test_duplicate_entities.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.mark.parametrize(
    "grezzo, atteso",
    [
        ("Next Group srl", "NEXT GROUP"),
        ("NEXT GROUP S.R.L.", "NEXT GROUP"),
        ("Piemmei Scarl", "PIEMMEI"),
        ("Wonder S.p.A.", "WONDER"),
        (None, ""),
    ],
)
def test_normalizza_ragione_sociale_collassa_forme_societarie(grezzo, atteso):
    assert normalizza_ragione_sociale(grezzo) == atteso


def test_normalizza_ragione_sociale_non_collassa_aziende_diverse():
    # Condividono la parola "Group" ma sono aziende diverse: la normalizzazione
    # non deve accorpare tutto cio' che condivide un termine comune.
    assert normalizza_ragione_sociale("Next Group srl") != normalizza_ragione_sociale("Alpha Group S.p.A.")


def test_normalizza_partita_iva_tiene_solo_cifre():
    assert normalizza_partita_iva("IT 06615351217") == "06615351217"
    assert normalizza_partita_iva(None) == ""


def _crea_ente(db_session, ragione_sociale, partita_iva):
    ente = models.ImplementingEntity(ragione_sociale=ragione_sociale, partita_iva=partita_iva)
    db_session.add(ente)
    db_session.commit()
    db_session.refresh(ente)
    return ente


def test_trova_il_duplicato_next_group(db_session):
    placeholder = _crea_ente(db_session, "Next Group srl", "00000000002")
    reale = _crea_ente(db_session, "NEXT GROUP S.R.L.", "06615351217")

    gruppi = trova_gruppi_duplicati(db_session)

    assert "NEXT GROUP" in gruppi
    ids_trovati = {candidato.id for candidato in gruppi["NEXT GROUP"]}
    assert ids_trovati == {placeholder.id, reale.id}


def test_non_segnala_aziende_diverse_come_duplicate(db_session):
    _crea_ente(db_session, "Next Group srl", "00000000002")
    _crea_ente(db_session, "Alpha Group S.p.A.", "12345678901")

    gruppi = trova_gruppi_duplicati(db_session)

    assert gruppi == {}


def test_azienda_senza_duplicati_non_compare(db_session):
    _crea_ente(db_session, "Wonder srl", "11122233344")

    gruppi = trova_gruppi_duplicati(db_session)

    assert gruppi == {}


def test_conta_progetti_collegati_per_candidato(db_session):
    placeholder = _crea_ente(db_session, "Next Group srl", "00000000002")
    reale = _crea_ente(db_session, "NEXT GROUP S.R.L.", "06615351217")
    progetto = models.Project(name="MAXI COMMUNICATION", ente_attuatore_id=placeholder.id)
    db_session.add(progetto)
    db_session.commit()

    gruppi = trova_gruppi_duplicati(db_session)

    per_id = {c.id: c.progetti_collegati for c in gruppi["NEXT GROUP"]}
    assert per_id[placeholder.id] == 1
    assert per_id[reale.id] == 0


def test_report_zero_scritture_e_leggibile(db_session):
    _crea_ente(db_session, "Next Group srl", "00000000002")
    _crea_ente(db_session, "NEXT GROUP S.R.L.", "06615351217")

    conteggio_prima = db_session.query(models.ImplementingEntity).count()
    gruppi = trova_gruppi_duplicati(db_session)
    report = genera_report(gruppi)
    conteggio_dopo = db_session.query(models.ImplementingEntity).count()

    assert conteggio_prima == conteggio_dopo == 2
    assert "NEXT GROUP" in report
    assert "Next Group srl" in report
    assert "NEXT GROUP S.R.L." in report


def test_report_senza_duplicati_lo_dichiara(db_session):
    _crea_ente(db_session, "Wonder srl", "11122233344")

    gruppi = trova_gruppi_duplicati(db_session)
    report = genera_report(gruppi)

    assert "Nessun duplicato rilevato" in report
