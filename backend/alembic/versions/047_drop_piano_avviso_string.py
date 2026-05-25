"""drop piano avviso string

Revision ID: 047
Revises: 046
Create Date: 2026-05-24
"""

from alembic import op
import sqlalchemy as sa

revision = "047"
down_revision = "046"
branch_labels = None
depends_on = None


def _cols(table):
    inspector = sa.inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return set()
    return {c["name"] for c in inspector.get_columns(table)}


def upgrade():
    if "avviso" in _cols("piani_finanziari"):
        op.drop_column("piani_finanziari", "avviso")


def downgrade():
    if "avviso" not in _cols("piani_finanziari"):
        op.add_column("piani_finanziari", sa.Column("avviso", sa.String(100), nullable=False, server_default=""))
        op.execute("""
            UPDATE piani_finanziari pf
            SET avviso = COALESCE(a.codice, '')
            FROM avvisi a
            WHERE pf.avviso_pf_id = a.id
        """)
