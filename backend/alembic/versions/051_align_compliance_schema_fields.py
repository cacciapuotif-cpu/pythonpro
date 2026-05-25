"""align compliance schema fields

Revision ID: 051
Revises: 050
Create Date: 2026-05-24
"""

from alembic import op
import sqlalchemy as sa

revision = "051"
down_revision = "050"
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(table_name):
    return table_name in _inspector().get_table_names()


def _columns(table_name):
    if not _has_table(table_name):
        return set()
    return {col["name"] for col in _inspector().get_columns(table_name)}


def _add(table_name, column):
    if _has_table(table_name) and column.name not in _columns(table_name):
        op.add_column(table_name, column)


def upgrade():
    if _has_table("collaborators"):
        for col in (
            sa.Column("consenso_email_agenti", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("consenso_whatsapp_agenti", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("anonimizzato", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("data_anonimizzazione", sa.DateTime(timezone=True), nullable=True),
        ):
            _add("collaborators", col)

    if _has_table("piani_finanziari"):
        _add("piani_finanziari", sa.Column("tipo_fondo", sa.String(30), nullable=True))
        _add("piani_finanziari", sa.Column("data_ammissione", sa.Date(), nullable=True))
        _add("piani_finanziari", sa.Column("stato_rendicontazione", sa.String(20), nullable=False, server_default="bozza"))
        _add("piani_finanziari", sa.Column("codice_progetto_fondo", sa.String(50), nullable=True))
        _add("piani_finanziari", sa.Column("importo_ammesso", sa.Numeric(12, 2), nullable=True))
        op.execute("""
            UPDATE piani_finanziari
            SET tipo_fondo = 'altro'
            WHERE tipo_fondo IS NULL
               OR tipo_fondo NOT IN ('fondimpresa', 'fonamcom', 'fse', 'regionale', 'altro')
        """)
        op.alter_column(
            "piani_finanziari",
            "tipo_fondo",
            existing_type=sa.String(50),
            type_=sa.String(30),
            nullable=True,
            existing_nullable=True,
            server_default=None,
        )

    if _has_table("massimali_fondo"):
        _add("massimali_fondo", sa.Column("massimale_orario_docenza", sa.Numeric(8, 2), nullable=True))
        _add("massimali_fondo", sa.Column("massimale_orario_tutoraggio", sa.Numeric(8, 2), nullable=True))
        _add("massimali_fondo", sa.Column("massimale_spese_generali_pct", sa.Numeric(5, 2), nullable=True))
        op.alter_column("massimali_fondo", "massimale_orario_docenza", existing_type=sa.Numeric(10, 2), type_=sa.Numeric(8, 2), existing_nullable=True)
        op.alter_column("massimali_fondo", "massimale_orario_tutoraggio", existing_type=sa.Numeric(10, 2), type_=sa.Numeric(8, 2), existing_nullable=True)
        op.execute("""
            INSERT INTO massimali_fondo (tipo_fondo, anno, massimale_orario_docenza, massimale_orario_tutoraggio, massimale_spese_generali_pct)
            VALUES ('fondimpresa', 2024, 100.00, 70.00, 20.00)
            ON CONFLICT ON CONSTRAINT uq_massimali_fondo_tipo_anno DO UPDATE SET
                massimale_orario_docenza = EXCLUDED.massimale_orario_docenza,
                massimale_orario_tutoraggio = EXCLUDED.massimale_orario_tutoraggio,
                massimale_spese_generali_pct = EXCLUDED.massimale_spese_generali_pct
        """)


def downgrade():
    if _has_table("piani_finanziari") and "tipo_fondo" in _columns("piani_finanziari"):
        op.execute("UPDATE piani_finanziari SET tipo_fondo = 'altro' WHERE tipo_fondo IS NULL")
        op.alter_column(
            "piani_finanziari",
            "tipo_fondo",
            existing_type=sa.String(30),
            type_=sa.String(50),
            nullable=False,
            existing_nullable=True,
            server_default=None,
        )
    if _has_table("massimali_fondo"):
        op.alter_column("massimali_fondo", "massimale_orario_docenza", existing_type=sa.Numeric(8, 2), type_=sa.Numeric(10, 2), existing_nullable=True)
        op.alter_column("massimali_fondo", "massimale_orario_tutoraggio", existing_type=sa.Numeric(8, 2), type_=sa.Numeric(10, 2), existing_nullable=True)
