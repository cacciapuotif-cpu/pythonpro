"""ONDATA ARCHIVIO AVVISI — V2: endpoint ingest revisione con app FastAPI minimale."""

from pathlib import Path
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import auth as auth_module
import models
from database import Base, get_db
from routers import avvisi as avvisi_router_module
from services import avviso_ingest
from ai_agents import avviso_extractor as extractor_module


@pytest.fixture
def client_factory(tmp_path, monkeypatch):
    monkeypatch.setattr(avviso_ingest, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(extractor_module, "UPLOAD_DIR", tmp_path)
    engine = create_engine(
        "sqlite:///{}".format(tmp_path / "api.db"), connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine, "connect")
    def _fk(dbapi_connection, _):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    session = factory()

    def make(role="admin"):
        user = session.query(auth_module.User).filter(auth_module.User.username == f"u_{role}").first()
        if user is None:
            user = auth_module.User(
                username=f"u_{role}", email=f"{role}@example.com",
                hashed_password="not-used",
                role=role, is_active=True,
            )
            session.add(user)
            session.commit()
            session.refresh(user)
        app = FastAPI()
        # il router ha già prefix="/api/v1/avvisi" (backend/routers/avvisi.py:11)
        app.include_router(avvisi_router_module.router)
        app.dependency_overrides[get_db] = lambda: session
        app.dependency_overrides[avvisi_router_module.get_current_user] = lambda: user
        return TestClient(app), session, user
    yield make
    session.close()


def _crea_avviso(session):
    avviso = models.Avviso(
        codice="1/2026", ente_erogatore="fapi", fondo="fapi", numero="1", anno=2026,
        titolo="Avviso FAPI 1/2026", stato="bozza",
    )
    session.add(avviso)
    session.commit()
    return avviso


def test_ingest_creates_revision_without_extraction(client_factory, monkeypatch):
    client, session, _ = client_factory("admin")
    avviso = _crea_avviso(session)
    monkeypatch.setenv("AGENT_AVVISO_EXTRACTOR_ENABLED", "false")
    response = client.post(
        f"/api/v1/avvisi/{avviso.id}/revisioni/ingest",
        data={"titolo": "Avviso FAPI 1/2026", "esegui_estrazione": "true"},
        files={"file": ("avviso.md", b"# Art. 1\nTesto avviso.\n", "text/markdown")},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["revisione"]["numero_revisione"] == 1
    assert body["revisione"]["stato_estrazione"] == "segmentato"
    assert body["estrazione"]["skipped"]


def test_ingest_duplicate_sha_returns_409(client_factory, monkeypatch):
    client, session, _ = client_factory("admin")
    avviso = _crea_avviso(session)
    monkeypatch.setenv("AGENT_AVVISO_EXTRACTOR_ENABLED", "false")
    payload = {"titolo": "Avviso", "esegui_estrazione": "false"}
    files = {"file": ("avviso.md", b"# Art. 1\nTesto avviso.\n", "text/markdown")}
    assert client.post(f"/api/v1/avvisi/{avviso.id}/revisioni/ingest", data=payload, files=files).status_code == 201
    response = client.post(f"/api/v1/avvisi/{avviso.id}/revisioni/ingest", data=payload, files=files)
    assert response.status_code == 409


def test_ingest_rejects_non_admin_manager(client_factory):
    client, session, _ = client_factory("viewer")
    avviso = _crea_avviso(session)
    response = client.post(
        f"/api/v1/avvisi/{avviso.id}/revisioni/ingest",
        data={"titolo": "X"},
        files={"file": ("avviso.md", b"# A\ntesto\n", "text/markdown")},
    )
    assert response.status_code == 403


def test_ingest_invalid_file_returns_422(client_factory):
    client, session, _ = client_factory("admin")
    avviso = _crea_avviso(session)
    response = client.post(
        f"/api/v1/avvisi/{avviso.id}/revisioni/ingest",
        data={"titolo": "X"},
        files={"file": ("avviso.pdf", b"%PDF-", "application/pdf")},
    )
    assert response.status_code == 422


def test_list_revisioni_ordered_desc(client_factory, monkeypatch):
    client, session, _ = client_factory("admin")
    avviso = _crea_avviso(session)
    monkeypatch.setenv("AGENT_AVVISO_EXTRACTOR_ENABLED", "false")
    for i in (1, 2):
        client.post(
            f"/api/v1/avvisi/{avviso.id}/revisioni/ingest",
            data={"titolo": f"Rev {i}", "esegui_estrazione": "false"},
            files={"file": ("avviso.md", f"# Art. {i}\ntesto {i}\n".encode(), "text/markdown")},
        )
    response = client.get(f"/api/v1/avvisi/{avviso.id}/revisioni")
    assert response.status_code == 200
    numeri = [r["numero_revisione"] for r in response.json()]
    assert numeri == [2, 1]


def test_list_revisioni_supports_legacy_rows_without_markdown_source(client_factory):
    client, session, user = client_factory("admin")
    avviso = _crea_avviso(session)
    legacy = models.AvvisoRevisione(
        avviso_id=avviso.id,
        numero_revisione=1,
        titolo="Revisione legacy importata",
        stato_estrazione="caricato",
        created_by_user_id=user.id,
        source_md_path=None,
        original_filename=None,
        source_sha256=None,
    )
    session.add(legacy)
    session.commit()

    response = client.get(f"/api/v1/avvisi/{avviso.id}/revisioni")

    assert response.status_code == 200, response.text
    assert response.json()[0]["source_md_path"] is None
    assert response.json()[0]["original_filename"] is None
    assert response.json()[0]["source_sha256"] is None


def test_delete_avviso_is_soft_and_reserved_to_writers(client_factory):
    viewer, session, _ = client_factory("viewer")
    avviso = _crea_avviso(session)
    assert viewer.delete(f"/api/v1/avvisi/{avviso.id}").status_code == 403

    admin, _, _ = client_factory("admin")
    response = admin.delete(f"/api/v1/avvisi/{avviso.id}")

    assert response.status_code == 200, response.text
    session.refresh(avviso)
    assert avviso.is_active is False


def test_permanent_delete_requires_admin_double_confirmation_and_reports_links(client_factory):
    viewer, session, _ = client_factory("viewer")
    avviso = _crea_avviso(session)
    project = models.Project(
        name="Progetto collegato",
        description="Impatto hard delete",
        status="active",
        avviso_id=avviso.id,
    )
    session.add(project)
    session.commit()

    assert viewer.get(f"/api/v1/avvisi/{avviso.id}/deletion-impact").status_code == 403
    admin, _, _ = client_factory("admin")
    impact_response = admin.get(f"/api/v1/avvisi/{avviso.id}/deletion-impact")
    assert impact_response.status_code == 200, impact_response.text
    impact = impact_response.json()
    assert impact["projects"] == [{"id": project.id, "label": "Progetto collegato"}]

    wrong = admin.request(
        "DELETE",
        f"/api/v1/avvisi/{avviso.id}/permanent",
        json={"confirmation_phrase": "ELIMINA", "linked_records_confirmed": True},
    )
    assert wrong.status_code == 400
    missing_link_confirmation = admin.request(
        "DELETE",
        f"/api/v1/avvisi/{avviso.id}/permanent",
        json={
            "confirmation_phrase": impact["confirmation_phrase"],
            "linked_records_confirmed": False,
        },
    )
    assert missing_link_confirmation.status_code == 400

    deleted = admin.request(
        "DELETE",
        f"/api/v1/avvisi/{avviso.id}/permanent",
        json={
            "confirmation_phrase": impact["confirmation_phrase"],
            "linked_records_confirmed": True,
        },
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["detached_projects"] == 1
    session.expire_all()
    assert session.query(models.Avviso).filter(models.Avviso.id == avviso.id).first() is None
    assert session.query(models.Project).filter(models.Project.id == project.id).one().avviso_id is None
    audit = session.query(models.SecurityAuditLog).filter(
        models.SecurityAuditLog.azione == "avviso_hard_delete",
        models.SecurityAuditLog.risorsa_id == str(avviso.id),
    ).one()
    assert "Progetto collegato" in audit.dati_prima
