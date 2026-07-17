"""
Test F2-004: portale allievi coerente.

La pagina /portale-allievi e' pubblica e autentica l'allievo con un
magic token in query string, ma l'endpoint profilo era incluso dietro
la protezione JWT globale: un allievo esterno (senza Bearer) riceveva
401 dal layer auth prima ancora che il token portale venisse valutato.

Design atteso:
- GET /api/v1/portale-allievi/profilo e' raggiungibile SENZA Bearer;
  l'autenticazione e' il magic token (401 solo se token invalido).
- Il generatore di magic link (/api/v1/allievi/{id}/magic-link) resta
  dietro la protezione JWT (funzione staff).
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
import models  # noqa: F401  # assicura registrazione metadata
from services.portale_allievi_tokens import issue_portal_token


def _magic_token(allievo_id: int, _email: str) -> str:
    return issue_portal_token(allievo_id)


@pytest.fixture(scope="function")
def db_session(tmp_path):
    """Fornisce una sessione DB isolata per ogni test."""
    db_path = tmp_path / "test_portale.db"
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
    """Client SENZA override di autenticazione: simula un utente esterno."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def allievo(db_session):
    obj = models.Allievo(nome="Mario", cognome="Rossi", email="mario.rossi@example.com")
    db_session.add(obj)
    db_session.commit()
    db_session.refresh(obj)
    return obj


class TestPortaleAllieviPubblico:
    """L'endpoint profilo deve funzionare senza Bearer JWT."""

    def test_token_valido_senza_bearer_200(self, client, allievo):
        token = _magic_token(allievo.id, allievo.email)
        response = client.get(f"/api/v1/portale-allievi/profilo?token={token}")
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["allievo"]["id"] == allievo.id
        assert data["allievo"]["nome"] == "Mario"
        assert data["progetti"] == []

    def test_token_invalido_401_dal_portale(self, client, allievo):
        response = client.get("/api/v1/portale-allievi/profilo?token=tokenfarlocco")
        assert response.status_code == 401
        assert response.json()["detail"] == "Token non valido o scaduto"

    def test_token_mancante_422(self, client):
        response = client.get("/api/v1/portale-allievi/profilo")
        assert response.status_code == 422


class TestMagicLinkResteProtetto:
    """Il generatore di magic link resta funzione staff dietro JWT."""

    def test_magic_link_senza_bearer_negato(self, client, allievo):
        response = client.get(f"/api/v1/allievi/{allievo.id}/magic-link")
        assert response.status_code in (401, 403)
