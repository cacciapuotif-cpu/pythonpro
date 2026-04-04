"""link piani finanziari templates by avviso

Revision ID: 010
Revises: 009
Create Date: 2026-04-02
"""

from alembic import op
import sqlalchemy as sa


revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contract_templates", sa.Column("ente_erogatore", sa.String(length=100), nullable=True))
    op.add_column("contract_templates", sa.Column("avviso", sa.String(length=100), nullable=True))
    op.add_column("piani_finanziari", sa.Column("template_id", sa.Integer(), nullable=True))

    op.create_index("ix_contract_templates_ente_erogatore", "contract_templates", ["ente_erogatore"], unique=False)
    op.create_index("ix_contract_templates_avviso", "contract_templates", ["avviso"], unique=False)
    op.create_index("ix_piani_finanziari_template_id", "piani_finanziari", ["template_id"], unique=False)

    op.create_foreign_key(
        "fk_piani_finanziari_template_id_contract_templates",
        "piani_finanziari",
        "contract_templates",
        ["template_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.execute("DROP INDEX IF EXISTS idx_unique_piano_progetto_anno_fondo")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_piano_progetto_anno_fondo_avviso "
        "ON piani_finanziari (progetto_id, anno, fondo, avviso)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_unique_piano_progetto_anno_fondo_avviso")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_piano_progetto_anno_fondo "
        "ON piani_finanziari (progetto_id, anno, fondo)"
    )

    op.drop_constraint("fk_piani_finanziari_template_id_contract_templates", "piani_finanziari", type_="foreignkey")
    op.drop_index("ix_piani_finanziari_template_id", table_name="piani_finanziari")
    op.drop_column("piani_finanziari", "template_id")

    op.drop_index("ix_contract_templates_avviso", table_name="contract_templates")
    op.drop_index("ix_contract_templates_ente_erogatore", table_name="contract_templates")
    op.drop_column("contract_templates", "avviso")
    op.drop_column("contract_templates", "ente_erogatore")
