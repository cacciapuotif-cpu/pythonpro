"""add assignment modulo fields

Revision ID: 040
Revises: 039
Create Date: 2026-04-22
"""

from alembic import op
import sqlalchemy as sa


revision = "040"
down_revision = "039"
branch_labels = None
depends_on = None


def _has_table(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    if not _has_table(inspector, table_name):
        return False
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _has_constraint(inspector, table_name: str, constraint_name: str) -> bool:
    return constraint_name in {constraint["name"] for constraint in inspector.get_foreign_keys(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, "moduli_formativi"):
        op.create_table(
            "moduli_formativi",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("azienda_beneficiaria_id", sa.Integer(), nullable=True),
            sa.Column("codice_progetto_fapi", sa.String(length=30), nullable=True),
            sa.Column("titolo_modulo", sa.String(length=300), nullable=False),
            sa.Column("materia", sa.String(length=200), nullable=True),
            sa.Column("modalita_erogazione", sa.String(length=30), nullable=True),
            sa.Column("tipo_attivita", sa.String(length=20), nullable=False, server_default="formativa"),
            sa.Column("ore_previste", sa.Float(), nullable=True),
            sa.Column("obiettivo", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["azienda_beneficiaria_id"], ["aziende_clienti.id"], ondelete="SET NULL"),
        )
        op.create_index("ix_moduli_formativi_project_id", "moduli_formativi", ["project_id"], unique=False)
        op.create_index("ix_moduli_formativi_azienda_beneficiaria_id", "moduli_formativi", ["azienda_beneficiaria_id"], unique=False)
        op.create_index("ix_moduli_formativi_codice_progetto_fapi", "moduli_formativi", ["codice_progetto_fapi"], unique=False)
        op.create_index("ix_moduli_formativi_modalita_erogazione", "moduli_formativi", ["modalita_erogazione"], unique=False)
        op.create_index("ix_moduli_formativi_tipo_attivita", "moduli_formativi", ["tipo_attivita"], unique=False)
        op.create_index("idx_modulo_project_codice", "moduli_formativi", ["project_id", "codice_progetto_fapi"], unique=False)
        inspector = sa.inspect(bind)

    if not _has_column(inspector, "assignments", "modulo_formativo_id"):
        op.add_column("assignments", sa.Column("modulo_formativo_id", sa.Integer(), nullable=True))
    if not _has_column(inspector, "assignments", "materia"):
        op.add_column("assignments", sa.Column("materia", sa.String(length=200), nullable=True))
    if not _has_column(inspector, "assignments", "modalita_erogazione"):
        op.add_column("assignments", sa.Column("modalita_erogazione", sa.String(length=30), nullable=True))

    op.create_index("ix_assignments_modulo_formativo_id", "assignments", ["modulo_formativo_id"], unique=False, if_not_exists=True)
    op.create_index("ix_assignments_modalita_erogazione", "assignments", ["modalita_erogazione"], unique=False, if_not_exists=True)

    inspector = sa.inspect(bind)
    if not _has_constraint(inspector, "assignments", "fk_assignments_modulo_formativo_id"):
        op.create_foreign_key(
            "fk_assignments_modulo_formativo_id",
            "assignments",
            "moduli_formativi",
            ["modulo_formativo_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_constraint(inspector, "assignments", "fk_assignments_modulo_formativo_id"):
        op.drop_constraint("fk_assignments_modulo_formativo_id", "assignments", type_="foreignkey")
    op.drop_index("ix_assignments_modalita_erogazione", table_name="assignments", if_exists=True)
    op.drop_index("ix_assignments_modulo_formativo_id", table_name="assignments", if_exists=True)

    inspector = sa.inspect(bind)
    for column_name in ("modalita_erogazione", "materia", "modulo_formativo_id"):
        if _has_column(inspector, "assignments", column_name):
            op.drop_column("assignments", column_name)
