"""Rename fondo → ente_erogatore su projects, piani_finanziari, piani_finanziari_fondimpresa.

Revision ID: 017
Revises: 016
Create Date: 2026-04-03
"""

from alembic import op
import sqlalchemy as sa

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Copia fondo → ente_erogatore su projects dove ente_erogatore è vuoto
    op.execute("""
        UPDATE projects
        SET ente_erogatore = fondo
        WHERE (ente_erogatore IS NULL OR ente_erogatore = '')
          AND fondo IS NOT NULL AND fondo != ''
    """)

    # 2. Rimuovi fondo da projects
    op.execute("DROP INDEX IF EXISTS idx_projects_fondo")
    op.drop_column("projects", "fondo")

    # 3. Rinomina fondo → ente_erogatore in piani_finanziari
    op.execute("DROP INDEX IF EXISTS idx_unique_piano_progetto_anno_fondo_avviso")
    op.execute("DROP INDEX IF EXISTS idx_unique_piano_progetto_anno_fondo")
    op.alter_column("piani_finanziari", "fondo", new_column_name="ente_erogatore")
    op.execute("""
        CREATE UNIQUE INDEX idx_unique_piano_progetto_anno_ente_avviso
        ON piani_finanziari (progetto_id, anno, ente_erogatore, avviso)
    """)

    # 4. Rinomina fondo → ente_erogatore in piani_finanziari_fondimpresa
    op.alter_column("piani_finanziari_fondimpresa", "fondo", new_column_name="ente_erogatore")


def downgrade():
    op.alter_column("piani_finanziari_fondimpresa", "ente_erogatore", new_column_name="fondo")
    op.execute("DROP INDEX IF EXISTS idx_unique_piano_progetto_anno_ente_avviso")
    op.alter_column("piani_finanziari", "ente_erogatore", new_column_name="fondo")
    op.execute("""
        CREATE UNIQUE INDEX idx_unique_piano_progetto_anno_fondo_avviso
        ON piani_finanziari (progetto_id, anno, fondo, avviso)
    """)
    op.add_column("projects", sa.Column("fondo", sa.String(50), nullable=True))
    op.execute("UPDATE projects SET fondo = ente_erogatore WHERE fondo IS NULL")
