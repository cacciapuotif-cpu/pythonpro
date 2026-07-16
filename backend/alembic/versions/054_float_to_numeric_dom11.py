"""DOM-11: Float -> Numeric su tutti i valori economici e le ore.

Aritmetica float sui valori monetari produce derive da 1 centesimo rispetto
ai fogli di verifica dei fondi (banker's rounding, accumuli binari) e
completed_hours NULL mandava in TypeError Assignment.remaining_hours.

Convenzioni:
- importi in euro:            Numeric(12, 2)
- tariffe orarie:             Numeric(10, 2)
- ore (anche frazionarie):    Numeric(6-8, 2)
- percentuali economiche:     Numeric(5, 2)
- progress_percentage e confidence_score restano Float (non monetari).

completed_hours: backfill NULL -> 0, poi NOT NULL con default 0 (D2 A2).

Verifica di precisione: i dati esistenti sono stati censiti prima della
migration (query round-trip a 2 decimali): nessun valore con scala > 2,
quindi la conversione con round(col::numeric, 2) è senza perdita.
La prova generale su DB copia confronta pre/post riga per riga.

Revision ID: 054
Revises: 053
"""

from alembic import op
import sqlalchemy as sa

revision = "054"
down_revision = "053"
branch_labels = None
depends_on = None

# (tabella, colonna, precisione, scala)
CONVERSIONS = [
    ("allievo_project", "ore_frequentate", 8, 2),
    ("projects", "costo_totale", 12, 2),
    ("projects", "contributo_ente", 12, 2),
    ("projects", "cofinanziamento", 12, 2),
    ("projects", "budget", 12, 2),
    ("projects", "ore_totali", 8, 2),
    ("projects", "ore_completate", 8, 2),
    ("attendances", "hours", 6, 2),
    ("attendances", "overtime_hours", 6, 2),
    ("assignments", "assigned_hours", 8, 2),
    ("assignments", "hourly_rate", 10, 2),
    ("assignments", "completed_hours", 8, 2),
    ("progetto_mansione_ente", "ore_previste", 8, 2),
    ("progetto_mansione_ente", "ore_effettive", 8, 2),
    ("progetto_mansione_ente", "tariffa_oraria", 10, 2),
    ("progetto_mansione_ente", "budget_totale", 12, 2),
    ("piani_finanziari", "budget_totale", 12, 2),
    ("piani_finanziari", "budget_approvato", 12, 2),
    ("piani_finanziari", "budget_utilizzato", 12, 2),
    ("piani_finanziari", "budget_rimanente", 12, 2),
    ("voci_piano_finanziario", "ore", 8, 2),
    ("voci_piano_finanziario", "ore_previste", 8, 2),
    ("voci_piano_finanziario", "ore_effettive", 8, 2),
    ("voci_piano_finanziario", "tariffa_oraria", 10, 2),
    ("voci_piano_finanziario", "importo_consuntivo", 12, 2),
    ("voci_piano_finanziario", "importo_preventivo", 12, 2),
    ("voci_piano_finanziario", "importo_approvato", 12, 2),
    ("voci_piano_finanziario", "importo_validato", 12, 2),
    ("voci_piano_finanziario", "importo_presentato", 12, 2),
    ("prodotti", "prezzo_base", 12, 2),
    ("listino_voci", "prezzo_override", 12, 2),
    ("listino_voci", "sconto_percentuale", 5, 2),
    ("consulenti", "provvigione_percentuale", 5, 2),
    ("azienda_cliente_projects", "cofinanziamento_perc", 5, 2),
    ("azienda_cliente_projects", "plafond_dichiarato", 12, 2),
    ("preventivo_righe", "quantita", 10, 2),
    ("preventivo_righe", "prezzo_unitario", 12, 2),
    ("preventivo_righe", "sconto_percentuale", 5, 2),
    ("preventivo_righe", "importo", 12, 2),
    ("dati_retributivi", "ral_annua", 12, 2),
    ("dati_retributivi", "costo_orario", 10, 2),
    ("dati_retributivi", "ore_1720", 8, 2),
    ("moduli_formativi", "ore_previste", 8, 2),
]


def _existing(inspector, table, column):
    if table not in inspector.get_table_names():
        return False
    return any(col["name"] == column for col in inspector.get_columns(table))


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table, column, precision, scale in CONVERSIONS:
        if not _existing(inspector, table, column):
            # Difensiva (cfr. NEW-003: catena greenfield incompleta): non
            # fallire se una tabella/colonna storica non esiste.
            continue
        op.alter_column(
            table,
            column,
            type_=sa.Numeric(precision, scale),
            postgresql_using=f"round({column}::numeric, {scale})",
        )

    # completed_hours: backfill NULL -> 0 e NOT NULL con default (D2 A2)
    if _existing(inspector, "assignments", "completed_hours"):
        op.execute("UPDATE assignments SET completed_hours = 0 WHERE completed_hours IS NULL")
        op.alter_column(
            "assignments",
            "completed_hours",
            nullable=False,
            server_default="0",
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _existing(inspector, "assignments", "completed_hours"):
        op.alter_column(
            "assignments",
            "completed_hours",
            nullable=True,
            server_default=None,
        )

    for table, column, _precision, _scale in CONVERSIONS:
        if not _existing(inspector, table, column):
            continue
        op.alter_column(
            table,
            column,
            type_=sa.Float(),
            postgresql_using=f"{column}::double precision",
        )
