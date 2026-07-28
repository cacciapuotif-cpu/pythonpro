"""UX-6b — archivio versionato dei documenti di progetto.

Revision ID: 065
Revises: 064
"""

from alembic import op
import sqlalchemy as sa


revision = "065"
down_revision = "064"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # La duplicazione resta vietata dal servizio salvo doppia conferma. Il
    # vincolo unique impediva però proprio l'azione esplicita richiesta.
    op.drop_index("ix_projects_codice_fapi", table_name="projects")
    op.create_index(
        "ix_projects_codice_fapi",
        "projects",
        ["codice_fapi"],
        unique=False,
    )

    op.create_table(
        "project_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("tipo_documento", sa.String(length=30), nullable=False),
        sa.Column("versione", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("mime_type", sa.String(length=100), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("caricato_da_user_id", sa.Integer(), nullable=True),
        sa.Column(
            "caricato_il",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "tipo_documento IN ('convenzione','atto_concessione','delibera')",
            name="ck_project_documento_tipo",
        ),
        sa.CheckConstraint(
            "versione > 0",
            name="ck_project_documento_versione",
        ),
        sa.ForeignKeyConstraint(
            ["caricato_da_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "tipo_documento",
            "versione",
            name="uq_project_documento_versione",
        ),
    )
    op.create_index(
        "ix_project_documents_id",
        "project_documents",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_project_documents_project_id",
        "project_documents",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_project_documents_tipo_documento",
        "project_documents",
        ["tipo_documento"],
        unique=False,
    )
    op.create_index(
        "ix_project_documents_caricato_da_user_id",
        "project_documents",
        ["caricato_da_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_project_documents_caricato_il",
        "project_documents",
        ["caricato_il"],
        unique=False,
    )
    op.create_index(
        "ix_project_documents_project_tipo",
        "project_documents",
        ["project_id", "tipo_documento"],
        unique=False,
    )

    # I documenti legacy restano consultabili: autore ignoto e versione 1 sono
    # dichiarazioni oneste, senza inferire metadati mai registrati.
    op.execute(
        sa.text(
            """
            INSERT INTO project_documents (
                project_id, tipo_documento, versione, file_path,
                file_name, mime_type, caricato_da_user_id
            )
            SELECT
                id, 'convenzione', 1, convenzione_file_path,
                NULL, 'application/pdf', NULL
            FROM projects
            WHERE convenzione_file_path IS NOT NULL
              AND btrim(convenzione_file_path) <> ''
            """
        )
    )


def downgrade() -> None:
    op.drop_index(
        "ix_project_documents_project_tipo",
        table_name="project_documents",
    )
    op.drop_index(
        "ix_project_documents_caricato_il",
        table_name="project_documents",
    )
    op.drop_index(
        "ix_project_documents_caricato_da_user_id",
        table_name="project_documents",
    )
    op.drop_index(
        "ix_project_documents_tipo_documento",
        table_name="project_documents",
    )
    op.drop_index(
        "ix_project_documents_project_id",
        table_name="project_documents",
    )
    op.drop_index("ix_project_documents_id", table_name="project_documents")
    op.drop_table("project_documents")

    op.drop_index("ix_projects_codice_fapi", table_name="projects")
    op.create_index(
        "ix_projects_codice_fapi",
        "projects",
        ["codice_fapi"],
        unique=True,
    )
