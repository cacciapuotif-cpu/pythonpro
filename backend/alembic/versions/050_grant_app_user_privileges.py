"""grant app user privileges

Revision ID: 050
Revises: 049
Create Date: 2026-05-24
"""

from alembic import op
import os

revision = "050"
down_revision = "049"
branch_labels = None
depends_on = None


def _quote_ident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def upgrade():
    app_user = os.getenv("DB_APP_USER")
    if not app_user:
        return
    user = _quote_ident(app_user)
    op.execute(f"GRANT CONNECT ON DATABASE {op.get_bind().engine.url.database} TO {user}")
    op.execute(f"GRANT USAGE ON SCHEMA public TO {user}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {user}")
    op.execute(f"GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO {user}")
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {user}")
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO {user}")


def downgrade():
    app_user = os.getenv("DB_APP_USER")
    if not app_user:
        return
    user = _quote_ident(app_user)
    op.execute(f"REVOKE SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public FROM {user}")
    op.execute(f"REVOKE USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public FROM {user}")
