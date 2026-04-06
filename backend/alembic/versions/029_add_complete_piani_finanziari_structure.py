"""add complete piani finanziari structure

Revision ID: 029_piani_fin_complete
Revises: a10d08b5e238
Create Date: 2026-04-05 10:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "029_piani_fin_complete"
down_revision = "a10d08b5e238"
branch_labels = None
depends_on = None


def _drop_fk_if_exists(table_name: str, constrained_columns: set[str]) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for fk in inspector.get_foreign_keys(table_name):
        cols = set(fk.get("constrained_columns") or [])
        if cols == constrained_columns and fk.get("name"):
            op.drop_constraint(fk["name"], table_name, type_="foreignkey")


def upgrade() -> None:
    op.create_table(
        "template_piani_finanziari",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("codice", sa.String(length=50), nullable=False),
        sa.Column("nome", sa.String(length=200), nullable=False),
        sa.Column("tipo_fondo", sa.String(length=50), nullable=False),
        sa.Column("versione", sa.String(length=20), nullable=True, server_default="1.0"),
        sa.Column("descrizione", sa.Text(), nullable=True),
        sa.Column("note_compilazione", sa.Text(), nullable=True),
        sa.Column("categorie_spesa", sa.Text(), nullable=True),
        sa.Column("percentuale_max_docenza", sa.Float(), nullable=True, server_default="100"),
        sa.Column("percentuale_max_coordinamento", sa.Float(), nullable=True, server_default="15"),
        sa.Column("percentuale_max_materiali", sa.Float(), nullable=True, server_default="20"),
        sa.Column("ore_minime_corso", sa.Integer(), nullable=True, server_default="8"),
        sa.Column("ore_massime_corso", sa.Integer(), nullable=True, server_default="200"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("codice", name="uq_template_piani_finanziari_codice"),
    )
    op.create_index("idx_template_piano_tipo_fondo", "template_piani_finanziari", ["tipo_fondo"], unique=False)
    op.create_index("idx_template_piano_active", "template_piani_finanziari", ["is_active"], unique=False)

    op.create_table(
        "avvisi_piani_finanziari",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("codice_avviso", sa.String(length=100), nullable=False),
        sa.Column("titolo", sa.String(length=300), nullable=False),
        sa.Column("descrizione", sa.Text(), nullable=True),
        sa.Column("data_apertura", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data_chiusura", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data_rendicontazione", sa.DateTime(timezone=True), nullable=True),
        sa.Column("budget_totale_avviso", sa.Float(), nullable=True),
        sa.Column("budget_max_progetto", sa.Float(), nullable=True),
        sa.Column("budget_min_progetto", sa.Float(), nullable=True),
        sa.Column("ore_minime", sa.Integer(), nullable=True),
        sa.Column("ore_massime", sa.Integer(), nullable=True),
        sa.Column("partecipanti_min", sa.Integer(), nullable=True),
        sa.Column("partecipanti_max", sa.Integer(), nullable=True),
        sa.Column("costo_ora_formazione_max", sa.Float(), nullable=True),
        sa.Column("costo_ora_docenza_max", sa.Float(), nullable=True),
        sa.Column("costo_ora_tutoraggio_max", sa.Float(), nullable=True),
        sa.Column("costo_ora_coordinamento_max", sa.Float(), nullable=True),
        sa.Column("documenti_richiesti", sa.Text(), nullable=True),
        sa.Column("stato", sa.String(length=20), nullable=False, server_default="aperto"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["template_id"], ["template_piani_finanziari.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("codice_avviso", name="uq_avvisi_piani_finanziari_codice_avviso"),
    )
    op.create_index("idx_avviso_piano_template", "avvisi_piani_finanziari", ["template_id"], unique=False)
    op.create_index("idx_avviso_piano_stato", "avvisi_piani_finanziari", ["stato"], unique=False)
    op.create_index("idx_avviso_piano_date", "avvisi_piani_finanziari", ["data_apertura", "data_chiusura"], unique=False)

    with op.batch_alter_table("piani_finanziari") as batch_op:
        batch_op.add_column(sa.Column("legacy_template_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("legacy_avviso_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("codice_piano", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("budget_approvato", sa.Float(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("budget_rimanente", sa.Float(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("data_approvazione", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("data_rendicontazione", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("note_ente", sa.Text(), nullable=True))

    op.execute(
        """
        UPDATE piani_finanziari
        SET legacy_template_id = template_id,
            legacy_avviso_id = avviso_id,
            template_id = NULL,
            avviso_id = NULL,
            budget_approvato = COALESCE(budget_approvato, 0),
            budget_rimanente = COALESCE(budget_totale, 0) - COALESCE(budget_utilizzato, 0)
        """
    )

    _drop_fk_if_exists("piani_finanziari", {"template_id"})
    _drop_fk_if_exists("piani_finanziari", {"avviso_id"})
    op.create_foreign_key(
        "fk_piani_finanziari_template_piani_finanziari",
        "piani_finanziari",
        "template_piani_finanziari",
        ["template_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_piani_finanziari_avvisi_piani_finanziari",
        "piani_finanziari",
        "avvisi_piani_finanziari",
        ["avviso_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_piani_finanziari_codice_piano", "piani_finanziari", ["codice_piano"], unique=True)
    op.create_index("idx_piano_template_avviso", "piani_finanziari", ["template_id", "avviso_id"], unique=False)

    with op.batch_alter_table("voci_piano_finanziario") as batch_op:
        batch_op.add_column(sa.Column("assignment_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("sottocategoria", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("mansione_riferimento", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("ore_previste", sa.Float(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("ore_effettive", sa.Float(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("tariffa_oraria", sa.Float(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("importo_approvato", sa.Float(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("importo_validato", sa.Float(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("stato", sa.String(length=20), nullable=False, server_default="previsto"))
        batch_op.add_column(sa.Column("note", sa.Text(), nullable=True))
        batch_op.create_foreign_key(
            "fk_voci_piano_finanziario_assignment_id_assignments",
            "assignments",
            ["assignment_id"],
            ["id"],
            ondelete="SET NULL",
        )

    op.execute(
        """
        UPDATE voci_piano_finanziario
        SET ore_previste = COALESCE(ore, 0),
            ore_effettive = COALESCE(ore, 0),
            importo_approvato = 0,
            importo_validato = 0,
            stato = CASE
                WHEN COALESCE(importo_consuntivo, 0) > 0 THEN 'rendicontato'
                ELSE 'previsto'
            END
        """
    )

    op.create_index("idx_voci_piano_assignment", "voci_piano_finanziario", ["assignment_id"], unique=False)
    op.create_index("idx_voci_piano_mansione", "voci_piano_finanziario", ["mansione_riferimento"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_voci_piano_mansione", table_name="voci_piano_finanziario")
    op.drop_index("idx_voci_piano_assignment", table_name="voci_piano_finanziario")
    with op.batch_alter_table("voci_piano_finanziario") as batch_op:
        batch_op.drop_constraint("fk_voci_piano_finanziario_assignment_id_assignments", type_="foreignkey")
        batch_op.drop_column("note")
        batch_op.drop_column("stato")
        batch_op.drop_column("importo_validato")
        batch_op.drop_column("importo_approvato")
        batch_op.drop_column("tariffa_oraria")
        batch_op.drop_column("ore_effettive")
        batch_op.drop_column("ore_previste")
        batch_op.drop_column("mansione_riferimento")
        batch_op.drop_column("sottocategoria")
        batch_op.drop_column("assignment_id")

    op.drop_index("idx_piano_template_avviso", table_name="piani_finanziari")
    op.drop_index("ix_piani_finanziari_codice_piano", table_name="piani_finanziari")
    op.drop_constraint("fk_piani_finanziari_avvisi_piani_finanziari", "piani_finanziari", type_="foreignkey")
    op.drop_constraint("fk_piani_finanziari_template_piani_finanziari", "piani_finanziari", type_="foreignkey")
    op.execute(
        """
        UPDATE piani_finanziari
        SET template_id = legacy_template_id,
            avviso_id = legacy_avviso_id
        """
    )
    with op.batch_alter_table("piani_finanziari") as batch_op:
        batch_op.drop_column("note_ente")
        batch_op.drop_column("data_rendicontazione")
        batch_op.drop_column("data_approvazione")
        batch_op.drop_column("budget_rimanente")
        batch_op.drop_column("budget_approvato")
        batch_op.drop_column("codice_piano")
        batch_op.drop_column("legacy_avviso_id")
        batch_op.drop_column("legacy_template_id")

    op.drop_index("idx_avviso_piano_date", table_name="avvisi_piani_finanziari")
    op.drop_index("idx_avviso_piano_stato", table_name="avvisi_piani_finanziari")
    op.drop_index("idx_avviso_piano_template", table_name="avvisi_piani_finanziari")
    op.drop_table("avvisi_piani_finanziari")

    op.drop_index("idx_template_piano_active", table_name="template_piani_finanziari")
    op.drop_index("idx_template_piano_tipo_fondo", table_name="template_piani_finanziari")
    op.drop_table("template_piani_finanziari")
