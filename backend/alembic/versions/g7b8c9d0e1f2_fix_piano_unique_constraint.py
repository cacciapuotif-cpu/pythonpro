"""fix piano finanziario unique constraint

Revision ID: g7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-04-07 11:05:00.000000+00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "g7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def _unique_constraint_names(inspector, table_name: str) -> set[str]:
    return {constraint["name"] for constraint in inspector.get_unique_constraints(table_name) if constraint.get("name")}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    unique_constraints = _unique_constraint_names(inspector, "piani_finanziari")

    legacy_constraint = "uq_piani_finanziari_progetto_id_anno_ente_erogatore_avviso"
    if legacy_constraint in unique_constraints:
        op.drop_constraint(legacy_constraint, "piani_finanziari", type_="unique")

    op.execute("DROP INDEX IF EXISTS idx_unique_piano_progetto_anno_ente_avviso")
    op.execute("DROP INDEX IF EXISTS idx_unique_piano_progetto_anno_ente_avviso_id")

    unique_constraints = _unique_constraint_names(inspector, "piani_finanziari")
    if "uq_piano_progetto_anno_avviso" not in unique_constraints:
        op.create_unique_constraint(
            "uq_piano_progetto_anno_avviso",
            "piani_finanziari",
            ["progetto_id", "anno", "avviso_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    unique_constraints = _unique_constraint_names(inspector, "piani_finanziari")

    if "uq_piano_progetto_anno_avviso" in unique_constraints:
        op.drop_constraint("uq_piano_progetto_anno_avviso", "piani_finanziari", type_="unique")

    op.create_index(
        "idx_unique_piano_progetto_anno_ente_avviso",
        "piani_finanziari",
        ["progetto_id", "anno", "ente_erogatore", "avviso"],
        unique=True,
    )
