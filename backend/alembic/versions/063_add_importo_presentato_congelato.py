"""DOM-18 — snapshot storico dell'importo presentato al fondo.

Aggiunge ``voci_piano_finanziario.importo_presentato_congelato``: la fotografia
di ``importo_presentato`` scattata al passaggio del piano allo stato
``inviato``. I ricalcoli successivi (presenze, tariffe, budget) continuano a
muovere ``importo_presentato``, ma NON toccano lo snapshot: è quello il valore
effettivamente presentato al fondo, e serve per la riconciliazione in
rendicontazione.

NULL = piano mai passato per ``inviato``, quindi nessuno snapshot.

Backfill
--------
Per i piani già in stato congelato ({inviato, rendicontato, chiuso}) al momento
della migration lo snapshot non esiste da nessuna parte: il miglior proxy
disponibile è l'``importo_presentato`` corrente, quindi lo si copia. Per gli
altri piani si lascia NULL: sarà ``crud._congela_importi_presentati`` a
riempirlo alla transizione.

Revision ID: 063
Revises: 062
"""
from alembic import op
import sqlalchemy as sa


revision = "063"
down_revision = "062"
branch_labels = None
depends_on = None


STATI_CONGELATI = ("inviato", "rendicontato", "chiuso")


def upgrade() -> None:
    op.add_column(
        "voci_piano_finanziario",
        sa.Column("importo_presentato_congelato", sa.Numeric(12, 2), nullable=True),
    )

    op.execute(
        sa.text(
            """
            UPDATE voci_piano_finanziario AS v
            SET importo_presentato_congelato = COALESCE(v.importo_presentato, 0)
            FROM piani_finanziari AS p
            WHERE p.id = v.piano_id
              AND p.stato IN :stati
            """
        ).bindparams(sa.bindparam("stati", value=STATI_CONGELATI, expanding=True))
    )


def downgrade() -> None:
    op.drop_column("voci_piano_finanziario", "importo_presentato_congelato")
