"""
UX-8: dissociazione di allievi e aziende da un progetto.

Fino a ora la dissociazione esisteva solo come effetto collaterale del PUT
progetto: `_sync_project_allievi` / `_sync_project_azienda_links` facevano un
replace secco della lista, quindi bastava omettere un id per staccare un
allievo che aveva gia' l'attestato emesso, senza controlli e senza traccia.

Guardie di dominio (decise col committente):

- `attestato_emesso` -> blocco ASSOLUTO, non superabile nemmeno da admin:
  il certificato e' gia' stato emesso a nome di quell'allievo su quel progetto.
- `ore_frequentate > 0` -> blocco FORZABILE da admin con motivo obbligatorio.
- righe in `dati_retributivi` -> blocco FORZABILE (dati di rendicontazione).
- azienda con propri allievi ancora associati al progetto -> blocco, niente
  cascata implicita: prima si staccano gli allievi.

Le stesse guardie valgono sull'endpoint dedicato e sul PUT progetto: la porta
laterale non deve restare aperta.
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


@pytest.fixture(scope="function")
def db_session(tmp_path):
    db_path = tmp_path / "test_ux8_dissociazione.db"
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


def _fake_user(role: str, user_id: int = 1):
    return type(
        "TestUser",
        (),
        {
            "id": user_id,
            "username": f"test-{role}",
            "email": f"test-{role}@example.com",
            "role": role,
            "is_active": True,
        },
    )()


@pytest.fixture(scope="function")
def make_client(db_session):
    """Client parametrico sul ruolo: serve per la guardia RBAC sulla forzatura."""
    original_startup = list(app.router.on_startup)
    app.router.on_startup.clear()

    def _factory(role: str = "admin"):
        def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = lambda: _fake_user(role)
        return TestClient(app)

    try:
        yield _factory
    finally:
        app.router.on_startup[:] = original_startup
        app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def client(make_client):
    with make_client("admin") as test_client:
        yield test_client


@pytest.fixture(scope="function")
def scenario(db_session):
    """Progetto con due aziende; ogni azienda ha un proprio allievo associato."""
    alpha = models.AziendaCliente(ragione_sociale="Alpha Srl")
    beta = models.AziendaCliente(ragione_sociale="Beta Srl")
    db_session.add_all([alpha, beta])
    db_session.flush()

    mario = models.Allievo(nome="Mario", cognome="Rossi", attivo=True, azienda_cliente_id=alpha.id)
    luigi = models.Allievo(nome="Luigi", cognome="Verdi", attivo=True, azienda_cliente_id=beta.id)
    db_session.add_all([mario, luigi])
    db_session.flush()

    project = models.Project(name="Progetto UX-8")
    db_session.add(project)
    db_session.flush()

    project.allievi_coinvolti = [mario, luigi]
    db_session.add_all([
        models.AziendaClienteProjectLink(azienda_cliente_id=alpha.id, project_id=project.id),
        models.AziendaClienteProjectLink(azienda_cliente_id=beta.id, project_id=project.id),
    ])
    db_session.commit()

    for obj in (alpha, beta, mario, luigi, project):
        db_session.refresh(obj)

    return {
        "project": project,
        "alpha": alpha,
        "beta": beta,
        "mario": mario,
        "luigi": luigi,
    }


def _link(db_session, project_id, allievo_id):
    return (
        db_session.query(models.AllievoProject)
        .filter(
            models.AllievoProject.project_id == project_id,
            models.AllievoProject.allievo_id == allievo_id,
        )
        .first()
    )


def _allievo_ids(db_session, project_id):
    rows = (
        db_session.query(models.AllievoProject.allievo_id)
        .filter(models.AllievoProject.project_id == project_id)
        .all()
    )
    return sorted(r[0] for r in rows)


def _azienda_ids(db_session, project_id):
    rows = (
        db_session.query(models.AziendaClienteProjectLink.azienda_cliente_id)
        .filter(models.AziendaClienteProjectLink.project_id == project_id)
        .all()
    )
    return sorted(r[0] for r in rows)


def _set_ore(db_session, project_id, allievo_id, ore):
    link = _link(db_session, project_id, allievo_id)
    link.ore_frequentate = ore
    db_session.commit()


def _emetti_attestato(db_session, project_id, allievo_id):
    link = _link(db_session, project_id, allievo_id)
    link.attestato_emesso = True
    db_session.commit()


def _aggiungi_dati_retributivi(db_session, project_id, allievo_id):
    db_session.add(models.DatiRetributivi(
        allievo_id=allievo_id,
        project_id=project_id,
        ral_annua=30000,
    ))
    db_session.commit()


def _codici(resp):
    detail = resp.json()["detail"]
    return sorted(b["codice"] for b in detail["blocchi"])


# ── Servizio guardie ─────────────────────────────────────────────────

class TestGuardieAllievo:
    def test_allievo_pulito_nessun_blocco(self, db_session, scenario):
        from services import dissociazione_progetto as svc

        blocchi = svc.blocchi_dissociazione_allievo(
            db_session, scenario["project"].id, scenario["mario"].id
        )
        assert blocchi == []

    def test_attestato_emesso_blocco_non_forzabile(self, db_session, scenario):
        from services import dissociazione_progetto as svc

        _emetti_attestato(db_session, scenario["project"].id, scenario["mario"].id)
        blocchi = svc.blocchi_dissociazione_allievo(
            db_session, scenario["project"].id, scenario["mario"].id
        )
        assert [b.codice for b in blocchi] == [svc.BLOCCO_ATTESTATO]
        assert blocchi[0].forzabile is False

    def test_ore_frequentate_blocco_forzabile(self, db_session, scenario):
        from services import dissociazione_progetto as svc

        _set_ore(db_session, scenario["project"].id, scenario["mario"].id, 8)
        blocchi = svc.blocchi_dissociazione_allievo(
            db_session, scenario["project"].id, scenario["mario"].id
        )
        assert [b.codice for b in blocchi] == [svc.BLOCCO_ORE]
        assert blocchi[0].forzabile is True

    def test_ore_zero_non_blocca(self, db_session, scenario):
        from services import dissociazione_progetto as svc

        _set_ore(db_session, scenario["project"].id, scenario["mario"].id, 0)
        assert svc.blocchi_dissociazione_allievo(
            db_session, scenario["project"].id, scenario["mario"].id
        ) == []

    def test_dati_retributivi_blocco_forzabile(self, db_session, scenario):
        from services import dissociazione_progetto as svc

        _aggiungi_dati_retributivi(db_session, scenario["project"].id, scenario["mario"].id)
        blocchi = svc.blocchi_dissociazione_allievo(
            db_session, scenario["project"].id, scenario["mario"].id
        )
        assert [b.codice for b in blocchi] == [svc.BLOCCO_DATI_RETRIBUTIVI]
        assert blocchi[0].forzabile is True

    def test_dati_retributivi_di_altro_progetto_non_blocca(self, db_session, scenario):
        from services import dissociazione_progetto as svc

        altro = models.Project(name="Altro progetto")
        db_session.add(altro)
        db_session.commit()
        _aggiungi_dati_retributivi(db_session, altro.id, scenario["mario"].id)

        assert svc.blocchi_dissociazione_allievo(
            db_session, scenario["project"].id, scenario["mario"].id
        ) == []

    def test_stato_non_e_una_guardia(self, db_session, scenario):
        """Decisione esplicita: `stato` da solo non blocca la dissociazione."""
        from services import dissociazione_progetto as svc

        link = _link(db_session, scenario["project"].id, scenario["mario"].id)
        link.stato = "ritirato"
        db_session.commit()

        assert svc.blocchi_dissociazione_allievo(
            db_session, scenario["project"].id, scenario["mario"].id
        ) == []

    def test_blocchi_multipli_cumulati(self, db_session, scenario):
        from services import dissociazione_progetto as svc

        pid, aid = scenario["project"].id, scenario["mario"].id
        _set_ore(db_session, pid, aid, 12)
        _aggiungi_dati_retributivi(db_session, pid, aid)
        _emetti_attestato(db_session, pid, aid)

        codici = sorted(b.codice for b in svc.blocchi_dissociazione_allievo(db_session, pid, aid))
        assert codici == sorted([svc.BLOCCO_ATTESTATO, svc.BLOCCO_ORE, svc.BLOCCO_DATI_RETRIBUTIVI])


class TestGuardieAzienda:
    def test_azienda_senza_propri_allievi_nessun_blocco(self, db_session, scenario):
        from services import dissociazione_progetto as svc

        # Alpha ha Mario; lo stacco prima
        pid = scenario["project"].id
        link = _link(db_session, pid, scenario["mario"].id)
        db_session.delete(link)
        db_session.commit()

        assert svc.blocchi_dissociazione_azienda(db_session, pid, scenario["alpha"].id) == []

    def test_azienda_con_propri_allievi_bloccata(self, db_session, scenario):
        from services import dissociazione_progetto as svc

        blocchi = svc.blocchi_dissociazione_azienda(
            db_session, scenario["project"].id, scenario["alpha"].id
        )
        assert [b.codice for b in blocchi] == [svc.BLOCCO_ALLIEVI_AZIENDA]
        assert blocchi[0].forzabile is False
        # il messaggio deve nominare l'allievo da staccare prima
        assert "Rossi" in blocchi[0].messaggio

    def test_allievi_di_altra_azienda_non_bloccano(self, db_session, scenario):
        from services import dissociazione_progetto as svc

        # Beta ha solo Luigi: staccando Luigi, Beta e' libera anche se Mario resta
        pid = scenario["project"].id
        db_session.delete(_link(db_session, pid, scenario["luigi"].id))
        db_session.commit()

        assert svc.blocchi_dissociazione_azienda(db_session, pid, scenario["beta"].id) == []


# ── Endpoint dissociazione allievo ───────────────────────────────────

class TestEndpointAllievo:
    def test_dissocia_allievo_pulito_200(self, client, db_session, scenario):
        pid = scenario["project"].id
        resp = client.request("DELETE", f"/api/v1/projects/{pid}/allievi/{scenario['mario'].id}")
        assert resp.status_code == 200, resp.text
        assert _allievo_ids(db_session, pid) == [scenario["luigi"].id]

    def test_attestato_409_anche_con_forza(self, client, db_session, scenario):
        pid, aid = scenario["project"].id, scenario["mario"].id
        _emetti_attestato(db_session, pid, aid)

        resp = client.request(
            "DELETE",
            f"/api/v1/projects/{pid}/allievi/{aid}",
            json={"forza": True, "motivo": "richiesta del cliente"},
        )
        assert resp.status_code == 409, resp.text
        assert resp.json()["detail"]["forzabile"] is False
        assert _link(db_session, pid, aid) is not None

    def test_ore_409_senza_forza(self, client, db_session, scenario):
        pid, aid = scenario["project"].id, scenario["mario"].id
        _set_ore(db_session, pid, aid, 6)

        resp = client.request("DELETE", f"/api/v1/projects/{pid}/allievi/{aid}")
        assert resp.status_code == 409, resp.text
        assert resp.json()["detail"]["forzabile"] is True
        assert _link(db_session, pid, aid) is not None

    def test_ore_200_con_forza_e_motivo(self, client, db_session, scenario):
        pid, aid = scenario["project"].id, scenario["mario"].id
        _set_ore(db_session, pid, aid, 6)

        resp = client.request(
            "DELETE",
            f"/api/v1/projects/{pid}/allievi/{aid}",
            json={"forza": True, "motivo": "iscritto per errore, verificato con l'ente"},
        )
        assert resp.status_code == 200, resp.text
        assert _link(db_session, pid, aid) is None

    def test_forza_senza_motivo_422(self, client, db_session, scenario):
        pid, aid = scenario["project"].id, scenario["mario"].id
        _set_ore(db_session, pid, aid, 6)

        resp = client.request(
            "DELETE",
            f"/api/v1/projects/{pid}/allievi/{aid}",
            json={"forza": True},
        )
        assert resp.status_code == 422, resp.text
        assert _link(db_session, pid, aid) is not None

    def test_forza_motivo_troppo_corto_422(self, client, db_session, scenario):
        pid, aid = scenario["project"].id, scenario["mario"].id
        _set_ore(db_session, pid, aid, 6)

        resp = client.request(
            "DELETE",
            f"/api/v1/projects/{pid}/allievi/{aid}",
            json={"forza": True, "motivo": "x"},
        )
        assert resp.status_code == 422, resp.text

    def test_forza_vietata_a_operatore_403(self, make_client, db_session, scenario):
        pid, aid = scenario["project"].id, scenario["mario"].id
        _set_ore(db_session, pid, aid, 6)

        with make_client("operatore") as c:
            resp = c.request(
                "DELETE",
                f"/api/v1/projects/{pid}/allievi/{aid}",
                json={"forza": True, "motivo": "motivo sufficientemente lungo"},
            )
        assert resp.status_code == 403, resp.text
        assert _link(db_session, pid, aid) is not None

    def test_progetto_inesistente_404(self, client, scenario):
        resp = client.request("DELETE", f"/api/v1/projects/999999/allievi/{scenario['mario'].id}")
        assert resp.status_code == 404

    def test_allievo_non_associato_404(self, client, db_session, scenario):
        estraneo = models.Allievo(nome="Anna", cognome="Bianchi", attivo=True)
        db_session.add(estraneo)
        db_session.commit()

        resp = client.request(
            "DELETE", f"/api/v1/projects/{scenario['project'].id}/allievi/{estraneo.id}"
        )
        assert resp.status_code == 404

    def test_audit_scritto_su_dissociazione(self, client, db_session, scenario):
        pid, aid = scenario["project"].id, scenario["mario"].id
        client.request("DELETE", f"/api/v1/projects/{pid}/allievi/{aid}")

        entry = (
            db_session.query(models.SecurityAuditLog)
            .filter(models.SecurityAuditLog.azione == "project_allievo_dissociato")
            .first()
        )
        assert entry is not None
        assert entry.risorsa_id == str(pid)
        assert str(aid) in (entry.dati_prima or "") + (entry.dati_dopo or "")

    def test_audit_registra_forzatura_e_motivo(self, client, db_session, scenario):
        pid, aid = scenario["project"].id, scenario["mario"].id
        _set_ore(db_session, pid, aid, 6)
        motivo = "iscritto per errore, verificato con l'ente"
        client.request(
            "DELETE",
            f"/api/v1/projects/{pid}/allievi/{aid}",
            json={"forza": True, "motivo": motivo},
        )

        entry = (
            db_session.query(models.SecurityAuditLog)
            .filter(models.SecurityAuditLog.azione == "project_allievo_dissociato")
            .first()
        )
        assert entry is not None
        assert motivo in (entry.dati_dopo or "")

    def test_blocco_non_lascia_audit_di_successo(self, client, db_session, scenario):
        pid, aid = scenario["project"].id, scenario["mario"].id
        _emetti_attestato(db_session, pid, aid)
        client.request("DELETE", f"/api/v1/projects/{pid}/allievi/{aid}")

        successi = (
            db_session.query(models.SecurityAuditLog)
            .filter(
                models.SecurityAuditLog.azione == "project_allievo_dissociato",
                models.SecurityAuditLog.esito == "success",
            )
            .count()
        )
        assert successi == 0


# ── Endpoint dissociazione azienda ───────────────────────────────────

class TestEndpointAzienda:
    def test_azienda_con_allievi_409(self, client, db_session, scenario):
        pid = scenario["project"].id
        resp = client.request("DELETE", f"/api/v1/projects/{pid}/aziende/{scenario['alpha'].id}")
        assert resp.status_code == 409, resp.text
        assert _codici(resp) == ["allievi_azienda_associati"]
        assert scenario["alpha"].id in _azienda_ids(db_session, pid)

    def test_azienda_libera_200(self, client, db_session, scenario):
        pid = scenario["project"].id
        db_session.delete(_link(db_session, pid, scenario["mario"].id))
        db_session.commit()

        resp = client.request("DELETE", f"/api/v1/projects/{pid}/aziende/{scenario['alpha'].id}")
        assert resp.status_code == 200, resp.text
        assert _azienda_ids(db_session, pid) == [scenario["beta"].id]

    def test_azienda_non_associata_404(self, client, db_session, scenario):
        estranea = models.AziendaCliente(ragione_sociale="Gamma Srl")
        db_session.add(estranea)
        db_session.commit()

        resp = client.request(
            "DELETE", f"/api/v1/projects/{scenario['project'].id}/aziende/{estranea.id}"
        )
        assert resp.status_code == 404

    def test_audit_scritto_su_dissociazione_azienda(self, client, db_session, scenario):
        pid = scenario["project"].id
        db_session.delete(_link(db_session, pid, scenario["mario"].id))
        db_session.commit()
        client.request("DELETE", f"/api/v1/projects/{pid}/aziende/{scenario['alpha'].id}")

        entry = (
            db_session.query(models.SecurityAuditLog)
            .filter(models.SecurityAuditLog.azione == "project_azienda_dissociata")
            .first()
        )
        assert entry is not None


# ── La porta laterale: PUT progetto ──────────────────────────────────

class TestPutNonAggiraLeGuardie:
    def test_put_non_puo_staccare_allievo_con_attestato(self, client, db_session, scenario):
        pid = scenario["project"].id
        _emetti_attestato(db_session, pid, scenario["mario"].id)

        resp = client.put(
            f"/api/v1/projects/{pid}",
            json={"allievo_ids": [scenario["luigi"].id]},
        )
        assert resp.status_code == 409, resp.text
        assert _allievo_ids(db_session, pid) == sorted(
            [scenario["mario"].id, scenario["luigi"].id]
        )

    def test_put_non_puo_staccare_allievo_con_ore(self, client, db_session, scenario):
        pid = scenario["project"].id
        _set_ore(db_session, pid, scenario["mario"].id, 4)

        resp = client.put(
            f"/api/v1/projects/{pid}",
            json={"allievo_ids": [scenario["luigi"].id]},
        )
        assert resp.status_code == 409, resp.text
        assert scenario["mario"].id in _allievo_ids(db_session, pid)

    def test_put_lista_vuota_bloccata_se_uno_e_protetto(self, client, db_session, scenario):
        pid = scenario["project"].id
        _emetti_attestato(db_session, pid, scenario["mario"].id)

        resp = client.put(f"/api/v1/projects/{pid}", json={"allievo_ids": []})
        assert resp.status_code == 409, resp.text
        assert _allievo_ids(db_session, pid) == sorted(
            [scenario["mario"].id, scenario["luigi"].id]
        )

    def test_put_stacca_allievo_pulito_200(self, client, db_session, scenario):
        """Non regressione: senza tracce il PUT continua a funzionare come prima."""
        pid = scenario["project"].id
        resp = client.put(
            f"/api/v1/projects/{pid}",
            json={"allievo_ids": [scenario["luigi"].id]},
        )
        assert resp.status_code == 200, resp.text
        assert _allievo_ids(db_session, pid) == [scenario["luigi"].id]

    def test_put_aggiungere_allievi_non_e_bloccato(self, client, db_session, scenario):
        """Le guardie riguardano solo le rimozioni."""
        pid = scenario["project"].id
        _emetti_attestato(db_session, pid, scenario["mario"].id)
        nuovo = models.Allievo(nome="Anna", cognome="Bianchi", attivo=True)
        db_session.add(nuovo)
        db_session.commit()

        resp = client.put(
            f"/api/v1/projects/{pid}",
            json={"allievo_ids": [scenario["mario"].id, scenario["luigi"].id, nuovo.id]},
        )
        assert resp.status_code == 200, resp.text
        assert _allievo_ids(db_session, pid) == sorted(
            [scenario["mario"].id, scenario["luigi"].id, nuovo.id]
        )

    def test_put_non_puo_staccare_azienda_con_propri_allievi(self, client, db_session, scenario):
        pid = scenario["project"].id
        resp = client.put(
            f"/api/v1/projects/{pid}",
            json={"azienda_ids": [scenario["beta"].id]},
        )
        assert resp.status_code == 409, resp.text
        assert _azienda_ids(db_session, pid) == sorted(
            [scenario["alpha"].id, scenario["beta"].id]
        )

    def test_put_stacca_azienda_libera_200(self, client, db_session, scenario):
        pid = scenario["project"].id
        db_session.delete(_link(db_session, pid, scenario["mario"].id))
        db_session.commit()

        resp = client.put(
            f"/api/v1/projects/{pid}",
            json={"azienda_ids": [scenario["beta"].id]},
        )
        assert resp.status_code == 200, resp.text
        assert _azienda_ids(db_session, pid) == [scenario["beta"].id]

    def test_put_stacca_azienda_e_i_suoi_allievi_nella_stessa_chiamata(
        self, client, db_session, scenario
    ):
        """Lo stato finale e' valido: l'azienda se ne va e i suoi allievi con lei.

        La guardia deve leggere lo stato che il PUT sta costruendo, non quello
        di partenza: gli allievi escono nella stessa richiesta, quindi al
        momento del controllo sull'azienda non sono piu' suoi allievi sul
        progetto. Se le due sincronizzazioni girano nell'ordine sbagliato (o
        senza flush in mezzo) questo caso legittimo diventa un 409 impossibile
        da superare, perche' il blocco azienda non e' forzabile.
        """
        pid = scenario["project"].id
        resp = client.put(
            f"/api/v1/projects/{pid}",
            json={
                "azienda_ids": [scenario["beta"].id],
                "allievo_ids": [scenario["luigi"].id],
            },
        )
        assert resp.status_code == 200, resp.text
        assert _azienda_ids(db_session, pid) == [scenario["beta"].id]
        assert _allievo_ids(db_session, pid) == [scenario["luigi"].id]

    def test_put_stacca_azienda_ma_tiene_i_suoi_allievi_409(
        self, client, db_session, scenario
    ):
        """Il verso opposto resta vietato: niente allievi orfani della loro azienda."""
        pid = scenario["project"].id
        resp = client.put(
            f"/api/v1/projects/{pid}",
            json={
                "azienda_ids": [scenario["beta"].id],
                "allievo_ids": [scenario["mario"].id, scenario["luigi"].id],
            },
        )
        assert resp.status_code == 409, resp.text
        assert _codici(resp) == ["allievi_azienda_associati"]
        assert _azienda_ids(db_session, pid) == sorted(
            [scenario["alpha"].id, scenario["beta"].id]
        )
        assert _allievo_ids(db_session, pid) == sorted(
            [scenario["mario"].id, scenario["luigi"].id]
        )


# ── RBAC ─────────────────────────────────────────────────────────────

class TestRbac:
    @pytest.mark.parametrize(
        "role,expected",
        [
            (UserRole.ADMIN.value, 200),
            (UserRole.OPERATORE.value, 200),
            (UserRole.CONSULTAZIONE.value, 403),
        ],
    )
    def test_dissociazione_non_e_consultabile(self, role, expected):
        for path in ("/api/v1/projects/1/allievi/2", "/api/v1/projects/1/aziende/2"):
            decision = rbac_decision_for("DELETE", path, role)
            assert decision["would_status"] == expected, (path, role)
