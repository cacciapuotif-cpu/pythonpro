"""FASE E1 (Task E1.2.c) — rinomina Avviso.template_id → contract_template_id.

Il vecchio campo puntava a contract_templates (template CONTRATTI) con un nome
che suggeriva i template dei piani finanziari. Contratto API dopo la rinomina:
- `contract_template_id` accettato in create/update ed esposto in lettura;
- il vecchio `template_id` viene rifiutato con 422 (non più ignorato in silenzio).
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
import models


AVVISO_PAYLOAD = {
    "codice": "9/2026",
    "ente_erogatore": "Fapi",
    "fondo": "fapi",
    "titolo": "Avviso test rinomina",
}


@pytest.fixture(scope="function")
def db_session(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test_avviso_rename.db'}",
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


@pytest.fixture
def contract_template(db_session):
    tpl = models.ContractTemplate(
        nome_template="Template contratto test",
        tipo_contratto="documento_generico",
        contenuto_html="<p>{{collaboratore_nome_completo}}</p>",
        is_active=True,
    )
    db_session.add(tpl)
    db_session.commit()
    return tpl


def test_create_avviso_con_contract_template_id(client, contract_template):
    payload = dict(AVVISO_PAYLOAD, contract_template_id=contract_template.id)
    resp = client.post("/api/v1/avvisi/", json=payload)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["contract_template_id"] == contract_template.id
    assert "template_id" not in body


def test_update_avviso_contract_template_id(client, contract_template):
    created = client.post("/api/v1/avvisi/", json=AVVISO_PAYLOAD)
    assert created.status_code == 200, created.text
    avviso_id = created.json()["id"]
    assert created.json()["contract_template_id"] is None

    resp = client.put(
        f"/api/v1/avvisi/{avviso_id}",
        json={"contract_template_id": contract_template.id},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["contract_template_id"] == contract_template.id


def test_vecchio_template_id_rifiutato_422(client, contract_template):
    payload = dict(AVVISO_PAYLOAD, template_id=contract_template.id)
    resp = client.post("/api/v1/avvisi/", json=payload)
    assert resp.status_code == 422, resp.text
    assert "contract_template_id" in resp.text

    created = client.post("/api/v1/avvisi/", json=AVVISO_PAYLOAD)
    avviso_id = created.json()["id"]
    resp = client.put(f"/api/v1/avvisi/{avviso_id}", json={"template_id": 1})
    assert resp.status_code == 422, resp.text
