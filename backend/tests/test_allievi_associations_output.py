"""Contratto Allievi: azienda corrente e tutte le partecipazioni progetto."""

from pathlib import Path
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import crud
from database import Base
import models
import schemas


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'allievi-associazioni.db'}",
        connect_args={"check_same_thread": False},
    )
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def prepara_allievo(db_session):
    azienda_attuale = models.AziendaCliente(
        ragione_sociale="Power Impianti srl",
        attivo=True,
    )
    nuova_azienda = models.AziendaCliente(
        ragione_sociale="Nuova Azienda srl",
        attivo=True,
    )
    progetto_attivo = models.Project(
        name="MAXI COMMUNICATION",
        status="active",
        is_active=True,
    )
    progetto_storico = models.Project(
        name="MAXI COMMUNICATION",
        status="cancelled",
        is_active=False,
    )
    allievo = models.Allievo(
        nome="GIOVANNI",
        cognome="CARUSO",
        occupato=True,
        azienda_cliente=azienda_attuale,
        attivo=True,
        projects=[progetto_storico, progetto_attivo],
    )
    db_session.add_all([
        azienda_attuale,
        nuova_azienda,
        progetto_attivo,
        progetto_storico,
        allievo,
    ])
    db_session.commit()
    return allievo, nuova_azienda, progetto_attivo, progetto_storico


def test_output_espone_azienda_corrente_e_tutti_i_progetti(db_session):
    allievo, _nuova, progetto_attivo, progetto_storico = prepara_allievo(db_session)

    payload = schemas.Allievo.model_validate(
        crud.get_allievo(db_session, allievo.id)
    ).model_dump()

    assert payload["azienda_cliente"] == {
        "id": allievo.azienda_cliente_id,
        "ragione_sociale": "Power Impianti srl",
    }
    assert {
        (project["id"], project["status"], project["is_active"])
        for project in payload["projects"]
    } == {
        (progetto_attivo.id, "active", True),
        (progetto_storico.id, "cancelled", False),
    }


def test_cambio_azienda_non_cancella_partecipazioni_storiche(db_session):
    allievo, nuova_azienda, progetto_attivo, progetto_storico = prepara_allievo(
        db_session
    )

    aggiornato = crud.update_allievo(
        db_session,
        allievo.id,
        schemas.AllievoUpdate(
            azienda_cliente_id=nuova_azienda.id,
            project_ids=[progetto_storico.id, progetto_attivo.id],
        ),
    )

    assert aggiornato.azienda_cliente_id == nuova_azienda.id
    assert {project.id for project in aggiornato.projects} == {
        progetto_attivo.id,
        progetto_storico.id,
    }


def test_non_si_puo_aggiungere_un_nuovo_progetto_gia_archiviato(db_session):
    allievo, _nuova, progetto_attivo, progetto_storico = prepara_allievo(db_session)
    storico_estraneo = models.Project(
        name="Storico estraneo",
        status="cancelled",
        is_active=False,
    )
    db_session.add(storico_estraneo)
    db_session.commit()

    with pytest.raises(ValueError, match="non più associabili"):
        crud.update_allievo(
            db_session,
            allievo.id,
            schemas.AllievoUpdate(
                project_ids=[
                    progetto_attivo.id,
                    progetto_storico.id,
                    storico_estraneo.id,
                ],
            ),
        )


def test_non_si_puo_aggiungere_un_progetto_attivo_di_altra_azienda(db_session):
    allievo, _nuova, progetto_attivo, progetto_storico = prepara_allievo(db_session)
    progetto_estraneo = models.Project(
        name="Progetto attivo di altra azienda",
        status="active",
        is_active=True,
    )
    db_session.add(progetto_estraneo)
    db_session.commit()

    with pytest.raises(ValueError, match="non associati all'azienda corrente"):
        crud.update_allievo(
            db_session,
            allievo.id,
            schemas.AllievoUpdate(
                project_ids=[
                    progetto_attivo.id,
                    progetto_storico.id,
                    progetto_estraneo.id,
                ],
            ),
        )


def test_si_puo_aggiungere_un_progetto_attivo_dell_azienda_corrente(db_session):
    allievo, _nuova, progetto_attivo, progetto_storico = prepara_allievo(db_session)
    progetto_nuovo = models.Project(
        name="Nuovo progetto Power",
        status="active",
        is_active=True,
    )
    db_session.add(progetto_nuovo)
    db_session.flush()
    db_session.add(models.AziendaClienteProjectLink(
        azienda_cliente_id=allievo.azienda_cliente_id,
        project_id=progetto_nuovo.id,
    ))
    db_session.commit()

    aggiornato = crud.update_allievo(
        db_session,
        allievo.id,
        schemas.AllievoUpdate(
            project_ids=[
                progetto_attivo.id,
                progetto_storico.id,
                progetto_nuovo.id,
            ],
        ),
    )

    assert {project.id for project in aggiornato.projects} == {
        progetto_attivo.id,
        progetto_storico.id,
        progetto_nuovo.id,
    }
