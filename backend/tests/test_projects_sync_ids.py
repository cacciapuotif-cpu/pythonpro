"""
NEW-030: POST/PUT /api/v1/projects/ deve accettare e sincronizzare
azienda_ids / allievo_ids.

Prima del fix gli schemi ProjectCreateExtended/ProjectUpdateExtended NON
dichiaravano questi campi: Pydantic (extra=ignore) li scartava e il sync in
crud (_sync_project_azienda_links / _sync_project_allievi) era codice morto.

Semantica attesa:
- lista di id  -> i link vengono sincronizzati a quella lista;
- None (campo non passato) -> i link NON vengono toccati;
- []           -> i link vengono svuotati.
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
from auth import UserRole, get_current_user, rbac_decision_for
import models  # noqa: F401  # assicura registrazione metadata


DATE_PROGETTO_VALIDE = {
    "data_approvazione": "2026-03-24",
    "data_avvio_piano": "2026-04-01",
}


@pytest.fixture(scope="function")
def db_session(tmp_path):
    db_path = tmp_path / "test_projects_sync.db"
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
def beneficiari(db_session):
    """Due aziende clienti e due allievi attivi selezionabili."""
    a1 = models.AziendaCliente(ragione_sociale="Alpha Srl")
    a2 = models.AziendaCliente(ragione_sociale="Beta Srl")
    al1 = models.Allievo(nome="Mario", cognome="Rossi", attivo=True)
    al2 = models.Allievo(nome="Luigi", cognome="Verdi", attivo=True)
    db_session.add_all([a1, a2, al1, al2])
    db_session.commit()
    for obj in (a1, a2, al1, al2):
        db_session.refresh(obj)
    return {"aziende": (a1, a2), "allievi": (al1, al2)}


def _azienda_link_ids(db_session, project_id):
    rows = (
        db_session.query(models.AziendaClienteProjectLink.azienda_cliente_id)
        .filter(models.AziendaClienteProjectLink.project_id == project_id)
        .all()
    )
    return sorted(r[0] for r in rows)


def _allievo_ids(db_session, project_id):
    project = db_session.query(models.Project).filter(models.Project.id == project_id).first()
    db_session.refresh(project)
    return sorted(a.id for a in project.allievi_coinvolti)


class TestCreateSync:
    def test_create_con_ids_crea_i_link(self, client, db_session, beneficiari):
        a1, a2 = beneficiari["aziende"]
        al1, al2 = beneficiari["allievi"]
        resp = client.post(
            "/api/v1/projects/",
            json={
                "name": "Progetto con beneficiari",
                **DATE_PROGETTO_VALIDE,
                "azienda_ids": [a1.id, a2.id],
                "allievo_ids": [al1.id, al2.id],
            },
        )
        assert resp.status_code == 200, resp.text
        pid = resp.json()["id"]
        assert _azienda_link_ids(db_session, pid) == sorted([a1.id, a2.id])
        assert _allievo_ids(db_session, pid) == sorted([al1.id, al2.id])
        # read exposure: la GET riespone gli id
        body = resp.json()
        assert sorted(body["azienda_ids"]) == sorted([a1.id, a2.id])
        assert sorted(body["allievo_ids"]) == sorted([al1.id, al2.id])

    def test_create_senza_ids_nessun_link(self, client, db_session):
        resp = client.post(
            "/api/v1/projects/",
            json={"name": "Progetto nudo", **DATE_PROGETTO_VALIDE},
        )
        assert resp.status_code == 200, resp.text
        pid = resp.json()["id"]
        assert _azienda_link_ids(db_session, pid) == []
        assert _allievo_ids(db_session, pid) == []
        assert resp.json()["azienda_ids"] == []
        assert resp.json()["allievo_ids"] == []


class TestUpdateSync:
    def _crea_progetto(self, client, azienda_ids=None, allievo_ids=None):
        payload = {"name": "Progetto base", **DATE_PROGETTO_VALIDE}
        if azienda_ids is not None:
            payload["azienda_ids"] = azienda_ids
        if allievo_ids is not None:
            payload["allievo_ids"] = allievo_ids
        resp = client.post("/api/v1/projects/", json=payload)
        assert resp.status_code == 200, resp.text
        return resp.json()["id"]

    def test_update_aggiorna_i_link(self, client, db_session, beneficiari):
        a1, a2 = beneficiari["aziende"]
        al1, al2 = beneficiari["allievi"]
        pid = self._crea_progetto(client, azienda_ids=[a1.id], allievo_ids=[al1.id])

        resp = client.put(
            f"/api/v1/projects/{pid}",
            json={"azienda_ids": [a2.id], "allievo_ids": [al1.id, al2.id]},
        )
        assert resp.status_code == 200, resp.text
        assert _azienda_link_ids(db_session, pid) == [a2.id]
        assert _allievo_ids(db_session, pid) == sorted([al1.id, al2.id])

    def test_update_none_lascia_invariato(self, client, db_session, beneficiari):
        a1, _ = beneficiari["aziende"]
        al1, _ = beneficiari["allievi"]
        pid = self._crea_progetto(client, azienda_ids=[a1.id], allievo_ids=[al1.id])

        # PUT che tocca solo il nome: azienda_ids/allievo_ids non passati -> invariati
        resp = client.put(f"/api/v1/projects/{pid}", json={"name": "Rinominato"})
        assert resp.status_code == 200, resp.text
        assert _azienda_link_ids(db_session, pid) == [a1.id]
        assert _allievo_ids(db_session, pid) == [al1.id]

    def test_update_lista_vuota_svuota(self, client, db_session, beneficiari):
        a1, _ = beneficiari["aziende"]
        al1, _ = beneficiari["allievi"]
        pid = self._crea_progetto(client, azienda_ids=[a1.id], allievo_ids=[al1.id])

        resp = client.put(
            f"/api/v1/projects/{pid}",
            json={"azienda_ids": [], "allievo_ids": []},
        )
        assert resp.status_code == 200, resp.text
        assert _azienda_link_ids(db_session, pid) == []
        assert _allievo_ids(db_session, pid) == []

    def test_update_azienda_inesistente_400(self, client, beneficiari):
        pid = self._crea_progetto(client)
        resp = client.put(f"/api/v1/projects/{pid}", json={"azienda_ids": [999999]})
        assert resp.status_code == 400


class TestLegacyKeysNonRegressione:
    """Il validator NEW-021 continua a rifiutare le chiavi legacy con 422,
    e i nuovi campi non sono confusi con quelle."""

    def test_create_legacy_key_422(self, client):
        resp = client.post(
            "/api/v1/projects/",
            json={"name": "X", "template_piano_finanziario_id": 5},
        )
        assert resp.status_code == 422

    def test_create_avviso_pf_id_422(self, client):
        resp = client.post(
            "/api/v1/projects/",
            json={"name": "X", "avviso_pf_id": 5},
        )
        assert resp.status_code == 422

    def test_update_legacy_key_422(self, client):
        resp = client.post(
            "/api/v1/projects/",
            json={"name": "X", **DATE_PROGETTO_VALIDE},
        )
        pid = resp.json()["id"]
        resp = client.put(
            f"/api/v1/projects/{pid}",
            json={"template_piano_finanziario_id": 5},
        )
        assert resp.status_code == 422


class TestRbacInvariato:
    @pytest.mark.parametrize(
        "method,path,expected",
        [
            ("POST", "/api/v1/projects/", {"admin": 200, "operatore": 200, "consultazione": 403}),
            ("PUT", "/api/v1/projects/1", {"admin": 200, "operatore": 200, "consultazione": 403}),
        ],
    )
    @pytest.mark.parametrize(
        "role",
        [UserRole.ADMIN.value, UserRole.OPERATORE.value, UserRole.CONSULTAZIONE.value],
    )
    def test_rbac(self, method, path, expected, role):
        decision = rbac_decision_for(method, path, role)
        assert decision["would_status"] == expected[role]
