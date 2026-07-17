"""ONDATA ARCHIVIO AVVISI V1: identita, revisioni e conoscenza.

Revision ID: 057
Revises: 056
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "057"
down_revision = "056"
branch_labels = None
depends_on = None


FONDI = "'fondimpresa','formazienda','fapi','regionale','altro'"
STATI_AVVISO = "'bozza','attivo','in_scadenza','scaduto','archiviato'"
STATI_DATO = "'proposta','validata','rifiutata','superata'"
CATEGORIE = (
    "'massimali','parametri_costo','destinatari','beneficiari','aiuti_di_stato',"
    "'presentazione','valutazione','attuazione','rendicontazione','delega','variazioni','altro'"
)


def upgrade():
    op.add_column("avvisi", sa.Column("fondo", sa.String(20), nullable=True))
    op.add_column("avvisi", sa.Column("numero", sa.String(50), nullable=True))
    op.add_column("avvisi", sa.Column("anno", sa.Integer(), nullable=True))
    op.add_column("avvisi", sa.Column("titolo", sa.String(300), nullable=True))
    op.add_column("avvisi", sa.Column("descrizione_breve", sa.Text(), nullable=True))
    op.add_column("avvisi", sa.Column("stato", sa.String(20), nullable=True))

    op.execute(
        """
        UPDATE avvisi
        SET fondo = CASE lower(trim(ente_erogatore))
                WHEN 'fondimpresa' THEN 'fondimpresa'
                WHEN 'formazienda' THEN 'formazienda'
                WHEN 'fapi' THEN 'fapi'
                WHEN 'regionale' THEN 'regionale'
                ELSE 'altro'
            END,
            numero = split_part(codice, '/', 1),
            anno = CASE
                WHEN split_part(codice, '/', 2) ~ '^[0-9]{4}$'
                THEN split_part(codice, '/', 2)::integer
                ELSE NULL
            END,
            titolo = COALESCE(NULLIF(trim(descrizione), ''), ente_erogatore || ' - Avviso ' || codice),
            descrizione_breve = NULLIF(trim(descrizione), ''),
            stato = CASE WHEN is_active THEN 'attivo' ELSE 'archiviato' END
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM avvisi
                WHERE fondo IS NULL OR numero IS NULL OR trim(numero) = ''
                   OR anno IS NULL OR anno NOT BETWEEN 2000 AND 2100
                   OR titolo IS NULL OR trim(titolo) = '' OR stato IS NULL
            ) THEN
                RAISE EXCEPTION 'Backfill avvisi V1 incompleto: correggere i record legacy';
            END IF;
        END $$
        """
    )
    for column in ("fondo", "numero", "anno", "titolo", "stato"):
        op.alter_column("avvisi", column, nullable=False)
    op.alter_column("avvisi", "fondo", server_default="altro")
    op.alter_column("avvisi", "stato", server_default="bozza")
    op.create_check_constraint("ck_avvisi_fondo", "avvisi", f"fondo IN ({FONDI})")
    op.create_check_constraint("ck_avvisi_stato", "avvisi", f"stato IN ({STATI_AVVISO})")
    op.create_check_constraint("ck_avvisi_anno", "avvisi", "anno BETWEEN 2000 AND 2100")
    op.create_index("ix_avvisi_fondo", "avvisi", ["fondo"])
    op.create_index("ix_avvisi_numero", "avvisi", ["numero"])
    op.create_index("ix_avvisi_anno", "avvisi", ["anno"])
    op.create_index("ix_avvisi_stato", "avvisi", ["stato"])
    op.create_index(
        "uq_avvisi_identita", "avvisi", ["fondo", "ente_erogatore", "numero", "anno"], unique=True
    )

    op.create_table(
        "avviso_revisioni",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("avviso_id", sa.Integer(), nullable=False),
        sa.Column("numero_revisione", sa.Integer(), nullable=False),
        sa.Column("etichetta_revisione", sa.String(50), nullable=True),
        sa.Column("revisione_precedente_id", sa.Integer(), nullable=True),
        sa.Column("titolo", sa.String(300), nullable=False),
        sa.Column("descrizione_breve", sa.Text(), nullable=True),
        sa.Column("data_pubblicazione", sa.Date(), nullable=True),
        sa.Column("data_scadenza_presentazione", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_md_path", sa.String(500), nullable=True),
        sa.Column("cleaned_md_path", sa.String(500), nullable=True),
        sa.Column("source_pdf_path", sa.String(500), nullable=True),
        sa.Column("original_filename", sa.String(255), nullable=True),
        sa.Column("source_sha256", sa.String(64), nullable=True),
        sa.Column("stato_estrazione", sa.String(30), nullable=False, server_default="caricato"),
        sa.Column("diff_from_previous", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("extraction_run_id", sa.Integer(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["avviso_id"], ["avvisi.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["revisione_precedente_id"], ["avviso_revisioni.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["extraction_run_id"], ["agent_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("avviso_id", "numero_revisione", name="uq_avviso_revisioni_numero"),
        sa.UniqueConstraint("avviso_id", "source_sha256", name="uq_avviso_revisioni_sha256"),
        sa.CheckConstraint("numero_revisione > 0", name="ck_avviso_revisioni_numero_positivo"),
        sa.CheckConstraint(
            "stato_estrazione IN ('caricato','pulito','segmentato','in_estrazione','estratto','errore')",
            name="ck_avviso_revisioni_stato_estrazione",
        ),
    )
    for name in (
        "id", "avviso_id", "revisione_precedente_id", "data_pubblicazione",
        "data_scadenza_presentazione", "stato_estrazione", "extraction_run_id",
        "created_by_user_id", "created_at",
    ):
        op.create_index(f"ix_avviso_revisioni_{name}", "avviso_revisioni", [name])

    op.execute(
        """
        INSERT INTO avviso_revisioni (
            avviso_id, numero_revisione, etichetta_revisione, titolo,
            descrizione_breve, stato_estrazione
        )
        SELECT id, 1, 'import legacy', titolo, descrizione_breve, 'caricato'
        FROM avvisi
        """
    )
    op.add_column("avvisi", sa.Column("revisione_corrente_id", sa.Integer(), nullable=True))
    op.execute(
        """
        UPDATE avvisi AS a SET revisione_corrente_id = r.id
        FROM avviso_revisioni AS r
        WHERE r.avviso_id = a.id AND r.numero_revisione = 1
        """
    )
    op.create_foreign_key(
        "fk_avvisi_revisione_corrente", "avvisi", "avviso_revisioni",
        ["revisione_corrente_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_avvisi_revisione_corrente_id", "avvisi", ["revisione_corrente_id"])

    _create_rules_table()
    _create_deadlines_table()
    _create_documents_table()
    _create_knowledge_tables()

    op.add_column("projects", sa.Column("avviso_revisione_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_projects_avviso_revisione", "projects", "avviso_revisioni",
        ["avviso_revisione_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_projects_avviso_revisione_id", "projects", ["avviso_revisione_id"])
    op.execute(
        """
        UPDATE projects AS p SET avviso_revisione_id = a.revisione_corrente_id
        FROM avvisi AS a WHERE p.avviso_id = a.id
        """
    )
    op.create_check_constraint(
        "ck_projects_avviso_revisione_requires_avviso", "projects",
        "avviso_revisione_id IS NULL OR avviso_id IS NOT NULL",
    )

    op.add_column("piani_finanziari", sa.Column("avviso_revisione_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_piani_avviso_revisione", "piani_finanziari", "avviso_revisioni",
        ["avviso_revisione_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_piani_finanziari_avviso_revisione_id", "piani_finanziari", ["avviso_revisione_id"])
    op.execute(
        """
        UPDATE piani_finanziari AS pf SET avviso_revisione_id = a.revisione_corrente_id
        FROM avvisi AS a WHERE pf.avviso_pf_id = a.id
        """
    )
    op.create_check_constraint(
        "ck_piani_avviso_revisione_requires_avviso", "piani_finanziari",
        "avviso_revisione_id IS NULL OR avviso_pf_id IS NOT NULL",
    )


def _create_rules_table():
    op.create_table(
        "avviso_regole",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("avviso_revisione_id", sa.Integer(), nullable=False),
        sa.Column("categoria", sa.String(30), nullable=False),
        sa.Column("sottocategoria", sa.String(80), nullable=True),
        sa.Column("chiave", sa.String(150), nullable=False),
        sa.Column("valore", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("tipo_valore", sa.String(30), nullable=False, server_default="oggetto"),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("unita", sa.String(50), nullable=True),
        sa.Column("applicabilita", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("testo_originale", sa.Text(), nullable=False),
        sa.Column("riferimento_articolo", sa.String(120), nullable=True),
        sa.Column("riferimento_sezione", sa.String(200), nullable=True),
        sa.Column("riferimento_pagina", sa.String(50), nullable=True),
        sa.Column("source_quote_sha256", sa.String(64), nullable=True),
        sa.Column("stato", sa.String(20), nullable=False, server_default="proposta"),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("needs_careful_review", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("origin_suggestion_id", sa.Integer(), nullable=True),
        sa.Column("carried_from_rule_id", sa.Integer(), nullable=True),
        sa.Column("supersedes_rule_id", sa.Integer(), nullable=True),
        sa.Column("validata_da_user_id", sa.Integer(), nullable=True),
        sa.Column("validata_il", sa.DateTime(timezone=True), nullable=True),
        sa.Column("nota_revisione", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["avviso_revisione_id"], ["avviso_revisioni.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["origin_suggestion_id"], ["agent_suggestions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["carried_from_rule_id"], ["avviso_regole.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["supersedes_rule_id"], ["avviso_regole.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["validata_da_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(f"categoria IN ({CATEGORIE})", name="ck_avviso_regole_categoria"),
        sa.CheckConstraint(f"stato IN ({STATI_DATO})", name="ck_avviso_regole_stato"),
        sa.CheckConstraint("confidence IS NULL OR confidence BETWEEN 0 AND 1", name="ck_avviso_regole_confidence"),
        sa.CheckConstraint("length(trim(chiave)) > 0", name="ck_avviso_regole_chiave_non_vuota"),
        sa.CheckConstraint("length(trim(testo_originale)) > 0", name="ck_avviso_regole_testo_non_vuoto"),
        sa.CheckConstraint(
            "stato <> 'validata' OR (validata_da_user_id IS NOT NULL AND validata_il IS NOT NULL)",
            name="ck_avviso_regole_validazione_completa",
        ),
    )
    for name in ("id", "avviso_revisione_id", "categoria", "sottocategoria", "chiave", "stato", "origin_suggestion_id", "validata_da_user_id", "created_at"):
        op.create_index(f"ix_avviso_regole_{name}", "avviso_regole", [name])
    op.create_index("ix_avviso_regole_revision_categoria_chiave", "avviso_regole", ["avviso_revisione_id", "categoria", "chiave"])
    op.create_index("ix_avviso_regole_revision_stato", "avviso_regole", ["avviso_revisione_id", "stato"])


def _create_deadlines_table():
    op.create_table(
        "avviso_scadenze",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("avviso_revisione_id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(30), nullable=False),
        sa.Column("data", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finestra_inizio", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finestra_fine", sa.DateTime(timezone=True), nullable=True),
        sa.Column("descrizione", sa.Text(), nullable=False),
        sa.Column("tassativa", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("condizione", sa.Text(), nullable=True),
        sa.Column("applicabilita", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("testo_originale", sa.Text(), nullable=False),
        sa.Column("riferimento_articolo", sa.String(120), nullable=True),
        sa.Column("stato", sa.String(20), nullable=False, server_default="proposta"),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("needs_careful_review", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("origin_suggestion_id", sa.Integer(), nullable=True),
        sa.Column("validata_da_user_id", sa.Integer(), nullable=True),
        sa.Column("validata_il", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["avviso_revisione_id"], ["avviso_revisioni.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["origin_suggestion_id"], ["agent_suggestions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["validata_da_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("avviso_revisione_id", "tipo", "data", "descrizione", name="uq_avviso_scadenze_esatta"),
        sa.CheckConstraint("tipo IN ('presentazione','avvio','chiusura','rendicontazione','altro')", name="ck_avviso_scadenze_tipo"),
        sa.CheckConstraint(f"stato IN ({STATI_DATO})", name="ck_avviso_scadenze_stato"),
        sa.CheckConstraint("confidence IS NULL OR confidence BETWEEN 0 AND 1", name="ck_avviso_scadenze_confidence"),
        sa.CheckConstraint("finestra_inizio IS NULL OR finestra_fine IS NULL OR finestra_fine >= finestra_inizio", name="ck_avviso_scadenze_finestra"),
        sa.CheckConstraint("stato <> 'validata' OR (validata_da_user_id IS NOT NULL AND validata_il IS NOT NULL)", name="ck_avviso_scadenze_validazione_completa"),
    )
    for name in ("id", "avviso_revisione_id", "tipo", "data", "stato", "origin_suggestion_id", "created_at"):
        op.create_index(f"ix_avviso_scadenze_{name}", "avviso_scadenze", [name])
    op.create_index("ix_avviso_scadenze_data_stato", "avviso_scadenze", ["data", "stato"])


def _create_documents_table():
    op.create_table(
        "avviso_documenti",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("avviso_id", sa.Integer(), nullable=False),
        sa.Column("avviso_revisione_id", sa.Integer(), nullable=True),
        sa.Column("tipo", sa.String(30), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["avviso_id"], ["avvisi.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["avviso_revisione_id"], ["avviso_revisioni.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("avviso_id", "sha256", name="uq_avviso_documenti_sha256"),
        sa.CheckConstraint("tipo IN ('avviso','allegato','vademecum','manuale_gestione','nota_interna','controdeduzione','altro')", name="ck_avviso_documenti_tipo"),
        sa.CheckConstraint("length(sha256) = 64", name="ck_avviso_documenti_sha256"),
    )
    for name in ("id", "avviso_id", "avviso_revisione_id", "tipo", "created_at"):
        op.create_index(f"ix_avviso_documenti_{name}", "avviso_documenti", [name])
    op.create_index("ix_avviso_documenti_avviso_tipo", "avviso_documenti", ["avviso_id", "tipo"])


def _create_knowledge_tables():
    op.create_table(
        "avviso_conoscenze",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("avviso_id", sa.Integer(), nullable=False),
        sa.Column("avviso_revisione_id", sa.Integer(), nullable=True),
        sa.Column("tipo", sa.String(30), nullable=False, server_default="nota_operativa"),
        sa.Column("contenuto", sa.Text(), nullable=False),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("riservatezza", sa.String(20), nullable=False, server_default="interna"),
        sa.Column("autore_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["avviso_id"], ["avvisi.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["avviso_revisione_id"], ["avviso_revisioni.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["autore_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint("length(trim(contenuto)) > 0", name="ck_avviso_conoscenze_contenuto"),
        sa.CheckConstraint("riservatezza IN ('interna','ristretta')", name="ck_avviso_conoscenze_riservatezza"),
    )
    for name in ("id", "avviso_id", "avviso_revisione_id", "tipo", "autore_user_id", "created_at"):
        op.create_index(f"ix_avviso_conoscenze_{name}", "avviso_conoscenze", [name])

    op.create_table(
        "avviso_esiti_progetto",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("avviso_id", sa.Integer(), nullable=False),
        sa.Column("avviso_revisione_id", sa.Integer(), nullable=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("piano_finanziario_id", sa.Integer(), nullable=True),
        sa.Column("esito", sa.String(30), nullable=False),
        sa.Column("data_evento", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("importo_richiesto", sa.Numeric(12, 2), nullable=True),
        sa.Column("importo_ammesso", sa.Numeric(12, 2), nullable=True),
        sa.Column("importo_rendicontato", sa.Numeric(12, 2), nullable=True),
        sa.Column("importo_riconosciuto", sa.Numeric(12, 2), nullable=True),
        sa.Column("importo_decurtato", sa.Numeric(12, 2), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("documento_id", sa.Integer(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["avviso_id"], ["avvisi.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["avviso_revisione_id"], ["avviso_revisioni.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["piano_finanziario_id"], ["piani_finanziari.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["documento_id"], ["avviso_documenti.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint("esito IN ('approvato','rigettato','attuato','rendicontato','decurtato','controdedotto')", name="ck_avviso_esiti_esito"),
        sa.CheckConstraint("COALESCE(importo_richiesto,0) >= 0 AND COALESCE(importo_ammesso,0) >= 0 AND COALESCE(importo_rendicontato,0) >= 0 AND COALESCE(importo_riconosciuto,0) >= 0 AND COALESCE(importo_decurtato,0) >= 0", name="ck_avviso_esiti_importi_non_negativi"),
    )
    for name in ("id", "avviso_id", "avviso_revisione_id", "project_id", "piano_finanziario_id", "esito", "data_evento", "created_at"):
        op.create_index(f"ix_avviso_esiti_progetto_{name}", "avviso_esiti_progetto", [name])
    op.create_index("ix_avviso_esiti_project_data", "avviso_esiti_progetto", ["project_id", "data_evento"])


def downgrade():
    op.drop_constraint("ck_piani_avviso_revisione_requires_avviso", "piani_finanziari", type_="check")
    op.drop_index("ix_piani_finanziari_avviso_revisione_id", table_name="piani_finanziari")
    op.drop_constraint("fk_piani_avviso_revisione", "piani_finanziari", type_="foreignkey")
    op.drop_column("piani_finanziari", "avviso_revisione_id")
    op.drop_constraint("ck_projects_avviso_revisione_requires_avviso", "projects", type_="check")
    op.drop_index("ix_projects_avviso_revisione_id", table_name="projects")
    op.drop_constraint("fk_projects_avviso_revisione", "projects", type_="foreignkey")
    op.drop_column("projects", "avviso_revisione_id")
    op.drop_table("avviso_esiti_progetto")
    op.drop_table("avviso_conoscenze")
    op.drop_table("avviso_documenti")
    op.drop_table("avviso_scadenze")
    op.drop_table("avviso_regole")
    op.drop_index("ix_avvisi_revisione_corrente_id", table_name="avvisi")
    op.drop_constraint("fk_avvisi_revisione_corrente", "avvisi", type_="foreignkey")
    op.drop_column("avvisi", "revisione_corrente_id")
    op.drop_table("avviso_revisioni")
    op.drop_index("uq_avvisi_identita", table_name="avvisi")
    for name in ("stato", "anno", "numero", "fondo"):
        op.drop_index(f"ix_avvisi_{name}", table_name="avvisi")
    op.drop_constraint("ck_avvisi_anno", "avvisi", type_="check")
    op.drop_constraint("ck_avvisi_stato", "avvisi", type_="check")
    op.drop_constraint("ck_avvisi_fondo", "avvisi", type_="check")
    for column in ("stato", "descrizione_breve", "titolo", "anno", "numero", "fondo"):
        op.drop_column("avvisi", column)
