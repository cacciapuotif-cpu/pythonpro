"""Add profiling fields to aziende_clienti.

Revision ID: 022
Revises: 021
Create Date: 2026-04-03
"""

from alembic import op
import sqlalchemy as sa


revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def _get_columns(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "aziende_clienti" not in inspector.get_table_names():
        return

    columns = _get_columns(inspector, "aziende_clienti")
    additions = [
        ("attivita_erogate", sa.Text()),
        ("sito_web", sa.String(length=255)),
        ("linkedin_url", sa.String(length=255)),
        ("facebook_url", sa.String(length=255)),
        ("instagram_url", sa.String(length=255)),
        ("legale_rappresentante_nome", sa.String(length=100)),
        ("legale_rappresentante_cognome", sa.String(length=100)),
        ("legale_rappresentante_codice_fiscale", sa.String(length=16)),
        ("legale_rappresentante_email", sa.String(length=100)),
        ("legale_rappresentante_telefono", sa.String(length=30)),
        ("legale_rappresentante_linkedin", sa.String(length=255)),
        ("referente_ruolo", sa.String(length=100)),
        ("referente_telefono", sa.String(length=30)),
        ("referente_linkedin", sa.String(length=255)),
        ("referente_facebook", sa.String(length=255)),
        ("referente_instagram", sa.String(length=255)),
    ]

    for name, column_type in additions:
        if name not in columns:
            op.add_column("aziende_clienti", sa.Column(name, column_type, nullable=True))

    null_count = bind.execute(
        sa.text("SELECT COUNT(*) FROM aziende_clienti WHERE partita_iva IS NULL OR btrim(partita_iva) = ''")
    ).scalar()
    if not null_count:
        op.alter_column("aziende_clienti", "partita_iva", existing_type=sa.String(length=11), nullable=False)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "aziende_clienti" not in inspector.get_table_names():
        return

    columns = _get_columns(inspector, "aziende_clienti")
    removable_columns = [
        "referente_instagram",
        "referente_facebook",
        "referente_linkedin",
        "referente_telefono",
        "referente_ruolo",
        "legale_rappresentante_linkedin",
        "legale_rappresentante_telefono",
        "legale_rappresentante_email",
        "legale_rappresentante_codice_fiscale",
        "legale_rappresentante_cognome",
        "legale_rappresentante_nome",
        "instagram_url",
        "facebook_url",
        "linkedin_url",
        "sito_web",
        "attivita_erogate",
    ]

    for name in removable_columns:
        if name in columns:
            op.drop_column("aziende_clienti", name)

    op.alter_column("aziende_clienti", "partita_iva", existing_type=sa.String(length=11), nullable=True)
