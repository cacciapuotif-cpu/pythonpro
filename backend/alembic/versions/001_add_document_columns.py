"""add document columns to collaborators

Revision ID: 001
Revises:
Create Date: 2025-10-01

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Aggiungi colonne per documenti se non esistono
    op.execute("""
        ALTER TABLE collaborators
        ADD COLUMN IF NOT EXISTS documento_identita_filename VARCHAR(255),
        ADD COLUMN IF NOT EXISTS documento_identita_path VARCHAR(500),
        ADD COLUMN IF NOT EXISTS documento_identita_uploaded_at TIMESTAMP,
        ADD COLUMN IF NOT EXISTS curriculum_filename VARCHAR(255),
        ADD COLUMN IF NOT EXISTS curriculum_path VARCHAR(500),
        ADD COLUMN IF NOT EXISTS curriculum_uploaded_at TIMESTAMP;
    """)


def downgrade() -> None:
    # Rimuovi colonne documenti
    op.execute("""
        ALTER TABLE collaborators
        DROP COLUMN IF EXISTS curriculum_uploaded_at,
        DROP COLUMN IF EXISTS curriculum_path,
        DROP COLUMN IF EXISTS curriculum_filename,
        DROP COLUMN IF EXISTS documento_identita_uploaded_at,
        DROP COLUMN IF EXISTS documento_identita_path,
        DROP COLUMN IF EXISTS documento_identita_filename;
    """)
