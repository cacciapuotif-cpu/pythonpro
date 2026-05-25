"""create core baseline tables

Revision ID: 000
Revises:
Create Date: 2026-05-24
"""

from alembic import op
import sqlalchemy as sa

revision = "000"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "collaborators",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(100), nullable=False),
        sa.Column("fiscal_code", sa.String(16), nullable=True),
        sa.Column("partita_iva", sa.String(11), nullable=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("position", sa.String(100), nullable=True),
        sa.Column("birthplace", sa.String(100), nullable=True),
        sa.Column("birth_date", sa.DateTime(), nullable=True),
        sa.Column("gender", sa.String(20), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("address", sa.String(255), nullable=True),
        sa.Column("education", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_login", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_collaborators_email", "collaborators", ["email"], unique=True)
    op.create_index("ix_collaborators_fiscal_code", "collaborators", ["fiscal_code"], unique=False)

    op.create_table(
        "implementing_entities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("partita_iva", sa.String(11), nullable=True),
        sa.Column("codice_fiscale", sa.String(16), nullable=True),
        sa.Column("email", sa.String(100), nullable=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("address", sa.String(255), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_date", sa.DateTime(), nullable=True),
        sa.Column("end_date", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("ente_erogatore", sa.String(100), nullable=True),
        sa.Column("ente_attuatore_id", sa.Integer(), nullable=True),
        sa.Column("budget", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("actual_cost", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("cup", sa.String(15), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["ente_attuatore_id"], ["implementing_entities.id"], name="projects_ente_attuatore_id_fkey"),
    )
    op.create_index("ix_projects_status", "projects", ["status"], unique=False)

    op.create_table(
        "collaborator_project",
        sa.Column("collaborator_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["collaborator_id"], ["collaborators.id"], name="collaborator_project_collaborator_id_fkey"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name="collaborator_project_project_id_fkey"),
        sa.PrimaryKeyConstraint("collaborator_id", "project_id"),
    )

    op.create_table(
        "assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("collaborator_id", sa.Integer(), sa.ForeignKey("collaborators.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(50), nullable=True),
        sa.Column("assigned_hours", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("start_date", sa.DateTime(), nullable=True),
        sa.Column("end_date", sa.DateTime(), nullable=True),
        sa.Column("hourly_rate", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "attendances",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("collaborator_id", sa.Integer(), sa.ForeignKey("collaborators.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assignment_id", sa.Integer(), sa.ForeignKey("assignments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.DateTime(), nullable=True),
        sa.Column("end_time", sa.DateTime(), nullable=True),
        sa.Column("hours", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "contract_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome_template", sa.String(200), nullable=False, server_default="Template"),
        sa.Column("descrizione", sa.Text(), nullable=True),
        sa.Column("ambito_template", sa.String(50), nullable=False, server_default="contratto"),
        sa.Column("chiave_documento", sa.String(100), nullable=True),
        sa.Column("tipo_contratto", sa.String(50), nullable=False, server_default="professionale"),
        sa.Column("contenuto", sa.Text(), nullable=True),
        sa.Column("contenuto_html", sa.Text(), nullable=False, server_default=""),
        sa.Column("intestazione", sa.Text(), nullable=True),
        sa.Column("pie_pagina", sa.Text(), nullable=True),
        sa.Column("include_logo_ente", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("posizione_logo", sa.String(20), nullable=True, server_default="header"),
        sa.Column("dimensione_logo", sa.String(20), nullable=True, server_default="medium"),
        sa.Column("include_clausola_privacy", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("include_clausola_riservatezza", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("include_clausola_proprieta_intellettuale", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("formato_data", sa.String(20), nullable=True, server_default="%d/%m/%Y"),
        sa.Column("formato_importo", sa.String(20), nullable=True, server_default="EUR {:.2f}"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("versione", sa.String(20), nullable=True, server_default="1.0"),
        sa.Column("note_interne", sa.Text(), nullable=True),
        sa.Column("numero_utilizzi", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("ultimo_utilizzo", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.String(100), nullable=True),
        sa.Column("updated_by", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("email", sa.String(100), nullable=False),
        sa.Column("hashed_password", sa.String(100), nullable=False),
        sa.Column("full_name", sa.String(100), nullable=True),
        sa.Column("role", sa.String(20), nullable=True, server_default="user"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("last_login", sa.DateTime(), nullable=True),
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("locked_until", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("collaborator_id", sa.Integer(), sa.ForeignKey("collaborators.id"), nullable=True),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "login_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(50), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=True),
        sa.Column("failure_reason", sa.String(100), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("login_attempts")
    op.drop_table("users")
    op.drop_table("contract_templates")
    op.drop_table("attendances")
    op.drop_table("assignments")
    op.drop_table("collaborator_project")
    op.drop_table("projects")
    op.drop_table("implementing_entities")
    op.drop_table("collaborators")
