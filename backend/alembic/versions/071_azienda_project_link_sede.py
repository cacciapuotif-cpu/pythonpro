"""add sede (ente o azienda) al collegamento azienda-progetto

Delivery multi-sede: per ogni azienda coinvolta in un progetto occorre poter
indicare dove si svolge il corso, che puo' essere una sede dell'ente
attuatore o una sede operativa dell'azienda cliente stessa.

Revision ID: 071
Revises: 070
Create Date: 2026-08-03
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "071"
down_revision = "070"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "azienda_cliente_projects",
        sa.Column("sede_tipo", sa.String(length=10), nullable=True),
    )
    op.add_column(
        "azienda_cliente_projects",
        sa.Column("sede_ente_location_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "azienda_cliente_projects",
        sa.Column("sede_azienda_operativa_id", sa.Integer(), nullable=True),
    )

    op.create_index(
        op.f("ix_azienda_cliente_projects_sede_ente_location_id"),
        "azienda_cliente_projects",
        ["sede_ente_location_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_azienda_cliente_projects_sede_azienda_operativa_id"),
        "azienda_cliente_projects",
        ["sede_azienda_operativa_id"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_azienda_cliente_projects_sede_ente_location_id",
        "azienda_cliente_projects",
        "implementing_entity_locations",
        ["sede_ente_location_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_azienda_cliente_projects_sede_azienda_operativa_id",
        "azienda_cliente_projects",
        "azienda_cliente_sedi_operative",
        ["sede_azienda_operativa_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_check_constraint(
        "ck_azienda_cliente_projects_sede_tipo",
        "azienda_cliente_projects",
        "sede_tipo IS NULL OR sede_tipo IN ('ente', 'azienda')",
    )
    op.create_check_constraint(
        "ck_azienda_cliente_projects_sede_coerente",
        "azienda_cliente_projects",
        "(sede_tipo IS NULL AND sede_ente_location_id IS NULL AND sede_azienda_operativa_id IS NULL) "
        "OR (sede_tipo = 'ente' AND sede_ente_location_id IS NOT NULL AND sede_azienda_operativa_id IS NULL) "
        "OR (sede_tipo = 'azienda' AND sede_azienda_operativa_id IS NOT NULL AND sede_ente_location_id IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_azienda_cliente_projects_sede_coerente", "azienda_cliente_projects", type_="check")
    op.drop_constraint("ck_azienda_cliente_projects_sede_tipo", "azienda_cliente_projects", type_="check")

    op.drop_constraint("fk_azienda_cliente_projects_sede_azienda_operativa_id", "azienda_cliente_projects", type_="foreignkey")
    op.drop_constraint("fk_azienda_cliente_projects_sede_ente_location_id", "azienda_cliente_projects", type_="foreignkey")

    op.drop_index(op.f("ix_azienda_cliente_projects_sede_azienda_operativa_id"), table_name="azienda_cliente_projects")
    op.drop_index(op.f("ix_azienda_cliente_projects_sede_ente_location_id"), table_name="azienda_cliente_projects")

    op.drop_column("azienda_cliente_projects", "sede_azienda_operativa_id")
    op.drop_column("azienda_cliente_projects", "sede_ente_location_id")
    op.drop_column("azienda_cliente_projects", "sede_tipo")
