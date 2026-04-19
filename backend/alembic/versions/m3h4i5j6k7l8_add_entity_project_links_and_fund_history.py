"""add entity project links and fund history

Revision ID: m3h4i5j6k7l8
Revises: l2g3h4i5j6k7
Create Date: 2026-04-07 16:20:00.000000+00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "m3h4i5j6k7l8"
down_revision = "l2g3h4i5j6k7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "implementing_entity_projects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["entity_id"], ["implementing_entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entity_id", "project_id", name="uq_implementing_entity_project"),
    )
    op.create_index(op.f("ix_implementing_entity_projects_id"), "implementing_entity_projects", ["id"], unique=False)
    op.create_index(op.f("ix_implementing_entity_projects_entity_id"), "implementing_entity_projects", ["entity_id"], unique=False)
    op.create_index(op.f("ix_implementing_entity_projects_project_id"), "implementing_entity_projects", ["project_id"], unique=False)
    op.create_index(op.f("ix_implementing_entity_projects_created_at"), "implementing_entity_projects", ["created_at"], unique=False)

    op.create_table(
        "implementing_entity_fund_memberships",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("fondo", sa.String(length=100), nullable=False),
        sa.Column("data_inizio", sa.DateTime(), nullable=False),
        sa.Column("data_fine", sa.DateTime(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["entity_id"], ["implementing_entities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_implementing_entity_fund_memberships_id"), "implementing_entity_fund_memberships", ["id"], unique=False)
    op.create_index(op.f("ix_implementing_entity_fund_memberships_entity_id"), "implementing_entity_fund_memberships", ["entity_id"], unique=False)
    op.create_index(op.f("ix_implementing_entity_fund_memberships_fondo"), "implementing_entity_fund_memberships", ["fondo"], unique=False)
    op.create_index(op.f("ix_implementing_entity_fund_memberships_data_inizio"), "implementing_entity_fund_memberships", ["data_inizio"], unique=False)
    op.create_index(op.f("ix_implementing_entity_fund_memberships_data_fine"), "implementing_entity_fund_memberships", ["data_fine"], unique=False)
    op.create_index(op.f("ix_implementing_entity_fund_memberships_created_at"), "implementing_entity_fund_memberships", ["created_at"], unique=False)
    op.create_index("idx_entity_fund_period", "implementing_entity_fund_memberships", ["entity_id", "data_inizio", "data_fine"], unique=False)

    op.execute(
        """
        INSERT INTO implementing_entity_projects (entity_id, project_id)
        SELECT DISTINCT ente_attuatore_id, id
        FROM projects
        WHERE ente_attuatore_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index("idx_entity_fund_period", table_name="implementing_entity_fund_memberships")
    op.drop_index(op.f("ix_implementing_entity_fund_memberships_created_at"), table_name="implementing_entity_fund_memberships")
    op.drop_index(op.f("ix_implementing_entity_fund_memberships_data_fine"), table_name="implementing_entity_fund_memberships")
    op.drop_index(op.f("ix_implementing_entity_fund_memberships_data_inizio"), table_name="implementing_entity_fund_memberships")
    op.drop_index(op.f("ix_implementing_entity_fund_memberships_fondo"), table_name="implementing_entity_fund_memberships")
    op.drop_index(op.f("ix_implementing_entity_fund_memberships_entity_id"), table_name="implementing_entity_fund_memberships")
    op.drop_index(op.f("ix_implementing_entity_fund_memberships_id"), table_name="implementing_entity_fund_memberships")
    op.drop_table("implementing_entity_fund_memberships")

    op.drop_index(op.f("ix_implementing_entity_projects_created_at"), table_name="implementing_entity_projects")
    op.drop_index(op.f("ix_implementing_entity_projects_project_id"), table_name="implementing_entity_projects")
    op.drop_index(op.f("ix_implementing_entity_projects_entity_id"), table_name="implementing_entity_projects")
    op.drop_index(op.f("ix_implementing_entity_projects_id"), table_name="implementing_entity_projects")
    op.drop_table("implementing_entity_projects")
