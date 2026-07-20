"""FASE E1 (piano Task E1.2; numerazione utente E1.5) — endpoint template piani.

Copre:
- ``GET /api/v1/piano-templates/`` — lista template attivi filtrata per fondo;
  con ``avviso_id`` il template collegato all'avviso ha ``preselezionato=true``;
- ``GET /api/v1/piano-templates/{id}/anteprima`` — voci del template + massimali
  con fonte (``regola_avviso`` con riferimento articolo quando la regola
  validata vince; ``massimale_fondo`` altrimenti);
- ``POST /api/v1/piani-finanziari/from-template`` — 201 con voci strutturate
  dal template; con ``avviso_id`` valorizza ``avviso_pf_id`` e
  ``avviso_revisione_id`` (revisione corrente);
- RBAC: listing/anteprima per tutti e tre i ruoli; ``from-template`` negato al
  ruolo consultazione (403 con ``RBAC_ENFORCE`` attivo, pattern
  test_rbac_download_endpoints.py);
- REGRESSIONE: il percorso libero ``POST /api/v1/piani-finanziari/`` resta
  invariato (201 + voci di default non dinamiche).
"""

from datetime import datetime
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app
from database import Base, get_db
import auth
from auth import User, get_current_user
import models  # noqa: F401 - registra i modelli sul Base
from piano_finanziario_config import VOICE_TEMPLATES
from services.piano_templates import seed_templates

ANNO = 2026


@pytest.fixture(scope="function")
def db_session(tmp_path):
    engine = create_engine(
        "sqlite:///{}".format(tmp_path / "test_piano_templates_api.db"),
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=engine, expire_on_commit=False
    )
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


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


@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: _fake_user("admin")
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def templates(db_session):
    """Seed reale dei 3 template (formazienda/fapi/fondimpresa v1)."""
    assert seed_templates(db_session) == 3
    return {
        t.tipo_fondo: t
        for t in db_session.query(models.PianoFinanziarioTemplate).all()
    }


@pytest.fixture
def avviso_con_revisione(db_session):
    """Avviso fondimpresa con revisione corrente valorizzata."""
    validator = User(
        username="validatore",
        email="validatore@example.com",
        hashed_password="x",
        role="admin",
    )
    db_session.add(validator)
    db_session.flush()
    avviso = models.Avviso(
        codice="AVV-E15",
        ente_erogatore="Fondimpresa",
        fondo="fondimpresa",
        numero="1/2026",
        anno=ANNO,
        titolo="Avviso E1.5",
    )
    db_session.add(avviso)
    db_session.flush()
    revisione = models.AvvisoRevisione(
        avviso_id=avviso.id,
        numero_revisione=1,
        titolo="Avviso E1.5 rev 1",
    )
    db_session.add(revisione)
    db_session.flush()
    avviso.revisione_corrente_id = revisione.id
    db_session.commit()
    return avviso, revisione


@pytest.fixture
def progetto(db_session):
    project = models.Project(
        name="Progetto E1.5",
        description="t",
        status="active",
        start_date=datetime(ANNO, 1, 1),
        end_date=datetime(ANNO, 12, 31),
    )
    db_session.add(project)
    db_session.commit()
    return project


def _regola_docenza_80(revisione):
    return models.AvvisoRegola(
        avviso_revisione_id=revisione.id,
        categoria="massimali",
        chiave="costo_orario_docenza",
        valore={"tipo": "denaro", "importo": 80, "valuta": "EUR"},
        tipo_valore="oggetto",
        testo_originale="Il costo orario della docenza non può superare 80 euro.",
        riferimento_articolo="Art. 12",
        stato="validata",
        validata_da_user_id=1,
        validata_il=datetime(ANNO, 7, 1, 10, 0, 0),
    )


def _massimale_fondo(tipo_fondo="fondimpresa", docenza=100, tutoraggio=70):
    return models.MassimaleFondo(
        tipo_fondo=tipo_fondo,
        anno=ANNO,
        massimale_orario_docenza=docenza,
        massimale_orario_tutoraggio=tutoraggio,
    )


# ------------------------------------------------------------------
# Listing
# ------------------------------------------------------------------

def test_listing_filtrato_per_fondo(client, db_session, templates):
    r = client.get("/api/v1/piano-templates/", params={"tipo_fondo": "fapi"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data) == 1
    assert data[0]["tipo_fondo"] == "fapi"
    assert data[0]["versione"] == 1
    assert data[0]["preselezionato"] is False
    assert {v["voce_codice"] for v in data[0]["struttura_voci"]["voci"]} == {
        tpl["voce_codice"] for tpl in VOICE_TEMPLATES
    }


def test_listing_esclude_template_disattivi(client, db_session, templates):
    templates["fapi"].is_active = False
    db_session.commit()
    r = client.get("/api/v1/piano-templates/")
    assert r.status_code == 200, r.text
    assert {t["tipo_fondo"] for t in r.json()} == {"formazienda", "fondimpresa"}


def test_listing_preselezione_da_avviso(client, db_session, templates, avviso_con_revisione):
    avviso, _ = avviso_con_revisione
    templates["fondimpresa"].avviso_id = avviso.id
    db_session.commit()

    r = client.get("/api/v1/piano-templates/", params={"avviso_id": avviso.id})
    assert r.status_code == 200, r.text
    by_id = {t["id"]: t for t in r.json()}
    assert by_id[templates["fondimpresa"].id]["preselezionato"] is True
    others = [t for t in r.json() if t["id"] != templates["fondimpresa"].id]
    assert all(t["preselezionato"] is False for t in others)


# ------------------------------------------------------------------
# Anteprima
# ------------------------------------------------------------------

def test_anteprima_fonte_regola_avviso(client, db_session, templates, avviso_con_revisione):
    """Regola validata docenza=80 vince sul fondo (docenza=100); il tutoraggio
    senza regola resta da massimale fondo."""
    avviso, revisione = avviso_con_revisione
    db_session.add_all([_regola_docenza_80(revisione), _massimale_fondo()])
    db_session.commit()

    template = templates["fondimpresa"]
    r = client.get(
        f"/api/v1/piano-templates/{template.id}/anteprima",
        params={"avviso_id": avviso.id, "anno": ANNO},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["template"]["id"] == template.id
    assert {v["voce_codice"] for v in data["voci"]} == {
        tpl["voce_codice"] for tpl in VOICE_TEMPLATES
    }
    massimali = {m["categoria"]: m for m in data["massimali"]}
    assert massimali["docenza"]["limite"] == 80.0
    assert massimali["docenza"]["fonte"] == "regola_avviso"
    assert massimali["docenza"]["riferimento_articolo"] == "Art. 12"
    assert massimali["tutoraggio"]["limite"] == 70.0
    assert massimali["tutoraggio"]["fonte"] == "massimale_fondo"
    assert massimali["tutoraggio"]["riferimento_articolo"] is None


def test_anteprima_fonte_solo_fondo(client, db_session, templates):
    """Senza avviso: entrambe le categorie da MassimaleFondo."""
    db_session.add(_massimale_fondo())
    db_session.commit()

    template = templates["fondimpresa"]
    r = client.get(
        f"/api/v1/piano-templates/{template.id}/anteprima",
        params={"anno": ANNO},
    )
    assert r.status_code == 200, r.text
    massimali = {m["categoria"]: m for m in r.json()["massimali"]}
    assert massimali["docenza"]["limite"] == 100.0
    assert massimali["docenza"]["fonte"] == "massimale_fondo"
    assert massimali["tutoraggio"]["limite"] == 70.0
    assert massimali["tutoraggio"]["fonte"] == "massimale_fondo"


def test_anteprima_template_inesistente(client, db_session, templates):
    r = client.get("/api/v1/piano-templates/999999/anteprima")
    assert r.status_code == 404


# ------------------------------------------------------------------
# Creazione da template
# ------------------------------------------------------------------

def _from_template_payload(template, progetto, **extra):
    payload = {
        "template_id": template.id,
        "progetto_id": progetto.id,
        "anno": ANNO,
        "nome": "Piano da template E1.5",
        "budget_totale": 50000.0,
    }
    payload.update(extra)
    return payload


def test_creazione_da_template_voci_e_avviso(client, db_session, templates, progetto, avviso_con_revisione):
    avviso, revisione = avviso_con_revisione
    template = templates["fondimpresa"]

    r = client.post(
        "/api/v1/piani-finanziari/from-template",
        json=_from_template_payload(template, progetto, avviso_id=avviso.id),
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["tipo_fondo"] == "fondimpresa"
    assert data["avviso_pf_id"] == avviso.id
    assert data["avviso_revisione_id"] == revisione.id
    assert len(data["voci"]) == len(VOICE_TEMPLATES)

    # Le voci del piano sono ESATTAMENTE quelle del template (incluse le
    # dinamiche B.2/B.3 con categoria derivata), non le sole default.
    db_voci = (
        db_session.query(models.VocePianoFinanziario)
        .filter(models.VocePianoFinanziario.piano_id == data["id"])
        .all()
    )
    assert {(v.voce_codice, v.macrovoce) for v in db_voci} == {
        (tpl["voce_codice"], tpl["macrovoce"]) for tpl in VOICE_TEMPLATES
    }
    by_codice = {v.voce_codice: v for v in db_voci}
    assert by_codice["B.2"].categoria == "docenza"
    assert by_codice["B.3"].categoria == "tutoraggio"


def test_creazione_da_template_senza_avviso(client, db_session, templates, progetto):
    template = templates["fapi"]
    r = client.post(
        "/api/v1/piani-finanziari/from-template",
        json=_from_template_payload(template, progetto),
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["tipo_fondo"] == "fapi"
    assert data["avviso_pf_id"] is None
    assert data["avviso_revisione_id"] is None


def test_creazione_da_template_inesistente(client, db_session, progetto):
    r = client.post(
        "/api/v1/piani-finanziari/from-template",
        json={
            "template_id": 999999,
            "progetto_id": progetto.id,
            "anno": ANNO,
            "nome": "Piano fantasma",
        },
    )
    assert r.status_code == 404, r.text


def test_creazione_da_template_malformato_400_senza_piano_orfano(client, db_session, progetto):
    """Template con struttura_voci senza voci: 400 PRIMA di creare il piano
    (nessun piano orfano committato)."""
    template = models.PianoFinanziarioTemplate(
        nome="Template rotto",
        tipo_fondo="fondimpresa",
        versione=1,
        struttura_voci={"voci": [], "limiti_macrovoce": {}},
    )
    db_session.add(template)
    db_session.commit()

    r = client.post(
        "/api/v1/piani-finanziari/from-template",
        json=_from_template_payload(template, progetto),
    )
    assert r.status_code == 400, r.text
    assert db_session.query(models.PianoFinanziario).count() == 0


def test_creazione_da_template_avviso_inesistente(client, db_session, templates, progetto):
    template = templates["fondimpresa"]
    r = client.post(
        "/api/v1/piani-finanziari/from-template",
        json=_from_template_payload(template, progetto, avviso_id=999999),
    )
    assert r.status_code == 404, r.text


# ------------------------------------------------------------------
# RBAC (enforcement attivo, pattern test_rbac_download_endpoints.py)
# ------------------------------------------------------------------

@pytest.fixture(scope="function")
def client_rbac(db_session, monkeypatch):
    monkeypatch.setattr(auth, "RBAC_ENFORCE", True)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_rbac_consultazione_403_su_from_template(client_rbac, db_session, templates, progetto):
    app.dependency_overrides[get_current_user] = lambda: _fake_user("consultazione")
    r = client_rbac.post(
        "/api/v1/piani-finanziari/from-template",
        json=_from_template_payload(templates["fondimpresa"], progetto),
    )
    assert r.status_code == 403, r.text
    assert "Permessi insufficienti" in r.text
    assert db_session.query(models.PianoFinanziario).count() == 0


@pytest.mark.parametrize("role", ["admin", "operatore", "consultazione"])
def test_rbac_listing_e_anteprima_tutti_i_ruoli(client_rbac, db_session, templates, role):
    app.dependency_overrides[get_current_user] = lambda: _fake_user(role)
    r = client_rbac.get("/api/v1/piano-templates/")
    assert r.status_code == 200, f"{role}: {r.status_code} {r.text[:200]}"
    template_id = r.json()[0]["id"]
    r = client_rbac.get(f"/api/v1/piano-templates/{template_id}/anteprima")
    assert r.status_code == 200, f"{role}: {r.status_code} {r.text[:200]}"


@pytest.mark.parametrize("role,expected", [("admin", 201), ("operatore", 201)])
def test_rbac_from_template_ruoli_ammessi(client_rbac, db_session, templates, progetto, role, expected):
    app.dependency_overrides[get_current_user] = lambda: _fake_user(role)
    r = client_rbac.post(
        "/api/v1/piani-finanziari/from-template",
        json=_from_template_payload(templates["fondimpresa"], progetto),
    )
    assert r.status_code == expected, f"{role}: {r.status_code} {r.text[:200]}"


# ------------------------------------------------------------------
# REGRESSIONE: percorso libero invariato
# ------------------------------------------------------------------

def test_regressione_percorso_libero_invariato(client, db_session, progetto):
    """POST /api/v1/piani-finanziari/ resta il percorso libero di sempre:
    201 e voci di default = tutte le NON dinamiche di VOICE_TEMPLATES."""
    r = client.post(
        "/api/v1/piani-finanziari/",
        json={
            "progetto_id": progetto.id,
            "nome": "Piano libero",
            "tipo_fondo": "fondimpresa",
            "budget_totale": 10000.0,
            "data_inizio": f"{ANNO}-01-01T00:00:00",
            "data_fine": f"{ANNO}-12-31T00:00:00",
        },
    )
    assert r.status_code == 201, r.text
    piano_id = r.json()["id"]
    db_voci = (
        db_session.query(models.VocePianoFinanziario)
        .filter(models.VocePianoFinanziario.piano_id == piano_id)
        .all()
    )
    attese = {tpl["voce_codice"] for tpl in VOICE_TEMPLATES if not tpl["is_dynamic"]}
    assert {v.voce_codice for v in db_voci} == attese
