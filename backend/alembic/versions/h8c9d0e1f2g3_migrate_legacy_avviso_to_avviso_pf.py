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


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return False
    return column_name in {col["name"] for col in inspector.get_columns(table_name)}


def upgrade() -> None:
    projects_has_avviso = _has_column("projects", "avviso")

    if projects_has_avviso:
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

    if projects_has_avviso:
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
    else:
        op.execute(
            """
            UPDATE projects p
            SET template_piano_finanziario_id = COALESCE(p.template_piano_finanziario_id, apf.template_id),
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

    if _has_column("projects", "ente_erogatore"):
        op.alter_column("projects", "ente_erogatore", existing_type=sa.String(length=100), nullable=True)
    if projects_has_avviso:
        op.alter_column("projects", "avviso", existing_type=sa.String(length=100), nullable=True)


def downgrade() -> None:
    op.alter_column("projects", "avviso", existing_type=sa.String(length=100), nullable=True)
    op.alter_column("projects", "ente_erogatore", existing_type=sa.String(length=100), nullable=True)
