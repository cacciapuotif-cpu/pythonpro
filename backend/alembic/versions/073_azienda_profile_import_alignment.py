"""allinea profilo azienda, sedi e conti per import/export

Revision ID: 073
Revises: 072
Create Date: 2026-08-03
"""

from alembic import op
import sqlalchemy as sa


revision = "073"
down_revision = "072"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "azienda_cliente_sedi_operative",
        sa.Column("tipo", sa.String(length=30), nullable=False, server_default="operativa"),
    )
    op.add_column("azienda_cliente_sedi_operative", sa.Column("email", sa.String(length=100), nullable=True))
    op.add_column("azienda_cliente_sedi_operative", sa.Column("telefono", sa.String(length=30), nullable=True))
    op.add_column(
        "azienda_cliente_sedi_operative",
        sa.Column("is_principale", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_check_constraint(
        "ck_azienda_cliente_sedi_operative_tipo",
        "azienda_cliente_sedi_operative",
        "tipo IN ('operativa', 'amministrativa', 'accreditata')",
    )
    op.create_index(
        "uq_azienda_cliente_one_primary_location",
        "azienda_cliente_sedi_operative",
        ["azienda_cliente_id"],
        unique=True,
        postgresql_where=sa.text("is_principale"),
    )

    op.create_table(
        "azienda_cliente_bank_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("azienda_cliente_id", sa.Integer(), nullable=False),
        sa.Column("banca", sa.String(length=200), nullable=True),
        sa.Column("agenzia", sa.String(length=200), nullable=True),
        sa.Column("iban", sa.String(length=34), nullable=False),
        sa.Column("bic_swift", sa.String(length=11), nullable=True),
        sa.Column("intestatario", sa.String(length=200), nullable=False),
        sa.Column("is_predefinito", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["azienda_cliente_id"], ["aziende_clienti.id"],
            name="fk_azienda_cliente_bank_accounts_azienda", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("azienda_cliente_id", "iban", name="uq_azienda_cliente_bank_account_iban"),
    )
    op.create_index(
        op.f("ix_azienda_cliente_bank_accounts_id"),
        "azienda_cliente_bank_accounts", ["id"], unique=False,
    )
    op.create_index(
        op.f("ix_azienda_cliente_bank_accounts_azienda_cliente_id"),
        "azienda_cliente_bank_accounts", ["azienda_cliente_id"], unique=False,
    )
    op.create_index(
        op.f("ix_azienda_cliente_bank_accounts_is_active"),
        "azienda_cliente_bank_accounts", ["is_active"], unique=False,
    )
    op.create_index(
        "uq_azienda_cliente_one_active_default_account",
        "azienda_cliente_bank_accounts", ["azienda_cliente_id"], unique=True,
        postgresql_where=sa.text("is_predefinito AND is_active"),
    )


def downgrade() -> None:
    op.drop_table("azienda_cliente_bank_accounts")
    op.drop_index(
        "uq_azienda_cliente_one_primary_location",
        table_name="azienda_cliente_sedi_operative",
    )
    op.drop_constraint(
        "ck_azienda_cliente_sedi_operative_tipo",
        "azienda_cliente_sedi_operative",
        type_="check",
    )
    op.drop_column("azienda_cliente_sedi_operative", "is_principale")
    op.drop_column("azienda_cliente_sedi_operative", "telefono")
    op.drop_column("azienda_cliente_sedi_operative", "email")
    op.drop_column("azienda_cliente_sedi_operative", "tipo")
