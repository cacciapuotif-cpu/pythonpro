"""Add email_inbox_items table.

Revision ID: 030
Revises: 029
Create Date: 2026-04-10
"""

from alembic import op
import sqlalchemy as sa


revision = "030"
down_revision = "p6k7l8m9n0o1"
branch_labels = None
depends_on = None


def _has_table(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _create_index_if_missing(table_name: str, index_name: str, columns: list) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {index["name"] for index in inspector.get_indexes(table_name)}
    if index_name not in existing:
        op.create_index(index_name, table_name, columns, unique=False)


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, "email_inbox_items"):
        op.create_table(
            "email_inbox_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("message_id", sa.String(length=500), nullable=False, unique=True),
            sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("sender_email", sa.String(length=255), nullable=False),
            sa.Column("subject", sa.String(length=500), nullable=True),
            sa.Column("entity_type", sa.String(length=50), nullable=True),
            sa.Column("entity_id", sa.Integer(), nullable=True),
            sa.Column("attachment_path", sa.String(length=1000), nullable=True),
            sa.Column("attachment_name", sa.String(length=255), nullable=True),
            sa.Column("processing_status", sa.String(length=50), nullable=False),
            sa.Column("llm_result", sa.Text(), nullable=True),
            sa.Column("reply_sent", sa.Boolean(), server_default="false", nullable=False),
            sa.Column("reply_sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    for table_name, index_name, columns in [
        ("email_inbox_items", "ix_email_inbox_items_message_id", ["message_id"]),
        ("email_inbox_items", "ix_email_inbox_items_entity", ["entity_type", "entity_id"]),
        ("email_inbox_items", "ix_email_inbox_items_status", ["processing_status"]),
        ("email_inbox_items", "ix_email_inbox_items_sender", ["sender_email"]),
    ]:
        _create_index_if_missing(table_name, index_name, columns)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _has_table(inspector, "email_inbox_items"):
        for index_name in [
            "ix_email_inbox_items_sender",
            "ix_email_inbox_items_status",
            "ix_email_inbox_items_entity",
            "ix_email_inbox_items_message_id",
        ]:
            try:
                op.drop_index(index_name, table_name="email_inbox_items")
            except Exception:
                pass
        op.drop_table("email_inbox_items")
