"""add_agent_tables

Revision ID: a10d08b5e238
Revises: d3de21183882
Create Date: 2026-04-05 08:12:51.187122+00:00

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a10d08b5e238"
down_revision = "d3de21183882"
branch_labels = None
depends_on = None


def _column_names(inspector, table_name):
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector, table_name):
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _has_fk(inspector, table_name, constrained_columns, referred_table):
    target = list(constrained_columns)
    for fk in inspector.get_foreign_keys(table_name):
        if fk.get("referred_table") == referred_table and fk.get("constrained_columns") == target:
            return True
    return False


def _drop_index_if_exists(inspector, table_name, index_name):
    if index_name in _index_names(inspector, table_name):
        op.drop_index(index_name, table_name=table_name)


def _drop_column_if_exists(inspector, table_name, column_name):
    if column_name in _column_names(inspector, table_name):
        op.drop_column(table_name, column_name)


def _ensure_agent_runs(inspector):
    if not inspector.has_table("agent_runs"):
        op.create_table(
            "agent_runs",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("agent_type", sa.String(length=100), nullable=False),
            sa.Column("agent_version", sa.String(length=20), nullable=False, server_default=sa.text("'1.0'")),
            sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'running'")),
            sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("triggered_by", sa.String(length=50), nullable=True),
            sa.Column("trigger_details", sa.Text(), nullable=True),
            sa.Column("items_processed", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("items_with_issues", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("suggestions_created", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("execution_time_ms", sa.Integer(), nullable=True),
            sa.Column("metadata", sa.Text(), nullable=True),
        )
        op.create_index("ix_agent_runs_id", "agent_runs", ["id"], unique=False)
        op.create_index("ix_agent_runs_agent_type", "agent_runs", ["agent_type"], unique=False)
        op.create_index("ix_agent_runs_status", "agent_runs", ["status"], unique=False)
        op.create_index("idx_agent_type_status", "agent_runs", ["agent_type", "status"], unique=False)
        op.create_index("idx_started_at", "agent_runs", ["started_at"], unique=False)
        return

    columns = _column_names(inspector, "agent_runs")
    for name, column in [
        ("agent_type", sa.Column("agent_type", sa.String(length=100), nullable=True)),
        ("agent_version", sa.Column("agent_version", sa.String(length=20), nullable=False, server_default=sa.text("'1.0'"))),
        ("triggered_by", sa.Column("triggered_by", sa.String(length=50), nullable=True)),
        ("trigger_details", sa.Column("trigger_details", sa.Text(), nullable=True)),
        ("items_processed", sa.Column("items_processed", sa.Integer(), nullable=False, server_default=sa.text("0"))),
        ("items_with_issues", sa.Column("items_with_issues", sa.Integer(), nullable=False, server_default=sa.text("0"))),
        ("suggestions_created", sa.Column("suggestions_created", sa.Integer(), nullable=False, server_default=sa.text("0"))),
        ("execution_time_ms", sa.Column("execution_time_ms", sa.Integer(), nullable=True)),
        ("metadata", sa.Column("metadata", sa.Text(), nullable=True)),
    ]:
        if name not in columns:
            op.add_column("agent_runs", column)

    if "agent_name" in columns:
        op.execute("UPDATE agent_runs SET agent_type = COALESCE(agent_type, agent_name, 'unknown')")
    else:
        op.execute("UPDATE agent_runs SET agent_type = COALESCE(agent_type, 'unknown') WHERE agent_type IS NULL")
    if "suggestions_count" in columns:
        op.execute("UPDATE agent_runs SET suggestions_created = COALESCE(suggestions_created, suggestions_count, 0)")
    op.execute("UPDATE agent_runs SET items_processed = COALESCE(items_processed, 0)")
    op.execute("UPDATE agent_runs SET items_with_issues = COALESCE(items_with_issues, 0)")

    op.alter_column("agent_runs", "agent_type", existing_type=sa.String(length=100), nullable=False)
    op.alter_column(
        "agent_runs",
        "agent_version",
        existing_type=sa.String(length=20),
        nullable=False,
        server_default=sa.text("'1.0'"),
    )
    op.alter_column(
        "agent_runs",
        "status",
        existing_type=sa.String(length=30),
        type_=sa.String(length=20),
        nullable=False,
        server_default=sa.text("'running'"),
    )
    op.alter_column(
        "agent_runs",
        "started_at",
        existing_type=sa.DateTime(),
        nullable=False,
        server_default=sa.text("now()"),
    )

    for legacy_column in [
        "agent_name",
        "entity_type",
        "entity_id",
        "requested_by_user_id",
        "input_payload",
        "result_summary",
        "suggestions_count",
    ]:
        _drop_column_if_exists(inspector, "agent_runs", legacy_column)

    for index_name in [
        "ix_agent_runs_agent_name",
        "ix_agent_runs_entity_type",
        "ix_agent_runs_entity_id",
        "ix_agent_runs_requested_by_user_id",
        "ix_agent_runs_completed_at",
    ]:
        _drop_index_if_exists(inspector, "agent_runs", index_name)

    existing_indexes = _index_names(inspector, "agent_runs")
    if "ix_agent_runs_id" not in existing_indexes:
        op.create_index("ix_agent_runs_id", "agent_runs", ["id"], unique=False)
    if "ix_agent_runs_agent_type" not in existing_indexes:
        op.create_index("ix_agent_runs_agent_type", "agent_runs", ["agent_type"], unique=False)
    if "idx_agent_type_status" not in existing_indexes:
        op.create_index("idx_agent_type_status", "agent_runs", ["agent_type", "status"], unique=False)
    if "idx_started_at" not in existing_indexes:
        op.create_index("idx_started_at", "agent_runs", ["started_at"], unique=False)


def _ensure_agent_suggestions(inspector):
    if not inspector.has_table("agent_suggestions"):
        op.create_table(
            "agent_suggestions",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("run_id", sa.Integer(), sa.ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("suggestion_type", sa.String(length=50), nullable=False),
            sa.Column("priority", sa.String(length=20), nullable=False, server_default=sa.text("'medium'")),
            sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'pending'")),
            sa.Column("entity_type", sa.String(length=50), nullable=False),
            sa.Column("entity_id", sa.Integer(), nullable=True),
            sa.Column("title", sa.String(length=300), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("suggested_action", sa.Text(), nullable=True),
            sa.Column("auto_fix_available", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("auto_fix_payload", sa.Text(), nullable=True),
            sa.Column("confidence_score", sa.Float(), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        )
        op.create_index("ix_agent_suggestions_id", "agent_suggestions", ["id"], unique=False)
        op.create_index("ix_agent_suggestions_run_id", "agent_suggestions", ["run_id"], unique=False)
        op.create_index("ix_agent_suggestions_suggestion_type", "agent_suggestions", ["suggestion_type"], unique=False)
        op.create_index("ix_agent_suggestions_status", "agent_suggestions", ["status"], unique=False)
        op.create_index("ix_agent_suggestions_priority", "agent_suggestions", ["priority"], unique=False)
        op.create_index("ix_agent_suggestions_expires_at", "agent_suggestions", ["expires_at"], unique=False)
        op.create_index("ix_agent_suggestions_created_at", "agent_suggestions", ["created_at"], unique=False)
        op.create_index("idx_status_priority", "agent_suggestions", ["status", "priority"], unique=False)
        op.create_index("idx_entity", "agent_suggestions", ["entity_type", "entity_id"], unique=False)
        return

    columns = _column_names(inspector, "agent_suggestions")
    for name, column in [
        ("priority", sa.Column("priority", sa.String(length=20), nullable=False, server_default=sa.text("'medium'"))),
        ("suggested_action", sa.Column("suggested_action", sa.Text(), nullable=True)),
        ("auto_fix_available", sa.Column("auto_fix_available", sa.Boolean(), nullable=False, server_default=sa.text("false"))),
        ("auto_fix_payload", sa.Column("auto_fix_payload", sa.Text(), nullable=True)),
        ("confidence_score", sa.Column("confidence_score", sa.Float(), nullable=True)),
        ("expires_at", sa.Column("expires_at", sa.DateTime(), nullable=True)),
    ]:
        if name not in columns:
            op.add_column("agent_suggestions", column)

    if "severity" in columns:
        op.execute(
            """
            UPDATE agent_suggestions
            SET priority = CASE
                WHEN priority IS NOT NULL THEN priority
                WHEN severity IN ('critical', 'high', 'medium', 'low') THEN severity
                ELSE 'medium'
            END
            """
        )
    else:
        op.execute("UPDATE agent_suggestions SET priority = COALESCE(priority, 'medium') WHERE priority IS NULL")
    if "confidence" in columns:
        op.execute("UPDATE agent_suggestions SET confidence_score = COALESCE(confidence_score, confidence)")

    op.alter_column(
        "agent_suggestions",
        "suggestion_type",
        existing_type=sa.String(length=100),
        type_=sa.String(length=50),
        nullable=False,
    )
    op.alter_column(
        "agent_suggestions",
        "priority",
        existing_type=sa.String(length=20),
        nullable=False,
        server_default=sa.text("'medium'"),
    )
    op.alter_column(
        "agent_suggestions",
        "status",
        existing_type=sa.String(length=20),
        nullable=False,
        server_default=sa.text("'pending'"),
    )
    op.alter_column(
        "agent_suggestions",
        "title",
        existing_type=sa.String(length=200),
        type_=sa.String(length=300),
        nullable=False,
    )
    op.alter_column("agent_suggestions", "description", existing_type=sa.Text(), nullable=True)
    op.alter_column(
        "agent_suggestions",
        "auto_fix_available",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.text("false"),
    )
    op.alter_column(
        "agent_suggestions",
        "created_at",
        existing_type=sa.DateTime(),
        nullable=False,
        server_default=sa.text("now()"),
    )

    for legacy_column in [
        "agent_name",
        "severity",
        "payload",
        "confidence",
        "reviewed_at",
        "reviewed_by_user_id",
    ]:
        _drop_column_if_exists(inspector, "agent_suggestions", legacy_column)

    existing_indexes = _index_names(inspector, "agent_suggestions")
    for index_name in [
        "ix_agent_suggestions_agent_name",
        "ix_agent_suggestions_severity",
        "ix_agent_suggestions_reviewed_at",
        "ix_agent_suggestions_reviewed_by_user_id",
    ]:
        if index_name in existing_indexes:
            op.drop_index(index_name, table_name="agent_suggestions")

    if "ix_agent_suggestions_id" not in existing_indexes:
        op.create_index("ix_agent_suggestions_id", "agent_suggestions", ["id"], unique=False)
    if "ix_agent_suggestions_priority" not in existing_indexes:
        op.create_index("ix_agent_suggestions_priority", "agent_suggestions", ["priority"], unique=False)
    if "ix_agent_suggestions_expires_at" not in existing_indexes:
        op.create_index("ix_agent_suggestions_expires_at", "agent_suggestions", ["expires_at"], unique=False)
    if "idx_status_priority" not in existing_indexes:
        op.create_index("idx_status_priority", "agent_suggestions", ["status", "priority"], unique=False)
    if "idx_entity" not in existing_indexes:
        op.create_index("idx_entity", "agent_suggestions", ["entity_type", "entity_id"], unique=False)

    if not _has_fk(inspector, "agent_suggestions", ["run_id"], "agent_runs"):
        op.create_foreign_key(
            "agent_suggestions_run_id_fkey",
            "agent_suggestions",
            "agent_runs",
            ["run_id"],
            ["id"],
            ondelete="CASCADE",
        )


def _ensure_agent_review_actions(inspector):
    if not inspector.has_table("agent_review_actions"):
        op.create_table(
            "agent_review_actions",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("suggestion_id", sa.Integer(), sa.ForeignKey("agent_suggestions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("action", sa.String(length=20), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )
        op.create_index("ix_agent_review_actions_id", "agent_review_actions", ["id"], unique=False)
        op.create_index("ix_agent_review_actions_suggestion_id", "agent_review_actions", ["suggestion_id"], unique=False)
        op.create_index("ix_agent_review_actions_action", "agent_review_actions", ["action"], unique=False)
        op.create_index("ix_agent_review_actions_reviewed_by_user_id", "agent_review_actions", ["reviewed_by_user_id"], unique=False)
        op.create_index("ix_agent_review_actions_created_at", "agent_review_actions", ["created_at"], unique=False)
        return

    if "ix_agent_review_actions_id" not in _index_names(inspector, "agent_review_actions"):
        op.create_index("ix_agent_review_actions_id", "agent_review_actions", ["id"], unique=False)

    if not _has_fk(inspector, "agent_review_actions", ["suggestion_id"], "agent_suggestions"):
        op.create_foreign_key(
            "agent_review_actions_suggestion_id_fkey",
            "agent_review_actions",
            "agent_suggestions",
            ["suggestion_id"],
            ["id"],
            ondelete="CASCADE",
        )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    _ensure_agent_runs(inspector)
    inspector = sa.inspect(bind)

    _ensure_agent_suggestions(inspector)
    inspector = sa.inspect(bind)

    _ensure_agent_review_actions(inspector)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("agent_review_actions"):
        op.drop_table("agent_review_actions")
    if inspector.has_table("agent_suggestions"):
        op.drop_table("agent_suggestions")
    if inspector.has_table("agent_runs"):
        op.drop_table("agent_runs")
