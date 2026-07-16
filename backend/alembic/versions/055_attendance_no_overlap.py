"""DOM-21: vincolo DB anti-overlap orario presenze.

Revision ID: 055
Revises: 054
"""

from alembic import op

revision = "055"
down_revision = "054"
branch_labels = None
depends_on = None

CONSTRAINT_NAME = "excl_attendances_collaborator_time_overlap"


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute(
        f"""
        ALTER TABLE attendances
        ADD CONSTRAINT {CONSTRAINT_NAME}
        EXCLUDE USING gist (
            collaborator_id WITH =,
            tsrange(start_time, end_time, '[)') WITH &&
        )
        """
    )


def downgrade():
    op.execute(
        f"ALTER TABLE attendances DROP CONSTRAINT IF EXISTS {CONSTRAINT_NAME}"
    )
