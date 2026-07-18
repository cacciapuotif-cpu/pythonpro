"""Attività predittive e playbook versionati."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "058"
down_revision = "057"
branch_labels = None
depends_on = None
JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
FONDI = "'fondimpresa','formazienda','fapi','regionale','altro'"
FASI = "'presentazione','avvio','gestione','rendicontazione'"


def upgrade():
    op.create_table(
        "playbooks",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("nome", sa.String(200), nullable=False),
        sa.Column("fondo", sa.String(20), nullable=False, server_default="altro"),
        sa.Column("ente_erogatore", sa.String(100)), sa.Column("descrizione", sa.Text()),
        sa.Column("versione_corrente_id", sa.Integer()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("fondo", "ente_erogatore", "nome", name="uq_playbooks_identita"),
        sa.CheckConstraint(f"fondo IN ({FONDI})", name="ck_playbooks_fondo"),
    )
    op.create_table(
        "playbook_versioni",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("playbook_id", sa.Integer(), nullable=False), sa.Column("numero_versione", sa.Integer(), nullable=False),
        sa.Column("versione_precedente_id", sa.Integer()), sa.Column("note", sa.Text()),
        sa.Column("created_by_user_id", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["playbook_id"], ["playbooks.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["versione_precedente_id"], ["playbook_versioni.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("playbook_id", "numero_versione", name="uq_playbook_versioni_numero"),
        sa.CheckConstraint("numero_versione > 0", name="ck_playbook_versioni_numero_positivo"),
    )
    op.create_foreign_key("fk_playbooks_versione_corrente", "playbooks", "playbook_versioni", ["versione_corrente_id"], ["id"], ondelete="SET NULL")
    op.create_table(
        "playbook_voci",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("playbook_versione_id", sa.Integer(), nullable=False), sa.Column("fase", sa.String(20), nullable=False),
        sa.Column("ordine", sa.Integer(), nullable=False, server_default="0"), sa.Column("titolo", sa.String(300), nullable=False),
        sa.Column("descrizione", sa.Text()), sa.Column("contenuto", JSON, nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"), sa.Column("applicabilita", JSON),
        sa.Column("origine", sa.String(20), nullable=False, server_default="manuale"), sa.Column("testo_originale", sa.Text()),
        sa.Column("riferimento_articolo", sa.String(100)), sa.Column("stato", sa.String(20), nullable=False, server_default="proposta"),
        sa.Column("confidence", sa.Numeric(5, 4)), sa.Column("needs_careful_review", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("origin_suggestion_id", sa.Integer()), sa.Column("carried_from_voce_id", sa.Integer()),
        sa.Column("validata_da_user_id", sa.Integer()), sa.Column("validata_il", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["playbook_versione_id"], ["playbook_versioni.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["origin_suggestion_id"], ["agent_suggestions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["carried_from_voce_id"], ["playbook_voci.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["validata_da_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("playbook_versione_id", "fase", "titolo", name="uq_playbook_voci_titolo"),
        sa.CheckConstraint(f"fase IN ({FASI})", name="ck_playbook_voci_fase"), sa.CheckConstraint("length(trim(titolo)) > 0", name="ck_playbook_voci_titolo_non_vuoto"),
        sa.CheckConstraint("origine IN ('manuale','vademecum','regola')", name="ck_playbook_voci_origine"), sa.CheckConstraint("stato IN ('proposta','validata','rifiutata','superata')", name="ck_playbook_voci_stato"),
        sa.CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="ck_playbook_voci_confidence"), sa.CheckConstraint("(stato <> 'validata') OR (validata_da_user_id IS NOT NULL AND validata_il IS NOT NULL)", name="ck_playbook_voci_validazione_completa"),
    )
    op.create_table(
        "attivita_operative",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("avviso_revisione_id", sa.Integer()), sa.Column("playbook_voce_id", sa.Integer()), sa.Column("avviso_scadenza_id", sa.Integer()),
        sa.Column("fase", sa.String(20), nullable=False), sa.Column("ordine", sa.Integer(), nullable=False, server_default="0"), sa.Column("titolo", sa.String(300), nullable=False), sa.Column("descrizione", sa.Text()),
        sa.Column("stato", sa.String(20), nullable=False, server_default="da_fare"), sa.Column("scadenza", sa.Date()), sa.Column("tassativa", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("assegnatario_user_id", sa.Integer()), sa.Column("origin_suggestion_id", sa.Integer()), sa.Column("completata_da_user_id", sa.Integer()), sa.Column("completata_il", sa.DateTime(timezone=True)), sa.Column("note", sa.Text()), sa.Column("created_by_user_id", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["avviso_revisione_id"], ["avviso_revisioni.id"], ondelete="SET NULL"), sa.ForeignKeyConstraint(["playbook_voce_id"], ["playbook_voci.id"], ondelete="SET NULL"), sa.ForeignKeyConstraint(["avviso_scadenza_id"], ["avviso_scadenze.id"], ondelete="SET NULL"), sa.ForeignKeyConstraint(["origin_suggestion_id"], ["agent_suggestions.id"], ondelete="SET NULL"), sa.ForeignKeyConstraint(["assegnatario_user_id"], ["users.id"], ondelete="SET NULL"), sa.ForeignKeyConstraint(["completata_da_user_id"], ["users.id"], ondelete="SET NULL"), sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("project_id", "fase", "titolo", name="uq_attivita_operative_titolo"), sa.CheckConstraint(f"fase IN ({FASI})", name="ck_attivita_operative_fase"), sa.CheckConstraint("length(trim(titolo)) > 0", name="ck_attivita_operative_titolo_non_vuoto"), sa.CheckConstraint("stato IN ('da_fare','in_corso','completata','non_applicabile')", name="ck_attivita_operative_stato"), sa.CheckConstraint("(stato <> 'completata') OR (completata_da_user_id IS NOT NULL AND completata_il IS NOT NULL)", name="ck_attivita_completamento"),
    )
    op.create_table(
        "attivita_eventi",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("attivita_id", sa.Integer(), nullable=False), sa.Column("tipo_evento", sa.String(30), nullable=False), sa.Column("payload", JSON), sa.Column("actor_user_id", sa.Integer()), sa.Column("actor_agente", sa.String(50)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["attivita_id"], ["attivita_operative.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint("tipo_evento IN ('creata','stato_cambiato','scadenza_modificata','assegnata','nota','riaperta')", name="ck_attivita_eventi_tipo"), sa.CheckConstraint("actor_user_id IS NOT NULL OR actor_agente IS NOT NULL", name="ck_attivita_eventi_actor"),
    )
    for table, cols in (("playbooks", ["ente_erogatore"]), ("playbook_versioni", ["playbook_id"]), ("playbook_voci", ["playbook_versione_id", "fase", "stato"]), ("attivita_operative", ["project_id", "fase", "stato", "scadenza"]), ("attivita_eventi", ["attivita_id", "tipo_evento", "created_at"])):
        op.create_index(f"ix_{table}_{'_'.join(cols)}", table, cols)


def downgrade():
    op.drop_table("attivita_eventi")
    op.drop_table("attivita_operative")
    op.drop_table("playbook_voci")
    op.drop_constraint("fk_playbooks_versione_corrente", "playbooks", type_="foreignkey")
    op.drop_table("playbook_versioni")
    op.drop_table("playbooks")
