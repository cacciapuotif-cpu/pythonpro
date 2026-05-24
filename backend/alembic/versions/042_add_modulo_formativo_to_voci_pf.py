"""add modulo formativo to voci piano finanziario

Revision ID: 042
Revises: 041
Create Date: 2026-04-23
"""

from alembic import op
import sqlalchemy as sa


revision = "042"
down_revision = "041"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return column_name in {col["name"] for col in inspector.get_columns(table_name)}


def _has_constraint(inspector, table_name: str, constraint_name: str) -> bool:
    return constraint_name in {fk["name"] for fk in inspector.get_foreign_keys(table_name)}


def _has_index(inspector, table_name: str, index_name: str) -> bool:
    return index_name in {idx["name"] for idx in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_column(inspector, "voci_piano_finanziario", "modulo_formativo_id"):
        op.add_column("voci_piano_finanziario", sa.Column("modulo_formativo_id", sa.Integer(), nullable=True))

    inspector = sa.inspect(bind)
    if not _has_index(inspector, "voci_piano_finanziario", "idx_voci_piano_modulo"):
        op.create_index("idx_voci_piano_modulo", "voci_piano_finanziario", ["modulo_formativo_id"])

    if not _has_constraint(inspector, "voci_piano_finanziario", "fk_voci_piano_modulo_formativo_id"):
        op.create_foreign_key(
            "fk_voci_piano_modulo_formativo_id",
            "voci_piano_finanziario",
            "moduli_formativi",
            ["modulo_formativo_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_constraint(inspector, "voci_piano_finanziario", "fk_voci_piano_modulo_formativo_id"):
        op.drop_constraint("fk_voci_piano_modulo_formativo_id", "voci_piano_finanziario", type_="foreignkey")
    if _has_index(inspector, "voci_piano_finanziario", "idx_voci_piano_modulo"):
        op.drop_index("idx_voci_piano_modulo", table_name="voci_piano_finanziario")
    if _has_column(inspector, "voci_piano_finanziario", "modulo_formativo_id"):
        op.drop_column("voci_piano_finanziario", "modulo_formativo_id")
