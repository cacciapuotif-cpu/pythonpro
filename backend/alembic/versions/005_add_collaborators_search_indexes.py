"""add search indexes on collaborators table

Revision ID: 005
Revises: 004
Create Date: 2026-03-30

"""
from alembic import op

revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Indici per ricerca full-text (già esistono su id, email, fiscal_code)
    # Aggiungiamo quelli mancanti per i filtri del Blocco 2
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_collab_fulltext_search
            ON collaborators (lower(first_name), lower(last_name));
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_collab_position
            ON collaborators (position);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_collab_city
            ON collaborators (city);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_collab_active_created
            ON collaborators (is_active, created_at DESC);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_collab_fulltext_search;")
    op.execute("DROP INDEX IF EXISTS idx_collab_position;")
    op.execute("DROP INDEX IF EXISTS idx_collab_city;")
    op.execute("DROP INDEX IF EXISTS idx_collab_active_created;")
