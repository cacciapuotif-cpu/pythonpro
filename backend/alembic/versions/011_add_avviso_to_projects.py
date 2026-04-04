"""add avviso to projects

Revision ID: 011
Revises: 010
Create Date: 2026-04-02
"""

from alembic import op
import sqlalchemy as sa


revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("avviso", sa.String(length=100), nullable=True))
    op.create_index("ix_projects_avviso", "projects", ["avviso"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_projects_avviso", table_name="projects")
    op.drop_column("projects", "avviso")
