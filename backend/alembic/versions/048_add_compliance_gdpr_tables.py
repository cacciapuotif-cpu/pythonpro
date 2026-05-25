"""add compliance gdpr tables

Revision ID: 048
Revises: 047
Create Date: 2026-05-24
"""

from alembic import op
import sqlalchemy as sa

revision = "048"
down_revision = "047"
branch_labels = None
depends_on = None


def _tables():
    return set(sa.inspect(op.get_bind()).get_table_names())


def _cols(table):
    inspector = sa.inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return set()
    return {c["name"] for c in inspector.get_columns(table)}


def _add(table, column):
    if column.name not in _cols(table):
        op.add_column(table, column)


def upgrade():
    tables = _tables()
    if "progetto_beneficiario" not in tables:
        op.create_table("progetto_beneficiario",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("progetto_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
            sa.Column("nome", sa.String(100), nullable=False),
            sa.Column("cognome", sa.String(100), nullable=False),
            sa.Column("cf", sa.String(16), nullable=False),
            sa.Column("ruolo", sa.String(100), nullable=True),
            sa.Column("data_inizio", sa.Date(), nullable=True),
            sa.Column("data_fine", sa.Date(), nullable=True),
        )
        op.create_index("ix_progetto_beneficiario_progetto_id", "progetto_beneficiario", ["progetto_id"])
        op.create_index("ix_progetto_beneficiario_cf", "progetto_beneficiario", ["cf"])

    if "massimali_fondo" not in tables:
        op.create_table("massimali_fondo",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tipo_fondo", sa.String(30), nullable=False),
            sa.Column("anno", sa.Integer(), nullable=False),
            sa.Column("massimale_orario_docenza", sa.Numeric(8, 2), nullable=True),
            sa.Column("massimale_orario_tutoraggio", sa.Numeric(8, 2), nullable=True),
            sa.Column("massimale_spese_generali_pct", sa.Numeric(5, 2), nullable=True),
            sa.UniqueConstraint("tipo_fondo", "anno", name="uq_massimali_fondo_tipo_anno"),
        )
        op.create_index("ix_massimali_fondo_tipo_fondo", "massimali_fondo", ["tipo_fondo"])
        op.create_index("ix_massimali_fondo_anno", "massimali_fondo", ["anno"])
    op.execute("""
        INSERT INTO massimali_fondo (tipo_fondo, anno, massimale_orario_docenza, massimale_orario_tutoraggio, massimale_spese_generali_pct)
        VALUES ('fondimpresa', 2024, 100.00, 70.00, 20.00)
        ON CONFLICT ON CONSTRAINT uq_massimali_fondo_tipo_anno DO NOTHING
    """)

    if "gdpr_consensi" not in tables:
        op.create_table("gdpr_consensi",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("collaboratore_id", sa.Integer(), sa.ForeignKey("collaborators.id", ondelete="CASCADE"), nullable=False),
            sa.Column("tipo_consenso", sa.String(50), nullable=False),
            sa.Column("data_consenso", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("ip_address_hash", sa.String(64), nullable=True),
            sa.Column("revocato", sa.Boolean(), server_default=sa.text("false"), nullable=False),
            sa.Column("data_revoca", sa.DateTime(timezone=True), nullable=True),
            sa.CheckConstraint("ip_address_hash IS NULL OR ip_address_hash ~ '^[a-f0-9]{64}$'", name="ck_gdpr_consensi_ip_sha256"),
        )
        op.create_index("ix_gdpr_consensi_collaboratore_id", "gdpr_consensi", ["collaboratore_id"])
        op.create_index("ix_gdpr_consensi_tipo_consenso", "gdpr_consensi", ["tipo_consenso"])

    for col in (
        sa.Column("data_ammissione", sa.Date(), nullable=True),
        sa.Column("stato_rendicontazione", sa.String(20), nullable=False, server_default="bozza"),
        sa.Column("codice_progetto_fondo", sa.String(50), nullable=True),
        sa.Column("importo_ammesso", sa.Numeric(12, 2), nullable=True),
    ):
        _add("piani_finanziari", col)
    op.execute("UPDATE piani_finanziari SET tipo_fondo = 'altro' WHERE tipo_fondo IS NULL OR tipo_fondo NOT IN ('fondimpresa', 'fonamcom', 'fse', 'regionale', 'altro')")

    for col in (
        sa.Column("consenso_email_agenti", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("consenso_whatsapp_agenti", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("anonimizzato", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("data_anonimizzazione", sa.DateTime(timezone=True), nullable=True),
    ):
        _add("collaborators", col)


def downgrade():
    for table in ("gdpr_consensi", "massimali_fondo", "progetto_beneficiario"):
        if table in _tables():
            op.drop_table(table)
    for column in ("data_anonimizzazione", "anonimizzato", "consenso_whatsapp_agenti", "consenso_email_agenti"):
        if column in _cols("collaborators"):
            op.drop_column("collaborators", column)
    for column in ("importo_ammesso", "codice_progetto_fondo", "stato_rendicontazione", "data_ammissione"):
        if column in _cols("piani_finanziari"):
            op.drop_column("piani_finanziari", column)
