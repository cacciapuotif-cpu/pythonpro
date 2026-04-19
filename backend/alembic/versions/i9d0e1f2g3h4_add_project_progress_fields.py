"""add project progress fields

Revision ID: i9d0e1f2g3h4
Revises: h8c9d0e1f2g3
Create Date: 2026-04-07 11:55:00.000000+00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "i9d0e1f2g3h4"
down_revision = "h8c9d0e1f2g3"
branch_labels = None
depends_on = None


def _column_names(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = _column_names(inspector, "projects")

    if "ore_totali" not in columns:
        op.add_column("projects", sa.Column("ore_totali", sa.Float(), nullable=False, server_default=sa.text("0")))
    if "ore_completate" not in columns:
        op.add_column("projects", sa.Column("ore_completate", sa.Float(), nullable=False, server_default=sa.text("0")))
    if "progress_percentage" not in columns:
        op.add_column("projects", sa.Column("progress_percentage", sa.Float(), nullable=False, server_default=sa.text("0")))

    op.execute(
        """
        UPDATE projects p
        SET ore_totali = COALESCE(ass.total_assigned_hours, 0),
            ore_completate = COALESCE(att.total_attendance_hours, 0),
            progress_percentage = CASE
                WHEN COALESCE(ass.total_assigned_hours, 0) > 0 THEN LEAST(
                    100,
                    ((COALESCE(att.total_attendance_hours, 0) / ass.total_assigned_hours) * 100)
                )
                ELSE 0
            END
        FROM (
            SELECT project_id, COALESCE(SUM(assigned_hours), 0) AS total_assigned_hours
            FROM assignments
            WHERE is_active = true
            GROUP BY project_id
        ) ass
        FULL OUTER JOIN (
            SELECT project_id, COALESCE(SUM(hours), 0) AS total_attendance_hours
            FROM attendances
            GROUP BY project_id
        ) att ON att.project_id = ass.project_id
        WHERE p.id = COALESCE(ass.project_id, att.project_id)
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = _column_names(inspector, "projects")

    for column_name in ["progress_percentage", "ore_completate", "ore_totali"]:
        if column_name in columns:
            op.drop_column("projects", column_name)
