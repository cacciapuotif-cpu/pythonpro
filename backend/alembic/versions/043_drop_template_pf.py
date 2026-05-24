"""drop obsolete piano finanziario templates

Revision ID: 043
Revises: 042
Create Date: 2026-04-23
"""

from alembic import op
import sqlalchemy as sa


revision = "043"
down_revision = "042"
branch_labels = None
depends_on = None


def _has_table(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    if not _has_table(inspector, table_name):
        return False
    return column_name in {col["name"] for col in inspector.get_columns(table_name)}


def _drop_fk_for_column(table_name: str, column_name: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _has_table(inspector, table_name):
        return
    for fk in inspector.get_foreign_keys(table_name):
        if column_name in fk.get("constrained_columns", []):
            op.drop_constraint(fk["name"], table_name, type_="foreignkey")


def _drop_index_if_exists(table_name: str, index_name: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _has_table(inspector, table_name):
        return
    if index_name in {idx["name"] for idx in inspector.get_indexes(table_name)}:
        op.drop_index(index_name, table_name=table_name)


def _drop_unique_if_exists(table_name: str, constraint_name: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _has_table(inspector, table_name):
        return
    if constraint_name in {uc["name"] for uc in inspector.get_unique_constraints(table_name)}:
        op.drop_constraint(constraint_name, table_name, type_="unique")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table_name, column_name in (
        ("projects", "avviso_pf_id"),
        ("projects", "template_piano_finanziario_id"),
        ("piani_finanziari", "template_id"),
        ("piani_finanziari", "avviso_id"),
    ):
        _drop_fk_for_column(table_name, column_name)

    _drop_index_if_exists("projects", "ix_projects_avviso_pf_id")
    _drop_index_if_exists("projects", "ix_projects_template_piano_finanziario_id")
    _drop_index_if_exists("piani_finanziari", "idx_piano_template_avviso")
    _drop_index_if_exists("piani_finanziari", "ix_piani_finanziari_template_id")
    _drop_index_if_exists("piani_finanziari", "ix_piani_finanziari_avviso_id")
    op.execute("DROP INDEX IF EXISTS idx_unique_piano_progetto_anno_ente_avviso_id")

    _drop_unique_if_exists("piani_finanziari", "uq_piano_progetto_anno_avviso")

    inspector = sa.inspect(bind)
    for table_name, column_name in (
        ("projects", "avviso_pf_id"),
        ("projects", "template_piano_finanziario_id"),
        ("piani_finanziari", "template_id"),
        ("piani_finanziari", "avviso_id"),
    ):
        if _has_column(inspector, table_name, column_name):
            op.drop_column(table_name, column_name)
            inspector = sa.inspect(bind)

    _drop_unique_if_exists("piani_finanziari", "uq_piano_progetto_anno_codice")
    op.create_unique_constraint(
        "uq_piano_progetto_anno_codice",
        "piani_finanziari",
        ["progetto_id", "anno", "codice_piano"],
    )

    for table_name in (
        "budget_margine_fondimpresa",
        "budget_costi_fissi_fondimpresa",
        "budget_consulenti_fondimpresa",
        "dettaglio_budget_fondimpresa",
        "documenti_fondimpresa",
        "righe_nominativo_fondimpresa",
        "voci_fondimpresa",
        "piani_finanziari_fondimpresa",
        "avvisi_piani_finanziari",
        "template_piani_finanziari",
    ):
        op.execute(f'DROP TABLE IF EXISTS "{table_name}"')


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_table(inspector, "projects"):
        with op.batch_alter_table("projects") as batch_op:
            if not _has_column(inspector, "projects", "avviso_pf_id"):
                batch_op.add_column(sa.Column("avviso_pf_id", sa.Integer(), nullable=True))
            if not _has_column(inspector, "projects", "template_piano_finanziario_id"):
                batch_op.add_column(sa.Column("template_piano_finanziario_id", sa.Integer(), nullable=True))

    inspector = sa.inspect(bind)
    if _has_table(inspector, "piani_finanziari"):
        with op.batch_alter_table("piani_finanziari") as batch_op:
            if not _has_column(inspector, "piani_finanziari", "template_id"):
                batch_op.add_column(sa.Column("template_id", sa.Integer(), nullable=True))
            if not _has_column(inspector, "piani_finanziari", "avviso_id"):
                batch_op.add_column(sa.Column("avviso_id", sa.Integer(), nullable=True))
