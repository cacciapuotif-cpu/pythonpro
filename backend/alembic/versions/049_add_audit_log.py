"""add audit log

Revision ID: 049
Revises: 048
Create Date: 2026-05-24
"""

from alembic import op
import sqlalchemy as sa

revision = "049"
down_revision = "048"
branch_labels = None
depends_on = None


def upgrade():
    if "audit_log" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table("audit_log",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("azione", sa.String(100), nullable=False),
            sa.Column("risorsa_tipo", sa.String(100), nullable=False),
            sa.Column("risorsa_id", sa.String(100), nullable=True),
            sa.Column("dati_prima", sa.Text(), nullable=True),
            sa.Column("dati_dopo", sa.Text(), nullable=True),
            sa.Column("ip_address_hash", sa.String(64), nullable=True),
            sa.Column("esito", sa.String(50), nullable=False, server_default="success"),
            sa.CheckConstraint("ip_address_hash IS NULL OR ip_address_hash ~ '^[a-f0-9]{64}$'", name="ck_audit_log_ip_sha256"),
        )
        op.create_index("ix_audit_log_timestamp", "audit_log", ["timestamp"])
        op.create_index("ix_audit_log_user_id", "audit_log", ["user_id"])
        op.create_index("ix_audit_log_risorsa", "audit_log", ["risorsa_tipo", "risorsa_id"])


def downgrade():
    if "audit_log" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("audit_log")
