"""DOC-1: archiviazione formulario e piano finanziario nei documenti progetto."""

from alembic import op

revision = "068"
down_revision = "067"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_project_documento_tipo", "project_documents", type_="check")
    op.create_check_constraint(
        "ck_project_documento_tipo",
        "project_documents",
        "tipo_documento IN ('convenzione','atto_concessione','delibera','formulario','piano_finanziario')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_project_documento_tipo", "project_documents", type_="check")
    op.create_check_constraint(
        "ck_project_documento_tipo",
        "project_documents",
        "tipo_documento IN ('convenzione','atto_concessione','delibera')",
    )
