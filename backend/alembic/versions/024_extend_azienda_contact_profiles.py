"""Extend azienda contact profiles.

Revision ID: 024
Revises: 023
Create Date: 2026-04-03
"""

from alembic import op
import sqlalchemy as sa


revision = "024"
down_revision = "023"
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
        ("legale_rappresentante_facebook", sa.String(length=255)),
        ("legale_rappresentante_instagram", sa.String(length=255)),
        ("legale_rappresentante_tiktok", sa.String(length=255)),
        ("referente_luogo_nascita", sa.String(length=100)),
        ("referente_data_nascita", sa.DateTime()),
        ("referente_tiktok", sa.String(length=255)),
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
    removable_columns = [
        "referente_tiktok",
        "referente_data_nascita",
        "referente_luogo_nascita",
        "legale_rappresentante_tiktok",
        "legale_rappresentante_instagram",
        "legale_rappresentante_facebook",
    ]

    for name in removable_columns:
        if name in columns:
            op.drop_column("aziende_clienti", name)
