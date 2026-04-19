"""add azienda sedi operative

Revision ID: p6k7l8m9n0o1
Revises: o5j6k7l8m9n0
Create Date: 2026-04-08
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "p6k7l8m9n0o1"
down_revision = "o5j6k7l8m9n0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "azienda_cliente_sedi_operative",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("azienda_cliente_id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=150), nullable=False),
        sa.Column("indirizzo", sa.String(length=255), nullable=True),
        sa.Column("citta", sa.String(length=100), nullable=True),
        sa.Column("cap", sa.String(length=5), nullable=True),
        sa.Column("provincia", sa.String(length=2), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["azienda_cliente_id"], ["aziende_clienti.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("azienda_cliente_id", "nome", name="uq_azienda_sede_operativa_nome"),
    )
    op.create_index(op.f("ix_azienda_cliente_sedi_operative_id"), "azienda_cliente_sedi_operative", ["id"], unique=False)
    op.create_index(op.f("ix_azienda_cliente_sedi_operative_azienda_cliente_id"), "azienda_cliente_sedi_operative", ["azienda_cliente_id"], unique=False)
    op.create_index(op.f("ix_azienda_cliente_sedi_operative_citta"), "azienda_cliente_sedi_operative", ["citta"], unique=False)
    op.create_index(op.f("ix_azienda_cliente_sedi_operative_created_at"), "azienda_cliente_sedi_operative", ["created_at"], unique=False)
    op.create_index("idx_azienda_sede_operativa_citta", "azienda_cliente_sedi_operative", ["azienda_cliente_id", "citta"], unique=False)

    op.add_column("allievi", sa.Column("azienda_sede_operativa_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_allievi_azienda_sede_operativa_id"), "allievi", ["azienda_sede_operativa_id"], unique=False)
    op.create_foreign_key(
        "fk_allievi_azienda_sede_operativa_id",
        "allievi",
        "azienda_cliente_sedi_operative",
        ["azienda_sede_operativa_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_allievi_azienda_sede_operativa_id", "allievi", type_="foreignkey")
    op.drop_index(op.f("ix_allievi_azienda_sede_operativa_id"), table_name="allievi")
    op.drop_column("allievi", "azienda_sede_operativa_id")

    op.drop_index("idx_azienda_sede_operativa_citta", table_name="azienda_cliente_sedi_operative")
    op.drop_index(op.f("ix_azienda_cliente_sedi_operative_created_at"), table_name="azienda_cliente_sedi_operative")
    op.drop_index(op.f("ix_azienda_cliente_sedi_operative_citta"), table_name="azienda_cliente_sedi_operative")
    op.drop_index(op.f("ix_azienda_cliente_sedi_operative_azienda_cliente_id"), table_name="azienda_cliente_sedi_operative")
    op.drop_index(op.f("ix_azienda_cliente_sedi_operative_id"), table_name="azienda_cliente_sedi_operative")
    op.drop_table("azienda_cliente_sedi_operative")
