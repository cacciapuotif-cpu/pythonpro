"""Add agent communication drafts table.

Revision ID: 028
Revises: 027
Create Date: 2026-04-04
"""

from alembic import op
import sqlalchemy as sa


revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def _has_table(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _create_index_if_missing(table_name: str, index_name: str, columns: list[str]) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {index["name"] for index in inspector.get_indexes(table_name)}
    if index_name not in existing:
        op.create_index(index_name, table_name, columns, unique=False)


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, "agent_communication_drafts"):
        op.create_table(
            "agent_communication_drafts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("run_id", sa.Integer(), sa.ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True),
            sa.Column("suggestion_id", sa.Integer(), sa.ForeignKey("agent_suggestions.id", ondelete="SET NULL"), nullable=True),
            sa.Column("agent_name", sa.String(length=100), nullable=False),
            sa.Column("channel", sa.String(length=20), nullable=False, server_default="email"),
            sa.Column("recipient_type", sa.String(length=50), nullable=False),
            sa.Column("recipient_id", sa.Integer(), nullable=True),
            sa.Column("recipient_email", sa.String(length=150), nullable=False),
            sa.Column("recipient_name", sa.String(length=200), nullable=True),
            sa.Column("subject", sa.String(length=255), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
            sa.Column("meta_payload", sa.Text(), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), nullable=True),
            sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )

    for table_name, index_name, columns in [
        ("agent_communication_drafts", "ix_agent_communication_drafts_run_id", ["run_id"]),
        ("agent_communication_drafts", "ix_agent_communication_drafts_suggestion_id", ["suggestion_id"]),
        ("agent_communication_drafts", "ix_agent_communication_drafts_agent_name", ["agent_name"]),
        ("agent_communication_drafts", "ix_agent_communication_drafts_channel", ["channel"]),
        ("agent_communication_drafts", "ix_agent_communication_drafts_recipient_type", ["recipient_type"]),
        ("agent_communication_drafts", "ix_agent_communication_drafts_recipient_id", ["recipient_id"]),
        ("agent_communication_drafts", "ix_agent_communication_drafts_recipient_email", ["recipient_email"]),
        ("agent_communication_drafts", "ix_agent_communication_drafts_status", ["status"]),
        ("agent_communication_drafts", "ix_agent_communication_drafts_created_by_user_id", ["created_by_user_id"]),
        ("agent_communication_drafts", "ix_agent_communication_drafts_reviewed_by_user_id", ["reviewed_by_user_id"]),
        ("agent_communication_drafts", "ix_agent_communication_drafts_sent_at", ["sent_at"]),
        ("agent_communication_drafts", "ix_agent_communication_drafts_created_at", ["created_at"]),
    ]:
        _create_index_if_missing(table_name, index_name, columns)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _has_table(inspector, "agent_communication_drafts"):
        for index_name in [
            "ix_agent_communication_drafts_created_at",
            "ix_agent_communication_drafts_sent_at",
            "ix_agent_communication_drafts_reviewed_by_user_id",
            "ix_agent_communication_drafts_created_by_user_id",
            "ix_agent_communication_drafts_status",
            "ix_agent_communication_drafts_recipient_email",
            "ix_agent_communication_drafts_recipient_id",
            "ix_agent_communication_drafts_recipient_type",
            "ix_agent_communication_drafts_channel",
            "ix_agent_communication_drafts_agent_name",
            "ix_agent_communication_drafts_suggestion_id",
            "ix_agent_communication_drafts_run_id",
        ]:
            op.drop_index(index_name, table_name="agent_communication_drafts")
        op.drop_table("agent_communication_drafts")
