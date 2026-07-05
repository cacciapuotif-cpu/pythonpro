"""Reconcile schema/model drift (F1-002, F2-007)

Chiude il drift rilevato da `alembic check` sul DB reale a head 052:
- crea la tabella mancante `giustificativo_spesa`
- droppa 38 indici legacy duplicati di indici `ix_*` equivalenti gia' presenti
- rinomina 4 indici legacy al nome atteso dai modelli
- sostituisce l'indice parziale `idx_agent_run_idempotency_key` con lo
  unique pieno `ix_agent_runs_idempotency_key` atteso dal modello
  (equivalente per l'unicita': in PostgreSQL i NULL restano distinti)
- crea gli indici dichiarati dai modelli e assenti nel DB
- droppa le colonne legacy rimpiazzate da property Python nei modelli
  (agent_runs.agent_name -> agent_type; agent_suggestions.agent_name,
  agent_suggestions.confidence -> confidence_score;
  agent_review_actions.created_at -> reviewed_at, reviewed_by ->
  reviewed_by_user_id). Verificato su dati live: nessun valore divergente.
- converte gli unique constraint di allievi.codice_fiscale e
  email_inbox_items.message_id negli unique index attesi dai modelli
- allarga projects.ente_erogatore a VARCHAR(100) (max len live: 11)
- allinea i NOT NULL DB-side (reviewed_at con backfill da created_at,
  auto_fix_applied, ambito_template, importo_presentato: 0 NULL live)
- aggiunge le 4 FK mancanti (0 righe orfane live)

Le divergenze in direzione opposta (DB piu' severo dei modelli) sono
state chiuse nei modelli, non qui: vedi models.py/auth.py nello stesso
commit.

Revision ID: 053
Revises: 052
Create Date: 2026-07-05
"""

from alembic import op
import sqlalchemy as sa


revision = "053"
down_revision = "052"
branch_labels = None
depends_on = None


# (nome_indice, tabella, colonne, unique)
INDEXES_TO_CREATE = [
    ("ix_agent_communication_drafts_id", "agent_communication_drafts", ["id"], False),
    ("ix_agent_review_actions_reviewed_at", "agent_review_actions", ["reviewed_at"], False),
    ("ix_allievi_created_at", "allievi", ["created_at"], False),
    ("ix_assignments_contract_signed_date", "assignments", ["contract_signed_date"], False),
    ("ix_assignments_edizione_label", "assignments", ["edizione_label"], False),
    ("ix_audit_log_azione", "audit_log", ["azione"], False),
    ("ix_audit_log_esito", "audit_log", ["esito"], False),
    ("ix_audit_log_id", "audit_log", ["id"], False),
    ("ix_audit_log_risorsa_id", "audit_log", ["risorsa_id"], False),
    ("ix_audit_log_risorsa_tipo", "audit_log", ["risorsa_tipo"], False),
    ("ix_audit_logs_id", "audit_logs", ["id"], False),
    ("ix_avvisi_created_at", "avvisi", ["created_at"], False),
    ("ix_avvisi_ente_erogatore", "avvisi", ["ente_erogatore"], False),
    ("ix_avvisi_id", "avvisi", ["id"], False),
    ("ix_avvisi_is_active", "avvisi", ["is_active"], False),
    ("ix_aziende_clienti_agenzia_id", "aziende_clienti", ["agenzia_id"], False),
    ("ix_collaborators_anonimizzato", "collaborators", ["anonimizzato"], False),
    ("ix_collaborators_consenso_email_agenti", "collaborators", ["consenso_email_agenti"], False),
    ("ix_collaborators_consenso_whatsapp_agenti", "collaborators", ["consenso_whatsapp_agenti"], False),
    ("ix_collaborators_is_agency", "collaborators", ["is_agency"], False),
    ("ix_collaborators_is_consultant", "collaborators", ["is_consultant"], False),
    ("ix_contract_templates_ambito_template", "contract_templates", ["ambito_template"], False),
    ("ix_contract_templates_avviso", "contract_templates", ["avviso"], False),
    ("ix_contract_templates_chiave_documento", "contract_templates", ["chiave_documento"], False),
    ("ix_contract_templates_ente_attuatore_id", "contract_templates", ["ente_attuatore_id"], False),
    ("ix_contract_templates_progetto_id", "contract_templates", ["progetto_id"], False),
    ("ix_document_counters_anno", "document_counters", ["anno"], False),
    ("ix_document_counters_id", "document_counters", ["id"], False),
    ("ix_email_inbox_items_id", "email_inbox_items", ["id"], False),
    ("ix_gdpr_consensi_id", "gdpr_consensi", ["id"], False),
    ("ix_gdpr_consensi_revocato", "gdpr_consensi", ["revocato"], False),
    ("ix_implementing_entities_legale_rappresentante_codice_fiscale", "implementing_entities", ["legale_rappresentante_codice_fiscale"], False),
    ("ix_massimali_fondo_id", "massimali_fondo", ["id"], False),
    ("ix_piani_finanziari_codice_progetto_fondo", "piani_finanziari", ["codice_progetto_fondo"], False),
    ("ix_piani_finanziari_stato_rendicontazione", "piani_finanziari", ["stato_rendicontazione"], False),
    ("ix_progetto_beneficiario_id", "progetto_beneficiario", ["id"], False),
    ("ix_projects_avviso", "projects", ["avviso"], False),
    ("ix_projects_codice_fapi", "projects", ["codice_fapi"], True),
    ("ix_voci_piano_finanziario_assignment_id", "voci_piano_finanziario", ["assignment_id"], False),
    ("ix_voci_piano_finanziario_mansione_riferimento", "voci_piano_finanziario", ["mansione_riferimento"], False),
    ("ix_voci_piano_finanziario_modulo_formativo_id", "voci_piano_finanziario", ["modulo_formativo_id"], False),
    ("ix_voci_piano_finanziario_stato", "voci_piano_finanziario", ["stato"], False),
]

# Indici legacy duplicati di indici ix_* equivalenti gia' esistenti.
DUPLICATE_INDEXES_TO_DROP = [
    "idx_agenzia_attivo", "idx_agenzia_nome",
    "idx_azienda_attivo", "idx_azienda_citta", "idx_azienda_consulente",
    "idx_azienda_partita_iva", "idx_azienda_ragione_sociale",
    "idx_collab_position",
    "idx_collaborators_fiscal_code", "idx_collaborators_fiscal_code_unique",
    "idx_consulente_agenzia", "idx_consulente_attivo",
    "idx_dati_retributivi_project",
    "idx_listino_attivo", "idx_listino_nome", "idx_listino_tipo_cliente",
    "idx_voce_listino", "idx_voce_prodotto",
    "idx_ordine_anno", "idx_ordine_azienda", "idx_ordine_preventivo", "idx_ordine_stato",
    "idx_piani_finanziari_anno", "idx_piani_finanziari_progetto",
    "idx_unique_piano_progetto_anno_codice_runtime",
    "idx_preventivo_anno", "idx_preventivo_attivo", "idx_preventivo_azienda", "idx_preventivo_stato",
    "idx_riga_preventivo", "idx_riga_prodotto",
    "idx_prodotto_attivo", "idx_prodotto_codice", "idx_prodotto_nome", "idx_prodotto_tipo",
    "idx_timesheet_generati_assignment",
    "idx_voci_piano_piano",
    "ix_email_inbox_items_message_id",  # duplicato non-unique del constraint, ricreato unique sotto
]

INDEX_RENAMES = [
    ("ix_agenzie_collaborator_id_unique", "ix_agenzie_collaborator_id"),
    ("ix_agenzie_partita_iva_unique", "ix_agenzie_partita_iva"),
    ("ix_collaborators_partita_iva_unique", "ix_collaborators_partita_iva"),
    ("ix_email_inbox_items_sender", "ix_email_inbox_items_sender_email"),
]


def _existing_indexes(bind) -> set:
    rows = bind.execute(sa.text(
        "SELECT indexname FROM pg_indexes WHERE schemaname = 'public'"
    ))
    return {r[0] for r in rows}


def _existing_columns(bind, table: str) -> set:
    inspector = sa.inspect(bind)
    return {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    # ── 1. Tabella giustificativo_spesa ─────────────────────────────
    if "giustificativo_spesa" not in tables:
        op.create_table(
            "giustificativo_spesa",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("voce_piano_id", sa.Integer(),
                      sa.ForeignKey("voci_piano_finanziario.id", ondelete="CASCADE"),
                      nullable=False),
            sa.Column("tipo", sa.String(length=50), nullable=False),
            sa.Column("importo", sa.Numeric(12, 2), nullable=False),
            sa.Column("numero_doc", sa.String(length=100), nullable=True),
            sa.Column("data_doc", sa.Date(), nullable=True),
            sa.Column("fornitore", sa.String(length=200), nullable=True),
            sa.Column("file_path", sa.String(length=500), nullable=True),
            sa.Column("validato", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("note", sa.Text(), nullable=True),
        )
        op.create_index("ix_giustificativo_spesa_id", "giustificativo_spesa", ["id"])
        op.create_index("ix_giustificativo_spesa_tipo", "giustificativo_spesa", ["tipo"])
        op.create_index("ix_giustificativo_spesa_validato", "giustificativo_spesa", ["validato"])
        op.create_index("ix_giustificativo_spesa_voce_piano_id", "giustificativo_spesa", ["voce_piano_id"])

    existing = _existing_indexes(bind)

    # ── 2. Drop indici duplicati legacy ──────────────────────────────
    for name in DUPLICATE_INDEXES_TO_DROP:
        if name in existing:
            op.execute(sa.text(f'DROP INDEX IF EXISTS "{name}"'))

    # ── 3. Rename indici legacy al nome atteso dai modelli ──────────
    for old, new in INDEX_RENAMES:
        if old in existing and new not in existing:
            op.execute(sa.text(f'ALTER INDEX "{old}" RENAME TO "{new}"'))

    # ── 4. idempotency_key: da unique parziale a unique pieno ───────
    if "idx_agent_run_idempotency_key" in existing:
        op.execute(sa.text('DROP INDEX IF EXISTS "idx_agent_run_idempotency_key"'))
    existing = _existing_indexes(bind)
    if "ix_agent_runs_idempotency_key" not in existing:
        op.create_index("ix_agent_runs_idempotency_key", "agent_runs", ["idempotency_key"], unique=True)

    # ── 5. Colonne legacy degli agenti (rimpiazzate da property) ────
    agent_runs_cols = _existing_columns(bind, "agent_runs")
    if "agent_name" in agent_runs_cols:
        op.drop_column("agent_runs", "agent_name")

    sugg_cols = _existing_columns(bind, "agent_suggestions")
    if "agent_name" in sugg_cols:
        op.drop_column("agent_suggestions", "agent_name")
    if "confidence" in sugg_cols:
        op.drop_column("agent_suggestions", "confidence")

    review_cols = _existing_columns(bind, "agent_review_actions")
    if "created_at" in review_cols:
        op.execute(sa.text(
            "UPDATE agent_review_actions SET reviewed_at = created_at WHERE reviewed_at IS NULL"
        ))
    op.execute(sa.text(
        "UPDATE agent_review_actions SET reviewed_at = now() WHERE reviewed_at IS NULL"
    ))
    op.alter_column("agent_review_actions", "reviewed_at",
                    existing_type=sa.TIMESTAMP(), nullable=False)
    if "created_at" in review_cols:
        op.drop_column("agent_review_actions", "created_at")
    if "reviewed_by" in review_cols:
        op.drop_column("agent_review_actions", "reviewed_by")

    # ── 6. Unique constraint -> unique index (come da modelli) ──────
    for c in inspector.get_unique_constraints("allievi"):
        if c["column_names"] == ["codice_fiscale"]:
            op.drop_constraint(c["name"], "allievi", type_="unique")
    existing = _existing_indexes(bind)
    if "ix_allievi_codice_fiscale" not in existing:
        op.create_index("ix_allievi_codice_fiscale", "allievi", ["codice_fiscale"], unique=True)

    for c in inspector.get_unique_constraints("email_inbox_items"):
        if c["column_names"] == ["message_id"]:
            op.drop_constraint(c["name"], "email_inbox_items", type_="unique")
    existing = _existing_indexes(bind)
    if "ix_email_inbox_items_message_id" not in existing:
        op.create_index("ix_email_inbox_items_message_id", "email_inbox_items", ["message_id"], unique=True)

    # ── 7. Allarga projects.ente_erogatore ──────────────────────────
    op.alter_column("projects", "ente_erogatore",
                    existing_type=sa.VARCHAR(length=50),
                    type_=sa.String(length=100),
                    existing_nullable=True)

    # ── 8. NOT NULL DB-side ─────────────────────────────────────────
    op.execute(sa.text("UPDATE agent_review_actions SET auto_fix_applied = false WHERE auto_fix_applied IS NULL"))
    op.alter_column("agent_review_actions", "auto_fix_applied",
                    existing_type=sa.Boolean(), nullable=False)
    op.execute(sa.text("UPDATE contract_templates SET ambito_template = 'contratto' WHERE ambito_template IS NULL"))
    op.alter_column("contract_templates", "ambito_template",
                    existing_type=sa.VARCHAR(length=50), nullable=False)
    op.execute(sa.text("UPDATE voci_piano_finanziario SET importo_presentato = 0 WHERE importo_presentato IS NULL"))
    op.alter_column("voci_piano_finanziario", "importo_presentato",
                    existing_type=sa.Float(), nullable=False)

    # ── 9. FK mancanti (0 orfani verificati su dati live) ───────────
    fks = {
        ("agenzie", "collaborator_id"): ("fk_agenzie_collaborator_id", "collaborators", "SET NULL"),
        ("aziende_clienti", "agenzia_id"): ("fk_aziende_clienti_agenzia_id", "agenzie", "SET NULL"),
        ("contract_templates", "ente_attuatore_id"): ("fk_contract_templates_ente_attuatore_id", "implementing_entities", "SET NULL"),
        ("contract_templates", "progetto_id"): ("fk_contract_templates_progetto_id", "projects", "SET NULL"),
    }
    for (table, col), (name, reftable, ondelete) in fks.items():
        existing_fks = {fk["name"] for fk in inspector.get_foreign_keys(table)}
        fk_cols = {tuple(fk["constrained_columns"]) for fk in inspector.get_foreign_keys(table)}
        if name not in existing_fks and (col,) not in fk_cols:
            op.create_foreign_key(name, table, reftable, [col], ["id"], ondelete=ondelete)

    # ── 10. Indici mancanti dichiarati dai modelli ───────────────────
    # Difensivo: su un DB costruito dalla sola catena storica alcune
    # colonne potrebbero mancare (drift storico della catena, censito nel
    # REMEDIATION_LOG); l'indice viene creato solo se la colonna esiste.
    existing = _existing_indexes(bind)
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    for name, table, cols, unique in INDEXES_TO_CREATE:
        if name in existing or table not in tables:
            continue
        table_cols = _existing_columns(bind, table)
        if all(col in table_cols for col in cols):
            op.create_index(name, table, cols, unique=unique)


def downgrade() -> None:
    # Best effort: ripristina solo cio' che e' reversibile senza perdita.
    bind = op.get_bind()
    existing = _existing_indexes(bind)
    for name, table, cols, unique in INDEXES_TO_CREATE:
        if name in existing:
            op.drop_index(name, table_name=table)
    for old, new in INDEX_RENAMES:
        if new in _existing_indexes(bind):
            op.execute(sa.text(f'ALTER INDEX "{new}" RENAME TO "{old}"'))
    op.alter_column("projects", "ente_erogatore",
                    existing_type=sa.String(length=100),
                    type_=sa.VARCHAR(length=50),
                    existing_nullable=True)
    op.add_column("agent_runs", sa.Column("agent_name", sa.String(length=100), nullable=True))
    op.add_column("agent_suggestions", sa.Column("agent_name", sa.String(length=100), nullable=True))
    op.add_column("agent_suggestions", sa.Column("confidence", sa.Float(), nullable=True))
    op.add_column("agent_review_actions", sa.Column("reviewed_by", sa.String(length=100), nullable=True))
    op.add_column("agent_review_actions", sa.Column("created_at", sa.TIMESTAMP(), nullable=True))
    op.execute(sa.text("UPDATE agent_review_actions SET created_at = reviewed_at"))
    if "giustificativo_spesa" in sa.inspect(bind).get_table_names():
        op.drop_table("giustificativo_spesa")
