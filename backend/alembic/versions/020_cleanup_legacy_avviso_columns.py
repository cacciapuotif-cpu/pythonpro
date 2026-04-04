"""Drop legacy avviso string columns after FK migration.

Revision ID: 020
Revises: 019
Create Date: 2026-04-03
"""

from alembic import op
import sqlalchemy as sa


revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def _get_columns(inspector, table_name: str) -> set[str]:
    return {col["name"] for col in inspector.get_columns(table_name)}


def _get_indexes(inspector, table_name: str) -> set[str]:
    return {idx["name"] for idx in inspector.get_indexes(table_name)}


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Update unique index on piani_finanziari: avviso(string) -> avviso_id(FK)
    if "piani_finanziari" in inspector.get_table_names():
        indexes = _get_indexes(inspector, "piani_finanziari")
        if "idx_unique_piano_progetto_anno_ente_avviso" in indexes:
            op.drop_index("idx_unique_piano_progetto_anno_ente_avviso", table_name="piani_finanziari")
        if "idx_unique_piano_progetto_anno_ente_avviso_id" not in indexes:
            op.create_index(
                "idx_unique_piano_progetto_anno_ente_avviso_id",
                "piani_finanziari",
                ["progetto_id", "anno", "ente_erogatore", "avviso_id"],
                unique=True,
            )

    # Drop legacy avviso string columns where present
    for table_name in ["projects", "piani_finanziari", "piani_finanziari_fondimpresa", "contract_templates"]:
        if table_name not in inspector.get_table_names():
            continue
        columns = _get_columns(inspector, table_name)
        if "avviso" in columns:
            op.drop_column(table_name, "avviso")


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Re-add legacy columns
    if "projects" in inspector.get_table_names() and "avviso" not in _get_columns(inspector, "projects"):
        op.add_column("projects", sa.Column("avviso", sa.String(length=100), nullable=True))

    if "piani_finanziari" in inspector.get_table_names() and "avviso" not in _get_columns(inspector, "piani_finanziari"):
        op.add_column("piani_finanziari", sa.Column("avviso", sa.String(length=100), nullable=False, server_default=""))

    if "piani_finanziari_fondimpresa" in inspector.get_table_names() and "avviso" not in _get_columns(inspector, "piani_finanziari_fondimpresa"):
        op.add_column("piani_finanziari_fondimpresa", sa.Column("avviso", sa.String(length=100), nullable=True))

    if "contract_templates" in inspector.get_table_names() and "avviso" not in _get_columns(inspector, "contract_templates"):
        op.add_column("contract_templates", sa.Column("avviso", sa.String(length=100), nullable=True))

    # Restore old unique index
    if "piani_finanziari" in inspector.get_table_names():
        indexes = _get_indexes(inspector, "piani_finanziari")
        if "idx_unique_piano_progetto_anno_ente_avviso_id" in indexes:
            op.drop_index("idx_unique_piano_progetto_anno_ente_avviso_id", table_name="piani_finanziari")
        if "idx_unique_piano_progetto_anno_ente_avviso" not in indexes:
            op.create_index(
                "idx_unique_piano_progetto_anno_ente_avviso",
                "piani_finanziari",
                ["progetto_id", "anno", "ente_erogatore", "avviso"],
                unique=True,
            )
