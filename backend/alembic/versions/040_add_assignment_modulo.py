"""add assignment modulo fields

Revision ID: 040
Revises: 039
Create Date: 2026-04-22
"""

from alembic import op
import sqlalchemy as sa


revision = "040"
down_revision = "039"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _has_constraint(inspector, table_name: str, constraint_name: str) -> bool:
    return constraint_name in {constraint["name"] for constraint in inspector.get_foreign_keys(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_column(inspector, "assignments", "modulo_formativo_id"):
        op.add_column("assignments", sa.Column("modulo_formativo_id", sa.Integer(), nullable=True))
    if not _has_column(inspector, "assignments", "materia"):
        op.add_column("assignments", sa.Column("materia", sa.String(length=200), nullable=True))
    if not _has_column(inspector, "assignments", "modalita_erogazione"):
        op.add_column("assignments", sa.Column("modalita_erogazione", sa.String(length=30), nullable=True))

    op.create_index("ix_assignments_modulo_formativo_id", "assignments", ["modulo_formativo_id"], unique=False, if_not_exists=True)
    op.create_index("ix_assignments_modalita_erogazione", "assignments", ["modalita_erogazione"], unique=False, if_not_exists=True)

    inspector = sa.inspect(bind)
    if not _has_constraint(inspector, "assignments", "fk_assignments_modulo_formativo_id"):
        op.create_foreign_key(
            "fk_assignments_modulo_formativo_id",
            "assignments",
            "moduli_formativi",
            ["modulo_formativo_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_constraint(inspector, "assignments", "fk_assignments_modulo_formativo_id"):
        op.drop_constraint("fk_assignments_modulo_formativo_id", "assignments", type_="foreignkey")
    op.drop_index("ix_assignments_modalita_erogazione", table_name="assignments", if_exists=True)
    op.drop_index("ix_assignments_modulo_formativo_id", table_name="assignments", if_exists=True)

    inspector = sa.inspect(bind)
    for column_name in ("modalita_erogazione", "materia", "modulo_formativo_id"):
        if _has_column(inspector, "assignments", column_name):
            op.drop_column("assignments", column_name)
