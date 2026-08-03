"""sedi delivery multiple per azienda e progetto

Revision ID: 072
Revises: 071
Create Date: 2026-08-03
"""

from alembic import op
import sqlalchemy as sa


revision = "072"
down_revision = "071"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_azienda_delivery_sedi",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("azienda_project_link_id", sa.Integer(), nullable=False),
        sa.Column("sede_tipo", sa.String(length=10), nullable=False),
        sa.Column("sede_ente_location_id", sa.Integer(), nullable=True),
        sa.Column("sede_azienda_operativa_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("sede_tipo IN ('ente', 'azienda')", name="ck_project_azienda_delivery_sedi_tipo"),
        sa.CheckConstraint(
            "(sede_tipo = 'ente' AND sede_ente_location_id IS NOT NULL AND sede_azienda_operativa_id IS NULL) "
            "OR (sede_tipo = 'azienda' AND sede_azienda_operativa_id IS NOT NULL AND sede_ente_location_id IS NULL)",
            name="ck_project_azienda_delivery_sedi_coerente",
        ),
        sa.ForeignKeyConstraint(
            ["azienda_project_link_id"], ["azienda_cliente_projects.id"],
            name="fk_delivery_sedi_azienda_project_link", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sede_ente_location_id"], ["implementing_entity_locations.id"],
            name="fk_delivery_sedi_ente_location", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sede_azienda_operativa_id"], ["azienda_cliente_sedi_operative.id"],
            name="fk_delivery_sedi_azienda_operativa", ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_project_azienda_delivery_sedi_id"), "project_azienda_delivery_sedi", ["id"])
    op.create_index(op.f("ix_project_azienda_delivery_sedi_azienda_project_link_id"), "project_azienda_delivery_sedi", ["azienda_project_link_id"])
    op.create_index(op.f("ix_project_azienda_delivery_sedi_sede_ente_location_id"), "project_azienda_delivery_sedi", ["sede_ente_location_id"])
    op.create_index(op.f("ix_project_azienda_delivery_sedi_sede_azienda_operativa_id"), "project_azienda_delivery_sedi", ["sede_azienda_operativa_id"])
    op.create_index(
        "uq_project_azienda_delivery_sedi_ente",
        "project_azienda_delivery_sedi",
        ["azienda_project_link_id", "sede_ente_location_id"],
        unique=True,
        postgresql_where=sa.text("sede_tipo = 'ente'"),
    )
    op.create_index(
        "uq_project_azienda_delivery_sedi_azienda",
        "project_azienda_delivery_sedi",
        ["azienda_project_link_id", "sede_azienda_operativa_id"],
        unique=True,
        postgresql_where=sa.text("sede_tipo = 'azienda'"),
    )

    # Conserva senza perdita tutte le scelte monovalore introdotte dalla 071.
    op.execute(
        """
        INSERT INTO project_azienda_delivery_sedi
            (azienda_project_link_id, sede_tipo, sede_ente_location_id, sede_azienda_operativa_id)
        SELECT id, sede_tipo, sede_ente_location_id, sede_azienda_operativa_id
        FROM azienda_cliente_projects
        WHERE sede_tipo IS NOT NULL
        """
    )

    op.drop_constraint("ck_azienda_cliente_projects_sede_coerente", "azienda_cliente_projects", type_="check")
    op.drop_constraint("ck_azienda_cliente_projects_sede_tipo", "azienda_cliente_projects", type_="check")
    op.drop_constraint("fk_azienda_cliente_projects_sede_azienda_operativa_id", "azienda_cliente_projects", type_="foreignkey")
    op.drop_constraint("fk_azienda_cliente_projects_sede_ente_location_id", "azienda_cliente_projects", type_="foreignkey")
    op.drop_index(op.f("ix_azienda_cliente_projects_sede_azienda_operativa_id"), table_name="azienda_cliente_projects")
    op.drop_index(op.f("ix_azienda_cliente_projects_sede_ente_location_id"), table_name="azienda_cliente_projects")
    op.drop_column("azienda_cliente_projects", "sede_azienda_operativa_id")
    op.drop_column("azienda_cliente_projects", "sede_ente_location_id")
    op.drop_column("azienda_cliente_projects", "sede_tipo")

    op.add_column("attendances", sa.Column("delivery_sede_id", sa.Integer(), nullable=True))
    op.add_column("attendances", sa.Column("delivery_sede_label", sa.String(length=500), nullable=True))
    op.create_index(op.f("ix_attendances_delivery_sede_id"), "attendances", ["delivery_sede_id"])
    op.create_foreign_key(
        "fk_attendances_delivery_sede_id",
        "attendances", "project_azienda_delivery_sedi",
        ["delivery_sede_id"], ["id"], ondelete="SET NULL",
    )
    op.add_column("timesheet_righe", sa.Column("delivery_sede_label", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("timesheet_righe", "delivery_sede_label")
    op.drop_constraint("fk_attendances_delivery_sede_id", "attendances", type_="foreignkey")
    op.drop_index(op.f("ix_attendances_delivery_sede_id"), table_name="attendances")
    op.drop_column("attendances", "delivery_sede_label")
    op.drop_column("attendances", "delivery_sede_id")

    op.add_column("azienda_cliente_projects", sa.Column("sede_tipo", sa.String(length=10), nullable=True))
    op.add_column("azienda_cliente_projects", sa.Column("sede_ente_location_id", sa.Integer(), nullable=True))
    op.add_column("azienda_cliente_projects", sa.Column("sede_azienda_operativa_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_azienda_cliente_projects_sede_ente_location_id"), "azienda_cliente_projects", ["sede_ente_location_id"])
    op.create_index(op.f("ix_azienda_cliente_projects_sede_azienda_operativa_id"), "azienda_cliente_projects", ["sede_azienda_operativa_id"])
    op.create_foreign_key("fk_azienda_cliente_projects_sede_ente_location_id", "azienda_cliente_projects", "implementing_entity_locations", ["sede_ente_location_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_azienda_cliente_projects_sede_azienda_operativa_id", "azienda_cliente_projects", "azienda_cliente_sedi_operative", ["sede_azienda_operativa_id"], ["id"], ondelete="SET NULL")
    op.create_check_constraint("ck_azienda_cliente_projects_sede_tipo", "azienda_cliente_projects", "sede_tipo IS NULL OR sede_tipo IN ('ente', 'azienda')")
    op.create_check_constraint(
        "ck_azienda_cliente_projects_sede_coerente", "azienda_cliente_projects",
        "(sede_tipo IS NULL AND sede_ente_location_id IS NULL AND sede_azienda_operativa_id IS NULL) "
        "OR (sede_tipo = 'ente' AND sede_ente_location_id IS NOT NULL AND sede_azienda_operativa_id IS NULL) "
        "OR (sede_tipo = 'azienda' AND sede_azienda_operativa_id IS NOT NULL AND sede_ente_location_id IS NULL)",
    )
    # Il vecchio schema può contenere una sola sede: conserva deterministicamente la prima.
    op.execute(
        """
        UPDATE azienda_cliente_projects link
        SET sede_tipo = src.sede_tipo,
            sede_ente_location_id = src.sede_ente_location_id,
            sede_azienda_operativa_id = src.sede_azienda_operativa_id
        FROM (
            SELECT DISTINCT ON (azienda_project_link_id)
                azienda_project_link_id, sede_tipo, sede_ente_location_id, sede_azienda_operativa_id
            FROM project_azienda_delivery_sedi
            ORDER BY azienda_project_link_id, id
        ) src
        WHERE link.id = src.azienda_project_link_id
        """
    )
    op.drop_table("project_azienda_delivery_sedi")
