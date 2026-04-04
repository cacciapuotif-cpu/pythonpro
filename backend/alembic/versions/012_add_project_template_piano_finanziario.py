"""add project template piano finanziario

Revision ID: 012
Revises: 011
Create Date: 2026-04-02
"""

from alembic import op
import sqlalchemy as sa


revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("template_piano_finanziario_id", sa.Integer(), nullable=True))
    op.create_index("ix_projects_template_piano_finanziario_id", "projects", ["template_piano_finanziario_id"], unique=False)
    op.create_foreign_key(
        "fk_projects_template_piano_finanziario_id_contract_templates",
        "projects",
        "contract_templates",
        ["template_piano_finanziario_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_projects_template_piano_finanziario_id_contract_templates", "projects", type_="foreignkey")
    op.drop_index("ix_projects_template_piano_finanziario_id", table_name="projects")
    op.drop_column("projects", "template_piano_finanziario_id")
