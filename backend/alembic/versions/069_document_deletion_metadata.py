"""DEL-01/DOC-01: stato e motivo sui documenti progetto."""
from alembic import op
import sqlalchemy as sa

revision = "069"
down_revision = "068"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("project_documents", sa.Column("stato", sa.String(20), nullable=False, server_default="corrente"))
    op.add_column("project_documents", sa.Column("annullato_motivo", sa.Text(), nullable=True))
    op.add_column("project_documents", sa.Column("source_removed", sa.Boolean(), nullable=False, server_default=sa.text("false")))

def downgrade() -> None:
    op.drop_column("project_documents", "source_removed")
    op.drop_column("project_documents", "annullato_motivo")
    op.drop_column("project_documents", "stato")
