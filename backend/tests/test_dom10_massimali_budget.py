"""
DOM-10 — Massimali di fatto spenti + budget senza enforcement (GATE W1.4).

Decisioni confermate al GATE:
1. tariffa oltre massimale configurato (fondo, anno): BLOCCO su assignment e voce;
2. tassonomia tipo_fondo estesa subito (formazienda, fapi) per rendere
   accendibili i massimali (bonifica dati B4 al GATE W1.5);
3. consuntivo oltre budget alla registrazione presenza: WARNING, mai blocco
   (la presenza registra un fatto avvenuto) + alert danger nel riepilogo;
4. preventivo oltre budget (voci manuali, nuove assignment): BLOCCO;
5. report violazioni esistenti: GET /api/v1/piani-finanziari/violazioni-massimali.
"""

from pathlib import Path
import sys
from datetime import datetime

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
    db_path = tmp_path / "test_dom10.db"
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
def base(db_session):
    """Collaboratore + progetto + piano fondimpresa 2026 con massimale
    docenza 100 €/h e tutoraggio 70 €/h."""
    collab = models.Collaborator(
        first_name="Luca",
        last_name="Verdi",
        email="luca.verdi@example.com",
        fiscal_code="VRDLCU80A01H501B",
        phone="3331112223",
        position="Formatore",
    )
    project = models.Project(
        name="Progetto DOM-10",
        description="t",
        status="active",
        start_date=datetime(2026, 7, 1),
        end_date=datetime(2026, 7, 31),
    )
    db_session.add_all([collab, project])
    db_session.commit()

    piano = models.PianoFinanziario(
        progetto_id=project.id,
        anno=2026,
        nome="Piano DOM-10",
        ente_erogatore="Fondimpresa",
        tipo_fondo="fondimpresa",
        budget_totale=10000.0,
        data_inizio=datetime(2026, 7, 1),
        data_fine=datetime(2026, 7, 31),
        stato="in_corso",
    )
    massimale = models.MassimaleFondo(
        tipo_fondo="fondimpresa",
        anno=2026,
        massimale_orario_docenza=100,
        massimale_orario_tutoraggio=70,
    )
    db_session.add_all([piano, massimale])
    db_session.commit()
    return collab, project, piano


def assignment_payload(collab, project, rate, role="Docenza", hours=10.0):
    return {
        "collaborator_id": collab.id,
        "project_id": project.id,
        "role": role,
        "assigned_hours": hours,
        "start_date": "2026-07-01T00:00:00",
        "end_date": "2026-07-31T00:00:00",
        "hourly_rate": rate,
    }


class TestMassimaliAssignment:
    def test_docenza_oltre_massimale_bloccata(self, client, base, db_session):
        """D4 S3.6: 900 €/h di docenza venivano accettati senza obiezioni."""
        collab, project, piano = base
        r = client.post("/api/v1/assignments/", json=assignment_payload(collab, project, 900))
        assert r.status_code == 400, r.text
        assert "massimale" in r.text.lower()
        n = db_session.query(models.Assignment).count()
        assert n == 0, "assignment oltre massimale persistita"

    def test_docenza_entro_massimale_ok(self, client, base):
        collab, project, piano = base
        r = client.post("/api/v1/assignments/", json=assignment_payload(collab, project, 80))
        assert r.status_code == 200, r.text

    def test_update_oltre_massimale_bloccato(self, client, base, db_session):
        collab, project, piano = base
        r = client.post("/api/v1/assignments/", json=assignment_payload(collab, project, 80))
        assert r.status_code == 200, r.text
        aid = r.json()["id"]
        r2 = client.put(f"/api/v1/assignments/{aid}", json={"hourly_rate": 900})
        assert r2.status_code == 400, r2.text
        db_session.expire_all()
        rate = db_session.query(models.Assignment.hourly_rate).filter_by(id=aid).scalar()
        assert float(rate) == 80.0, "tariffa oltre massimale persistita dall'update"

    def test_ruolo_senza_massimale_non_bloccato(self, client, base):
        """Categoria fuori da docenza/tutoraggio: nessun massimale applicabile."""
        collab, project, piano = base
        r = client.post(
            "/api/v1/assignments/",
            json=assignment_payload(collab, project, 200, role="Coordinamento", hours=5.0),
        )
        assert r.status_code == 200, r.text


class TestTassonomiaFondi:
    def test_formazienda_e_fapi_ammessi(self, db_session):
        """Prerequisito massimali: prima 'formazienda'/'fapi' erano rifiutati
        dal validator e i piani restavano 'altro' per sempre (D2 A11)."""
        p = models.Project(name="P tass", description="t", status="active")
        db_session.add(p)
        db_session.commit()
        for fondo in ("formazienda", "fapi"):
            piano = models.PianoFinanziario(
                progetto_id=p.id,
                anno=2026,
                nome=f"Piano {fondo}",
                ente_erogatore=fondo,
                tipo_fondo=fondo,
            )
            db_session.add(piano)
        db_session.commit()


class TestBudgetPreventivo:
    def test_voce_oltre_budget_bloccata(self, client, base, db_session):
        collab, project, piano = base
        r = client.post(
            f"/api/v1/piani-finanziari/{piano.id}/voci",
            json={
                "piano_id": piano.id,
                "descrizione": "Voce enorme",
                "importo_preventivo": 15000.0,
            },
        )
        assert r.status_code == 400, r.text
        assert "budget" in r.text.lower()
        n = db_session.query(models.VocePianoFinanziario).filter_by(piano_id=piano.id).count()
        assert n == 0, "voce oltre budget persistita"

    def test_assignment_oltre_budget_bloccata(self, client, base, db_session):
        """40h × 300 €/h = 12.000 > budget 10.000 (tutoraggio entro massimale?
        no: usa ruolo senza massimale per isolare il caso budget)."""
        collab, project, piano = base
        r = client.post(
            "/api/v1/assignments/",
            json=assignment_payload(collab, project, 300, role="Coordinamento", hours=40.0),
        )
        assert r.status_code == 400, r.text
        assert "budget" in r.text.lower()
        assert db_session.query(models.Assignment).count() == 0

    def test_voce_entro_budget_ok(self, client, base):
        collab, project, piano = base
        r = client.post(
            f"/api/v1/piani-finanziari/{piano.id}/voci",
            json={
                "piano_id": piano.id,
                "descrizione": "Voce ok",
                "importo_preventivo": 500.0,
            },
        )
        assert r.status_code == 201, r.text

    def test_budget_zero_non_blocca(self, client, db_session):
        """budget_totale=0 = non configurato: nessun blocco preventivo."""
        p = models.Project(name="P nb", description="t", status="active")
        db_session.add(p)
        db_session.commit()
        piano = models.PianoFinanziario(
            progetto_id=p.id, anno=2026, nome="Piano nb",
            ente_erogatore="Formazienda", budget_totale=0.0, stato="in_corso",
        )
        db_session.add(piano)
        db_session.commit()
        r = client.post(
            f"/api/v1/piani-finanziari/{piano.id}/voci",
            json={"piano_id": piano.id, "descrizione": "V", "importo_preventivo": 999999.0},
        )
        assert r.status_code == 201, r.text


class TestBudgetConsuntivoWarning:
    def _setup_consuntivo_quasi_pieno(self, client, db_session, base):
        collab, project, piano = base
        # Voce manuale che occupa quasi tutto il budget a consuntivo
        r = client.post(
            f"/api/v1/piani-finanziari/{piano.id}/voci",
            json={
                "piano_id": piano.id,
                "descrizione": "Spese già sostenute",
                "importo_preventivo": 9000.0,
                "importo_consuntivo": 9900.0,
            },
        )
        assert r.status_code == 201, r.text
        # Assignment docenza entro massimale e budget: 10h × 80 = 800 prev
        r = client.post("/api/v1/assignments/", json=assignment_payload(collab, project, 80))
        assert r.status_code == 200, r.text
        return collab, project, piano, r.json()["id"]

    def test_presenza_oltre_budget_registrata_con_warning(self, client, db_session, base):
        collab, project, piano, aid = self._setup_consuntivo_quasi_pieno(client, db_session, base)
        # 3h × 80 = 240 → consuntivo 10.140 > budget 10.000: warning, NON blocco
        r = client.post(
            "/api/v1/attendances/",
            json={
                "collaborator_id": collab.id,
                "project_id": project.id,
                "assignment_id": aid,
                "date": "2026-07-06T00:00:00",
                "start_time": "2026-07-06T09:00:00",
                "end_time": "2026-07-06T12:00:00",
                "hours": 3.0,
            },
        )
        assert r.status_code == 200, r.text
        assert "x-budget-warning" in {k.lower() for k in r.headers.keys()}, (
            "warning di superamento budget assente dalla risposta"
        )
        assert db_session.query(models.Attendance).count() == 1

    def test_riepilogo_alert_budget_superato(self, client, db_session, base):
        collab, project, piano, aid = self._setup_consuntivo_quasi_pieno(client, db_session, base)
        client.post(
            "/api/v1/attendances/",
            json={
                "collaborator_id": collab.id,
                "project_id": project.id,
                "assignment_id": aid,
                "date": "2026-07-06T00:00:00",
                "start_time": "2026-07-06T09:00:00",
                "end_time": "2026-07-06T12:00:00",
                "hours": 3.0,
            },
        )
        r = client.get(f"/api/v1/piani-finanziari/{piano.id}/riepilogo")
        assert r.status_code == 200, r.text
        codes = {a.get("code") for a in (r.json().get("alerts") or [])}
        assert "budget_superato" in codes


class TestReportViolazioni:
    def test_report_censisce_violazioni_e_non_verificabili(self, client, db_session, base):
        collab, project, piano = base
        # Dato legacy: assignment oltre massimale inserita direttamente a DB
        # (simula i dati entrati prima dell'enforcement, es. D2 A12: 1.000 €/h)
        legacy = models.Assignment(
            collaborator_id=collab.id,
            project_id=project.id,
            role="B.2 – Docenza",
            assigned_hours=20.0,
            start_date=datetime(2026, 7, 1),
            end_date=datetime(2026, 7, 31),
            hourly_rate=1000.0,
            completed_hours=0.0,
            is_active=True,
        )
        db_session.add(legacy)
        db_session.commit()

        r = client.get("/api/v1/piani-finanziari/violazioni-massimali")
        assert r.status_code == 200, r.text
        data = r.json()
        violazioni = data.get("violazioni") or []
        assert any(
            v.get("entita") == "assignment" and v.get("entita_id") == legacy.id
            for v in violazioni
        ), f"assignment 1000 €/h non censita: {data}"
