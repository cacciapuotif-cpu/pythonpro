"""Regressione: il default timestamp dell'inbox deve essere SQLite-compatible."""
from datetime import datetime

from sqlalchemy import create_engine, insert, select

import models


def test_email_inbox_created_at_default_is_valid_on_sqlite():
    engine = create_engine("sqlite:///:memory:")
    table = models.EmailInboxItem.__table__
    table.create(engine)
    with engine.begin() as connection:
        connection.execute(insert(table).values(
            message_id="regression-1", received_at=datetime.utcnow(),
            sender_email="test@example.com", processing_status="received",
        ))
        value = connection.execute(select(table.c.created_at)).scalar_one()
    assert value is not None
