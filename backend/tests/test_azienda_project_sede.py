"""
UX-9b: delivery multi-sede. Per ogni azienda coinvolta in un progetto va
indicata la sede del corso, che puo' essere una sede dell'ente attuatore o
una sede operativa dell'azienda stessa — mai una sede di un'altra entita'.

Prima di questo lavoro il progetto aveva un solo campo libero
`sede_aziendale_*` per l'intero progetto (nessun legame con l'azienda che
frequenta il corso). Quel campo resta invariato per i contratti dei
collaboratori (binario separato, decisione esplicita utente); questi test
coprono solo il nuovo modello azienda -> sede -> allievi.
"""

from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app
from database import Base, get_db
from auth import get_current_user
import models  # noqa: F401


DATE_PROGETTO_VALIDE = {
    "data_approvazione": "2026-03-24",
    "data_avvio_piano": "2026-04-01",
}


@pytest.fixture(scope="function")
def db_session(tmp_path):
    db_path = tmp_path / "test_azienda_project_sede.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
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

    def override_get_current_user():
        return type(
            "TestUser",
            (),
            {
                "id": 1,
                "username": "test-admin",
                "email": "test-admin@example.com",
                "role": "admin",
                "is_active": True,
            },
        )()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def scenario(db_session):
    """Due enti (uno con sede attiva), due aziende ciascuna con una sede propria."""
    ente = models.ImplementingEntity(ragione_sociale="Ente Uno", partita_iva="00000000001")
    altro_ente = models.ImplementingEntity(ragione_sociale="Ente Due", partita_iva="00000000002")
    db_session.add_all([ente, altro_ente])
    db_session.flush()

    sede_ente = models.ImplementingEntityLocation(
        ente_id=ente.id, tipo="operativa", denominazione="Sede Ente Uno", is_active=True,
    )
    sede_altro_ente = models.ImplementingEntityLocation(
        ente_id=altro_ente.id, tipo="operativa", denominazione="Sede Ente Due", is_active=True,
    )
    sede_ente_inattiva = models.ImplementingEntityLocation(
        ente_id=ente.id, tipo="amministrativa", denominazione="Sede Ente Uno dismessa", is_active=False,
    )
    db_session.add_all([sede_ente, sede_altro_ente, sede_ente_inattiva])

    azienda1 = models.AziendaCliente(ragione_sociale="Alpha Srl")
    azienda2 = models.AziendaCliente(ragione_sociale="Beta Srl")
    db_session.add_all([azienda1, azienda2])
    db_session.flush()

    sede_azienda1 = models.AziendaClienteSedeOperativa(azienda_cliente_id=azienda1.id, nome="Alpha - stabilimento")
    sede_azienda1_bis = models.AziendaClienteSedeOperativa(azienda_cliente_id=azienda1.id, nome="Alpha - aula 2")
    sede_azienda2 = models.AziendaClienteSedeOperativa(azienda_cliente_id=azienda2.id, nome="Beta - filiale")
    db_session.add_all([sede_azienda1, sede_azienda1_bis, sede_azienda2])
    db_session.commit()

    return {
        "ente": ente, "altro_ente": altro_ente,
        "sede_ente": sede_ente, "sede_altro_ente": sede_altro_ente, "sede_ente_inattiva": sede_ente_inattiva,
        "azienda1": azienda1, "azienda2": azienda2,
        "sede_azienda1": sede_azienda1, "sede_azienda1_bis": sede_azienda1_bis, "sede_azienda2": sede_azienda2,
    }


def _crea_progetto(client, **overrides):
    payload = {
        "name": "Corso Sede Test",
        "description": "desc",
        "atto_approvazione": "DD 1/2026",
        **DATE_PROGETTO_VALIDE,
        **overrides,
    }
    return client.post("/api/v1/projects/", json=payload)


def test_sede_azienda_propria_accettata(client, scenario):
    resp = _crea_progetto(
        client,
        ente_attuatore_id=scenario["ente"].id,
        azienda_ids=[scenario["azienda1"].id],
        azienda_sedi=[{
            "azienda_id": scenario["azienda1"].id,
            "sede_tipo": "azienda",
            "sede_id": scenario["sede_azienda1"].id,
        }],
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    delivery = body["aziende_delivery"]
    assert len(delivery) == 1
    assert delivery[0]["sedi"][0]["sede_tipo"] == "azienda"
    assert delivery[0]["sedi"][0]["sede_azienda_operativa_id"] == scenario["sede_azienda1"].id
    assert delivery[0]["sedi"][0]["sede_ente_location_id"] is None
    assert "Alpha" in delivery[0]["sedi"][0]["sede_label"]


def test_sede_ente_attuatore_accettata(client, scenario):
    resp = _crea_progetto(
        client,
        ente_attuatore_id=scenario["ente"].id,
        azienda_ids=[scenario["azienda1"].id],
        azienda_sedi=[{
            "azienda_id": scenario["azienda1"].id,
            "sede_tipo": "ente",
            "sede_id": scenario["sede_ente"].id,
        }],
    )
    assert resp.status_code == 200, resp.text
    delivery = resp.json()["aziende_delivery"]
    assert delivery[0]["sedi"][0]["sede_tipo"] == "ente"
    assert delivery[0]["sedi"][0]["sede_ente_location_id"] == scenario["sede_ente"].id


def test_sede_azienda_di_unaltra_azienda_rifiutata(client, scenario):
    """CONFUTATORE: la sede operativa appartiene a Beta, il link e' su Alpha."""
    resp = _crea_progetto(
        client,
        ente_attuatore_id=scenario["ente"].id,
        azienda_ids=[scenario["azienda1"].id],
        azienda_sedi=[{
            "azienda_id": scenario["azienda1"].id,
            "sede_tipo": "azienda",
            "sede_id": scenario["sede_azienda2"].id,
        }],
    )
    assert resp.status_code in (400, 422), resp.text


def test_sede_ente_di_unaltro_ente_rifiutata(client, scenario):
    """CONFUTATORE: la sede appartiene a 'Ente Due', il progetto ha attuatore 'Ente Uno'."""
    resp = _crea_progetto(
        client,
        ente_attuatore_id=scenario["ente"].id,
        azienda_ids=[scenario["azienda1"].id],
        azienda_sedi=[{
            "azienda_id": scenario["azienda1"].id,
            "sede_tipo": "ente",
            "sede_id": scenario["sede_altro_ente"].id,
        }],
    )
    assert resp.status_code in (400, 422), resp.text


def test_sede_ente_inattiva_rifiutata(client, scenario):
    resp = _crea_progetto(
        client,
        ente_attuatore_id=scenario["ente"].id,
        azienda_ids=[scenario["azienda1"].id],
        azienda_sedi=[{
            "azienda_id": scenario["azienda1"].id,
            "sede_tipo": "ente",
            "sede_id": scenario["sede_ente_inattiva"].id,
        }],
    )
    assert resp.status_code in (400, 422), resp.text


def test_sede_ente_senza_ente_attuatore_rifiutata(client, scenario):
    resp = _crea_progetto(
        client,
        azienda_ids=[scenario["azienda1"].id],
        azienda_sedi=[{
            "azienda_id": scenario["azienda1"].id,
            "sede_tipo": "ente",
            "sede_id": scenario["sede_ente"].id,
        }],
    )
    assert resp.status_code in (400, 422), resp.text


def test_sede_per_azienda_non_coinvolta_rifiutata(client, scenario):
    """CONFUTATORE: sede indicata per Beta, ma solo Alpha e' tra azienda_ids."""
    resp = _crea_progetto(
        client,
        ente_attuatore_id=scenario["ente"].id,
        azienda_ids=[scenario["azienda1"].id],
        azienda_sedi=[{
            "azienda_id": scenario["azienda2"].id,
            "sede_tipo": "azienda",
            "sede_id": scenario["sede_azienda2"].id,
        }],
    )
    assert resp.status_code in (400, 422), resp.text


def test_azienda_senza_sede_resta_ammessa(client, scenario):
    """Un'azienda puo' restare coinvolta senza sede definita (UX-9)."""
    resp = _crea_progetto(
        client,
        ente_attuatore_id=scenario["ente"].id,
        azienda_ids=[scenario["azienda1"].id],
    )
    assert resp.status_code == 200, resp.text
    delivery = resp.json()["aziende_delivery"]
    assert delivery[0]["sedi"] == []


def test_due_aziende_sedi_indipendenti(client, scenario):
    """CONFUTATORE: due aziende sullo stesso progetto non devono incrociare le sedi."""
    resp = _crea_progetto(
        client,
        ente_attuatore_id=scenario["ente"].id,
        azienda_ids=[scenario["azienda1"].id, scenario["azienda2"].id],
        azienda_sedi=[
            {"azienda_id": scenario["azienda1"].id, "sede_tipo": "azienda", "sede_id": scenario["sede_azienda1"].id},
            {"azienda_id": scenario["azienda2"].id, "sede_tipo": "ente", "sede_id": scenario["sede_ente"].id},
        ],
    )
    assert resp.status_code == 200, resp.text
    by_azienda = {item["azienda_id"]: item for item in resp.json()["aziende_delivery"]}
    assert by_azienda[scenario["azienda1"].id]["sedi"][0]["sede_tipo"] == "azienda"
    assert by_azienda[scenario["azienda1"].id]["sedi"][0]["sede_azienda_operativa_id"] == scenario["sede_azienda1"].id
    assert by_azienda[scenario["azienda2"].id]["sedi"][0]["sede_tipo"] == "ente"
    assert by_azienda[scenario["azienda2"].id]["sedi"][0]["sede_ente_location_id"] == scenario["sede_ente"].id


def test_stessa_azienda_supporta_due_sedi(client, scenario):
    resp = _crea_progetto(
        client,
        ente_attuatore_id=scenario["ente"].id,
        azienda_ids=[scenario["azienda1"].id],
        azienda_sedi=[
            {"azienda_id": scenario["azienda1"].id, "sede_tipo": "azienda", "sede_id": scenario["sede_azienda1"].id},
            {"azienda_id": scenario["azienda1"].id, "sede_tipo": "azienda", "sede_id": scenario["sede_azienda1_bis"].id},
            {"azienda_id": scenario["azienda1"].id, "sede_tipo": "ente", "sede_id": scenario["sede_ente"].id},
        ],
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["aziende_delivery"][0]["sedi"]) == 3


def test_update_cambia_sede_esistente(client, scenario):
    creato = _crea_progetto(
        client,
        ente_attuatore_id=scenario["ente"].id,
        azienda_ids=[scenario["azienda1"].id],
        azienda_sedi=[{
            "azienda_id": scenario["azienda1"].id,
            "sede_tipo": "azienda",
            "sede_id": scenario["sede_azienda1"].id,
        }],
    )
    assert creato.status_code == 200, creato.text
    project_id = creato.json()["id"]

    aggiornato = client.put(
        f"/api/v1/projects/{project_id}",
        json={
            "azienda_ids": [scenario["azienda1"].id],
            "azienda_sedi": [{
                "azienda_id": scenario["azienda1"].id,
                "sede_tipo": "ente",
                "sede_id": scenario["sede_ente"].id,
            }],
        },
    )
    assert aggiornato.status_code == 200, aggiornato.text
    delivery = aggiornato.json()["aziende_delivery"]
    assert delivery[0]["sedi"][0]["sede_tipo"] == "ente"
    assert delivery[0]["sedi"][0]["sede_ente_location_id"] == scenario["sede_ente"].id


def test_update_senza_azienda_sedi_non_tocca_sede_esistente(client, scenario):
    """CONFUTATORE: un update che non passa azienda_sedi non deve azzerare quella gia' salvata."""
    creato = _crea_progetto(
        client,
        ente_attuatore_id=scenario["ente"].id,
        azienda_ids=[scenario["azienda1"].id],
        azienda_sedi=[{
            "azienda_id": scenario["azienda1"].id,
            "sede_tipo": "azienda",
            "sede_id": scenario["sede_azienda1"].id,
        }],
    )
    project_id = creato.json()["id"]

    aggiornato = client.put(
        f"/api/v1/projects/{project_id}",
        json={"name": "Corso Sede Test rinominato"},
    )
    assert aggiornato.status_code == 200, aggiornato.text
    delivery = aggiornato.json()["aziende_delivery"]
    assert delivery[0]["sedi"][0]["sede_tipo"] == "azienda"
    assert delivery[0]["sedi"][0]["sede_azienda_operativa_id"] == scenario["sede_azienda1"].id


def test_rimuovere_azienda_rimuove_anche_la_sua_sede(client, scenario):
    creato = _crea_progetto(
        client,
        ente_attuatore_id=scenario["ente"].id,
        azienda_ids=[scenario["azienda1"].id, scenario["azienda2"].id],
        azienda_sedi=[
            {"azienda_id": scenario["azienda1"].id, "sede_tipo": "azienda", "sede_id": scenario["sede_azienda1"].id},
            {"azienda_id": scenario["azienda2"].id, "sede_tipo": "azienda", "sede_id": scenario["sede_azienda2"].id},
        ],
    )
    project_id = creato.json()["id"]

    aggiornato = client.put(
        f"/api/v1/projects/{project_id}",
        json={"azienda_ids": [scenario["azienda1"].id]},
    )
    assert aggiornato.status_code == 200, aggiornato.text
    delivery = aggiornato.json()["aziende_delivery"]
    assert len(delivery) == 1
    assert delivery[0]["azienda_id"] == scenario["azienda1"].id


def test_creazione_sede_azienda_al_volo_resta_in_anagrafica(client, db_session, scenario):
    response = client.post(
        f"/api/v1/aziende-clienti/{scenario['azienda1'].id}/sedi-operative",
        json={
            "nome": "Alpha - aula creata dal Delivery",
            "indirizzo": "Via Verdi 10",
            "citta": "Napoli",
            "provincia": "NA",
            "cap": "80100",
        },
    )
    assert response.status_code == 201, response.text
    sede_id = response.json()["id"]
    persisted = db_session.query(models.AziendaClienteSedeOperativa).filter_by(id=sede_id).one()
    assert persisted.azienda_cliente_id == scenario["azienda1"].id
    assert persisted.nome == "Alpha - aula creata dal Delivery"
