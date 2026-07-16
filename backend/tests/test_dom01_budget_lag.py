"""
DOM-01 / DOM-14 — Budget lag e atomicità presenze.

Riproduce il bug D4 S1-AUTOFLUSH: `budget_utilizzato` memorizzato sempre
indietro dell'ultima presenza registrata (autoflush=False + SUM SQL eseguita
prima del flush della voce modificata in sessione).

Il test legge il valore DAL DATABASE (query scalare, non l'oggetto in
sessione) perché è quello che vedono viste/report: il numero deve essere
esatto dopo OGNI registrazione/modifica/cancellazione di presenza.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from database import Base
import models
import crud
import schemas

TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
# Stessa configurazione di produzione: autoflush=False, expire_on_commit=False
TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, expire_on_commit=False
)

if "users" not in Base.metadata.tables:
    from sqlalchemy import Table

    Table("users", Base.metadata, Column("id", Integer, primary_key=True))

RATE = 60.0


@pytest.fixture
def ctx():
    """Collaboratore + progetto + piano + assignment 40h@60€ con voce agganciata."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    collab = models.Collaborator(
        first_name="Mario",
        last_name="Rossi",
        email="mario.rossi@example.com",
        fiscal_code="RSSMRA80A01H501U",
        phone="3331234567",
        position="Formatore",
    )
    project = models.Project(
        name="Progetto DOM-01",
        description="Test budget lag",
        status="active",
        start_date=datetime(2026, 7, 1),
        end_date=datetime(2026, 7, 31),
    )
    db.add_all([collab, project])
    db.commit()

    piano = models.PianoFinanziario(
        progetto_id=project.id,
        anno=2026,
        nome="Piano DOM-01",
        ente_erogatore="Formazienda",
        budget_totale=5000.0,
        data_inizio=datetime(2026, 7, 1),
        data_fine=datetime(2026, 7, 31),
        stato="in_corso",
    )
    db.add(piano)
    db.commit()

    assignment = crud.create_assignment(
        db,
        schemas.AssignmentCreate(
            collaborator_id=collab.id,
            project_id=project.id,
            role="Docenza",
            assigned_hours=40.0,
            start_date=datetime(2026, 7, 1),
            end_date=datetime(2026, 7, 31),
            hourly_rate=RATE,
        ),
    )
    voce = crud.get_voce_by_assignment(db, assignment.id)
    assert voce is not None, "voce piano non agganciata all'assignment"
    assert float(voce.tariffa_oraria) == RATE

    yield db, collab, project, piano, assignment

    db.close()
    Base.metadata.drop_all(bind=engine)


def budget_dal_db(db, piano_id):
    """Valore di budget_utilizzato come lo vede chiunque legga il DB."""
    return db.query(models.PianoFinanziario.budget_utilizzato).filter(
        models.PianoFinanziario.id == piano_id
    ).scalar()


def make_attendance(db, collab, project, assignment, day, start_h, hours):
    return crud.create_attendance(
        db,
        schemas.AttendanceCreate(
            collaborator_id=collab.id,
            project_id=project.id,
            assignment_id=assignment.id,
            date=datetime(2026, 7, day),
            start_time=datetime(2026, 7, day, start_h, 0),
            end_time=datetime(2026, 7, day, start_h + int(hours), int((hours % 1) * 60)),
            hours=hours,
        ),
    )


class TestBudgetMaiInRitardo:
    def test_budget_esatto_dopo_ogni_registrazione(self, ctx):
        """Sequenza D4 S1: dopo OGNI presenza il budget memorizzato è esatto."""
        db, collab, project, piano, assignment = ctx
        sequenza = [4.0, 6.5, 3.5]  # 14h totali, con frazionarie
        atteso = 0.0
        for i, ore in enumerate(sequenza):
            make_attendance(db, collab, project, assignment, day=6 + i, start_h=9, hours=ore)
            atteso += ore * RATE
            reale = budget_dal_db(db, piano.id)
            assert reale == pytest.approx(atteso), (
                f"dopo presenza #{i + 1} ({ore}h): budget_utilizzato={reale}, "
                f"atteso {atteso} — il budget è in ritardo"
            )

    def test_budget_esatto_dopo_modifica(self, ctx):
        db, collab, project, piano, assignment = ctx
        att = make_attendance(db, collab, project, assignment, day=6, start_h=9, hours=4.0)
        assert budget_dal_db(db, piano.id) == pytest.approx(4.0 * RATE)

        crud.update_attendance(
            db, att.id,
            schemas.AttendanceUpdate(
                hours=2.0,
                end_time=datetime(2026, 7, 6, 11, 0),
            ),
        )
        assert budget_dal_db(db, piano.id) == pytest.approx(2.0 * RATE), (
            "dopo la correzione 4h→2h il budget memorizzato non riflette la modifica"
        )

    def test_budget_esatto_dopo_cancellazione(self, ctx):
        db, collab, project, piano, assignment = ctx
        att1 = make_attendance(db, collab, project, assignment, day=6, start_h=9, hours=4.0)
        make_attendance(db, collab, project, assignment, day=7, start_h=9, hours=6.0)
        assert budget_dal_db(db, piano.id) == pytest.approx(10.0 * RATE)

        crud.delete_attendance(db, att1.id)
        assert budget_dal_db(db, piano.id) == pytest.approx(6.0 * RATE), (
            "dopo la cancellazione il budget memorizzato non riflette la rimozione"
        )

    def test_residuo_coerente_con_budget_totale(self, ctx):
        db, collab, project, piano, assignment = ctx
        make_attendance(db, collab, project, assignment, day=6, start_h=9, hours=4.0)
        row = db.query(
            models.PianoFinanziario.budget_utilizzato,
            models.PianoFinanziario.budget_rimanente,
            models.PianoFinanziario.budget_totale,
        ).filter(models.PianoFinanziario.id == piano.id).first()
        assert row.budget_rimanente == pytest.approx(row.budget_totale - row.budget_utilizzato)
        assert row.budget_utilizzato == pytest.approx(4.0 * RATE)


class TestVoceManualeSincronizzaBudget:
    def test_update_voce_manuale_aggiorna_budget_nello_stesso_ciclo(self, ctx):
        """Stesso meccanismo di lag su update_voce_piano (setattr + SUM senza flush)."""
        db, collab, project, piano, assignment = ctx
        voce_manuale = crud.create_voce_piano(
            db,
            schemas.VocePianoFinanziarioCreate(
                piano_id=piano.id,
                descrizione="Voce manuale",
                importo_preventivo=100.0,
                importo_consuntivo=100.0,
            ),
        )
        assert budget_dal_db(db, piano.id) == pytest.approx(100.0)

        crud.update_voce_piano(
            db, voce_manuale.id,
            schemas.VocePianoFinanziarioUpdate(importo_consuntivo=250.0),
        )
        assert budget_dal_db(db, piano.id) == pytest.approx(250.0), (
            "budget non aggiornato dopo update manuale della voce"
        )


class TestAtomicitaPresenza:
    def test_errore_nei_ricalcoli_non_lascia_presenza_orfana(self, ctx, monkeypatch):
        """DOM-14: se un ricalcolo fallisce, la presenza NON deve restare salvata
        con gli aggregati stale (oggi: commit separati + errore degradato a warning)."""
        db, collab, project, piano, assignment = ctx

        def boom(self, _db):
            raise RuntimeError("ricalcolo voce fallito (simulato)")

        monkeypatch.setattr(models.VocePianoFinanziario, "aggiorna_da_presenze", boom)

        with pytest.raises(Exception):
            make_attendance(db, collab, project, assignment, day=6, start_h=9, hours=4.0)

        db.rollback()
        n = db.query(models.Attendance).filter(
            models.Attendance.assignment_id == assignment.id
        ).count()
        assert n == 0, (
            "presenza persistita nonostante il fallimento dei ricalcoli: "
            "create_attendance non è atomica"
        )
