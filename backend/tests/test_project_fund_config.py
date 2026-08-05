"""
Vista progetto unificata: ogni progetto, di qualunque fondo (o nessuno),
espone fund_config nella risposta GET /projects/{id}, con le etichette
risolte da atto_concessorio_registry. Mai assente, mai null.
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
from auth import get_current_user
import models  # noqa: F401


@pytest.fixture(scope="function")
def db_session(tmp_path):
    db_path = tmp_path / "test_fund_config.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
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


def _crea_progetto(db_session, ente_erogatore):
    project = models.Project(name=f"Progetto {ente_erogatore}", ente_erogatore=ente_erogatore)
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


@pytest.mark.parametrize(
    "ente_erogatore, atteso_codice_progetto",
    [
        ("FAPI", "Codice FAPI"),
        ("Formazienda", "Codice pratica Formazienda"),
        ("Fondimpresa", "Codice pratica Fondimpresa"),
        ("Ente Non Censito", "Codice progetto"),
        (None, "Codice progetto"),
    ],
)
def test_fund_config_su_get_project(client, db_session, ente_erogatore, atteso_codice_progetto):
    project = _crea_progetto(db_session, ente_erogatore)

    response = client.get(f"/api/v1/projects/{project.id}")
    assert response.status_code == 200, response.text
    fund_config = response.json()["fund_config"]

    assert fund_config is not None
    assert fund_config["etichetta_codice_progetto"] == atteso_codice_progetto
    assert fund_config["etichetta_atto"]
    assert fund_config["etichetta_formulario"]
    assert fund_config["etichetta_piano_finanziario"]


def test_fund_config_su_lista_progetti(client, db_session):
    _crea_progetto(db_session, "FAPI")
    _crea_progetto(db_session, "Formazienda")

    response = client.get("/api/v1/projects")
    assert response.status_code == 200, response.text
    progetti = response.json()
    assert len(progetti) == 2
    for progetto in progetti:
        assert progetto["fund_config"] is not None
