"""add allievi and project links

Revision ID: o5j6k7l8m9n0
Revises: n4i5j6k7l8m9
Create Date: 2026-04-07 19:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "o5j6k7l8m9n0"
down_revision = "n4i5j6k7l8m9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "allievi",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=100), nullable=False),
        sa.Column("cognome", sa.String(length=100), nullable=False),
        sa.Column("codice_fiscale", sa.String(length=16), nullable=True),
        sa.Column("luogo_nascita", sa.String(length=100), nullable=True),
        sa.Column("data_nascita", sa.DateTime(), nullable=True),
        sa.Column("telefono", sa.String(length=30), nullable=True),
        sa.Column("email", sa.String(length=100), nullable=True),
        sa.Column("residenza", sa.String(length=255), nullable=True),
        sa.Column("cap", sa.String(length=5), nullable=True),
        sa.Column("citta", sa.String(length=100), nullable=True),
        sa.Column("provincia", sa.String(length=2), nullable=True),
        sa.Column("occupato", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("azienda_cliente_id", sa.Integer(), nullable=True),
        sa.Column("data_assunzione", sa.DateTime(), nullable=True),
        sa.Column("tipo_contratto", sa.String(length=100), nullable=True),
        sa.Column("ccnl", sa.String(length=100), nullable=True),
        sa.Column("mansione", sa.String(length=100), nullable=True),
        sa.Column("livello_inquadramento", sa.String(length=100), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("attivo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["azienda_cliente_id"], ["aziende_clienti.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("codice_fiscale", name="uq_allievi_codice_fiscale"),
    )
    op.create_index(op.f("ix_allievi_id"), "allievi", ["id"], unique=False)
    op.create_index(op.f("ix_allievi_nome"), "allievi", ["nome"], unique=False)
    op.create_index(op.f("ix_allievi_cognome"), "allievi", ["cognome"], unique=False)
    op.create_index(op.f("ix_allievi_email"), "allievi", ["email"], unique=False)
    op.create_index(op.f("ix_allievi_data_nascita"), "allievi", ["data_nascita"], unique=False)
    op.create_index(op.f("ix_allievi_citta"), "allievi", ["citta"], unique=False)
    op.create_index(op.f("ix_allievi_provincia"), "allievi", ["provincia"], unique=False)
    op.create_index(op.f("ix_allievi_occupato"), "allievi", ["occupato"], unique=False)
    op.create_index(op.f("ix_allievi_attivo"), "allievi", ["attivo"], unique=False)
    op.create_index(op.f("ix_allievi_azienda_cliente_id"), "allievi", ["azienda_cliente_id"], unique=False)
    op.create_index(op.f("ix_allievi_data_assunzione"), "allievi", ["data_assunzione"], unique=False)

    op.create_table(
        "allievo_project",
        sa.Column("allievo_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["allievo_id"], ["allievi.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("allievo_id", "project_id"),
    )
    op.create_index("ix_allievo_project_allievo_id", "allievo_project", ["allievo_id"], unique=False)
    op.create_index("ix_allievo_project_project_id", "allievo_project", ["project_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_allievo_project_project_id", table_name="allievo_project")
    op.drop_index("ix_allievo_project_allievo_id", table_name="allievo_project")
    op.drop_table("allievo_project")

    op.drop_index(op.f("ix_allievi_data_assunzione"), table_name="allievi")
    op.drop_index(op.f("ix_allievi_azienda_cliente_id"), table_name="allievi")
    op.drop_index(op.f("ix_allievi_attivo"), table_name="allievi")
    op.drop_index(op.f("ix_allievi_occupato"), table_name="allievi")
    op.drop_index(op.f("ix_allievi_provincia"), table_name="allievi")
    op.drop_index(op.f("ix_allievi_citta"), table_name="allievi")
    op.drop_index(op.f("ix_allievi_data_nascita"), table_name="allievi")
    op.drop_index(op.f("ix_allievi_email"), table_name="allievi")
    op.drop_index(op.f("ix_allievi_cognome"), table_name="allievi")
    op.drop_index(op.f("ix_allievi_nome"), table_name="allievi")
    op.drop_index(op.f("ix_allievi_id"), table_name="allievi")
    op.drop_table("allievi")
