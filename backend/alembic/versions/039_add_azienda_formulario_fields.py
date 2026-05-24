"""add azienda formulario fields

Revision ID: 039
Revises: 037
Create Date: 2026-04-22
"""

from alembic import op
import sqlalchemy as sa


revision = "039"
down_revision = "037"
branch_labels = None
depends_on = None


FIELDS = [
    ("natura_giuridica", sa.String(length=50)),
    ("settore_codice", sa.String(length=10)),
    ("settore_descrizione", sa.String(length=255)),
    ("sede_legale_indirizzo", sa.String(length=255)),
    ("sede_legale_cap", sa.String(length=5)),
    ("sede_legale_comune", sa.String(length=100)),
    ("sede_legale_provincia", sa.String(length=100)),
    ("sede_operativa_indirizzo", sa.String(length=255)),
    ("sede_operativa_cap", sa.String(length=5)),
    ("sede_operativa_comune", sa.String(length=100)),
    ("sede_operativa_provincia", sa.String(length=100)),
    ("matricola_inps", sa.String(length=30)),
    ("anno_adesione", sa.String(length=4)),
    ("regime_aiuto_default", sa.String(length=30)),
    ("num_dipendenti", sa.Integer()),
    ("ccnl_prevalente", sa.String(length=255)),
]


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for name, column_type in FIELDS:
        if not _has_column(inspector, "aziende_clienti", name):
            op.add_column("aziende_clienti", sa.Column(name, column_type, nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for name, _column_type in reversed(FIELDS):
        if _has_column(inspector, "aziende_clienti", name):
            op.drop_column("aziende_clienti", name)
