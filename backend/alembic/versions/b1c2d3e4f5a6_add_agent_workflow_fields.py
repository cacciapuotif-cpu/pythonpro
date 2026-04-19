"""add_agent_workflow_fields

Revision ID: b1c2d3e4f5a6
Revises: 029_piani_fin_complete
Create Date: 2026-04-05 18:00:00.000000+00:00

"""

from alembic import op
import sqlalchemy as sa


revision = "b1c2d3e4f5a6"
down_revision = "029_piani_fin_complete"
branch_labels = None
depends_on = None


def _column_names(inspector, table_name):
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade():
    inspector = sa.inspect(op.get_bind())

    # ── agent_runs: add workflow system fields ──
    if inspector.has_table("agent_runs"):
        cols = _column_names(inspector, "agent_runs")
        for col_name, col_obj in [
            ("agent_name",          sa.Column("agent_name", sa.String(100), nullable=True)),
            ("entity_type",         sa.Column("entity_type", sa.String(50), nullable=True)),
            ("entity_id",           sa.Column("entity_id", sa.Integer(), nullable=True)),
            ("requested_by_user_id", sa.Column("requested_by_user_id", sa.Integer(), nullable=True)),
            ("input_payload",       sa.Column("input_payload", sa.Text(), nullable=True)),
            ("result_summary",      sa.Column("result_summary", sa.Text(), nullable=True)),
            ("suggestions_count",   sa.Column("suggestions_count", sa.Integer(), nullable=False, server_default=sa.text("0"))),
        ]:
            if col_name not in cols:
                op.add_column("agent_runs", col_obj)

        # Make agent_type nullable (it was NOT NULL before)
        if "agent_type" in cols:
            op.alter_column("agent_runs", "agent_type", nullable=True)

        # Add indexes if not exist
        existing_indexes = {idx["name"] for idx in inspector.get_indexes("agent_runs")}
        for idx_name, columns in [
            ("ix_agent_runs_agent_name", ["agent_name"]),
            ("ix_agent_runs_entity_type", ["entity_type"]),
            ("ix_agent_runs_entity_id", ["entity_id"]),
            ("ix_agent_runs_requested_by_user_id", ["requested_by_user_id"]),
        ]:
            if idx_name not in existing_indexes:
                op.create_index(idx_name, "agent_runs", columns)

    # ── agent_suggestions: add workflow system fields ──
    if inspector.has_table("agent_suggestions"):
        cols = _column_names(inspector, "agent_suggestions")
        for col_name, col_obj in [
            ("agent_name",          sa.Column("agent_name", sa.String(100), nullable=True)),
            ("severity",            sa.Column("severity", sa.String(20), nullable=True)),
            ("payload",             sa.Column("payload", sa.Text(), nullable=True)),
            ("confidence",          sa.Column("confidence", sa.Float(), nullable=True)),
            ("reviewed_at",         sa.Column("reviewed_at", sa.DateTime(), nullable=True)),
            ("reviewed_by_user_id", sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True)),
        ]:
            if col_name not in cols:
                op.add_column("agent_suggestions", col_obj)

        existing_indexes = {idx["name"] for idx in inspector.get_indexes("agent_suggestions")}
        for idx_name, columns in [
            ("ix_agent_suggestions_agent_name", ["agent_name"]),
            ("ix_agent_suggestions_severity", ["severity"]),
            ("ix_agent_suggestions_reviewed_by_user_id", ["reviewed_by_user_id"]),
        ]:
            if idx_name not in existing_indexes:
                op.create_index(idx_name, "agent_suggestions", columns)

    # ── agent_review_actions: add reviewed_by_user_id, make reviewed_by nullable ──
    if inspector.has_table("agent_review_actions"):
        cols = _column_names(inspector, "agent_review_actions")

        # Add reviewed_by_user_id
        if "reviewed_by_user_id" not in cols:
            op.add_column("agent_review_actions", sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True))

        # Make reviewed_by nullable (new workflow system may not set it)
        if "reviewed_by" in cols:
            op.alter_column("agent_review_actions", "reviewed_by", nullable=True)

        # Widen action column to allow longer workflow action names
        op.alter_column(
            "agent_review_actions",
            "action",
            type_=sa.String(50),
            existing_nullable=False,
        )

        existing_indexes = {idx["name"] for idx in inspector.get_indexes("agent_review_actions")}
        if "ix_agent_review_actions_reviewed_by_user_id" not in existing_indexes:
            op.create_index(
                "ix_agent_review_actions_reviewed_by_user_id",
                "agent_review_actions",
                ["reviewed_by_user_id"],
            )


def downgrade():
    inspector = sa.inspect(op.get_bind())

    if inspector.has_table("agent_review_actions"):
        existing_indexes = {idx["name"] for idx in inspector.get_indexes("agent_review_actions")}
        if "ix_agent_review_actions_reviewed_by_user_id" in existing_indexes:
            op.drop_index("ix_agent_review_actions_reviewed_by_user_id", table_name="agent_review_actions")
        cols = _column_names(inspector, "agent_review_actions")
        if "reviewed_by_user_id" in cols:
            op.drop_column("agent_review_actions", "reviewed_by_user_id")
        if "reviewed_by" in cols:
            op.alter_column("agent_review_actions", "reviewed_by", nullable=False)
        op.alter_column("agent_review_actions", "action", type_=sa.String(20), existing_nullable=False)

    if inspector.has_table("agent_suggestions"):
        for col in ["agent_name", "severity", "payload", "confidence", "reviewed_at", "reviewed_by_user_id"]:
            cols = _column_names(inspector, "agent_suggestions")
            if col in cols:
                op.drop_column("agent_suggestions", col)

    if inspector.has_table("agent_runs"):
        for col in ["agent_name", "entity_type", "entity_id", "requested_by_user_id",
                    "input_payload", "result_summary", "suggestions_count"]:
            cols = _column_names(inspector, "agent_runs")
            if col in cols:
                op.drop_column("agent_runs", col)
        op.alter_column("agent_runs", "agent_type", nullable=False)
