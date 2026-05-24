"""add idempotency_key to agent_runs

Revision ID: 032
Revises: 031
Create Date: 2026-04-20
"""
from alembic import op
import sqlalchemy as sa

revision = '032'
down_revision = '031'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'agent_runs',
        sa.Column('idempotency_key', sa.String(64), nullable=True)
    )
    op.create_index(
        'idx_agent_run_idempotency_key',
        'agent_runs',
        ['idempotency_key'],
        unique=True,
        postgresql_where=sa.text('idempotency_key IS NOT NULL'),
    )


def downgrade() -> None:
    op.drop_index('idx_agent_run_idempotency_key', table_name='agent_runs')
    op.drop_column('agent_runs', 'idempotency_key')
