"""expand assignment role length

Revision ID: 041
Revises: 040
Create Date: 2026-04-23
"""

from alembic import op
import sqlalchemy as sa


revision = "041"
down_revision = "040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "assignments",
        "role",
        existing_type=sa.String(length=50),
        type_=sa.String(length=300),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "assignments",
        "role",
        existing_type=sa.String(length=300),
        type_=sa.String(length=50),
        existing_nullable=False,
    )
