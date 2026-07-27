"""Contratto API per sedi operative delle aziende clienti.

Una sede inviata dal frontend non deve essere scartata silenziosamente:
deve essere persistita e riesposta dalle API usate dall'import XLSX allievi.
"""

from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

from auth import get_current_user
from database import Base, get_db
from main import app
import models  # noqa: F401 - registra tutte le tabelle sul metadata


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test_azienda_sedi.db'}",
        connect_args={"check_same_thread": False},
    )
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = testing_session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

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


def test_update_persiste_e_riespone_sede_operativa(client, db_session):
    azienda = models.AziendaCliente(
        ragione_sociale="Power Impianti srl",
        partita_iva="12345678903",
    )
    db_session.add(azienda)
    db_session.commit()
    db_session.refresh(azienda)

    response = client.put(
        f"/api/v1/aziende-clienti/{azienda.id}",
        json={
            "sedi_operative": [
                {
                    "nome": "Napoli",
                    "indirizzo": "Via Roma 1",
                    "citta": "Napoli",
                    "cap": "80100",
                    "provincia": "na",
                }
            ]
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["sedi_operative"][0]["nome"] == "Napoli"
    assert response.json()["sedi_operative"][0]["provincia"] == "NA"

    db_session.expire_all()
    persisted = (
        db_session.query(models.AziendaClienteSedeOperativa)
        .filter(models.AziendaClienteSedeOperativa.azienda_cliente_id == azienda.id)
        .one()
    )
    assert persisted.nome == "Napoli"

    listing = client.get("/api/v1/aziende-clienti/?page=1&limit=100")
    assert listing.status_code == 200, listing.text
    item = next(row for row in listing.json()["items"] if row["id"] == azienda.id)
    assert item["sedi_operative"][0]["id"] == persisted.id
    assert item["sedi_operative"][0]["nome"] == "Napoli"


def test_create_persiste_relazioni_azienda(client, db_session):
    response = client.post(
        "/api/v1/aziende-clienti/",
        json={
            "ragione_sociale": "Azienda con sede",
            "partita_iva": "12345678903",
            "sedi_operative": [{"nome": "Napoli"}],
            "fund_memberships": [
                {
                    "fondo": "Fondimpresa",
                    "data_inizio": "2026-01-01T00:00:00Z",
                }
            ],
            "project_ids": [],
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["project_ids"] == []
    assert body["sedi_operative"][0]["nome"] == "Napoli"
    assert body["fund_memberships"][0]["fondo"] == "Fondimpresa"
    assert db_session.query(models.AziendaClienteSedeOperativa).count() == 1
    assert db_session.query(models.AziendaClienteFundMembership).count() == 1
