"""migrate legacy project avviso fields to avviso pf

Revision ID: h8c9d0e1f2g3
Revises: g7b8c9d0e1f2
Create Date: 2026-04-07 11:25:00.000000+00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "h8c9d0e1f2g3"
down_revision = "g7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE projects p
        SET avviso_pf_id = apf.id
        FROM avvisi_piani_finanziari apf
        WHERE p.avviso_pf_id IS NULL
          AND p.avviso IS NOT NULL
          AND btrim(p.avviso) <> ''
          AND upper(btrim(p.avviso)) = upper(btrim(apf.codice_avviso))
        """
    )

    op.execute(
        """
        UPDATE projects p
        SET template_piano_finanziario_id = COALESCE(p.template_piano_finanziario_id, apf.template_id),
            avviso = apf.codice_avviso,
            ente_erogatore = CASE lower(coalesce(tpf.tipo_fondo, ''))
                WHEN 'formazienda' THEN 'FORMAZIENDA'
                WHEN 'fapi' THEN 'FAPI'
                WHEN 'fondimpresa' THEN 'FONDIMPRESA'
                WHEN 'fse' THEN 'FSE'
                ELSE upper(coalesce(tpf.tipo_fondo, ''))
            END
        FROM avvisi_piani_finanziari apf
        JOIN template_piani_finanziari tpf ON tpf.id = apf.template_id
        WHERE p.avviso_pf_id = apf.id
        """
    )

    op.alter_column("projects", "ente_erogatore", existing_type=sa.String(length=100), nullable=True)
    op.alter_column("projects", "avviso", existing_type=sa.String(length=100), nullable=True)


def downgrade() -> None:
    op.alter_column("projects", "avviso", existing_type=sa.String(length=100), nullable=True)
    op.alter_column("projects", "ente_erogatore", existing_type=sa.String(length=100), nullable=True)
