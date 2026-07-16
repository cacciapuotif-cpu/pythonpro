"""DOM-21 — il DB serializza due presenze concorrenti sovrapposte."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

URL = os.getenv("DOM21_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not URL or not URL.startswith("postgresql"),
    reason="richiede DOM21_TEST_DATABASE_URL PostgreSQL dedicato",
)


def test_constraint_blocca_overlap_concorrente():
    engine = create_engine(URL)
    with engine.connect() as conn:
        constraint = conn.execute(text(
            "SELECT 1 FROM pg_constraint WHERE conname = "
            "'excl_attendances_collaborator_time_overlap'"
        )).scalar()
        collaborator_id = conn.execute(text(
            "SELECT id FROM collaborators ORDER BY id LIMIT 1"
        )).scalar()
        project_id = conn.execute(text(
            "SELECT id FROM projects ORDER BY id LIMIT 1"
        )).scalar()
    assert constraint == 1
    assert collaborator_id and project_id

    start = datetime(2099, 1, 2, 9)

    def insert(offset_minutes):
        try:
            with engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO attendances
                        (collaborator_id, project_id, date, start_time, end_time, hours)
                    VALUES (:collaborator_id, :project_id, :date, :start_time, :end_time, 2)
                """), {
                    "collaborator_id": collaborator_id,
                    "project_id": project_id,
                    "date": start + timedelta(minutes=offset_minutes),
                    "start_time": start + timedelta(minutes=offset_minutes),
                    "end_time": start + timedelta(hours=2, minutes=offset_minutes),
                })
            return "ok"
        except IntegrityError:
            return "blocked"

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(insert, (0, 30)))
        assert sorted(results) == ["blocked", "ok"]
    finally:
        with engine.begin() as conn:
            conn.execute(text(
                "DELETE FROM attendances WHERE collaborator_id=:cid AND start_time >= :start"
            ), {"cid": collaborator_id, "start": start})
        engine.dispose()
