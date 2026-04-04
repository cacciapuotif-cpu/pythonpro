"""fix unique default template index

Revision ID: 013
Revises: 012
Create Date: 2026-04-02
"""

from alembic import op


revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_unique_default_per_tipo")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_default_per_tipo "
        "ON contract_templates (tipo_contratto, is_default) "
        "WHERE is_default = true"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_unique_default_per_tipo")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_default_per_tipo "
        "ON contract_templates (tipo_contratto, is_default)"
    )
