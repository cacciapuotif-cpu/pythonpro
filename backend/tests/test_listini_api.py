"""
Test F2-001: CRUD listini.

I GET principali dei listini andavano in 500 perche' il router chiamava
funzioni CRUD assenti (crud.get_listini, crud.get_listino, ecc.).
Questi test coprono il ciclo completo listino + voci e la matrice RBAC.
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
    """Fornisce una sessione DB isolata per ogni test."""
    db_path = tmp_path / "test_listini.db"
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
    """Override di get_db per usare il DB temporaneo del test."""

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


def _crea_listino(client, **overrides):
    payload = {
        "nome": "Listino Standard",
        "descrizione": "Listino di test",
        "tipo_cliente": "standard",
        "attivo": True,
    }
    payload.update(overrides)
    response = client.post("/api/v1/listini/", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _crea_prodotto(db_session):
    prodotto = models.Prodotto(
        codice="PRD-TEST-1",
        nome="Corso Python",
        tipo="formazione",
        prezzo_base=100.0,
        unita_misura="ora",
        attivo=True,
    )
    db_session.add(prodotto)
    db_session.commit()
    db_session.refresh(prodotto)
    return prodotto


class TestListiniCrud:
    """F2-001: i GET listini devono rispondere 200/404, mai 500."""

    def test_get_listini_vuoto(self, client):
        response = client.get("/api/v1/listini/")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_e_get_listini(self, client):
        creato = _crea_listino(client)
        response = client.get("/api/v1/listini/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == creato["id"]
        assert data[0]["nome"] == "Listino Standard"

    def test_get_listino_dettaglio(self, client):
        creato = _crea_listino(client)
        response = client.get(f"/api/v1/listini/{creato['id']}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == creato["id"]
        assert data["voci"] == []

    def test_get_listino_inesistente_404(self, client):
        response = client.get("/api/v1/listini/999999")
        assert response.status_code == 404

    def test_get_voci_listino_inesistente_404(self, client):
        response = client.get("/api/v1/listini/999999/voci")
        assert response.status_code == 404

    def test_filtro_tipo_cliente(self, client):
        _crea_listino(client, nome="Listino Standard", tipo_cliente="standard")
        _crea_listino(client, nome="Listino Apprendistato", tipo_cliente="apprendistato")
        response = client.get("/api/v1/listini/", params={"tipo_cliente": "apprendistato"})
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["tipo_cliente"] == "apprendistato"

    def test_filtro_search(self, client):
        _crea_listino(client, nome="Listino Alfa")
        _crea_listino(client, nome="Listino Beta")
        response = client.get("/api/v1/listini/", params={"search": "beta"})
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["nome"] == "Listino Beta"

    def test_update_listino(self, client):
        creato = _crea_listino(client)
        response = client.put(
            f"/api/v1/listini/{creato['id']}",
            json={"nome": "Listino Rinominato"},
        )
        assert response.status_code == 200
        assert response.json()["nome"] == "Listino Rinominato"

    def test_update_listino_inesistente_404(self, client):
        response = client.put("/api/v1/listini/999999", json={"nome": "Nuovo Nome"})
        assert response.status_code == 404

    def test_delete_listino_soft(self, client):
        creato = _crea_listino(client)
        response = client.delete(f"/api/v1/listini/{creato['id']}")
        assert response.status_code == 200
        assert response.json()["attivo"] is False
        # Il listino resta leggibile (soft delete)
        response = client.get(f"/api/v1/listini/{creato['id']}")
        assert response.status_code == 200

    def test_delete_listino_inesistente_404(self, client):
        response = client.delete("/api/v1/listini/999999")
        assert response.status_code == 404


class TestListinoVoci:
    """Ciclo voci con prodotto embedded e prezzo calcolato."""

    def test_add_e_get_voci(self, client, db_session):
        listino = _crea_listino(client)
        prodotto = _crea_prodotto(db_session)
        response = client.post(
            f"/api/v1/listini/{listino['id']}/voci",
            json={
                "listino_id": listino["id"],
                "prodotto_id": prodotto.id,
                "sconto_percentuale": 10.0,
            },
        )
        assert response.status_code == 201, response.text
        voce = response.json()
        assert voce["prezzo_finale"] == pytest.approx(90.0)

        response = client.get(f"/api/v1/listini/{listino['id']}/voci")
        assert response.status_code == 200
        voci = response.json()
        assert len(voci) == 1
        assert voci[0]["prodotto"]["id"] == prodotto.id
        assert voci[0]["prezzo_finale"] == pytest.approx(90.0)

    def test_dettaglio_listino_include_voci(self, client, db_session):
        listino = _crea_listino(client)
        prodotto = _crea_prodotto(db_session)
        client.post(
            f"/api/v1/listini/{listino['id']}/voci",
            json={"listino_id": listino["id"], "prodotto_id": prodotto.id},
        )
        response = client.get(f"/api/v1/listini/{listino['id']}")
        assert response.status_code == 200
        assert len(response.json()["voci"]) == 1


class TestListiniRbacMatrix:
    """RBAC: listini e' prefisso operativo, matrice gia' coperta da require_role."""

    @pytest.mark.parametrize(
        "method,path,expected_by_role",
        [
            ("GET", "/api/v1/listini/", {"admin": 200, "operatore": 200, "consultazione": 200}),
            ("GET", "/api/v1/listini/1", {"admin": 200, "operatore": 200, "consultazione": 200}),
            ("GET", "/api/v1/listini/1/voci", {"admin": 200, "operatore": 200, "consultazione": 200}),
            ("POST", "/api/v1/listini/", {"admin": 200, "operatore": 200, "consultazione": 403}),
            ("PUT", "/api/v1/listini/1", {"admin": 200, "operatore": 200, "consultazione": 403}),
            ("DELETE", "/api/v1/listini/1", {"admin": 200, "operatore": 200, "consultazione": 403}),
        ],
    )
    @pytest.mark.parametrize(
        "role",
        [UserRole.ADMIN.value, UserRole.OPERATORE.value, UserRole.CONSULTAZIONE.value],
    )
    def test_rbac_listini(self, method, path, expected_by_role, role):
        decision = rbac_decision_for(method, path, role)
        assert decision["would_status"] == expected_by_role[role]
