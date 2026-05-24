"""add document counters and agent metadata column

Revision ID: 031
Revises: 030
Create Date: 2026-04-20
"""

from alembic import op
import sqlalchemy as sa


revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None


def _table_exists(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _column_names(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "document_counters"):
        op.create_table(
            "document_counters",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("document_type", sa.String(length=20), nullable=False),
            sa.Column("anno", sa.Integer(), nullable=False),
            sa.Column("last_number", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("document_type", "anno", name="uq_document_counter_type_anno"),
        )

    inspector = sa.inspect(bind)
    if "idx_document_counter_type_anno" not in _index_names(inspector, "document_counters"):
        op.create_index(
            "idx_document_counter_type_anno",
            "document_counters",
            ["document_type", "anno"],
            unique=True,
        )

    if _table_exists(inspector, "agent_runs"):
        columns = _column_names(inspector, "agent_runs")
        if "agent_metadata" not in columns:
            if "metadata" in columns:
                renamed = False
                try:
                    with op.batch_alter_table("agent_runs") as batch_op:
                        batch_op.alter_column(
                            "metadata",
                            existing_type=sa.Text(),
                            new_column_name="agent_metadata",
                        )
                    renamed = True
                except Exception:
                    renamed = False

                if not renamed:
                    op.add_column("agent_runs", sa.Column("agent_metadata", sa.Text(), nullable=True))
                    op.execute(
                        sa.text(
                            "UPDATE agent_runs "
                            "SET agent_metadata = metadata "
                            "WHERE agent_metadata IS NULL AND metadata IS NOT NULL"
                        )
                    )
            else:
                op.add_column("agent_runs", sa.Column("agent_metadata", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "agent_runs"):
        columns = _column_names(inspector, "agent_runs")
        if "agent_metadata" in columns and "metadata" not in columns:
            renamed = False
            try:
                with op.batch_alter_table("agent_runs") as batch_op:
                    batch_op.alter_column(
                        "agent_metadata",
                        existing_type=sa.Text(),
                        new_column_name="metadata",
                    )
                renamed = True
            except Exception:
                renamed = False

            if not renamed:
                op.add_column("agent_runs", sa.Column("metadata", sa.Text(), nullable=True))
                op.execute(
                    sa.text(
                        "UPDATE agent_runs "
                        "SET metadata = agent_metadata "
                        "WHERE metadata IS NULL AND agent_metadata IS NOT NULL"
                    )
                )

    if _table_exists(inspector, "document_counters"):
        if "idx_document_counter_type_anno" in _index_names(inspector, "document_counters"):
            op.drop_index("idx_document_counter_type_anno", table_name="document_counters")
        op.drop_table("document_counters")
