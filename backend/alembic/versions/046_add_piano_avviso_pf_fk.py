"""add piano avviso pf fk

Revision ID: 046
Revises: 045
Create Date: 2026-05-24
"""

from alembic import op
import sqlalchemy as sa

revision = "046"
down_revision = "045"
branch_labels = None
depends_on = None


def _cols(table):
    inspector = sa.inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return set()
    return {c["name"] for c in inspector.get_columns(table)}


def _idx(table):
    inspector = sa.inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return set()
    return {i["name"] for i in inspector.get_indexes(table)}


def upgrade():
    if "avviso_pf_id" not in _cols("piani_finanziari"):
        op.add_column("piani_finanziari", sa.Column("avviso_pf_id", sa.Integer(), nullable=True))
    if "ix_piani_finanziari_avviso_pf_id" not in _idx("piani_finanziari"):
        op.create_index("ix_piani_finanziari_avviso_pf_id", "piani_finanziari", ["avviso_pf_id"])
    inspector = sa.inspect(op.get_bind())
    fk_names = {fk.get("name") for fk in inspector.get_foreign_keys("piani_finanziari")}
    if "fk_piani_finanziari_avviso_pf_id_avvisi" not in fk_names:
        op.create_foreign_key("fk_piani_finanziari_avviso_pf_id_avvisi", "piani_finanziari", "avvisi", ["avviso_pf_id"], ["id"], ondelete="SET NULL")
    if "avviso" in _cols("piani_finanziari"):
        op.execute("""
            UPDATE piani_finanziari pf
            SET avviso_pf_id = a.id
            FROM avvisi a
            WHERE pf.avviso_pf_id IS NULL
              AND pf.avviso IS NOT NULL
              AND btrim(pf.avviso) <> ''
              AND upper(btrim(pf.avviso)) = upper(btrim(a.codice))
        """)


def downgrade():
    inspector = sa.inspect(op.get_bind())
    for fk in inspector.get_foreign_keys("piani_finanziari"):
        if fk.get("name") == "fk_piani_finanziari_avviso_pf_id_avvisi":
            op.drop_constraint(fk["name"], "piani_finanziari", type_="foreignkey")
    if "ix_piani_finanziari_avviso_pf_id" in _idx("piani_finanziari"):
        op.drop_index("ix_piani_finanziari_avviso_pf_id", table_name="piani_finanziari")
    if "avviso_pf_id" in _cols("piani_finanziari"):
        op.drop_column("piani_finanziari", "avviso_pf_id")
