"""consolidate runtime schema updates into alembic

Revision ID: e4f5a6b7c8d9
Revises: c2d3e4f5a6b7
Create Date: 2026-04-07 10:30:00.000000+00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "e4f5a6b7c8d9"
down_revision = "c2d3e4f5a6b7"
branch_labels = None
depends_on = None


def _column_names(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _table_exists(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _add_column_if_missing(inspector, table_name: str, column: sa.Column) -> None:
    if _table_exists(inspector, table_name) and column.name not in _column_names(inspector, table_name):
        op.add_column(table_name, column)


def _drop_index_if_exists(inspector, table_name: str, index_name: str) -> None:
    if _table_exists(inspector, table_name) and index_name in _index_names(inspector, table_name):
        op.drop_index(index_name, table_name=table_name)


def _create_index_if_missing(
    inspector,
    table_name: str,
    index_name: str,
    columns: list[str],
    *,
    unique: bool = False,
) -> None:
    if _table_exists(inspector, table_name) and index_name not in _index_names(inspector, table_name):
        op.create_index(index_name, table_name, columns, unique=unique)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    _add_column_if_missing(inspector, "assignments", sa.Column("contract_signed_date", sa.DateTime(), nullable=True))
    _add_column_if_missing(inspector, "assignments", sa.Column("edizione_label", sa.String(length=100), nullable=True))

    _add_column_if_missing(inspector, "collaborators", sa.Column("documento_identita_scadenza", sa.DateTime(), nullable=True))
    _add_column_if_missing(inspector, "collaborators", sa.Column("is_agency", sa.Boolean(), nullable=True, server_default=sa.text("false")))
    _add_column_if_missing(inspector, "collaborators", sa.Column("is_consultant", sa.Boolean(), nullable=True, server_default=sa.text("false")))
    _add_column_if_missing(inspector, "collaborators", sa.Column("partita_iva", sa.String(length=11), nullable=True))

    _add_column_if_missing(inspector, "agenzie", sa.Column("partita_iva", sa.String(length=11), nullable=True))
    _add_column_if_missing(inspector, "agenzie", sa.Column("collaborator_id", sa.Integer(), nullable=True))

    _add_column_if_missing(inspector, "projects", sa.Column("atto_approvazione", sa.String(length=255), nullable=True))
    _add_column_if_missing(inspector, "projects", sa.Column("sede_aziendale_comune", sa.String(length=100), nullable=True))
    _add_column_if_missing(inspector, "projects", sa.Column("sede_aziendale_via", sa.String(length=200), nullable=True))
    _add_column_if_missing(inspector, "projects", sa.Column("sede_aziendale_numero_civico", sa.String(length=20), nullable=True))
    _add_column_if_missing(inspector, "projects", sa.Column("ente_erogatore", sa.String(length=100), nullable=True))

    _add_column_if_missing(inspector, "implementing_entities", sa.Column("legale_rappresentante_nome", sa.String(length=50), nullable=True))
    _add_column_if_missing(inspector, "implementing_entities", sa.Column("legale_rappresentante_cognome", sa.String(length=50), nullable=True))
    _add_column_if_missing(inspector, "implementing_entities", sa.Column("legale_rappresentante_luogo_nascita", sa.String(length=100), nullable=True))
    _add_column_if_missing(inspector, "implementing_entities", sa.Column("legale_rappresentante_data_nascita", sa.DateTime(), nullable=True))
    _add_column_if_missing(inspector, "implementing_entities", sa.Column("legale_rappresentante_comune_residenza", sa.String(length=100), nullable=True))
    _add_column_if_missing(inspector, "implementing_entities", sa.Column("legale_rappresentante_via_residenza", sa.String(length=200), nullable=True))
    _add_column_if_missing(inspector, "implementing_entities", sa.Column("legale_rappresentante_codice_fiscale", sa.String(length=16), nullable=True))

    _add_column_if_missing(
        inspector,
        "contract_templates",
        sa.Column("ambito_template", sa.String(length=50), nullable=True, server_default=sa.text("'contratto'")),
    )
    _add_column_if_missing(inspector, "contract_templates", sa.Column("chiave_documento", sa.String(length=100), nullable=True))
    _add_column_if_missing(inspector, "contract_templates", sa.Column("ente_attuatore_id", sa.Integer(), nullable=True))
    _add_column_if_missing(inspector, "contract_templates", sa.Column("progetto_id", sa.Integer(), nullable=True))

    _add_column_if_missing(
        inspector,
        "piani_finanziari",
        sa.Column("avviso", sa.String(length=100), nullable=True, server_default=sa.text("''")),
    )
    _add_column_if_missing(inspector, "piani_finanziari_fondimpresa", sa.Column("avviso_id", sa.Integer(), nullable=True))

    _add_column_if_missing(inspector, "agent_review_actions", sa.Column("reviewed_at", sa.DateTime(), nullable=True))
    _add_column_if_missing(
        inspector,
        "agent_review_actions",
        sa.Column("auto_fix_applied", sa.Boolean(), nullable=True, server_default=sa.text("false")),
    )
    _add_column_if_missing(inspector, "agent_review_actions", sa.Column("result_success", sa.Boolean(), nullable=True))
    _add_column_if_missing(inspector, "agent_review_actions", sa.Column("result_message", sa.Text(), nullable=True))

    _add_column_if_missing(
        inspector,
        "voci_piano_finanziario",
        sa.Column("importo_presentato", sa.Float(), nullable=True, server_default=sa.text("0")),
    )

    _drop_index_if_exists(inspector, "piani_finanziari", "idx_unique_piano_progetto_anno")
    _drop_index_if_exists(inspector, "piani_finanziari", "idx_unique_piano_progetto_anno_fondo")
    _drop_index_if_exists(inspector, "piani_finanziari", "idx_unique_piano_progetto_anno_fondo_avviso")

    _create_index_if_missing(
        inspector,
        "collaborators",
        "ix_collaborators_partita_iva_unique",
        ["partita_iva"],
        unique=True,
    )
    _create_index_if_missing(
        inspector,
        "agenzie",
        "ix_agenzie_partita_iva_unique",
        ["partita_iva"],
        unique=True,
    )
    _create_index_if_missing(
        inspector,
        "agenzie",
        "ix_agenzie_collaborator_id_unique",
        ["collaborator_id"],
        unique=True,
    )
    _create_index_if_missing(
        inspector,
        "piani_finanziari",
        "idx_unique_piano_progetto_anno_ente_avviso_id",
        ["progetto_id", "anno", "ente_erogatore", "avviso_id"],
        unique=True,
    )
    _create_index_if_missing(
        inspector,
        "avvisi",
        "idx_unique_avvisi_codice_ente",
        ["codice", "ente_erogatore"],
        unique=True,
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    _drop_index_if_exists(inspector, "avvisi", "idx_unique_avvisi_codice_ente")
    _drop_index_if_exists(inspector, "piani_finanziari", "idx_unique_piano_progetto_anno_ente_avviso_id")
    _drop_index_if_exists(inspector, "agenzie", "ix_agenzie_collaborator_id_unique")
    _drop_index_if_exists(inspector, "agenzie", "ix_agenzie_partita_iva_unique")
    _drop_index_if_exists(inspector, "collaborators", "ix_collaborators_partita_iva_unique")

    for table_name, column_names in [
        ("voci_piano_finanziario", ["importo_presentato"]),
        ("agent_review_actions", ["result_message", "result_success", "auto_fix_applied", "reviewed_at"]),
        ("piani_finanziari_fondimpresa", ["avviso_id"]),
        ("piani_finanziari", ["avviso"]),
        ("contract_templates", ["progetto_id", "ente_attuatore_id", "chiave_documento", "ambito_template"]),
        (
            "implementing_entities",
            [
                "legale_rappresentante_codice_fiscale",
                "legale_rappresentante_via_residenza",
                "legale_rappresentante_comune_residenza",
                "legale_rappresentante_data_nascita",
                "legale_rappresentante_luogo_nascita",
                "legale_rappresentante_cognome",
                "legale_rappresentante_nome",
            ],
        ),
        (
            "projects",
            [
                "ente_erogatore",
                "sede_aziendale_numero_civico",
                "sede_aziendale_via",
                "sede_aziendale_comune",
                "atto_approvazione",
            ],
        ),
        ("agenzie", ["collaborator_id", "partita_iva"]),
        ("collaborators", ["partita_iva", "is_consultant", "is_agency", "documento_identita_scadenza"]),
        ("assignments", ["edizione_label", "contract_signed_date"]),
    ]:
        if not _table_exists(inspector, table_name):
            continue
        existing_columns = _column_names(inspector, table_name)
        for column_name in column_names:
            if column_name in existing_columns:
                op.drop_column(table_name, column_name)
