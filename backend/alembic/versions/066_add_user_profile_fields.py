"""Area personale — nome, cognome, telefono e foto profilo.

Revision ID: 066
Revises: 065
"""

from alembic import op
import sqlalchemy as sa


revision = "066"
down_revision = "065"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("first_name", sa.String(length=50), nullable=True))
    op.add_column("users", sa.Column("last_name", sa.String(length=50), nullable=True))
    op.add_column("users", sa.Column("phone", sa.String(length=30), nullable=True))
    op.add_column("users", sa.Column("avatar_path", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "avatar_path")
    op.drop_column("users", "phone")
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")
