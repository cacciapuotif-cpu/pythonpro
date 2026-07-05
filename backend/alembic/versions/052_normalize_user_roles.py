"""normalize user roles for minimal rbac

Revision ID: 052
Revises: 051
Create Date: 2026-07-05
"""

from alembic import op
import sqlalchemy as sa


revision = "052"
down_revision = "051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "users" not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns("users")}
    if "role" not in columns:
        op.add_column("users", sa.Column("role", sa.String(length=20), nullable=True))

    op.execute("""
        UPDATE users
        SET role = CASE
            WHEN role = 'admin' THEN 'admin'
            WHEN role IN ('user', 'manager') THEN 'operatore'
            WHEN role = 'readonly' THEN 'consultazione'
            WHEN role = 'dpo' THEN 'admin'
            WHEN role IN ('operatore', 'consultazione') THEN role
            ELSE 'consultazione'
        END
        WHERE role IS NULL
           OR role NOT IN ('admin', 'operatore', 'consultazione')
    """)
    op.alter_column(
        "users",
        "role",
        existing_type=sa.String(length=20),
        nullable=False,
        server_default="consultazione",
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "users" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("users")}
    if "role" not in columns:
        return

    op.execute("""
        UPDATE users
        SET role = CASE
            WHEN role = 'operatore' THEN 'user'
            WHEN role = 'consultazione' THEN 'readonly'
            ELSE role
        END
    """)
    op.alter_column(
        "users",
        "role",
        existing_type=sa.String(length=20),
        nullable=True,
        server_default=None,
    )
