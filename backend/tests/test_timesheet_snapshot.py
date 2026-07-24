"""Wave 2.1: snapshot immutabile e sblocco auditato dei timesheet."""

from datetime import datetime
from decimal import Decimal
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import crud
import models
import schemas
from auth import get_current_user
from database import Base, get_db
from main import app
from routers import timesheet as timesheet_router


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine(
        "sqlite:///{}".format(tmp_path / "timesheet.db"),
        connect_args={"check_same_thread": False},
    )
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def current_user():
    return type(
        "TestUser",
        (),
        {"id": 91, "username": "wave2-admin", "role": "admin", "is_active": True},
    )()


@pytest.fixture
def client(db_session, current_user, tmp_path, monkeypatch):
    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: current_user
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(
        timesheet_router,
        "_build_timesheet_pdf",
        lambda db, assignment, presenze=None: (
            "PDF:" + "|".join(str(p.notes) for p in (presenze or []))
        ).encode(),
    )
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def real_pdf_client(db_session, current_user, tmp_path, monkeypatch):
    """Client di integrazione che non sostituisce il generatore ReportLab."""
    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: current_user
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path / "uploads-real-pdf"))
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def attendance(db_session):
    collaborator = models.Collaborator(
        first_name="Ada",
        last_name="Lovelace",
        email="ada.timesheet@example.com",
        fiscal_code="LVLDAX80A01H501Q",
    )
    project = models.Project(
        name="Wave 2",
        status="active",
        start_date=datetime(2026, 7, 1),
        end_date=datetime(2026, 7, 31),
    )
    assignment = models.Assignment(
        collaborator=collaborator,
        project=project,
        role="Docente",
        assigned_hours=Decimal("20"),
        completed_hours=Decimal("0"),
        hourly_rate=Decimal("50"),
        start_date=datetime(2026, 7, 1),
        end_date=datetime(2026, 7, 31),
        is_active=True,
    )
    presence = models.Attendance(
        collaborator=collaborator,
        project=project,
        assignment=assignment,
        date=datetime(2026, 7, 10),
        start_time=datetime(2026, 7, 10, 9),
        end_time=datetime(2026, 7, 10, 12, 30),
        hours=Decimal("3.50"),
        notes="snapshot-originale",
    )
    db_session.add(presence)
    db_session.commit()
    return presence


def _generate(client, attendance):
    """B5.1: la generazione avviene via POST (comando con side-effect)."""
    response = client.post("/api/v1/assignments/{}/timesheet".format(attendance.assignment_id))
    assert response.status_code == 200
    return response


def test_route_generates_real_pdf_with_decimal_assignment_values(
    real_pdf_client, db_session, attendance
):
    """UI-04: la route reale deve accettare i Decimal restituiti dall'ORM."""
    response = real_pdf_client.post(
        "/api/v1/assignments/{}/timesheet".format(attendance.assignment_id)
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert db_session.query(models.TimesheetGenerato).count() == 1


def test_missing_real_pdf_is_rebuilt_from_frozen_decimal_snapshot(
    real_pdf_client, db_session, attendance
):
    """UI-04: anche la fotografia congelata deve essere sempre ristampabile.

    B5.1: la GET read-only ricostruisce il PDF in memoria dallo snapshot ma
    NON lo riscrive su disco (nessun side-effect)."""
    url = "/api/v1/assignments/{}/timesheet".format(attendance.assignment_id)
    first = real_pdf_client.post(url)
    assert first.status_code == 200

    record = db_session.query(models.TimesheetGenerato).one()
    Path(record.pdf_path).unlink()

    rebuilt = real_pdf_client.get(url)

    assert rebuilt.status_code == 200
    assert rebuilt.headers["content-type"] == "application/pdf"
    assert rebuilt.content.startswith(b"%PDF")
    # Read-only: il file mancante NON viene riscritto dalla GET.
    assert not Path(record.pdf_path).exists()


def test_generation_persists_rows_totals_and_actor(client, db_session, attendance):
    _generate(client, attendance)

    record = db_session.query(models.TimesheetGenerato).one()
    row = db_session.query(models.TimesheetRiga).one()
    assert record.bloccato is True
    assert record.presenze_count == 1
    assert record.totale_ore == Decimal("3.50")
    assert record.generato_da == "wave2-admin"
    assert record.generato_da_user_id == 91
    assert row.attendance_id == attendance.id
    assert row.hours == Decimal("3.50")
    assert row.notes == "snapshot-originale"


def test_locked_timesheet_rejects_forced_regeneration(client, attendance):
    _generate(client, attendance)
    response = client.post(
        "/api/v1/assignments/{}/timesheet?rigenera=true".format(attendance.assignment_id)
    )
    assert response.status_code == 409


def test_unlock_requires_reason_and_uses_authenticated_actor(
    client, db_session, attendance
):
    _generate(client, attendance)
    url = "/api/v1/assignments/{}/timesheet/unlock".format(attendance.assignment_id)
    assert client.post(url, json={"motivo": "  "}).status_code == 422

    response = client.post(url, json={"motivo": "Correzione ore firmata"})
    assert response.status_code == 200
    record = db_session.query(models.TimesheetGenerato).one()
    assert record.bloccato is False
    assert record.sbloccato_da == "wave2-admin"
    assert record.sbloccato_da_user_id == 91
    assert record.sblocco_motivo == "Correzione ore firmata"
    assert record.sbloccato_il is not None


def test_unlock_rejects_consultation_role(client, attendance):
    readonly = type(
        "ReadOnlyUser",
        (),
        {"id": 92, "username": "readonly", "role": "consultazione", "is_active": True},
    )()
    _generate(client, attendance)
    app.dependency_overrides[get_current_user] = lambda: readonly
    response = client.post(
        "/api/v1/assignments/{}/timesheet/unlock".format(attendance.assignment_id),
        json={"motivo": "Tentativo non autorizzato"},
    )
    assert response.status_code == 403


def test_locked_snapshot_blocks_update_and_delete(db_session, client, attendance):
    _generate(client, attendance)
    with pytest.raises(ValueError, match="timesheet bloccato"):
        crud.update_attendance(
            db_session, attendance.id, schemas.AttendanceUpdate(notes="modificata")
        )
    with pytest.raises(ValueError, match="timesheet bloccato"):
        crud.delete_attendance(db_session, attendance.id)


def test_update_allowed_after_unlock_and_new_generation_is_new_version(
    client, db_session, attendance
):
    _generate(client, attendance)
    client.post(
        "/api/v1/assignments/{}/timesheet/unlock".format(attendance.assignment_id),
        json={"motivo": "Rettifica presenza"},
    )
    updated = crud.update_attendance(
        db_session, attendance.id, schemas.AttendanceUpdate(notes="versione-nuova")
    )
    assert updated.notes == "versione-nuova"

    _generate(client, attendance)
    versions = db_session.query(models.TimesheetGenerato).order_by(
        models.TimesheetGenerato.id
    ).all()
    assert len(versions) == 2
    assert versions[0].bloccato is False
    assert versions[1].bloccato is True
    assert versions[0].righe[0].notes == "snapshot-originale"
    assert versions[1].righe[0].notes == "versione-nuova"


def test_missing_pdf_is_rebuilt_from_snapshot(client, db_session, attendance):
    _generate(client, attendance)
    record = db_session.query(models.TimesheetGenerato).one()
    Path(record.pdf_path).unlink()

    # Simula una modifica esterna: il rebuild deve ignorare la riga live.
    attendance.notes = "live-mutata"
    db_session.commit()
    response = client.get("/api/v1/assignments/{}/timesheet".format(attendance.assignment_id))
    assert response.status_code == 200
    assert response.content == b"PDF:snapshot-originale"
    # B5.1: la GET e' read-only, non riscrive il file mancante su disco.
    assert not Path(record.pdf_path).exists()


def test_new_attendance_can_be_added_while_old_snapshot_is_locked(
    client, db_session, attendance
):
    _generate(client, attendance)
    second = models.Attendance(
        collaborator_id=attendance.collaborator_id,
        project_id=attendance.project_id,
        assignment_id=attendance.assignment_id,
        date=datetime(2026, 7, 11),
        start_time=datetime(2026, 7, 11, 9),
        end_time=datetime(2026, 7, 11, 11),
        hours=Decimal("2"),
        notes="non inclusa",
    )
    db_session.add(second)
    db_session.commit()
    assert second.id is not None
    assert db_session.query(models.TimesheetRiga).count() == 1


# ------------------------------------------------------------------
# B5.1: POST genera (comando) / GET scarica (interrogazione read-only)
# ------------------------------------------------------------------


def test_get_without_generation_returns_404(client, db_session, attendance):
    """B5.1: la GET non genera nulla; se il timesheet non esiste -> 404 chiaro."""
    response = client.get(
        "/api/v1/assignments/{}/timesheet".format(attendance.assignment_id)
    )
    assert response.status_code == 404
    assert "POST" in response.json()["detail"]
    # Nessun side-effect: nessun record creato dalla GET.
    assert db_session.query(models.TimesheetGenerato).count() == 0


def test_get_after_post_returns_existing_pdf(client, db_session, attendance):
    """B5.1: flusso POST-then-GET. Il POST genera, la GET scarica lo stesso PDF."""
    generated = _generate(client, attendance)
    assert db_session.query(models.TimesheetGenerato).count() == 1

    downloaded = client.get(
        "/api/v1/assignments/{}/timesheet".format(attendance.assignment_id)
    )
    assert downloaded.status_code == 200
    assert downloaded.content == generated.content


def test_get_has_no_side_effect_on_db_or_disk(client, db_session, attendance):
    """B5.1: molteplici GET non creano nuovi TimesheetGenerato/TimesheetRiga."""
    _generate(client, attendance)
    record = db_session.query(models.TimesheetGenerato).one()
    righe_before = db_session.query(models.TimesheetRiga).count()

    for _ in range(3):
        resp = client.get(
            "/api/v1/assignments/{}/timesheet".format(attendance.assignment_id)
        )
        assert resp.status_code == 200

    # Un solo record e le stesse righe: la GET non ha mai scritto.
    assert db_session.query(models.TimesheetGenerato).count() == 1
    assert db_session.query(models.TimesheetRiga).count() == righe_before
    still = db_session.query(models.TimesheetGenerato).one()
    assert still.id == record.id


def test_post_regenerates_new_version_after_unlock(client, db_session, attendance):
    """B5.1: la rigenerazione (nuova versione) resta un comando POST."""
    _generate(client, attendance)
    client.post(
        "/api/v1/assignments/{}/timesheet/unlock".format(attendance.assignment_id),
        json={"motivo": "Rettifica"},
    )
    _generate(client, attendance)
    assert db_session.query(models.TimesheetGenerato).count() == 2


def test_get_does_not_exist_after_only_get_attempts(client, db_session, attendance):
    """B5.1: anche ripetute GET su un assignment senza timesheet non generano."""
    url = "/api/v1/assignments/{}/timesheet".format(attendance.assignment_id)
    for _ in range(3):
        assert client.get(url).status_code == 404
    assert db_session.query(models.TimesheetGenerato).count() == 0
