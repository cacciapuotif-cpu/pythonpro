"""add document expiry column to collaborators

Revision ID: 003
Revises: 002
Create Date: 2026-03-27

"""
from alembic import op

# revision identifiers
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE collaborators
        ADD COLUMN IF NOT EXISTS documento_identita_scadenza TIMESTAMP;
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE collaborators
        DROP COLUMN IF EXISTS documento_identita_scadenza;
    """)
