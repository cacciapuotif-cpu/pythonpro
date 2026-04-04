"""Add avvisi table and FK columns on projects/piani.

Revision ID: 019
Revises: 018
Create Date: 2026-04-03
"""

from alembic import op
import sqlalchemy as sa


revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def _get_columns(inspector, table_name: str) -> set[str]:
    return {col["name"] for col in inspector.get_columns(table_name)}


def _get_indexes(inspector, table_name: str) -> set[str]:
    return {idx["name"] for idx in inspector.get_indexes(table_name)}


def _get_fks(inspector, table_name: str) -> set[str]:
    return {fk["name"] for fk in inspector.get_foreign_keys(table_name) if fk.get("name")}


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "avvisi" not in inspector.get_table_names():
        op.create_table(
            "avvisi",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("codice", sa.String(length=50), nullable=False),
            sa.Column("ente_erogatore", sa.String(length=100), nullable=False),
            sa.Column("descrizione", sa.String(length=200), nullable=True),
            sa.Column("template_id", sa.Integer(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["template_id"], ["contract_templates.id"], ondelete="SET NULL"),
        )

    indexes = _get_indexes(inspector, "avvisi") if "avvisi" in inspector.get_table_names() else set()
    if "idx_unique_avvisi_codice_ente" not in indexes:
        op.create_index("idx_unique_avvisi_codice_ente", "avvisi", ["codice", "ente_erogatore"], unique=True)

    indexes = _get_indexes(inspector, "avvisi") if "avvisi" in inspector.get_table_names() else set()
    if "ix_avvisi_template_id_unique" not in indexes:
        op.create_index("ix_avvisi_template_id_unique", "avvisi", ["template_id"], unique=True)

    for table_name in ["projects", "piani_finanziari", "piani_finanziari_fondimpresa"]:
        columns = _get_columns(inspector, table_name)
        if "avviso_id" not in columns:
            op.add_column(table_name, sa.Column("avviso_id", sa.Integer(), nullable=True))

        fks = _get_fks(inspector, table_name)
        fk_name = f"fk_{table_name}_avviso_id"
        if fk_name not in fks:
            op.create_foreign_key(fk_name, table_name, "avvisi", ["avviso_id"], ["id"], ondelete="SET NULL")

        indexes = _get_indexes(inspector, table_name)
        idx_name = f"ix_{table_name}_avviso_id"
        if idx_name not in indexes:
            op.create_index(idx_name, table_name, ["avviso_id"], unique=False)


def downgrade():
    for table_name in ["projects", "piani_finanziari", "piani_finanziari_fondimpresa"]:
        op.drop_index(f"ix_{table_name}_avviso_id", table_name=table_name)
        op.drop_constraint(f"fk_{table_name}_avviso_id", table_name, type_="foreignkey")
        op.drop_column(table_name, "avviso_id")

    op.drop_index("ix_avvisi_template_id_unique", table_name="avvisi")
    op.drop_index("idx_unique_avvisi_codice_ente", table_name="avvisi")
    op.drop_table("avvisi")
