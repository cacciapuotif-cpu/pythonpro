"""Formazienda: classe dimensionale azienda + soggetti delegati progetto."""
from alembic import op
import sqlalchemy as sa

revision = "074"
down_revision = "073"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("aziende_clienti", sa.Column("classe_dimensionale", sa.String(10), nullable=True))
    op.create_table(
        "project_soggetti_delegati",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("ragione_sociale", sa.String(200), nullable=False),
        sa.Column("codice_fiscale", sa.String(16), nullable=True),
        sa.Column("partita_iva", sa.String(11), nullable=True),
        sa.Column("legale_rappresentante_nome", sa.String(100), nullable=True),
        sa.Column("legale_rappresentante_cognome", sa.String(100), nullable=True),
        sa.Column("tipologia", sa.String(50), nullable=True),
        sa.Column("importo", sa.Numeric(12, 2), nullable=True),
        sa.Column("percentuale", sa.Numeric(5, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("project_soggetti_delegati")
    op.drop_column("aziende_clienti", "classe_dimensionale")
