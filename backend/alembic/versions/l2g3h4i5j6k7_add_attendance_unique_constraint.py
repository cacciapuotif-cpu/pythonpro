"""add attendance unique constraint

Revision ID: l2g3h4i5j6k7
Revises: k1f2g3h4i5j6
Create Date: 2026-04-07 15:05:00.000000+00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "l2g3h4i5j6k7"
down_revision = "k1f2g3h4i5j6"
branch_labels = None
depends_on = None


def _unique_constraint_names(inspector, table_name: str) -> set[str]:
    return {item["name"] for item in inspector.get_unique_constraints(table_name) if item.get("name")}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    unique_constraints = _unique_constraint_names(inspector, "attendances")

    op.execute(
        """
        DELETE FROM attendances a1
        USING attendances a2
        WHERE a1.id > a2.id
          AND a1.collaborator_id = a2.collaborator_id
          AND a1.project_id = a2.project_id
          AND a1.date = a2.date
          AND a1.start_time = a2.start_time
        """
    )

    if "uq_attendance_collaborator_project_date_time" not in unique_constraints:
        op.create_unique_constraint(
            "uq_attendance_collaborator_project_date_time",
            "attendances",
            ["collaborator_id", "project_id", "date", "start_time"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    unique_constraints = _unique_constraint_names(inspector, "attendances")

    if "uq_attendance_collaborator_project_date_time" in unique_constraints:
        op.drop_constraint(
            "uq_attendance_collaborator_project_date_time",
            "attendances",
            type_="unique",
        )
