"""FASE E1 (Task E1.2.d) — i riferimenti legacy sui progetti non vengono più scartati in silenzio.

`crud._resolve_project_financial_refs` faceva `payload.pop("template_piano_finanziario_id")`
e `payload.pop("avviso_pf_id")`: chiavi che Pydantic aveva già ignorato (extra=ignore),
quindi un client che le inviava riceveva 200 senza che il dato fosse applicato.
Ora lo schema le rifiuta esplicitamente → 422.
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


PROJECT_PAYLOAD = {
    "name": "Progetto test legacy refs",
    "description": "desc",
    "status": "active",
    "atto_approvazione": "ATTO-1",
    "data_approvazione": "2026-03-24",
    "data_avvio_piano": "2026-04-01",
}


@pytest.fixture(scope="function")
def db_session(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test_legacy_refs.db'}",
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


@pytest.mark.parametrize("legacy_key", ["template_piano_finanziario_id", "avviso_pf_id"])
def test_create_project_con_chiave_legacy_422(client, legacy_key):
    payload = dict(PROJECT_PAYLOAD)
    payload[legacy_key] = 123
    resp = client.post("/api/v1/projects/", json=payload)
    assert resp.status_code == 422, resp.text
    assert legacy_key in resp.text


@pytest.mark.parametrize("legacy_key", ["template_piano_finanziario_id", "avviso_pf_id"])
def test_update_project_con_chiave_legacy_422(client, legacy_key):
    created = client.post("/api/v1/projects/", json=PROJECT_PAYLOAD)
    assert created.status_code == 200, created.text
    project_id = created.json()["id"]

    resp = client.put(f"/api/v1/projects/{project_id}", json={"name": "Nuovo nome", legacy_key: 5})
    assert resp.status_code == 422, resp.text
    assert legacy_key in resp.text


def test_create_e_update_senza_chiavi_legacy_invariati(client):
    created = client.post("/api/v1/projects/", json=PROJECT_PAYLOAD)
    assert created.status_code == 200, created.text
    project_id = created.json()["id"]

    updated = client.put(f"/api/v1/projects/{project_id}", json={"name": "Rinominato"})
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "Rinominato"
