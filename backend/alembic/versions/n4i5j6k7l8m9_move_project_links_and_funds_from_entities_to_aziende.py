"""move project links and funds from entities to aziende

Revision ID: n4i5j6k7l8m9
Revises: m3h4i5j6k7l8
Create Date: 2026-04-07 16:55:00.000000+00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "n4i5j6k7l8m9"
down_revision = "m3h4i5j6k7l8"
branch_labels = None
depends_on = None


def _table_exists(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "azienda_cliente_projects"):
        op.create_table(
            "azienda_cliente_projects",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("azienda_cliente_id", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
            sa.ForeignKeyConstraint(["azienda_cliente_id"], ["aziende_clienti.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("azienda_cliente_id", "project_id", name="uq_azienda_cliente_project"),
        )
        op.create_index(op.f("ix_azienda_cliente_projects_id"), "azienda_cliente_projects", ["id"], unique=False)
        op.create_index(op.f("ix_azienda_cliente_projects_azienda_cliente_id"), "azienda_cliente_projects", ["azienda_cliente_id"], unique=False)
        op.create_index(op.f("ix_azienda_cliente_projects_project_id"), "azienda_cliente_projects", ["project_id"], unique=False)
        op.create_index(op.f("ix_azienda_cliente_projects_created_at"), "azienda_cliente_projects", ["created_at"], unique=False)

    if not _table_exists(inspector, "azienda_cliente_fund_memberships"):
        op.create_table(
            "azienda_cliente_fund_memberships",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("azienda_cliente_id", sa.Integer(), nullable=False),
            sa.Column("fondo", sa.String(length=100), nullable=False),
            sa.Column("data_inizio", sa.DateTime(), nullable=False),
            sa.Column("data_fine", sa.DateTime(), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["azienda_cliente_id"], ["aziende_clienti.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_azienda_cliente_fund_memberships_id"), "azienda_cliente_fund_memberships", ["id"], unique=False)
        op.create_index(op.f("ix_azienda_cliente_fund_memberships_azienda_cliente_id"), "azienda_cliente_fund_memberships", ["azienda_cliente_id"], unique=False)
        op.create_index(op.f("ix_azienda_cliente_fund_memberships_fondo"), "azienda_cliente_fund_memberships", ["fondo"], unique=False)
        op.create_index(op.f("ix_azienda_cliente_fund_memberships_data_inizio"), "azienda_cliente_fund_memberships", ["data_inizio"], unique=False)
        op.create_index(op.f("ix_azienda_cliente_fund_memberships_data_fine"), "azienda_cliente_fund_memberships", ["data_fine"], unique=False)
        op.create_index(op.f("ix_azienda_cliente_fund_memberships_created_at"), "azienda_cliente_fund_memberships", ["created_at"], unique=False)
        op.create_index("idx_azienda_fund_period", "azienda_cliente_fund_memberships", ["azienda_cliente_id", "data_inizio", "data_fine"], unique=False)

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "implementing_entity_fund_memberships"):
        op.drop_index("idx_entity_fund_period", table_name="implementing_entity_fund_memberships")
        op.drop_index(op.f("ix_implementing_entity_fund_memberships_created_at"), table_name="implementing_entity_fund_memberships")
        op.drop_index(op.f("ix_implementing_entity_fund_memberships_data_fine"), table_name="implementing_entity_fund_memberships")
        op.drop_index(op.f("ix_implementing_entity_fund_memberships_data_inizio"), table_name="implementing_entity_fund_memberships")
        op.drop_index(op.f("ix_implementing_entity_fund_memberships_fondo"), table_name="implementing_entity_fund_memberships")
        op.drop_index(op.f("ix_implementing_entity_fund_memberships_entity_id"), table_name="implementing_entity_fund_memberships")
        op.drop_index(op.f("ix_implementing_entity_fund_memberships_id"), table_name="implementing_entity_fund_memberships")
        op.drop_table("implementing_entity_fund_memberships")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "implementing_entity_projects"):
        op.drop_index(op.f("ix_implementing_entity_projects_created_at"), table_name="implementing_entity_projects")
        op.drop_index(op.f("ix_implementing_entity_projects_project_id"), table_name="implementing_entity_projects")
        op.drop_index(op.f("ix_implementing_entity_projects_entity_id"), table_name="implementing_entity_projects")
        op.drop_index(op.f("ix_implementing_entity_projects_id"), table_name="implementing_entity_projects")
        op.drop_table("implementing_entity_projects")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "azienda_cliente_fund_memberships"):
        op.drop_index("idx_azienda_fund_period", table_name="azienda_cliente_fund_memberships")
        op.drop_index(op.f("ix_azienda_cliente_fund_memberships_created_at"), table_name="azienda_cliente_fund_memberships")
        op.drop_index(op.f("ix_azienda_cliente_fund_memberships_data_fine"), table_name="azienda_cliente_fund_memberships")
        op.drop_index(op.f("ix_azienda_cliente_fund_memberships_data_inizio"), table_name="azienda_cliente_fund_memberships")
        op.drop_index(op.f("ix_azienda_cliente_fund_memberships_fondo"), table_name="azienda_cliente_fund_memberships")
        op.drop_index(op.f("ix_azienda_cliente_fund_memberships_azienda_cliente_id"), table_name="azienda_cliente_fund_memberships")
        op.drop_index(op.f("ix_azienda_cliente_fund_memberships_id"), table_name="azienda_cliente_fund_memberships")
        op.drop_table("azienda_cliente_fund_memberships")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "azienda_cliente_projects"):
        op.drop_index(op.f("ix_azienda_cliente_projects_created_at"), table_name="azienda_cliente_projects")
        op.drop_index(op.f("ix_azienda_cliente_projects_project_id"), table_name="azienda_cliente_projects")
        op.drop_index(op.f("ix_azienda_cliente_projects_azienda_cliente_id"), table_name="azienda_cliente_projects")
        op.drop_index(op.f("ix_azienda_cliente_projects_id"), table_name="azienda_cliente_projects")
        op.drop_table("azienda_cliente_projects")
