"""Espressioni server-side condivise per ordinare nominativi."""
from sqlalchemy import func


def normalized_person_column(column, bind):
    """Ordina senza distinguere maiuscole/accidenti (PostgreSQL) o case (SQLite)."""
    if getattr(bind.dialect, "name", "") == "postgresql":
        return func.lower(func.unaccent(column))
    return func.lower(column)


def person_order(last_name, first_name, bind):
    return (
        normalized_person_column(last_name, bind).asc(),
        normalized_person_column(first_name, bind).asc(),
    )
