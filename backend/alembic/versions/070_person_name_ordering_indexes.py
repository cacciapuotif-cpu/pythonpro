"""UX: indici per ordinamento nominativi case/accent insensitive."""
from alembic import op

revision = "070"
down_revision = "069"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    op.execute("""
        CREATE OR REPLACE FUNCTION immutable_unaccent(text)
        RETURNS text LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT AS $$
          SELECT public.unaccent('public.unaccent', $1)
        $$
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_collaborators_person_order ON collaborators (immutable_unaccent(lower(last_name)), immutable_unaccent(lower(first_name)), id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_allievi_person_order ON allievi (immutable_unaccent(lower(cognome)), immutable_unaccent(lower(nome)), id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_consulenti_person_order ON consulenti (immutable_unaccent(lower(cognome)), immutable_unaccent(lower(nome)), id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_consulenti_person_order")
    op.execute("DROP INDEX IF EXISTS ix_allievi_person_order")
    op.execute("DROP INDEX IF EXISTS ix_collaborators_person_order")
    op.execute("DROP FUNCTION IF EXISTS immutable_unaccent(text)")
