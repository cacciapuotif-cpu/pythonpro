"""Add immutable audit_logs table and overlap-optimization indexes.

Revision ID: 018
Revises: 017
Create Date: 2026-04-03
"""

from alembic import op
import sqlalchemy as sa


revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_tables = set(inspector.get_table_names())
    if "audit_logs" not in existing_tables:
        op.create_table(
            "audit_logs",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("entity", sa.String(length=100), nullable=False),
            sa.Column("action", sa.String(length=50), nullable=False),
            sa.Column("old_value", sa.Text(), nullable=True),
            sa.Column("new_value", sa.Text(), nullable=True),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        )

    def _create_index_if_missing(table_name: str, index_name: str, columns: list[str]) -> None:
        existing_indexes = {idx["name"] for idx in inspector.get_indexes(table_name)}
        if index_name not in existing_indexes:
            op.create_index(index_name, table_name, columns, unique=False)

    _create_index_if_missing("audit_logs", "ix_audit_logs_entity", ["entity"])
    _create_index_if_missing("audit_logs", "ix_audit_logs_action", ["action"])
    _create_index_if_missing("audit_logs", "ix_audit_logs_user_id", ["user_id"])
    _create_index_if_missing("audit_logs", "ix_audit_logs_created_at", ["created_at"])

    _create_index_if_missing(
        "assignments",
        "idx_assignment_overlap_guard",
        ["collaborator_id", "is_active", "start_date", "end_date"],
    )
    _create_index_if_missing(
        "attendances",
        "idx_attendance_overlap_guard",
        ["collaborator_id", "start_time", "end_time"],
    )


def downgrade():
    op.drop_index("idx_attendance_overlap_guard", table_name="attendances")
    op.drop_index("idx_assignment_overlap_guard", table_name="assignments")

    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_user_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_entity", table_name="audit_logs")

    op.drop_table("audit_logs")
