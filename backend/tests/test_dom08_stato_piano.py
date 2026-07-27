"""DOM-08 / DOM-18 — macchina a stati del piano finanziario (Wave 2.2).

Regola di dominio (GATE confermato):
- stati CONGELATI = {inviato, rendicontato, chiuso}: voci e presenze collegate
  diventano read-only. Ogni scrittura è rifiutata (PianoCongelatoError → 409).
- eccezione: un utente ADMIN può forzare la scrittura con override esplicito +
  motivo obbligatorio; l'override viene tracciato nell'audit trail.
- DOM-18: al passaggio del piano allo stato 'inviato', l'importo_presentato di
  ogni voce viene congelato nella colonna storica importo_presentato_congelato,
  che i ricalcoli successivi NON sovrascrivono.
"""

from datetime import datetime
from pathlib import Path
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import Base
import crud
import models
import schemas


def _admin():
    return type("U", (), {"id": 1, "role": "admin", "is_active": True})()


def _operatore():
    return type("U", (), {"id": 2, "role": "operatore", "is_active": True})()


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'dom08.db'}",
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
def scenario(db_session):
    """Piano in bozza con una voce agganciata a un assignment. Ritorna
    (collaborator, project, piano, assignment, voce)."""
    collaborator = models.Collaborator(
        first_name="Ada",
        last_name="Rossi",
        email="ada.rossi@example.com",
        fiscal_code="RSSDAA80A01H501Q",
        phone="3331234567",
        position="Docente",
    )
    project = models.Project(
        name="DOM-08",
        description="Macchina a stati",
        status="active",
        start_date=datetime(2026, 7, 1),
        end_date=datetime(2026, 7, 31),
    )
    db_session.add_all([collaborator, project])
    db_session.commit()

    piano = models.PianoFinanziario(
        progetto_id=project.id,
        anno=2026,
        nome="Piano DOM-08",
        ente_erogatore="Formazienda",
        budget_totale=100000.0,
        data_inizio=datetime(2026, 7, 1),
        data_fine=datetime(2026, 7, 31),
        stato="bozza",
    )
    db_session.add(piano)
    db_session.commit()

    assignment = crud.create_assignment(
        db_session,
        schemas.AssignmentCreate(
            collaborator_id=collaborator.id,
            project_id=project.id,
            role="Docenza",
            assigned_hours=40.0,
            start_date=datetime(2026, 7, 1),
            end_date=datetime(2026, 7, 31),
            hourly_rate=50.0,
        ),
    )
    voce = crud.get_voce_by_assignment(db_session, assignment.id)
    assert voce is not None
    return collaborator, project, piano, assignment, voce


def _freeze(db_session, piano, stato):
    piano.stato = stato
    db_session.commit()


class TestScrittureBloccateSuPianoCongelato:
    @pytest.mark.parametrize("stato", ["inviato", "rendicontato", "chiuso"])
    def test_create_voce_bloccata(self, db_session, scenario, stato):
        _, _, piano, _, _ = scenario
        _freeze(db_session, piano, stato)
        prima = db_session.query(models.VocePianoFinanziario).count()
        with pytest.raises(crud.PianoCongelatoError):
            crud.create_voce_piano(
                db_session,
                schemas.VocePianoFinanziarioCreate(
                    piano_id=piano.id,
                    descrizione="Nuova voce",
                    importo_preventivo=1000.0,
                ),
            )
        assert db_session.query(models.VocePianoFinanziario).count() == prima

    def test_update_voce_bloccata(self, db_session, scenario):
        _, _, piano, _, voce = scenario
        _freeze(db_session, piano, "rendicontato")
        with pytest.raises(crud.PianoCongelatoError):
            crud.update_voce_piano(
                db_session,
                voce.id,
                schemas.VocePianoFinanziarioUpdate(descrizione="modificata"),
            )

    def test_delete_voce_bloccata(self, db_session, scenario):
        _, _, piano, _, voce = scenario
        _freeze(db_session, piano, "chiuso")
        with pytest.raises(crud.PianoCongelatoError):
            crud.delete_voce_piano(db_session, voce.id)
        assert crud.get_voce_piano(db_session, voce.id) is not None

    def test_create_attendance_bloccata(self, db_session, scenario):
        collaborator, project, piano, assignment, _ = scenario
        _freeze(db_session, piano, "inviato")  # progetto resta active
        with pytest.raises(crud.PianoCongelatoError):
            crud.create_attendance(
                db_session,
                schemas.AttendanceCreate(
                    collaborator_id=collaborator.id,
                    project_id=project.id,
                    assignment_id=assignment.id,
                    date=datetime(2026, 7, 10),
                    start_time=datetime(2026, 7, 10, 9),
                    end_time=datetime(2026, 7, 10, 13),
                    hours=4,
                ),
            )
        assert db_session.query(models.Attendance).count() == 0


class TestScritturaConsentitaSuPianoModificabile:
    def test_bozza_consente_create_voce(self, db_session, scenario):
        _, _, piano, _, _ = scenario  # resta bozza
        voce = crud.create_voce_piano(
            db_session,
            schemas.VocePianoFinanziarioCreate(
                piano_id=piano.id,
                descrizione="Voce lecita",
                importo_preventivo=500.0,
            ),
        )
        assert voce.id is not None


class TestOverrideAdmin:
    def test_override_admin_con_motivo_consente_e_traccia(self, db_session, scenario):
        _, _, piano, _, _ = scenario
        _freeze(db_session, piano, "inviato")
        audit_prima = db_session.query(models.SecurityAuditLog).count()
        voce = crud.create_voce_piano(
            db_session,
            schemas.VocePianoFinanziarioCreate(
                piano_id=piano.id,
                descrizione="Correzione post-invio",
                importo_preventivo=200.0,
            ),
            override=True,
            motivo="Rettifica richiesta dal fondo",
            user=_admin(),
        )
        assert voce.id is not None
        assert db_session.query(models.SecurityAuditLog).count() == audit_prima + 1

    def test_override_senza_motivo_rifiutato(self, db_session, scenario):
        _, _, piano, _, _ = scenario
        _freeze(db_session, piano, "inviato")
        with pytest.raises(crud.PianoCongelatoError):
            crud.create_voce_piano(
                db_session,
                schemas.VocePianoFinanziarioCreate(
                    piano_id=piano.id,
                    descrizione="x",
                    importo_preventivo=1.0,
                ),
                override=True,
                motivo="   ",
                user=_admin(),
            )

    def test_override_non_admin_rifiutato(self, db_session, scenario):
        _, _, piano, _, _ = scenario
        _freeze(db_session, piano, "inviato")
        with pytest.raises(crud.PianoCongelatoError):
            crud.create_voce_piano(
                db_session,
                schemas.VocePianoFinanziarioCreate(
                    piano_id=piano.id,
                    descrizione="x",
                    importo_preventivo=1.0,
                ),
                override=True,
                motivo="motivo valido",
                user=_operatore(),
            )


class TestSnapshotImportoPresentato:
    def test_congela_al_passaggio_inviato_e_non_si_sovrascrive(
        self, db_session, scenario
    ):
        _, _, piano, _, voce = scenario
        voce.importo_consuntivo = 840.0
        voce.importo_presentato = 840.0
        db_session.commit()

        # transizione bozza -> inviato: congela lo snapshot
        crud.update_piano_finanziario(
            db_session,
            piano.id,
            schemas.PianoFinanziarioUpdate(stato="inviato"),
        )
        db_session.refresh(voce)
        assert float(voce.importo_presentato_congelato) == 840.0

        # un ricalcolo successivo cambia importo_presentato ma NON lo snapshot
        voce.importo_presentato = 600.0
        db_session.commit()
        db_session.refresh(voce)
        assert float(voce.importo_presentato_congelato) == 840.0
