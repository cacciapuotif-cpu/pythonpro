"""Add referente_cognome to aziende_clienti.

Revision ID: 025
Revises: 024
Create Date: 2026-04-03
"""

from alembic import op
import sqlalchemy as sa


revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def _get_columns(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "aziende_clienti" not in inspector.get_table_names():
        return

    columns = _get_columns(inspector, "aziende_clienti")
    if "referente_cognome" not in columns:
        op.add_column("aziende_clienti", sa.Column("referente_cognome", sa.String(length=100), nullable=True))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "aziende_clienti" not in inspector.get_table_names():
        return

    columns = _get_columns(inspector, "aziende_clienti")
    if "referente_cognome" in columns:
        op.drop_column("aziende_clienti", "referente_cognome")
