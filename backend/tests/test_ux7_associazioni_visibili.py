"""UX-7 — le associazioni salvate devono essere anche leggibili dall'API.

Bug osservato in uso reale: dopo aver associato aziende e allievi a un
progetto, la scheda continua a mostrare "Nessuna azienda associata" /
"Nessun allievo associato".

Diagnosi: **non e' un problema di scrittura**. Le righe esistono
(``azienda_cliente_projects`` e ``allievo_project``), scrittura e lettura
usano la stessa relazione canonica e ``crud.get_project(s)`` fa gia' il
``selectinload`` di entrambe. Il difetto e' nella serializzazione: lo schema
di risposta ``schemas.Project`` espone solo ``azienda_ids``/``allievo_ids``
(interi), mentre la scheda progetto legge ``project.aziende_coinvolte`` e
``project.allievi_coinvolti`` — campi che l'API non ha mai restituito. Erano
quindi sempre ``undefined``, e il ramo "nessuno" scattava a prescindere dai
dati.

Questi test bloccano il contratto: chi legge il progetto deve poter mostrare
CHI e' associato, non solo quanti id.
"""

from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app
from database import Base, get_db
from auth import get_current_user
import models  # noqa: F401 - registra i modelli sul Base


@pytest.fixture
def engine(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'ux7.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db_session(engine):
    factory = sessionmaker(
        autocommit=False, autoflush=False, bind=engine, expire_on_commit=False
    )
    session = factory()
    try:
        yield session
    finally:
        session.close()


def _fake_user(role="admin"):
    return type(
        "TestUser",
        (),
        {
            "id": 1,
            "username": f"test-{role}",
            "email": f"test-{role}@example.com",
            "role": role,
            "is_active": True,
        },
    )()


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: _fake_user("admin")
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def scenario(db_session):
    """Un progetto con 2 aziende e 3 allievi associati."""
    aziende = [
        models.AziendaCliente(ragione_sociale="Alfa Srl", partita_iva="11111111111", attivo=True),
        models.AziendaCliente(ragione_sociale="Beta Spa", partita_iva="22222222222", attivo=True),
    ]
    db_session.add_all(aziende)
    db_session.flush()

    allievi = [
        models.Allievo(nome="Ada", cognome="Rossi", codice_fiscale="RSSDAA80A41H501Q",
                       azienda_cliente_id=aziende[0].id, attivo=True),
        models.Allievo(nome="Bruno", cognome="Verdi", codice_fiscale="VRDBRN80A01H501Q",
                       azienda_cliente_id=aziende[0].id, attivo=True),
        models.Allievo(nome="Carla", cognome="Neri", codice_fiscale="NRECRL80A41H501Q",
                       azienda_cliente_id=aziende[1].id, attivo=True),
    ]
    db_session.add_all(allievi)
    db_session.flush()

    project = models.Project(name="Progetto UX-7", status="active")
    db_session.add(project)
    db_session.flush()

    for azienda in aziende:
        db_session.add(models.AziendaClienteProjectLink(
            azienda_cliente_id=azienda.id, project_id=project.id
        ))
    project.allievi_coinvolti = allievi
    db_session.commit()

    return {"project": project, "aziende": aziende, "allievi": allievi}


def test_dettaglio_progetto_espone_le_aziende_associate(client, scenario):
    resp = client.get(f"/api/v1/projects/{scenario['project'].id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    ragioni = {a["ragione_sociale"] for a in body["aziende_coinvolte"]}
    assert ragioni == {"Alfa Srl", "Beta Spa"}


def test_dettaglio_progetto_espone_gli_allievi_associati(client, scenario):
    resp = client.get(f"/api/v1/projects/{scenario['project'].id}")
    body = resp.json()

    nomi = {f"{a['nome']} {a['cognome']}" for a in body["allievi_coinvolti"]}
    assert nomi == {"Ada Rossi", "Bruno Verdi", "Carla Neri"}


def test_allievo_porta_la_propria_azienda(client, scenario):
    """Serve all'albero azienda -> allievi (UX-9) senza una seconda chiamata."""
    body = client.get(f"/api/v1/projects/{scenario['project'].id}").json()
    per_nome = {a["nome"]: a for a in body["allievi_coinvolti"]}
    assert per_nome["Ada"]["azienda_cliente_id"] == scenario["aziende"][0].id
    assert per_nome["Carla"]["azienda_cliente_id"] == scenario["aziende"][1].id


def test_anche_il_listing_espone_gli_associati(client, scenario):
    """La scheda progetto si legge dal listing: se manca li', il bug resta."""
    resp = client.get("/api/v1/projects/")
    assert resp.status_code == 200, resp.text
    progetto = next(p for p in resp.json() if p["id"] == scenario["project"].id)

    assert len(progetto["aziende_coinvolte"]) == 2
    assert len(progetto["allievi_coinvolti"]) == 3


def test_gli_id_restano_coerenti_con_gli_oggetti(client, scenario):
    body = client.get(f"/api/v1/projects/{scenario['project'].id}").json()
    assert sorted(body["azienda_ids"]) == sorted(a["id"] for a in body["aziende_coinvolte"])
    assert sorted(body["allievo_ids"]) == sorted(a["id"] for a in body["allievi_coinvolti"])


def test_il_conteggio_regge_una_rilettura(client, scenario):
    """Equivale al ricaricare la pagina: nessun contatore di comodo."""
    prima = client.get(f"/api/v1/projects/{scenario['project'].id}").json()
    dopo = client.get(f"/api/v1/projects/{scenario['project'].id}").json()
    assert len(prima["aziende_coinvolte"]) == len(dopo["aziende_coinvolte"]) == 2
    assert len(prima["allievi_coinvolti"]) == len(dopo["allievi_coinvolti"]) == 3


def test_progetto_senza_associazioni_resta_vuoto(client, db_session):
    vuoto = models.Project(name="Senza associati", status="active")
    db_session.add(vuoto)
    db_session.commit()

    body = client.get(f"/api/v1/projects/{vuoto.id}").json()
    assert body["aziende_coinvolte"] == []
    assert body["allievi_coinvolti"] == []


def test_il_listing_non_fa_una_query_per_progetto(client, db_session, engine, scenario):
    """Regressione N+1: gli associati sono gia' in selectinload, restino li'."""
    for indice in range(4):
        altro = models.Project(name=f"Extra {indice}", status="active")
        db_session.add(altro)
        db_session.flush()
        db_session.add(models.AziendaClienteProjectLink(
            azienda_cliente_id=scenario["aziende"][0].id, project_id=altro.id
        ))
    db_session.commit()

    query_eseguite = []

    @event.listens_for(engine, "before_cursor_execute")
    def _registra(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            query_eseguite.append(statement)

    try:
        resp = client.get("/api/v1/projects/")
        assert resp.status_code == 200, resp.text
        assert len(resp.json()) == 5
    finally:
        event.remove(engine, "before_cursor_execute", _registra)

    # progetti + avvisi + aziende + allievi: un pugno di SELECT, non una per riga
    assert len(query_eseguite) <= 6, "\n".join(query_eseguite)


def test_dopo_il_salvataggio_la_risposta_mostra_gia_gli_associati(client, db_session):
    """Il sintomo riferito: associo, salvo, e non vedo nulla.

    ``azienda_ids`` ora legge la relazione viewonly ``aziende_coinvolte``:
    se restasse stantia dopo la sincronizzazione dei link, la risposta del
    salvataggio tornerebbe vuota anche con i dati scritti.
    """
    azienda = models.AziendaCliente(ragione_sociale="Gamma Srl", partita_iva="33333333333", attivo=True)
    allievo = models.Allievo(nome="Dina", cognome="Bianchi", codice_fiscale="BNCDNI80A41H501Q", attivo=True)
    db_session.add_all([azienda, allievo])
    db_session.commit()

    creato = client.post("/api/v1/projects/", json={
        "name": "Progetto appena salvato",
        "status": "active",
        "azienda_ids": [azienda.id],
        "allievo_ids": [allievo.id],
    })
    assert creato.status_code in (200, 201), creato.text
    body = creato.json()
    assert body["azienda_ids"] == [azienda.id]
    assert body["allievo_ids"] == [allievo.id]

    riletto = client.get(f"/api/v1/projects/{body['id']}").json()
    assert [a["ragione_sociale"] for a in riletto["aziende_coinvolte"]] == ["Gamma Srl"]
    assert [a["cognome"] for a in riletto["allievi_coinvolti"]] == ["Bianchi"]


def test_rimuovere_un_azienda_si_riflette_in_lettura(client, db_session, scenario):
    """Anche il verso opposto: se svuoto, la scheda deve svuotarsi."""
    progetto_id = scenario["project"].id
    resp = client.put(f"/api/v1/projects/{progetto_id}", json={"azienda_ids": []})
    assert resp.status_code == 200, resp.text

    riletto = client.get(f"/api/v1/projects/{progetto_id}").json()
    assert riletto["aziende_coinvolte"] == []
    assert riletto["azienda_ids"] == []
    # gli allievi non sono stati toccati
    assert len(riletto["allievi_coinvolti"]) == 3
