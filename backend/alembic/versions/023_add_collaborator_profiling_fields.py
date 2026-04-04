"""Add profiling and social fields to collaborators.

Revision ID: 023
Revises: 022
Create Date: 2026-04-03
"""

from alembic import op
import sqlalchemy as sa


revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def _get_columns(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "collaborators" not in inspector.get_table_names():
        return

    columns = _get_columns(inspector, "collaborators")
    additions = [
        ("profilo_professionale", sa.Text()),
        ("competenze_principali", sa.Text()),
        ("certificazioni", sa.Text()),
        ("sito_web", sa.String(length=255)),
        ("portfolio_url", sa.String(length=255)),
        ("linkedin_url", sa.String(length=255)),
        ("facebook_url", sa.String(length=255)),
        ("instagram_url", sa.String(length=255)),
        ("tiktok_url", sa.String(length=255)),
    ]

    for name, column_type in additions:
        if name not in columns:
            op.add_column("collaborators", sa.Column(name, column_type, nullable=True))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "collaborators" not in inspector.get_table_names():
        return

    columns = _get_columns(inspector, "collaborators")
    removable_columns = [
        "tiktok_url",
        "instagram_url",
        "facebook_url",
        "linkedin_url",
        "portfolio_url",
        "sito_web",
        "certificazioni",
        "competenze_principali",
        "profilo_professionale",
    ]

    for name in removable_columns:
        if name in columns:
            op.drop_column("collaborators", name)
