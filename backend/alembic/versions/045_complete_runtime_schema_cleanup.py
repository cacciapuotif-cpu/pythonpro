"""complete runtime schema cleanup

Revision ID: 045
Revises: 044
Create Date: 2026-05-24
"""

from alembic import op
import sqlalchemy as sa

revision = "045"
down_revision = "044"
branch_labels = None
depends_on = None


def _has_table(inspector, table_name):
    return table_name in inspector.get_table_names()


def _columns(inspector, table_name):
    if not _has_table(inspector, table_name):
        return set()
    return {col["name"] for col in inspector.get_columns(table_name)}


def _indexes(inspector, table_name):
    if not _has_table(inspector, table_name):
        return set()
    return {idx["name"] for idx in inspector.get_indexes(table_name)}


def _add(table_name, column):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _has_table(inspector, table_name) and column.name not in _columns(inspector, table_name):
        op.add_column(table_name, column)


def _drop(table_name, column_name):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if column_name in _columns(inspector, table_name):
        op.drop_column(table_name, column_name)


def _index(table_name, index_name, columns, unique=False):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _has_table(inspector, table_name) and index_name not in _indexes(inspector, table_name):
        op.create_index(index_name, table_name, columns, unique=unique)


def upgrade():
    # Residui rimasti nel vecchio ensure_runtime_schema_updates().
    for col in (
        sa.Column("profilo_professionale", sa.Text(), nullable=True),
        sa.Column("competenze_principali", sa.Text(), nullable=True),
        sa.Column("certificazioni", sa.Text(), nullable=True),
        sa.Column("sito_web", sa.String(255), nullable=True),
        sa.Column("portfolio_url", sa.String(255), nullable=True),
        sa.Column("linkedin_url", sa.String(255), nullable=True),
        sa.Column("facebook_url", sa.String(255), nullable=True),
        sa.Column("instagram_url", sa.String(255), nullable=True),
        sa.Column("tiktok_url", sa.String(255), nullable=True),
    ):
        _add("collaborators", col)

    for col in (
        sa.Column("agenzia_id", sa.Integer(), nullable=True),
        sa.Column("attivita_erogate", sa.Text(), nullable=True),
        sa.Column("sito_web", sa.String(255), nullable=True),
        sa.Column("linkedin_url", sa.String(255), nullable=True),
        sa.Column("facebook_url", sa.String(255), nullable=True),
        sa.Column("instagram_url", sa.String(255), nullable=True),
        sa.Column("legale_rappresentante_nome", sa.String(100), nullable=True),
        sa.Column("legale_rappresentante_cognome", sa.String(100), nullable=True),
        sa.Column("legale_rappresentante_codice_fiscale", sa.String(16), nullable=True),
        sa.Column("legale_rappresentante_email", sa.String(100), nullable=True),
        sa.Column("legale_rappresentante_telefono", sa.String(30), nullable=True),
        sa.Column("legale_rappresentante_indirizzo", sa.String(255), nullable=True),
        sa.Column("legale_rappresentante_linkedin", sa.String(255), nullable=True),
        sa.Column("legale_rappresentante_facebook", sa.String(255), nullable=True),
        sa.Column("legale_rappresentante_instagram", sa.String(255), nullable=True),
        sa.Column("legale_rappresentante_tiktok", sa.String(255), nullable=True),
        sa.Column("referente_cognome", sa.String(100), nullable=True),
        sa.Column("referente_ruolo", sa.String(100), nullable=True),
        sa.Column("referente_telefono", sa.String(30), nullable=True),
        sa.Column("referente_indirizzo", sa.String(255), nullable=True),
        sa.Column("referente_luogo_nascita", sa.String(100), nullable=True),
        sa.Column("referente_data_nascita", sa.DateTime(), nullable=True),
        sa.Column("referente_linkedin", sa.String(255), nullable=True),
        sa.Column("referente_facebook", sa.String(255), nullable=True),
        sa.Column("referente_instagram", sa.String(255), nullable=True),
        sa.Column("referente_tiktok", sa.String(255), nullable=True),
    ):
        _add("aziende_clienti", col)

    try:
        op.alter_column("aziende_clienti", "partita_iva", existing_type=sa.String(11), nullable=True)
    except Exception:
        pass

    for col in (
        sa.Column("ente_erogatore", sa.String(100), nullable=True),
        sa.Column("avviso", sa.String(100), nullable=True),
    ):
        _add("contract_templates", col)

    _add("voci_piano_finanziario", sa.Column("modulo_formativo_id", sa.Integer(), nullable=True))

    for col in (
        sa.Column("codice", sa.String(50), nullable=True),
        sa.Column("ente_erogatore", sa.String(100), nullable=True),
        sa.Column("descrizione", sa.String(200), nullable=True),
        sa.Column("template_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.text("true")),
    ):
        _add("avvisi", col)

    _index("collaborators", "ix_collaborators_partita_iva_unique", ["partita_iva"], unique=True)
    _index("agenzie", "ix_agenzie_partita_iva_unique", ["partita_iva"], unique=True)
    _index("agenzie", "ix_agenzie_collaborator_id_unique", ["collaborator_id"], unique=True)
    _index("avvisi", "idx_unique_avvisi_codice_ente", ["codice", "ente_erogatore"], unique=True)


def downgrade():
    for table, columns in (
        ("avvisi", ["is_active", "template_id", "descrizione", "ente_erogatore", "codice"]),
        ("voci_piano_finanziario", ["modulo_formativo_id"]),
        ("contract_templates", ["avviso", "ente_erogatore"]),
        ("aziende_clienti", ["referente_tiktok", "referente_instagram", "referente_facebook", "referente_linkedin", "referente_data_nascita", "referente_luogo_nascita", "referente_indirizzo", "referente_telefono", "referente_ruolo", "referente_cognome", "legale_rappresentante_tiktok", "legale_rappresentante_instagram", "legale_rappresentante_facebook", "legale_rappresentante_linkedin", "legale_rappresentante_indirizzo", "legale_rappresentante_telefono", "legale_rappresentante_email", "legale_rappresentante_codice_fiscale", "legale_rappresentante_cognome", "legale_rappresentante_nome", "instagram_url", "facebook_url", "linkedin_url", "sito_web", "attivita_erogate", "agenzia_id"]),
        ("collaborators", ["tiktok_url", "instagram_url", "facebook_url", "linkedin_url", "portfolio_url", "sito_web", "certificazioni", "competenze_principali", "profilo_professionale"]),
    ):
        for column in columns:
            _drop(table, column)
