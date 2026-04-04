"""Add contact addresses to aziende_clienti.

Revision ID: 026
Revises: 025
Create Date: 2026-04-03
"""

from alembic import op
import sqlalchemy as sa


revision = "026"
down_revision = "025"
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
    additions = [
        ("legale_rappresentante_indirizzo", sa.String(length=255)),
        ("referente_indirizzo", sa.String(length=255)),
    ]

    for name, column_type in additions:
        if name not in columns:
            op.add_column("aziende_clienti", sa.Column(name, column_type, nullable=True))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "aziende_clienti" not in inspector.get_table_names():
        return

    columns = _get_columns(inspector, "aziende_clienti")
    for name in ["referente_indirizzo", "legale_rappresentante_indirizzo"]:
        if name in columns:
            op.drop_column("aziende_clienti", name)
