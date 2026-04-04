"""Add core tables for agent runs, suggestions and review actions.

Revision ID: 027
Revises: 026
Create Date: 2026-04-04
"""

from alembic import op
import sqlalchemy as sa


revision = "027"
down_revision = "026"
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

    if not _has_table(inspector, "agent_runs"):
        op.create_table(
            "agent_runs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("agent_name", sa.String(length=100), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False),
            sa.Column("entity_type", sa.String(length=50), nullable=True),
            sa.Column("entity_id", sa.Integer(), nullable=True),
            sa.Column("requested_by_user_id", sa.Integer(), nullable=True),
            sa.Column("input_payload", sa.Text(), nullable=True),
            sa.Column("result_summary", sa.Text(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("suggestions_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        )

    if not _has_table(inspector, "agent_suggestions"):
        op.create_table(
            "agent_suggestions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("run_id", sa.Integer(), sa.ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("agent_name", sa.String(length=100), nullable=False),
            sa.Column("entity_type", sa.String(length=50), nullable=False),
            sa.Column("entity_id", sa.Integer(), nullable=True),
            sa.Column("suggestion_type", sa.String(length=100), nullable=False),
            sa.Column("severity", sa.String(length=20), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("payload", sa.Text(), nullable=True),
            sa.Column("confidence", sa.Float(), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    if not _has_table(inspector, "agent_review_actions"):
        op.create_table(
            "agent_review_actions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("suggestion_id", sa.Integer(), sa.ForeignKey("agent_suggestions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("action", sa.String(length=20), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    for table_name, index_name, columns in [
        ("agent_runs", "ix_agent_runs_agent_name", ["agent_name"]),
        ("agent_runs", "ix_agent_runs_status", ["status"]),
        ("agent_runs", "ix_agent_runs_entity_type", ["entity_type"]),
        ("agent_runs", "ix_agent_runs_entity_id", ["entity_id"]),
        ("agent_runs", "ix_agent_runs_requested_by_user_id", ["requested_by_user_id"]),
        ("agent_runs", "ix_agent_runs_started_at", ["started_at"]),
        ("agent_runs", "ix_agent_runs_completed_at", ["completed_at"]),
        ("agent_suggestions", "ix_agent_suggestions_run_id", ["run_id"]),
        ("agent_suggestions", "ix_agent_suggestions_agent_name", ["agent_name"]),
        ("agent_suggestions", "ix_agent_suggestions_entity_type", ["entity_type"]),
        ("agent_suggestions", "ix_agent_suggestions_entity_id", ["entity_id"]),
        ("agent_suggestions", "ix_agent_suggestions_suggestion_type", ["suggestion_type"]),
        ("agent_suggestions", "ix_agent_suggestions_severity", ["severity"]),
        ("agent_suggestions", "ix_agent_suggestions_status", ["status"]),
        ("agent_suggestions", "ix_agent_suggestions_reviewed_at", ["reviewed_at"]),
        ("agent_suggestions", "ix_agent_suggestions_reviewed_by_user_id", ["reviewed_by_user_id"]),
        ("agent_suggestions", "ix_agent_suggestions_created_at", ["created_at"]),
        ("agent_review_actions", "ix_agent_review_actions_suggestion_id", ["suggestion_id"]),
        ("agent_review_actions", "ix_agent_review_actions_action", ["action"]),
        ("agent_review_actions", "ix_agent_review_actions_reviewed_by_user_id", ["reviewed_by_user_id"]),
        ("agent_review_actions", "ix_agent_review_actions_created_at", ["created_at"]),
    ]:
        _create_index_if_missing(table_name, index_name, columns)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "agent_review_actions"):
        for index_name in [
            "ix_agent_review_actions_created_at",
            "ix_agent_review_actions_reviewed_by_user_id",
            "ix_agent_review_actions_action",
            "ix_agent_review_actions_suggestion_id",
        ]:
            op.drop_index(index_name, table_name="agent_review_actions")
        op.drop_table("agent_review_actions")

    if _has_table(inspector, "agent_suggestions"):
        for index_name in [
            "ix_agent_suggestions_created_at",
            "ix_agent_suggestions_reviewed_by_user_id",
            "ix_agent_suggestions_reviewed_at",
            "ix_agent_suggestions_status",
            "ix_agent_suggestions_severity",
            "ix_agent_suggestions_suggestion_type",
            "ix_agent_suggestions_entity_id",
            "ix_agent_suggestions_entity_type",
            "ix_agent_suggestions_agent_name",
            "ix_agent_suggestions_run_id",
        ]:
            op.drop_index(index_name, table_name="agent_suggestions")
        op.drop_table("agent_suggestions")

    if _has_table(inspector, "agent_runs"):
        for index_name in [
            "ix_agent_runs_completed_at",
            "ix_agent_runs_started_at",
            "ix_agent_runs_requested_by_user_id",
            "ix_agent_runs_entity_id",
            "ix_agent_runs_entity_type",
            "ix_agent_runs_status",
            "ix_agent_runs_agent_name",
        ]:
            op.drop_index(index_name, table_name="agent_runs")
        op.drop_table("agent_runs")
