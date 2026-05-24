"""add project external plan id

Revision ID: 044
Revises: 043
Create Date: 2026-04-23
"""

from alembic import op
import sqlalchemy as sa


revision = "044"
down_revision = "043"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column_name in {col["name"] for col in inspector.get_columns(table_name)}


def _has_index(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return index_name in {idx["name"] for idx in inspector.get_indexes(table_name)}


def upgrade() -> None:
    if not _has_column("projects", "id_piano_esterno"):
        op.add_column("projects", sa.Column("id_piano_esterno", sa.String(length=50), nullable=True))
    if not _has_index("projects", "ix_projects_id_piano_esterno"):
        op.create_index("ix_projects_id_piano_esterno", "projects", ["id_piano_esterno"])

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.alter_column("projects", "cup", type_=sa.String(length=50), existing_type=sa.String(length=15), existing_nullable=True)


def downgrade() -> None:
    if _has_index("projects", "ix_projects_id_piano_esterno"):
        op.drop_index("ix_projects_id_piano_esterno", table_name="projects")
    if _has_column("projects", "id_piano_esterno"):
        op.drop_column("projects", "id_piano_esterno")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.alter_column("projects", "cup", type_=sa.String(length=15), existing_type=sa.String(length=50), existing_nullable=True)

