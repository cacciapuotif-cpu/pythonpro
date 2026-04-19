"""remove legacy agent fields

Revision ID: j0e1f2g3h4i5
Revises: i9d0e1f2g3h4
Create Date: 2026-04-07 14:20:00.000000+00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "j0e1f2g3h4i5"
down_revision = "i9d0e1f2g3h4"
branch_labels = None
depends_on = None


def _column_names(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    run_columns = _column_names(inspector, "agent_runs")
    run_indexes = _index_names(inspector, "agent_runs")
    suggestion_columns = _column_names(inspector, "agent_suggestions")
    suggestion_indexes = _index_names(inspector, "agent_suggestions")

    if "agent_name" in run_columns:
        op.execute(
            """
            UPDATE agent_runs
            SET agent_type = COALESCE(agent_type, agent_name, 'unknown')
            WHERE agent_type IS NULL
            """
        )
    else:
        op.execute(
            """
            UPDATE agent_runs
            SET agent_type = 'unknown'
            WHERE agent_type IS NULL
            """
        )

    if "confidence" in suggestion_columns and "confidence_score" in suggestion_columns:
        op.execute(
            """
            UPDATE agent_suggestions
            SET confidence_score = COALESCE(confidence_score, confidence, 0.0)
            WHERE confidence_score IS NULL
            """
        )

    op.alter_column("agent_runs", "agent_type", existing_type=sa.String(length=100), nullable=False)

    if "ix_agent_runs_agent_name" in run_indexes:
        op.drop_index("ix_agent_runs_agent_name", table_name="agent_runs")
    if "agent_name" in run_columns:
        op.drop_column("agent_runs", "agent_name")

    if "ix_agent_suggestions_agent_name" in suggestion_indexes:
        op.drop_index("ix_agent_suggestions_agent_name", table_name="agent_suggestions")
    if "confidence" in suggestion_columns:
        op.drop_column("agent_suggestions", "confidence")
    if "agent_name" in suggestion_columns:
        op.drop_column("agent_suggestions", "agent_name")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    run_columns = _column_names(inspector, "agent_runs")
    suggestion_columns = _column_names(inspector, "agent_suggestions")

    if "agent_name" not in run_columns:
        op.add_column("agent_runs", sa.Column("agent_name", sa.String(length=100), nullable=True))
        op.create_index("ix_agent_runs_agent_name", "agent_runs", ["agent_name"], unique=False)
        op.execute("UPDATE agent_runs SET agent_name = agent_type WHERE agent_name IS NULL")

    if "agent_name" not in suggestion_columns:
        op.add_column("agent_suggestions", sa.Column("agent_name", sa.String(length=100), nullable=True))
        op.create_index("ix_agent_suggestions_agent_name", "agent_suggestions", ["agent_name"], unique=False)
        op.execute(
            """
            UPDATE agent_suggestions s
            SET agent_name = r.agent_type
            FROM agent_runs r
            WHERE s.run_id = r.id AND s.agent_name IS NULL
            """
        )

    if "confidence" not in suggestion_columns:
        op.add_column("agent_suggestions", sa.Column("confidence", sa.Float(), nullable=True))
        op.execute("UPDATE agent_suggestions SET confidence = confidence_score WHERE confidence IS NULL")

    op.alter_column("agent_runs", "agent_type", existing_type=sa.String(length=100), nullable=True)
