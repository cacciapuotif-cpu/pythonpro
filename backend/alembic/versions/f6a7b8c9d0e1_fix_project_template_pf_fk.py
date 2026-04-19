"""fix project template piano finanziario foreign key

Revision ID: f6a7b8c9d0e1
Revises: e4f5a6b7c8d9
Create Date: 2026-04-07 10:50:00.000000+00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "f6a7b8c9d0e1"
down_revision = "e4f5a6b7c8d9"
branch_labels = None
depends_on = None


def _foreign_key_names(inspector, table_name: str) -> set[str]:
    return {fk["name"] for fk in inspector.get_foreign_keys(table_name) if fk.get("name")}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    fk_names = _foreign_key_names(inspector, "projects")

    legacy_fk = "fk_projects_template_piano_finanziario_id_contract_templates"
    if legacy_fk in fk_names:
        op.drop_constraint(legacy_fk, "projects", type_="foreignkey")

    replacement_fk = "projects_template_piano_finanziario_id_fkey"
    if replacement_fk in fk_names:
        op.drop_constraint(replacement_fk, "projects", type_="foreignkey")

    op.execute(
        """
        UPDATE projects
        SET template_piano_finanziario_id = NULL
        WHERE template_piano_finanziario_id IS NOT NULL
          AND template_piano_finanziario_id NOT IN (
              SELECT id FROM template_piani_finanziari
          )
        """
    )

    op.create_foreign_key(
        replacement_fk,
        "projects",
        "template_piani_finanziari",
        ["template_piano_finanziario_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    fk_names = _foreign_key_names(inspector, "projects")

    replacement_fk = "projects_template_piano_finanziario_id_fkey"
    if replacement_fk in fk_names:
        op.drop_constraint(replacement_fk, "projects", type_="foreignkey")

    op.create_foreign_key(
        "fk_projects_template_piano_finanziario_id_contract_templates",
        "projects",
        "contract_templates",
        ["template_piano_finanziario_id"],
        ["id"],
        ondelete="SET NULL",
    )
