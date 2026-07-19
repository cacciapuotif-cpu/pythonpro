"""Stato e progresso onesti per l'estrazione avvisi.

Revision ID: 059
Revises: 058
"""
import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "059"
down_revision = "058"
branch_labels = None
depends_on = None

JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
SECTIONS = ["economiche", "soggetti", "procedura", "gestione", "scadenze"]
CATEGORIES = [
    "massimali", "parametri_costo",
    "destinatari", "beneficiari", "aiuti_di_stato",
    "presentazione", "valutazione",
    "attuazione", "rendicontazione", "delega", "variazioni",
    "scadenze",
]


def _legacy_progress(state, run_status, raw_summary):
    try:
        summary = json.loads(raw_summary) if raw_summary else {}
    except (TypeError, ValueError):
        summary = {}

    total = int(summary.get("gruppi_totali") or len(SECTIONS))
    failed = int(summary.get("gruppi_falliti") or 0)
    processed = max(0, total - failed)
    base = {
        "version": 1,
        "sezioni_totali": len(SECTIONS),
        "categorie_totali": len(CATEGORIES),
        "elementi_scartati": 0,
        "elementi_scartati_per_sezione": {},
        "errori_sezioni": {},
        "backfill_source": "legacy_agent_run_summary",
    }

    if state == "errore" or run_status == "failed" or (failed >= total and total > 0):
        return "fallita", {
            **base,
            "sezioni_status": {section: "fallita" for section in SECTIONS},
            "sezioni_processate": 0,
            "sezioni_processate_nomi": [],
            "sezioni_complete": 0,
            "sezioni_complete_nomi": [],
            "sezioni_mancanti": list(SECTIONS),
            "categorie_coperte": [],
            "categorie_coperte_count": 0,
            "categorie_mancanti": list(CATEGORIES),
        }

    if state == "estratto" and total > 0 and failed == 0:
        return "completata", {
            **base,
            "sezioni_status": {section: "completa" for section in SECTIONS},
            "sezioni_processate": len(SECTIONS),
            "sezioni_processate_nomi": list(SECTIONS),
            "sezioni_complete": len(SECTIONS),
            "sezioni_complete_nomi": list(SECTIONS),
            "sezioni_mancanti": [],
            "categorie_coperte": list(CATEGORIES),
            "categorie_coperte_count": len(CATEGORIES),
            "categorie_mancanti": [],
        }

    # I vecchi summary contano i fallimenti ma non dicono quali gruppi erano
    # coinvolti: manteniamo il conteggio ricostruibile e segnaliamo l'incertezza.
    return "parziale", {
        **base,
        "sezioni_status": {section: "storico_non_determinabile" for section in SECTIONS},
        "sezioni_processate": processed,
        "sezioni_processate_nomi": [],
        "sezioni_complete": None,
        "sezioni_complete_nomi": [],
        "sezioni_mancanti": list(SECTIONS),
        "categorie_coperte": [],
        "categorie_coperte_count": None,
        "categorie_mancanti": list(CATEGORIES),
        "copertura_storica_non_ricostruibile": True,
    }


def upgrade():
    op.add_column("avviso_revisioni", sa.Column("extraction_progress", JSON, nullable=True))
    op.drop_constraint(
        "ck_avviso_revisioni_stato_estrazione",
        "avviso_revisioni",
        type_="check",
    )
    bind = op.get_bind()
    revisions = sa.table(
        "avviso_revisioni",
        sa.column("id", sa.Integer),
        sa.column("stato_estrazione", sa.String),
        sa.column("extraction_run_id", sa.Integer),
        sa.column("extraction_progress", JSON),
    )
    runs = sa.table(
        "agent_runs",
        sa.column("id", sa.Integer),
        sa.column("status", sa.String),
        sa.column("result_summary", sa.Text),
    )
    rows = bind.execute(
        sa.select(
            revisions.c.id,
            revisions.c.stato_estrazione,
            runs.c.status.label("run_status"),
            runs.c.result_summary,
        ).select_from(
            revisions.outerjoin(runs, revisions.c.extraction_run_id == runs.c.id)
        ).where(revisions.c.stato_estrazione.in_(["estratto", "errore"]))
    ).mappings()
    for row in rows:
        new_state, progress = _legacy_progress(
            row["stato_estrazione"], row["run_status"], row["result_summary"]
        )
        bind.execute(
            revisions.update().where(revisions.c.id == row["id"]).values(
                stato_estrazione=new_state,
                extraction_progress=progress,
            )
        )
    op.create_check_constraint(
        "ck_avviso_revisioni_stato_estrazione",
        "avviso_revisioni",
        "stato_estrazione IN ('caricato','pulito','segmentato','in_estrazione',"
        "'completata','parziale','fallita')",
    )


def downgrade():
    bind = op.get_bind()
    bind.execute(sa.text(
        "UPDATE avviso_revisioni SET stato_estrazione = CASE "
        "WHEN stato_estrazione = 'completata' THEN 'estratto' ELSE 'errore' END "
        "WHERE stato_estrazione IN ('completata','parziale','fallita')"
    ))
    op.drop_constraint(
        "ck_avviso_revisioni_stato_estrazione",
        "avviso_revisioni",
        type_="check",
    )
    op.create_check_constraint(
        "ck_avviso_revisioni_stato_estrazione",
        "avviso_revisioni",
        "stato_estrazione IN ('caricato','pulito','segmentato','in_estrazione','estratto','errore')",
    )
    op.drop_column("avviso_revisioni", "extraction_progress")
