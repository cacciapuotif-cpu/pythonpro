"""UX-5 — modello esplicito delle date di progetto."""

from datetime import date, datetime
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
import crud
import models
import schemas


NUOVE_DATE = {
    "data_approvazione",
    "data_avvio_piano",
    "data_termine_piano",
    "data_avvio_attivita_formative",
    "data_fine_attivita_formative",
    "data_termine_rendicontazione",
    "data_chiusura_effettiva",
}


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'ux5-date.db'}",
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
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            db_session.rollback()

    def override_user():
        return type("User", (), {"id": 1, "role": "admin", "is_active": True})()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def payload_valido():
    return {
        "name": "UX-5 date esplicite",
        "description": "Progetto di prova",
        "status": "active",
        "data_approvazione": "2026-03-24",
        "data_avvio_piano": "2026-04-01",
        "data_termine_piano": "2027-03-31",
        "data_avvio_attivita_formative": None,
        "data_fine_attivita_formative": None,
        "data_termine_rendicontazione": "2027-05-31",
        "data_chiusura_effettiva": None,
    }


def test_modello_e_schema_espongono_le_sette_date():
    assert NUOVE_DATE <= set(models.Project.__table__.columns.keys())
    assert NUOVE_DATE <= set(schemas.Project.model_fields)
    assert NUOVE_DATE <= set(schemas.ProjectCreateExtended.model_fields)
    assert NUOVE_DATE <= set(schemas.ProjectUpdateExtended.model_fields)


def test_nuovo_progetto_attivo_richiede_approvazione_e_avvio_piano(client, db_session):
    response = client.post(
        "/api/v1/projects/",
        json={"name": "Senza date", "description": "Non valido", "status": "active"},
    )
    assert response.status_code in {400, 422}, response.text
    assert db_session.query(models.Project).count() == 0


def test_nuovo_progetto_con_date_coerenti_viene_creato(client, db_session):
    response = client.post("/api/v1/projects/", json=payload_valido())
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["data_approvazione"] == "2026-03-24"
    assert body["data_avvio_piano"] == "2026-04-01"
    assert body["data_termine_piano"] == "2027-03-31"

    project = db_session.get(models.Project, body["id"])
    assert project.data_avvio_piano == date(2026, 4, 1)
    assert project.start_date is None
    assert project.end_date is None


@pytest.mark.parametrize(
    ("campo", "valore", "messaggio"),
    [
        ("data_approvazione", "2026-04-02", "approvazione"),
        ("data_termine_piano", "2026-03-31", "termine del piano"),
        ("data_fine_attivita_formative", "2026-04-09", "attività formative"),
        ("data_termine_rendicontazione", "2026-04-09", "rendicontazione"),
        ("data_chiusura_effettiva", "2026-04-09", "chiusura"),
    ],
)
def test_combinazioni_temporali_incoerenti_sono_rifiutate(
    client, db_session, campo, valore, messaggio
):
    payload = payload_valido()
    payload["data_avvio_attivita_formative"] = "2026-04-10"
    payload["data_fine_attivita_formative"] = "2026-04-20"
    payload[campo] = valore

    response = client.post("/api/v1/projects/", json=payload)
    assert response.status_code in {400, 422}, response.text
    assert messaggio.lower() in response.text.lower()
    assert db_session.query(models.Project).count() == 0


def test_record_legacy_resta_aggiornabile_senza_backfill(db_session):
    legacy = models.Project(
        name="Legacy",
        description="Date ambigue conservate",
        status="active",
        start_date=datetime(2026, 1, 1),
        end_date=datetime(2026, 12, 31),
    )
    db_session.add(legacy)
    db_session.commit()

    updated = crud.update_project(
        db_session,
        legacy.id,
        schemas.ProjectUpdateExtended(description="Aggiornato senza inventare date"),
    )
    assert updated.description == "Aggiornato senza inventare date"
    assert updated.data_avvio_piano is None
    assert updated.start_date == datetime(2026, 1, 1)
    assert updated.end_date == datetime(2026, 12, 31)


def test_update_che_introduce_date_incoerenti_e_rifiutato(db_session):
    legacy = models.Project(name="Legacy", status="active")
    db_session.add(legacy)
    db_session.commit()

    with pytest.raises(ValueError, match="termine del piano"):
        crud.update_project(
            db_session,
            legacy.id,
            schemas.ProjectUpdateExtended(
                data_approvazione=date(2026, 3, 24),
                data_avvio_piano=date(2026, 4, 1),
                data_termine_piano=date(2026, 3, 31),
            ),
        )


def test_migration_non_contiene_backfill_dai_campi_legacy():
    migration = (
        Path(__file__).parent.parent
        / "alembic"
        / "versions"
        / "064_ux5_date_progetto_esplicite.py"
    ).read_text()
    lowered = migration.lower()
    assert "update projects" not in lowered
    assert "start_date" not in lowered
    assert "end_date" not in lowered
