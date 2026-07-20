"""Entità PianoFinanziarioTemplate versionata (FASE E1).

Revision ID: 060
Revises: 059
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "060"
down_revision = "059"
branch_labels = None
depends_on = None

JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    # ── E1.1: nuova tabella template piani finanziari ──────────────────
    op.create_table(
        "piano_finanziario_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(length=200), nullable=False),
        sa.Column("descrizione", sa.Text(), nullable=True),
        sa.Column("tipo_fondo", sa.String(length=30), nullable=False),
        sa.Column("ente_erogatore", sa.String(length=100), nullable=True),
        sa.Column("avviso_id", sa.Integer(), nullable=True),
        sa.Column("versione", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("struttura_voci", JSON, nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["avviso_id"], ["avvisi.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("nome", "versione", name="uq_pf_template_nome_versione"),
        sa.CheckConstraint("versione > 0", name="ck_pf_template_versione_positiva"),
    )
    op.create_index("ix_piano_finanziario_templates_id", "piano_finanziario_templates", ["id"])
    op.create_index("ix_piano_finanziario_templates_tipo_fondo", "piano_finanziario_templates", ["tipo_fondo"])
    op.create_index("ix_piano_finanziario_templates_avviso_id", "piano_finanziario_templates", ["avviso_id"])


def downgrade() -> None:
    op.drop_index("ix_piano_finanziario_templates_avviso_id", table_name="piano_finanziario_templates")
    op.drop_index("ix_piano_finanziario_templates_tipo_fondo", table_name="piano_finanziario_templates")
    op.drop_index("ix_piano_finanziario_templates_id", table_name="piano_finanziario_templates")
    op.drop_table("piano_finanziario_templates")
