"""crud.get_attendances_calendar: multi-selezione collaboratori/progetti,
esclusione progetti chiusi di default, conteggio totale server-side."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import crud
import models
from database import Base


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _make_collaborator(db, **overrides):
    _n = overrides.get('_n', 1)
    defaults = dict(
        first_name="Mario",
        last_name="Rossi",
        email=f"m{_n}@x.it",
        fiscal_code=f"RSSMRA{80+_n:02d}A001{_n:04d}"
    )
    defaults.update({k: v for k, v in overrides.items() if k != "_n"})
    c = models.Collaborator(**defaults)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _make_project(db, *, is_active=True, **overrides):
    defaults = dict(name="Progetto Test", status="active" if is_active else "completed", is_active=is_active)
    defaults.update(overrides)
    p = models.Project(**defaults)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _make_attendance(db, *, collaborator_id, project_id, when):
    a = models.Attendance(
        collaborator_id=collaborator_id,
        project_id=project_id,
        date=when,
        start_time=when,
        end_time=when + timedelta(hours=1),
        hours=1,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def test_filtra_per_piu_collaboratori_e_piu_progetti(db_session):
    c1 = _make_collaborator(db_session, _n=1)
    c2 = _make_collaborator(db_session, _n=2)
    c3 = _make_collaborator(db_session, _n=3)
    p1 = _make_project(db_session)
    p2 = _make_project(db_session)
    now = datetime(2026, 7, 1, 9, 0)
    _make_attendance(db_session, collaborator_id=c1.id, project_id=p1.id, when=now)
    _make_attendance(db_session, collaborator_id=c2.id, project_id=p2.id, when=now)
    _make_attendance(db_session, collaborator_id=c3.id, project_id=p1.id, when=now)

    items, total = crud.get_attendances_calendar(
        db_session,
        collaborator_ids=[c1.id, c2.id],
        project_ids=[p1.id, p2.id],
        start_date=now - timedelta(days=1),
        end_date=now + timedelta(days=1),
    )

    assert total == 2
    assert {a.collaborator_id for a in items} == {c1.id, c2.id}


def test_esclude_progetti_chiusi_di_default(db_session):
    c1 = _make_collaborator(db_session, _n=1)
    p_aperto = _make_project(db_session, is_active=True)
    p_chiuso = _make_project(db_session, is_active=False)
    now = datetime(2026, 7, 1, 9, 0)
    _make_attendance(db_session, collaborator_id=c1.id, project_id=p_aperto.id, when=now)
    _make_attendance(db_session, collaborator_id=c1.id, project_id=p_chiuso.id, when=now)

    items, total = crud.get_attendances_calendar(
        db_session, start_date=now - timedelta(days=1), end_date=now + timedelta(days=1),
    )
    assert total == 1
    assert items[0].project_id == p_aperto.id

    items_incl, total_incl = crud.get_attendances_calendar(
        db_session,
        start_date=now - timedelta(days=1),
        end_date=now + timedelta(days=1),
        include_closed_projects=True,
    )
    assert total_incl == 2


def test_total_conta_tutte_le_righe_anche_oltre_il_limit(db_session):
    c1 = _make_collaborator(db_session, _n=1)
    p1 = _make_project(db_session)
    now = datetime(2026, 7, 1, 9, 0)
    for i in range(5):
        _make_attendance(db_session, collaborator_id=c1.id, project_id=p1.id, when=now + timedelta(hours=i))

    items, total = crud.get_attendances_calendar(
        db_session, start_date=now - timedelta(days=1), end_date=now + timedelta(days=1), limit=2,
    )
    assert total == 5
    assert len(items) == 2


def test_collaborator_ids_lista_vuota_non_mostra_nulla(db_session):
    """Regressione: only_mine senza collaborator_id collegato passa [] (non
    None). [] deve significare 'nessun risultato', non 'nessun filtro' —
    altrimenti un utente senza collaboratore vede le presenze di tutti."""
    c1 = _make_collaborator(db_session, _n=1)
    p1 = _make_project(db_session)
    now = datetime(2026, 7, 1, 9, 0)
    _make_attendance(db_session, collaborator_id=c1.id, project_id=p1.id, when=now)

    items, total = crud.get_attendances_calendar(
        db_session,
        collaborator_ids=[],
        start_date=now - timedelta(days=1),
        end_date=now + timedelta(days=1),
    )
    assert total == 0
    assert items == []
