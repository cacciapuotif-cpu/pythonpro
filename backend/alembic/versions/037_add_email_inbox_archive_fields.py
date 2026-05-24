"""add email inbox archive fields

Revision ID: 037
Revises: 036
Create Date: 2026-04-21
"""

from alembic import op
import sqlalchemy as sa


revision = "037"
down_revision = "036"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_column(inspector, "email_inbox_items", "archived"):
        op.add_column(
            "email_inbox_items",
            sa.Column("archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        )
    if not _has_column(inspector, "email_inbox_items", "archived_at"):
        op.add_column("email_inbox_items", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))

    op.create_index("ix_email_inbox_items_archived", "email_inbox_items", ["archived"], unique=False, if_not_exists=True)


def downgrade() -> None:
    op.drop_index("ix_email_inbox_items_archived", table_name="email_inbox_items", if_exists=True)
    op.drop_column("email_inbox_items", "archived_at")
    op.drop_column("email_inbox_items", "archived")
