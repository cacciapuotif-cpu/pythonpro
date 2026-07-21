"""Indici GIN FTS per la ricerca archivio (FASE E3, Task E3.1).

Tre indici expression ``to_tsvector('italian', ...)`` sulle fonti della
ricerca archivio (``services/archivio_search.py``); le espressioni SQL sono
identiche a quelle costruite dal servizio, cosi' il planner puo' usarli:

- avviso_regole (parziale ``WHERE stato = 'validata'``): chiave + valore + testo_originale;
- avviso_conoscenze: contenuto + tags;
- avviso_esiti_progetto: esito + note.

Immutabilita' verificata empiricamente su PostgreSQL 15 (probe 2026-07-21):
``jsonb::text`` via I/O-conversion e' accettato nelle index expression, quindi
anche le colonne JSONB (valore, tags) sono indicizzate — nessun compromesso.
Le coalesce rendono l'espressione totale anche con colonne NULL.

Solo schema, PostgreSQL-only (guard sul dialect come 044): su SQLite la
ricerca usa il fallback ILIKE e non servono indici.

Revision ID: 061
Revises: 060
"""
from alembic import op


revision = "061"
down_revision = "060"
branch_labels = None
depends_on = None

_INDEXES = (
    (
        "ix_fts_avviso_regole_validata",
        """
        CREATE INDEX IF NOT EXISTS ix_fts_avviso_regole_validata
        ON avviso_regole USING gin (
            to_tsvector('italian',
                coalesce(cast(chiave AS text), '') || ' ' ||
                coalesce(cast(valore AS text), '') || ' ' ||
                coalesce(cast(testo_originale AS text), ''))
        )
        WHERE stato = 'validata'
        """,
    ),
    (
        "ix_fts_avviso_conoscenze",
        """
        CREATE INDEX IF NOT EXISTS ix_fts_avviso_conoscenze
        ON avviso_conoscenze USING gin (
            to_tsvector('italian',
                coalesce(cast(contenuto AS text), '') || ' ' ||
                coalesce(cast(tags AS text), ''))
        )
        """,
    ),
    (
        "ix_fts_avviso_esiti",
        """
        CREATE INDEX IF NOT EXISTS ix_fts_avviso_esiti
        ON avviso_esiti_progetto USING gin (
            to_tsvector('italian',
                coalesce(cast(esito AS text), '') || ' ' ||
                coalesce(cast(note AS text), ''))
        )
        """,
    ),
)


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for _name, ddl in _INDEXES:
        op.execute(ddl)


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for name, _ddl in _INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {name}")
