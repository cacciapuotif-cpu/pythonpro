"""Utility temporali centralizzate.

Mantiene output naive UTC per compatibilita' con colonne SQLAlchemy DateTime
non timezone-aware gia' presenti nello schema, evitando il vecchio metodo UTC.
"""
from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
