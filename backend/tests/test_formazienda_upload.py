from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from auth import get_current_user
from database import Base, get_db
from main import app
import models

CAMPIONE = Path(__file__).parent.parent.parent / "imports" / "formazienda" / "ALLEGATO E.pdf"


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'formazienda_upload.db'}",
        connect_args={"check_same_thread": False},
    )
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: type(
        "TestUser", (), {"id": 1, "username": "op", "email": "op@example.com", "role": "admin", "is_active": True},
    )()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _upload(client):
    with open(CAMPIONE, "rb") as fh:
        return client.post(
            "/api/v1/projects/formazienda/upload-atto-adesione",
            files={"file": ("ALLEGATO E.pdf", fh, "application/pdf")},
        )


def test_upload_espone_ente_e_piano_senza_aziende(client):
    response = _upload(client)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["piano"]["titolo"] == "WHITE FORM"
    assert body["ente_attuatore"]["ragione_sociale"] == "NEXT GROUP S.R.L."
    assert body["aziende_beneficiarie"] == []


def test_confirm_crea_progetto_formazienda_con_ente_derivato_e_nessun_blocco(client, db_session):
    preview = _upload(client).json()
    response = client.post(
        "/api/v1/projects/formazienda/confirm-atto-adesione",
        json={"preview_token": preview["preview_token"], "data_avvio_piano": "2026-07-01"},
    )
    assert response.status_code == 200, response.text
    project_id = response.json()["project_id"]

    project = db_session.query(models.Project).get(project_id)
    assert project.ente_erogatore == "Formazienda"
    assert project.ente_attuatore is not None
    assert project.ente_attuatore.ragione_sociale == "NEXT GROUP S.R.L."
    assert project.ente_attuatore.legale_rappresentante_cognome == "CACCIAPUOTI"

    documento = db_session.query(models.ProjectDocumento).filter(
        models.ProjectDocumento.project_id == project_id,
    ).first()
    assert documento.tipo_documento == "atto_concessione"
    assert documento.stato == "corrente"

    context = client.get(f"/api/v1/projects/{project_id}/delivery-context")
    assert context.status_code == 200, context.text
    assert context.json()["blocked_reason"] is None
    assert context.json()["ente_attuatore"]["ragione_sociale"] == "NEXT GROUP S.R.L."


def test_documento_illeggibile_si_archivia_comunque_e_permette_inserimento_manuale(client, tmp_path):
    junk = tmp_path / "junk.pdf"
    junk.write_bytes(b"%PDF-1.4 not a real pdf")
    with open(junk, "rb") as fh:
        response = client.post(
            "/api/v1/projects/formazienda/upload-atto-adesione",
            files={"file": ("junk.pdf", fh, "application/pdf")},
        )
    # Il parser non deve esplodere: torna un risultato vuoto con warning,
    # l'operatore prosegue a mano (Punto 3e). L'endpoint non deve restituire 500.
    assert response.status_code == 200, response.text
    assert response.json()["ente_attuatore"] == {}
    assert len(response.json()["warnings"]) > 0
