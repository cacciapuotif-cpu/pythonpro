"""add_avviso_pf_id_to_projects

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-04-05 19:00:00.000000+00:00

"""

from alembic import op
import sqlalchemy as sa


revision = "c2d3e4f5a6b7"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())

    if inspector.has_table("projects"):
        cols = {c["name"] for c in inspector.get_columns("projects")}
        if "avviso_pf_id" not in cols:
            op.add_column(
                "projects",
                sa.Column(
                    "avviso_pf_id",
                    sa.Integer(),
                    sa.ForeignKey("avvisi_piani_finanziari.id", ondelete="SET NULL"),
                    nullable=True,
                ),
            )
            existing_indexes = {idx["name"] for idx in inspector.get_indexes("projects")}
            if "ix_projects_avviso_pf_id" not in existing_indexes:
                op.create_index("ix_projects_avviso_pf_id", "projects", ["avviso_pf_id"])


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("projects"):
        existing_indexes = {idx["name"] for idx in inspector.get_indexes("projects")}
        if "ix_projects_avviso_pf_id" in existing_indexes:
            op.drop_index("ix_projects_avviso_pf_id", table_name="projects")
        cols = {c["name"] for c in inspector.get_columns("projects")}
        if "avviso_pf_id" in cols:
            op.drop_column("projects", "avviso_pf_id")
