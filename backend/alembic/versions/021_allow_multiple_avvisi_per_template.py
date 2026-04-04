"""Allow many avvisi for one financial template.

Revision ID: 021
Revises: 020
Create Date: 2026-04-03
"""

from alembic import op
import sqlalchemy as sa


revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def _get_indexes(inspector, table_name: str) -> set[str]:
    return {idx["name"] for idx in inspector.get_indexes(table_name)}


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "avvisi" not in inspector.get_table_names():
        return

    indexes = _get_indexes(inspector, "avvisi")
    if "ix_avvisi_template_id_unique" in indexes:
        op.drop_index("ix_avvisi_template_id_unique", table_name="avvisi")

    indexes = _get_indexes(inspector, "avvisi")
    if "ix_avvisi_template_id" not in indexes:
        op.create_index("ix_avvisi_template_id", "avvisi", ["template_id"], unique=False)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "avvisi" not in inspector.get_table_names():
        return

    indexes = _get_indexes(inspector, "avvisi")
    if "ix_avvisi_template_id" in indexes:
        op.drop_index("ix_avvisi_template_id", table_name="avvisi")

    indexes = _get_indexes(inspector, "avvisi")
    if "ix_avvisi_template_id_unique" not in indexes:
        op.create_index("ix_avvisi_template_id_unique", "avvisi", ["template_id"], unique=True)
