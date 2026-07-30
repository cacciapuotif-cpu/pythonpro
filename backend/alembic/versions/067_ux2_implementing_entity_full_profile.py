"""UX-2: scheda completa enti, sedi, conti e configurazione stampa.

Revision ID: 067
Revises: 066
"""

from alembic import op
import sqlalchemy as sa


revision = "067"
down_revision = "066"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "implementing_entities",
        "iban",
        existing_type=sa.String(length=27),
        type_=sa.String(length=34),
        existing_nullable=True,
    )
    op.add_column("implementing_entities", sa.Column("sito_web", sa.String(length=500), nullable=True))
    op.add_column(
        "implementing_entities",
        sa.Column("social_links", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column("implementing_entities", sa.Column("letterhead_filename", sa.String(length=255), nullable=True))
    op.add_column("implementing_entities", sa.Column("letterhead_path", sa.String(length=500), nullable=True))
    op.add_column("implementing_entities", sa.Column("letterhead_uploaded_at", sa.DateTime(), nullable=True))
    op.add_column(
        "implementing_entities",
        sa.Column("print_config_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "implementing_entities",
        sa.Column("print_margin_top_mm", sa.Float(), nullable=False, server_default=sa.text("20")),
    )
    op.add_column(
        "implementing_entities",
        sa.Column("print_margin_bottom_mm", sa.Float(), nullable=False, server_default=sa.text("20")),
    )
    op.add_column(
        "implementing_entities",
        sa.Column("print_margin_left_mm", sa.Float(), nullable=False, server_default=sa.text("20")),
    )
    op.add_column(
        "implementing_entities",
        sa.Column("print_margin_right_mm", sa.Float(), nullable=False, server_default=sa.text("20")),
    )
    op.add_column(
        "implementing_entities",
        sa.Column("print_logo_width_mm", sa.Float(), nullable=False, server_default=sa.text("40")),
    )
    op.add_column(
        "implementing_entities",
        sa.Column("print_logo_height_mm", sa.Float(), nullable=False, server_default=sa.text("20")),
    )
    op.add_column(
        "implementing_entities",
        sa.Column("print_logo_x_mm", sa.Float(), nullable=False, server_default=sa.text("20")),
    )
    op.add_column(
        "implementing_entities",
        sa.Column("print_logo_y_mm", sa.Float(), nullable=False, server_default=sa.text("8")),
    )
    op.add_column(
        "implementing_entities",
        sa.Column("print_letterhead_pages", sa.String(length=20), nullable=False, server_default="first"),
    )
    op.add_column("implementing_entities", sa.Column("print_footer", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_implementing_entities_letterhead_pages",
        "implementing_entities",
        "print_letterhead_pages IN ('first', 'all')",
    )
    op.create_check_constraint(
        "ck_implementing_entities_print_margins_nonnegative",
        "implementing_entities",
        "print_margin_top_mm >= 0 AND print_margin_bottom_mm >= 0 "
        "AND print_margin_left_mm >= 0 AND print_margin_right_mm >= 0",
    )

    op.create_table(
        "implementing_entity_locations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "ente_id",
            sa.Integer(),
            sa.ForeignKey("implementing_entities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tipo", sa.String(length=30), nullable=False),
        sa.Column("denominazione", sa.String(length=200), nullable=False),
        sa.Column("indirizzo", sa.String(length=200), nullable=True),
        sa.Column("cap", sa.String(length=20), nullable=True),
        sa.Column("citta", sa.String(length=100), nullable=True),
        sa.Column("provincia", sa.String(length=10), nullable=True),
        sa.Column("nazione", sa.String(length=2), nullable=False, server_default="IT"),
        sa.Column("email", sa.String(length=100), nullable=True),
        sa.Column("pec", sa.String(length=100), nullable=True),
        sa.Column("telefono", sa.String(length=30), nullable=True),
        sa.Column("is_principale", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("accreditamento_ente", sa.String(length=200), nullable=True),
        sa.Column("accreditamento_codice", sa.String(length=100), nullable=True),
        sa.Column("accreditamento_data", sa.Date(), nullable=True),
        sa.Column("accreditamento_scadenza", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("attiva_dal", sa.Date(), nullable=True),
        sa.Column("dismessa_dal", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "tipo IN ('legale', 'operativa', 'amministrativa', 'accreditata')",
            name="ck_implementing_entity_locations_tipo",
        ),
        sa.CheckConstraint(
            "dismessa_dal IS NULL OR attiva_dal IS NULL OR dismessa_dal >= attiva_dal",
            name="ck_implementing_entity_locations_dates",
        ),
    )
    op.create_index("ix_implementing_entity_locations_ente_id", "implementing_entity_locations", ["ente_id"])
    op.create_index("ix_implementing_entity_locations_tipo", "implementing_entity_locations", ["tipo"])
    op.create_index(
        "uq_implementing_entity_one_active_legal_location",
        "implementing_entity_locations",
        ["ente_id"],
        unique=True,
        postgresql_where=sa.text("tipo = 'legale' AND is_active"),
        sqlite_where=sa.text("tipo = 'legale' AND is_active = 1"),
    )
    op.create_index(
        "uq_implementing_entity_one_active_primary_location",
        "implementing_entity_locations",
        ["ente_id"],
        unique=True,
        postgresql_where=sa.text("is_principale AND is_active"),
        sqlite_where=sa.text("is_principale = 1 AND is_active = 1"),
    )

    op.create_table(
        "implementing_entity_bank_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "ente_id",
            sa.Integer(),
            sa.ForeignKey("implementing_entities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("banca", sa.String(length=200), nullable=True),
        sa.Column("agenzia", sa.String(length=200), nullable=True),
        sa.Column("iban", sa.String(length=34), nullable=False),
        sa.Column("bic_swift", sa.String(length=11), nullable=True),
        sa.Column("intestatario", sa.String(length=200), nullable=False),
        sa.Column("is_predefinito", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_implementing_entity_bank_accounts_ente_id",
        "implementing_entity_bank_accounts",
        ["ente_id"],
    )
    op.create_index(
        "uq_implementing_entity_one_active_default_account",
        "implementing_entity_bank_accounts",
        ["ente_id"],
        unique=True,
        postgresql_where=sa.text("is_predefinito AND is_active"),
        sqlite_where=sa.text("is_predefinito = 1 AND is_active = 1"),
    )

    # I dati storici restano anche nelle colonne legacy: questo rende il
    # rollout retrocompatibile e garantisce che i documenti già generati e il
    # rendering con configurazione vuota continuino a usare gli stessi valori.
    op.execute(
        """
        INSERT INTO implementing_entity_locations (
            ente_id, tipo, denominazione, indirizzo, cap, citta, provincia,
            nazione, email, pec, telefono, is_principale, is_active, created_at
        )
        SELECT id, 'legale', ragione_sociale || ' - Sede legale', indirizzo,
               cap, citta, provincia, COALESCE(nazione, 'IT'), email, pec,
               telefono, true, true, CURRENT_TIMESTAMP
        FROM implementing_entities
        """
    )
    op.execute(
        """
        INSERT INTO implementing_entity_bank_accounts (
            ente_id, iban, intestatario, is_predefinito, is_active, created_at
        )
        SELECT id, UPPER(REPLACE(iban, ' ', '')),
               COALESCE(NULLIF(intestatario_conto, ''), ragione_sociale),
               true, true, CURRENT_TIMESTAMP
        FROM implementing_entities
        WHERE iban IS NOT NULL AND TRIM(iban) <> ''
        """
    )


def downgrade() -> None:
    op.drop_index(
        "uq_implementing_entity_one_active_default_account",
        table_name="implementing_entity_bank_accounts",
    )
    op.drop_index("ix_implementing_entity_bank_accounts_ente_id", table_name="implementing_entity_bank_accounts")
    op.drop_table("implementing_entity_bank_accounts")

    op.drop_index(
        "uq_implementing_entity_one_active_primary_location",
        table_name="implementing_entity_locations",
    )
    op.drop_index(
        "uq_implementing_entity_one_active_legal_location",
        table_name="implementing_entity_locations",
    )
    op.drop_index("ix_implementing_entity_locations_tipo", table_name="implementing_entity_locations")
    op.drop_index("ix_implementing_entity_locations_ente_id", table_name="implementing_entity_locations")
    op.drop_table("implementing_entity_locations")

    op.drop_constraint(
        "ck_implementing_entities_print_margins_nonnegative",
        "implementing_entities",
        type_="check",
    )
    op.drop_constraint(
        "ck_implementing_entities_letterhead_pages",
        "implementing_entities",
        type_="check",
    )
    for column in (
        "print_footer",
        "print_letterhead_pages",
        "print_logo_y_mm",
        "print_logo_x_mm",
        "print_logo_height_mm",
        "print_logo_width_mm",
        "print_margin_right_mm",
        "print_margin_left_mm",
        "print_margin_bottom_mm",
        "print_margin_top_mm",
        "print_config_enabled",
        "letterhead_uploaded_at",
        "letterhead_path",
        "letterhead_filename",
        "social_links",
        "sito_web",
    ):
        op.drop_column("implementing_entities", column)
    op.alter_column(
        "implementing_entities",
        "iban",
        existing_type=sa.String(length=34),
        type_=sa.String(length=27),
        existing_nullable=True,
    )
