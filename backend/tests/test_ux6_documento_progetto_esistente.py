"""UX-6 — un atto/convenzione caricato dentro un progetto non crea un doppione.

Bug osservato in uso reale (2026-07-27): dalla scheda di un progetto il
pulsante "Carica Convenzione" apriva il flusso *project-less*
(``POST /api/v1/projects/upload-convenzione`` + ``confirm-convenzione``), che
esegue incondizionatamente ``db.add(models.Project(...))``. Risultato: un
progetto gemello per ogni atto caricato, con i dati dell'atto finiti sul
gemello invece che sul progetto reale. Sul DB di produzione ha prodotto il
progetto 13 "Piano FAPI" (nome di fallback) cinque minuti dopo il 12.

La guardia 409 esistente non poteva intercettarlo: era condizionata a
``if codice_fapi:`` e l'atto di concessione caricato dall'utente non e' una
convenzione FAPI, quindi il parser non estraeva alcun codice.

Contratto verificato qui:

1. esiste un percorso *project-scoped* che associa il documento al progetto
   corrente e non crea mai un secondo progetto;
2. i campi vuoti del progetto vengono arricchiti dai dati estratti;
3. i campi gia' valorizzati e discordanti NON vengono sovrascritti in
   silenzio: entrano nel diff come conflitti e si applicano solo se
   l'utente li elenca esplicitamente;
4. il percorso di creazione rifiuta un documento da cui non si estrae nulla,
   invece di generare un progetto fantasma.
"""

from datetime import date
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
import models  # noqa: F401 - registra i modelli sul Base
import routers.convenzione_upload as convenzione_router


PDF_FINTO = b"%PDF-1.4 atto di concessione"


def _estrazione(**piano):
    """Risultato del parser con i campi piano richiesti (resto vuoto)."""
    base = {
        "codice_fapi": None,
        "titolo": None,
        "delibera_numero": None,
        "delibera_data": None,
        "costo_totale": None,
        "contributo_ente": None,
        "cofinanziamento": None,
    }
    base.update(piano)
    return {
        "piano": base,
        "ente_attuatore": {"ragione_sociale": None, "partita_iva": None},
        "aziende_beneficiarie": [],
        "codici_progetto": [],
        "warnings": [],
    }


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'ux6.db'}",
        connect_args={"check_same_thread": False},
    )
    factory = sessionmaker(
        autocommit=False, autoflush=False, bind=engine, expire_on_commit=False
    )
    Base.metadata.create_all(bind=engine)
    session = factory()
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


@pytest.fixture
def client(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(convenzione_router, "UPLOAD_DIR", str(tmp_path / "convenzioni"))
    Path(tmp_path / "convenzioni").mkdir(parents=True, exist_ok=True)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: _fake_user("admin")
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def progetto(db_session):
    """Progetto reale gia' esistente, con alcuni dati gia' validati."""
    project = models.Project(
        name="MAXI COMMUNICATION",
        ente_erogatore="FAPI",
        status="active",
        costo_totale=51242.03,
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


def _carica(client, project_id, monkeypatch, estrazione):
    monkeypatch.setattr(
        "services.parsers.fapi.convenzione_parser.parse_convenzione",
        lambda _path: estrazione,
    )
    resp = client.post(
        f"/api/v1/projects/{project_id}/upload-convenzione",
        files={"file": ("atto_concessione.pdf", PDF_FINTO, "application/pdf")},
    )
    return resp


def test_conferma_dentro_progetto_non_crea_un_secondo_progetto(
    client, db_session, progetto, monkeypatch
):
    """Il bug in una riga: dopo il caricamento i progetti restano uno."""
    upload = _carica(client, progetto.id, monkeypatch, _estrazione(codice_fapi="ABC123"))
    assert upload.status_code == 200, upload.text

    conferma = client.post(
        f"/api/v1/projects/{progetto.id}/confirm-convenzione",
        json={"preview_token": upload.json()["preview_token"]},
    )
    assert conferma.status_code == 200, conferma.text
    assert conferma.json()["project_id"] == progetto.id

    assert db_session.query(models.Project).count() == 1


def test_il_documento_resta_agganciato_al_progetto_corrente(
    client, db_session, progetto, monkeypatch
):
    upload = _carica(client, progetto.id, monkeypatch, _estrazione(codice_fapi="ABC123"))
    client.post(
        f"/api/v1/projects/{progetto.id}/confirm-convenzione",
        json={"preview_token": upload.json()["preview_token"]},
    )

    db_session.expire_all()
    aggiornato = db_session.get(models.Project, progetto.id)
    assert aggiornato.convenzione_file_path
    assert Path(aggiornato.convenzione_file_path).exists()


def test_campi_vuoti_arricchiti_dai_dati_estratti(
    client, db_session, progetto, monkeypatch
):
    """Arricchimento: cio' che sul progetto manca viene riempito."""
    upload = _carica(
        client,
        progetto.id,
        monkeypatch,
        _estrazione(
            codice_fapi="20250611CMIA001",
            delibera_numero="42",
            delibera_data="2026-03-01",
            contributo_ente=30000.0,
        ),
    )
    conferma = client.post(
        f"/api/v1/projects/{progetto.id}/confirm-convenzione",
        json={"preview_token": upload.json()["preview_token"]},
    )
    assert conferma.status_code == 200, conferma.text

    db_session.expire_all()
    aggiornato = db_session.get(models.Project, progetto.id)
    assert aggiornato.codice_fapi == "20250611CMIA001"
    assert aggiornato.delibera_numero == "42"
    assert aggiornato.delibera_data == date(2026, 3, 1)
    assert float(aggiornato.contributo_ente) == 30000.0


def test_valore_discordante_e_un_conflitto_non_una_sovrascrittura(
    client, db_session, progetto, monkeypatch
):
    """Il progetto ha gia' costo_totale validato: l'atto non lo ribalta."""
    upload = _carica(
        client, progetto.id, monkeypatch, _estrazione(costo_totale=99999.0)
    )
    assert upload.status_code == 200, upload.text

    diff = {c["campo"]: c for c in upload.json()["diff"]}
    assert diff["costo_totale"]["conflitto"] is True
    assert float(diff["costo_totale"]["valore_attuale"]) == 51242.03
    assert float(diff["costo_totale"]["valore_estratto"]) == 99999.0

    conferma = client.post(
        f"/api/v1/projects/{progetto.id}/confirm-convenzione",
        json={"preview_token": upload.json()["preview_token"]},
    )
    assert conferma.status_code == 200, conferma.text
    assert "costo_totale" in conferma.json()["campi_in_conflitto_non_applicati"]

    db_session.expire_all()
    assert float(db_session.get(models.Project, progetto.id).costo_totale) == 51242.03


def test_conflitto_applicato_solo_se_scelto_esplicitamente(
    client, db_session, progetto, monkeypatch
):
    upload = _carica(
        client, progetto.id, monkeypatch, _estrazione(costo_totale=99999.0)
    )
    conferma = client.post(
        f"/api/v1/projects/{progetto.id}/confirm-convenzione",
        json={
            "preview_token": upload.json()["preview_token"],
            "campi_da_applicare": ["costo_totale"],
        },
    )
    assert conferma.status_code == 200, conferma.text
    assert "costo_totale" in conferma.json()["campi_applicati"]

    db_session.expire_all()
    assert float(db_session.get(models.Project, progetto.id).costo_totale) == 99999.0


def test_token_di_un_altro_progetto_rifiutato(
    client, db_session, progetto, monkeypatch
):
    altro = models.Project(name="Altro", ente_erogatore="FAPI", status="active")
    db_session.add(altro)
    db_session.commit()

    upload = _carica(client, progetto.id, monkeypatch, _estrazione(codice_fapi="X1"))
    conferma = client.post(
        f"/api/v1/projects/{altro.id}/confirm-convenzione",
        json={"preview_token": upload.json()["preview_token"]},
    )
    assert conferma.status_code == 400


def test_documento_non_riconosciuto_non_crea_progetti_fantasma(
    client, db_session, monkeypatch
):
    """Regressione diretta del progetto 13 "Piano FAPI" creato in produzione.

    Il percorso di creazione riceve un PDF che non e' una convenzione: il
    parser non estrae ne' codice ne' titolo. Prima si creava comunque un
    progetto col nome di fallback.
    """
    monkeypatch.setattr(
        "services.parsers.fapi.convenzione_parser.parse_convenzione",
        lambda _path: _estrazione(),
    )
    upload = client.post(
        "/api/v1/projects/upload-convenzione",
        files={"file": ("atto_concessione.pdf", PDF_FINTO, "application/pdf")},
    )
    assert upload.status_code == 200, upload.text

    conferma = client.post(
        "/api/v1/projects/confirm-convenzione",
        json={
            "preview_token": upload.json()["preview_token"],
            "data_approvazione": "2026-03-24",
            "data_avvio_piano": "2026-04-01",
        },
    )
    assert conferma.status_code == 422, conferma.text
    assert "non riconosciuto" in conferma.json()["detail"].lower()
    assert db_session.query(models.Project).count() == 0


def test_creazione_resta_possibile_con_documento_riconosciuto(
    client, db_session, monkeypatch
):
    """Non-regressione: la convenzione vera continua a creare il progetto."""
    monkeypatch.setattr(
        "services.parsers.fapi.convenzione_parser.parse_convenzione",
        lambda _path: _estrazione(codice_fapi="20250611CMIA001", costo_totale=1000.0),
    )
    upload = client.post(
        "/api/v1/projects/upload-convenzione",
        files={"file": ("convenzione.pdf", PDF_FINTO, "application/pdf")},
    )
    conferma = client.post(
        "/api/v1/projects/confirm-convenzione",
        json={
            "preview_token": upload.json()["preview_token"],
            "data_approvazione": "2026-03-24",
            "data_avvio_piano": "2026-04-01",
        },
    )
    assert conferma.status_code == 200, conferma.text
    assert db_session.query(models.Project).count() == 1
    assert conferma.json()["codice_fapi"] == "20250611CMIA001"


def test_creazione_da_convenzione_richiede_le_date_amministrative(
    client, db_session, monkeypatch
):
    monkeypatch.setattr(
        "services.parsers.fapi.convenzione_parser.parse_convenzione",
        lambda _path: _estrazione(codice_fapi="FAPI-SENZA-DATE"),
    )
    upload = client.post(
        "/api/v1/projects/upload-convenzione",
        files={"file": ("convenzione.pdf", PDF_FINTO, "application/pdf")},
    )
    conferma = client.post(
        "/api/v1/projects/confirm-convenzione",
        json={"preview_token": upload.json()["preview_token"]},
    )

    assert conferma.status_code == 400, conferma.text
    assert "data approvazione" in conferma.json()["detail"].lower()
    assert "data avvio piano" in conferma.json()["detail"].lower()
    assert db_session.query(models.Project).count() == 0


# ------------------------------------------------------------------
# RBAC: i nuovi endpoint ricadono sotto /api/v1/projects (operational)
# ------------------------------------------------------------------


@pytest.fixture
def client_rbac(db_session, tmp_path, monkeypatch):
    import auth as auth_module

    monkeypatch.setattr(auth_module, "RBAC_ENFORCE", True)
    monkeypatch.setattr(convenzione_router, "UPLOAD_DIR", str(tmp_path / "convenzioni"))
    Path(tmp_path / "convenzioni").mkdir(parents=True, exist_ok=True)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_rbac_consultazione_non_puo_caricare_documenti(client_rbac, progetto):
    app.dependency_overrides[get_current_user] = lambda: _fake_user("consultazione")
    resp = client_rbac.post(
        f"/api/v1/projects/{progetto.id}/upload-convenzione",
        files={"file": ("atto.pdf", PDF_FINTO, "application/pdf")},
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.parametrize("role", ["admin", "operatore"])
def test_rbac_ruoli_operativi_possono_associare(
    client_rbac, progetto, monkeypatch, role
):
    app.dependency_overrides[get_current_user] = lambda: _fake_user(role)
    monkeypatch.setattr(
        "services.parsers.fapi.convenzione_parser.parse_convenzione",
        lambda _path: _estrazione(codice_fapi=f"COD-{role}"),
    )
    resp = client_rbac.post(
        f"/api/v1/projects/{progetto.id}/upload-convenzione",
        files={"file": ("atto.pdf", PDF_FINTO, "application/pdf")},
    )
    assert resp.status_code == 200, f"{role}: {resp.text[:200]}"


# ------------------------------------------------------------------
# Fondimpresa: stessa classe di bug, stessa regola
# ------------------------------------------------------------------

import routers.fondimpresa_upload as fondimpresa_router  # noqa: E402


@pytest.fixture
def client_fondimpresa(db_session, tmp_path, monkeypatch):
    ammissioni = tmp_path / "ammissioni"
    ammissioni.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(fondimpresa_router, "AMMISSIONI_DIR", str(ammissioni))

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: _fake_user("admin")
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _patch_ammissione(monkeypatch, dati):
    monkeypatch.setattr(
        fondimpresa_router.AmmissioneParser, "parse", lambda _self, _path: dict(dati)
    )


def test_ammissione_dentro_progetto_non_crea_un_secondo_progetto(
    client_fondimpresa, db_session, progetto, monkeypatch
):
    _patch_ammissione(monkeypatch, {"codice_piano": "FI-1", "titolo_piano": "Piano FI"})
    upload = client_fondimpresa.post(
        f"/api/v1/projects/{progetto.id}/fondimpresa/upload-ammissione",
        files={"file": ("lettera.pdf", PDF_FINTO, "application/pdf")},
    )
    assert upload.status_code == 200, upload.text

    conferma = client_fondimpresa.post(
        f"/api/v1/projects/{progetto.id}/fondimpresa/confirm-ammissione",
        json={"preview_token": upload.json()["preview_token"]},
    )
    assert conferma.status_code == 200, conferma.text
    assert db_session.query(models.Project).count() == 1
    db_session.expire_all()
    assert db_session.get(models.Project, progetto.id).codice_fapi == "FI-1"


def test_ammissione_non_riconosciuta_non_crea_progetti_fantasma(
    client_fondimpresa, db_session, monkeypatch
):
    _patch_ammissione(monkeypatch, {"codice_piano": None, "titolo_piano": None})
    upload = client_fondimpresa.post(
        "/api/v1/projects/fondimpresa/upload-ammissione",
        files={"file": ("lettera.pdf", PDF_FINTO, "application/pdf")},
    )
    assert upload.status_code == 200, upload.text

    conferma = client_fondimpresa.post(
        "/api/v1/projects/fondimpresa/confirm-ammissione",
        json={
            "preview_token": upload.json()["preview_token"],
            "data_approvazione": "2026-03-24",
            "data_avvio_piano": "2026-04-01",
        },
    )
    assert conferma.status_code == 422, conferma.text
    assert db_session.query(models.Project).count() == 0


def test_ammissione_riconosciuta_continua_a_creare_il_progetto(
    client_fondimpresa, db_session, monkeypatch
):
    _patch_ammissione(
        monkeypatch, {"codice_piano": "FI-9", "titolo_piano": "Piano Fondimpresa"}
    )
    upload = client_fondimpresa.post(
        "/api/v1/projects/fondimpresa/upload-ammissione",
        files={"file": ("lettera.pdf", PDF_FINTO, "application/pdf")},
    )
    conferma = client_fondimpresa.post(
        "/api/v1/projects/fondimpresa/confirm-ammissione",
        json={
            "preview_token": upload.json()["preview_token"],
            "data_approvazione": "2026-03-24",
            "data_avvio_piano": "2026-04-01",
        },
    )
    assert conferma.status_code == 200, conferma.text
    assert db_session.query(models.Project).count() == 1


def test_creazione_da_ammissione_richiede_le_date_amministrative(
    client_fondimpresa, db_session, monkeypatch
):
    _patch_ammissione(
        monkeypatch, {"codice_piano": "FI-SENZA-DATE", "titolo_piano": "Piano"}
    )
    upload = client_fondimpresa.post(
        "/api/v1/projects/fondimpresa/upload-ammissione",
        files={"file": ("lettera.pdf", PDF_FINTO, "application/pdf")},
    )
    conferma = client_fondimpresa.post(
        "/api/v1/projects/fondimpresa/confirm-ammissione",
        json={"preview_token": upload.json()["preview_token"]},
    )

    assert conferma.status_code == 400, conferma.text
    assert "data approvazione" in conferma.json()["detail"].lower()
    assert "data avvio piano" in conferma.json()["detail"].lower()
    assert db_session.query(models.Project).count() == 0


def test_ente_attuatore_arricchito_come_intero(client, db_session, progetto, monkeypatch):
    """La FK e' Integer: un float ci finirebbe dentro senza rumore."""
    ente = models.ImplementingEntity(ragione_sociale="Ente Attuatore Srl", partita_iva="12345678901")
    db_session.add(ente)
    db_session.commit()

    estrazione = _estrazione(codice_fapi="ENTE-1")
    estrazione["ente_attuatore"] = {"ragione_sociale": "Ente Attuatore Srl", "partita_iva": "12345678901"}
    upload = _carica(client, progetto.id, monkeypatch, estrazione)
    assert upload.status_code == 200, upload.text

    voce = next(d for d in upload.json()["diff"] if d["campo"] == "ente_attuatore_id")
    assert voce["valore_estratto"] == ente.id
    assert isinstance(voce["valore_estratto"], int)

    client.post(
        f"/api/v1/projects/{progetto.id}/confirm-convenzione",
        json={"preview_token": upload.json()["preview_token"]},
    )
    db_session.expire_all()
    assert db_session.get(models.Project, progetto.id).ente_attuatore_id == ente.id
