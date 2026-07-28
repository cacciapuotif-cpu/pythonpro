"""UX-6b — il match globale deve offrire associazione, update o creazione esplicita."""

from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

from auth import get_current_user, rbac_decision_for
from database import Base, get_db
from main import app
import models
import routers.convenzione_upload as convenzione_router


PDF_FINTO = b"%PDF-1.4 convenzione UX-6b"


def estrazione(*, costo=200.0, contributo=50.0):
    return {
        "piano": {
            "codice_fapi": "20250611CMIA001",
            "titolo": "Titolo estratto",
            "delibera_numero": "42",
            "delibera_data": "2026-03-24",
            "costo_totale": costo,
            "contributo_ente": contributo,
            "cofinanziamento": 150.0,
        },
        "ente_attuatore": {
            "ragione_sociale": "Ente Test",
            "partita_iva": "12345678901",
        },
        "aziende_beneficiarie": [
            {
                "ragione_sociale": "Beneficiaria Srl",
                "partita_iva": "10987654321",
                "num_partecipanti": 4,
                "codice_progetto": "20250611CMIA00101",
                "importo": 200.0,
            }
        ],
        "codici_progetto": ["20250611CMIA00101"],
        "warnings": [],
    }


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'ux6b.db'}",
        connect_args={"check_same_thread": False},
    )
    factory = sessionmaker(
        autocommit=False, autoflush=False, expire_on_commit=False, bind=engine
    )
    Base.metadata.create_all(bind=engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def client(db_session, tmp_path, monkeypatch):
    upload_dir = tmp_path / "convenzioni"
    upload_dir.mkdir()
    monkeypatch.setattr(convenzione_router, "UPLOAD_DIR", str(upload_dir))
    monkeypatch.setattr(
        "services.parsers.fapi.convenzione_parser.parse_convenzione",
        lambda _path: estrazione(),
    )

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: type(
        "User",
        (),
        {
            "id": 1,
            "username": "ux6b-admin",
            "email": "ux6b@example.com",
            "role": "admin",
            "is_active": True,
        },
    )()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def progetto(db_session):
    ente = models.ImplementingEntity(
        ragione_sociale="Ente Test",
        partita_iva="12345678901",
    )
    azienda = models.AziendaCliente(
        ragione_sociale="Beneficiaria Srl",
        partita_iva="10987654321",
        attivo=True,
    )
    project = models.Project(
        name="Titolo validato",
        codice_fapi="20250611CMIA001",
        costo_totale=100,
        ente_attuatore=ente,
        status="active",
    )
    db_session.add_all([ente, azienda, project])
    db_session.flush()
    db_session.add(
        models.AziendaClienteProjectLink(
            project_id=project.id,
            azienda_cliente_id=azienda.id,
        )
    )
    db_session.commit()
    return project


def upload_globale(client):
    response = client.post(
        "/api/v1/projects/upload-convenzione",
        files={"file": ("convenzione.pdf", PDF_FINTO, "application/pdf")},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_match_esatto_restituisce_bivio_e_confronto_completo(client, progetto):
    preview = upload_globale(client)

    assert preview["existing_project_id"] == progetto.id
    assert preview["azione_predefinita"] == "associa"
    assert preview["match"]["stato"] == "esatto"
    assert preview["match"]["candidati"][0]["project_id"] == progetto.id
    confronto = {riga["campo"]: riga for riga in preview["confronto"]}
    assert confronto["codice_fapi"]["stato"] == "identico"
    assert confronto["name"]["stato"] == "diverso"
    assert confronto["contributo_ente"]["stato"] == "assente_nel_sistema"


def test_azione_predefinita_associa_archivia_senza_creare(client, db_session, progetto):
    preview = upload_globale(client)
    response = client.post(
        f"/api/v1/projects/{progetto.id}/confirm-convenzione",
        json={
            "preview_token": preview["preview_token"],
            "modalita": "associa",
            "tipo_documento": "convenzione",
            "campi_da_applicare": [],
        },
    )
    assert response.status_code == 200, response.text
    assert db_session.query(models.Project).count() == 1
    db_session.refresh(progetto)
    assert float(progetto.costo_totale) == 100.0
    assert progetto.contributo_ente is None

    documento_model = getattr(models, "ProjectDocumento", None)
    assert documento_model is not None
    documento = db_session.query(documento_model).one()
    assert documento.project_id == progetto.id
    assert documento.tipo_documento == "convenzione"
    assert documento.versione == 1
    assert documento.caricato_da_user_id == 1


def test_associa_documento_non_crea_aziende_o_collegamenti(
    client, db_session, progetto, monkeypatch
):
    altra = estrazione()
    altra["aziende_beneficiarie"] = [{
        "ragione_sociale": "Impresa non censita",
        "partita_iva": "11111111111",
        "num_partecipanti": 3,
        "codice_progetto": "20250611CMIA00199",
        "importo": 1234.0,
    }]
    monkeypatch.setattr(
        "services.parsers.fapi.convenzione_parser.parse_convenzione",
        lambda _path: altra,
    )
    aziende_prima = db_session.query(models.AziendaCliente).count()
    link_prima = db_session.query(models.AziendaClienteProjectLink).count()

    preview = upload_globale(client)
    response = client.post(
        f"/api/v1/projects/{progetto.id}/confirm-convenzione",
        json={"preview_token": preview["preview_token"], "modalita": "associa"},
    )

    assert response.status_code == 200, response.text
    assert db_session.query(models.AziendaCliente).count() == aziende_prima
    assert db_session.query(models.AziendaClienteProjectLink).count() == link_prima


def test_update_applica_solo_i_campi_scelti(client, db_session, progetto):
    preview = upload_globale(client)
    response = client.post(
        f"/api/v1/projects/{progetto.id}/confirm-convenzione",
        json={
            "preview_token": preview["preview_token"],
            "modalita": "aggiorna",
            "tipo_documento": "atto_concessione",
            "campi_da_applicare": ["costo_totale"],
        },
    )
    assert response.status_code == 200, response.text
    db_session.refresh(progetto)
    assert float(progetto.costo_totale) == 200.0
    assert progetto.name == "Titolo validato"
    assert progetto.contributo_ente is None
    assert response.json()["campi_applicati"] == ["costo_totale"]


def test_crea_comunque_pretende_seconda_conferma_server_side(
    client, db_session, progetto
):
    preview = upload_globale(client)
    senza_conferma = client.post(
        "/api/v1/projects/confirm-convenzione",
        json={
            "preview_token": preview["preview_token"],
            "data_approvazione": "2026-03-24",
            "data_avvio_piano": "2026-04-01",
        },
    )
    assert senza_conferma.status_code == 409
    assert db_session.query(models.Project).count() == 1

    preview = upload_globale(client)
    confermato = client.post(
        "/api/v1/projects/confirm-convenzione",
        json={
            "preview_token": preview["preview_token"],
            "data_approvazione": "2026-03-24",
            "data_avvio_piano": "2026-04-01",
            "conferma_creazione_duplicato": True,
        },
    )
    assert confermato.status_code == 200, confermato.text
    assert db_session.query(models.Project).count() == 2


def test_azienda_gia_associata_non_viene_duplicata(client, db_session, progetto):
    preview = upload_globale(client)
    response = client.post(
        f"/api/v1/projects/{progetto.id}/confirm-convenzione",
        json={
            "preview_token": preview["preview_token"],
            "modalita": "associa",
            "campi_da_applicare": [],
        },
    )
    assert response.status_code == 200, response.text
    links = db_session.query(models.AziendaClienteProjectLink).filter_by(
        project_id=progetto.id
    ).all()
    assert len(links) == 1


def test_documenti_stesso_tipo_sono_versionati(client, db_session, progetto):
    for _ in range(2):
        preview = upload_globale(client)
        response = client.post(
            f"/api/v1/projects/{progetto.id}/confirm-convenzione",
            json={
                "preview_token": preview["preview_token"],
                "modalita": "associa",
                "tipo_documento": "convenzione",
            },
        )
        assert response.status_code == 200, response.text

    documento_model = getattr(models, "ProjectDocumento", None)
    assert documento_model is not None
    versioni = [
        row.versione
        for row in db_session.query(documento_model)
        .filter_by(project_id=progetto.id, tipo_documento="convenzione")
        .order_by(documento_model.versione)
    ]
    assert versioni == [1, 2]


def test_due_match_esatti_restano_ambiguamente_da_scegliere(
    client, db_session, progetto
):
    db_session.add(
        models.Project(
            name="Secondo candidato",
            codice_fapi=progetto.codice_fapi,
            status="active",
        )
    )
    db_session.commit()

    preview = upload_globale(client)
    assert preview["existing_project_id"] is None
    assert preview["match"]["stato"] == "incerto"
    assert {c["project_id"] for c in preview["match"]["candidati"]} == {
        progetto.id,
        progetto.id + 1,
    }
    confronti = preview["confronti_per_progetto"]
    assert set(confronti) == {str(progetto.id), str(progetto.id + 1)}
    primo = {riga["campo"]: riga for riga in confronti[str(progetto.id)]}
    secondo = {riga["campo"]: riga for riga in confronti[str(progetto.id + 1)]}
    assert primo["name"]["valore_attuale"] == "Titolo validato"
    assert secondo["name"]["valore_attuale"] == "Secondo candidato"


def test_token_match_non_puo_essere_associato_a_un_progetto_estraneo(
    client, db_session, progetto
):
    estraneo = models.Project(name="Estraneo", codice_fapi="ALTRO", status="active")
    db_session.add(estraneo)
    db_session.commit()
    preview = upload_globale(client)

    response = client.post(
        f"/api/v1/projects/{estraneo.id}/confirm-convenzione",
        json={"preview_token": preview["preview_token"], "modalita": "associa"},
    )
    assert response.status_code == 400
    assert db_session.query(models.ProjectDocumento).count() == 0


def test_match_su_codice_progetto_dei_moduli(client, db_session, progetto):
    progetto.codice_fapi = None
    db_session.add(
        models.ModuloFormativo(
            project_id=progetto.id,
            codice_progetto_fapi="20250611CMIA00101",
            titolo_modulo="Modulo",
            tipo_attivita="formativa",
        )
    )
    db_session.commit()

    preview = upload_globale(client)
    assert preview["existing_project_id"] == progetto.id
    assert "codice_progetto" in preview["match"]["candidati"][0]["motivi"]


def test_match_fallback_triplo_e_sempre_sottoposto_a_scelta(
    client, db_session, progetto, monkeypatch
):
    progetto.codice_fapi = None
    progetto.delibera_numero = "42"
    progetto.costo_totale = 200
    db_session.commit()
    fallback = estrazione()
    fallback["piano"]["codice_fapi"] = None
    monkeypatch.setattr(
        "services.parsers.fapi.convenzione_parser.parse_convenzione",
        lambda _path: fallback,
    )

    preview = upload_globale(client)
    assert preview["existing_project_id"] is None
    assert preview["match"]["stato"] == "incerto"
    assert preview["match"]["candidati"][0]["project_id"] == progetto.id
    assert preview["match"]["candidati"][0]["motivi"] == [
        "ente_attuatore",
        "delibera",
        "costo_totale",
    ]


def test_documento_e_consultabile_e_scaricabile(client, progetto):
    preview = upload_globale(client)
    conferma = client.post(
        f"/api/v1/projects/{progetto.id}/confirm-convenzione",
        json={"preview_token": preview["preview_token"], "modalita": "associa"},
    )
    documento_id = conferma.json()["documento_id"]

    elenco = client.get(f"/api/v1/projects/{progetto.id}/documenti")
    assert elenco.status_code == 200, elenco.text
    assert elenco.json()[0]["id"] == documento_id
    download = client.get(
        f"/api/v1/projects/{progetto.id}/documenti/{documento_id}/download"
    )
    assert download.status_code == 200, download.text
    assert download.content == PDF_FINTO


@pytest.mark.parametrize("role", ["admin", "operatore", "consultazione"])
def test_rbac_documenti_progetto_leggibili_dai_tre_ruoli(role):
    assert rbac_decision_for(
        "GET", "/api/v1/projects/11/documenti", role
    )["would_status"] == 200
    assert rbac_decision_for(
        "GET", "/api/v1/projects/11/documenti/9/download", role
    )["would_status"] == 200
