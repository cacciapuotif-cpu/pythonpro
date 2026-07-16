"""
DOM-11 — Float sui valori economici: derive da centesimo e crash latente.

Casi di deriva provati in D3:
- round(2.675, 2) = 2.67 in float (banker's rounding) — il fondo con
  Excel/decimale ottiene 2.68;
- 10,5h × 33,33 €/h = 349,965 → round float = 349,96; il foglio di verifica
  del fondo dice 349,97 → contestazione da 1 centesimo;
- 0.1+0.1+0.1 != 0.3 → accumuli su somme di voci;
- completed_hours NULL → TypeError su Assignment.remaining_hours.

Regola unica di arrotondamento (W1.3): ROUND_HALF_UP a 2 decimali,
centralizzata in money_utils (quantize_euro / quantize_ore).
"""

import sys
from decimal import Decimal
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
TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, expire_on_commit=False
)

if "users" not in Base.metadata.tables:
    from sqlalchemy import Table

    Table("users", Base.metadata, Column("id", Integer, primary_key=True))


@pytest.fixture
def ctx():
    """Assignment Docenza 40h a 33,33 €/h con voce agganciata (caso D3)."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    collab = models.Collaborator(
        first_name="Anna",
        last_name="Bianchi",
        email="anna.bianchi@example.com",
        fiscal_code="BNCNNA80A41H501X",
        phone="3339876543",
        position="Formatrice",
    )
    project = models.Project(
        name="Progetto DOM-11",
        description="t",
        status="active",
        start_date=datetime(2026, 7, 1),
        end_date=datetime(2026, 7, 31),
    )
    db.add_all([collab, project])
    db.commit()

    piano = models.PianoFinanziario(
        progetto_id=project.id,
        anno=2026,
        nome="Piano DOM-11",
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
            hourly_rate=33.33,
        ),
    )
    yield db, collab, project, piano, assignment

    db.close()
    Base.metadata.drop_all(bind=engine)


def make_attendance(db, collab, project, assignment, day, start_h, hours, start_min=0):
    total_min = int(round(hours * 60))
    end_h = start_h + (start_min + total_min) // 60
    end_min = (start_min + total_min) % 60
    return crud.create_attendance(
        db,
        schemas.AttendanceCreate(
            collaborator_id=collab.id,
            project_id=project.id,
            assignment_id=assignment.id,
            date=datetime(2026, 7, day),
            start_time=datetime(2026, 7, day, start_h, start_min),
            end_time=datetime(2026, 7, day, end_h, end_min),
            hours=hours,
        ),
    )


def as_decimal(value):
    return Decimal(str(value))


class TestQuantizzazioneCentralizzata:
    def test_regola_unica_round_half_up(self):
        from money_utils import quantize_euro

        # Il caso che il banker's rounding sbaglia: 2,675 → 2,68 (non 2,67)
        assert quantize_euro(Decimal("2.675")) == Decimal("2.68")
        assert quantize_euro(Decimal("349.965")) == Decimal("349.97")
        assert quantize_euro(Decimal("0.005")) == Decimal("0.01")
        assert quantize_euro(None) == Decimal("0.00")

    def test_quantize_accetta_float_e_stringhe(self):
        from money_utils import quantize_euro

        # I float vanno convertiti via str, non direttamente
        # (Decimal(2.675) = 2.67499999... ripeterebbe l'errore)
        assert quantize_euro(2.675) == Decimal("2.68")
        assert quantize_euro("10.5") == Decimal("10.50")

    def test_quantize_ore(self):
        from money_utils import quantize_ore

        assert quantize_ore(Decimal("6.505")) == Decimal("6.51")
        assert quantize_ore(None) == Decimal("0.00")


class TestConsuntiviAlCentesimo:
    def test_caso_d3_10h30_a_33_33(self, ctx):
        """10,5h × 33,33 = 349,965 → 349,97 (float dava 349,96)."""
        db, collab, project, piano, assignment = ctx
        make_attendance(db, collab, project, assignment, day=6, start_h=9, hours=10.5)

        voce = crud.get_voce_by_assignment(db, assignment.id)
        assert as_decimal(voce.importo_consuntivo) == Decimal("349.97"), (
            f"consuntivo {voce.importo_consuntivo}: deriva da centesimo "
            "(atteso 349.97 come nei fogli di verifica del fondo)"
        )

    def test_budget_piano_al_centesimo(self, ctx):
        db, collab, project, piano, assignment = ctx
        make_attendance(db, collab, project, assignment, day=6, start_h=9, hours=10.5)

        budget = db.query(models.PianoFinanziario.budget_utilizzato).filter(
            models.PianoFinanziario.id == piano.id
        ).scalar()
        assert as_decimal(budget) == Decimal("349.97")

    def test_accumulo_frazioni_senza_deriva(self, ctx):
        """3 presenze da 0,1h: le somme non devono accumulare errore binario."""
        db, collab, project, piano, assignment = ctx
        for i in range(3):
            make_attendance(
                db, collab, project, assignment,
                day=6 + i, start_h=9, hours=0.1,
            )
        voce = crud.get_voce_by_assignment(db, assignment.id)
        assert as_decimal(voce.ore_effettive) == Decimal("0.3")
        # 0,3h × 33,33 = 9,999 → 10,00
        assert as_decimal(voce.importo_consuntivo) == Decimal("10.00")


class TestNullSafety:
    def test_db_rifiuta_completed_hours_null(self, ctx):
        """completed_hours NULL reale (D2 A2, assignment 47): ora la colonna
        è NOT NULL — lo stato corrotto non può più entrare dal DB."""
        from sqlalchemy.exc import IntegrityError

        db, collab, project, piano, assignment = ctx
        with pytest.raises(IntegrityError):
            db.query(models.Assignment).filter(
                models.Assignment.id == assignment.id
            ).update({"completed_hours": None}, synchronize_session=False)
            db.commit()
        db.rollback()

    def test_remaining_hours_tollera_none_in_memoria(self):
        """Il guard della property resta per oggetti non ancora persistiti."""
        a = models.Assignment(
            collaborator_id=1,
            project_id=1,
            role="Docenza",
            assigned_hours=40.0,
            start_date=datetime(2026, 7, 1),
            end_date=datetime(2026, 7, 31),
            hourly_rate=50.0,
        )
        # completed_hours non ancora valorizzato (None prima del flush)
        assert a.remaining_hours == pytest.approx(40.0)
