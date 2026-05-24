"""add production readiness indexes

Revision ID: 036
Revises: 035
Create Date: 2026-04-21
"""
from alembic import op

revision = '036'
down_revision = '035'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        'ix_email_inbox_items_created_at',
        'email_inbox_items',
        ['created_at'],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        'ix_documenti_richiesti_stato',
        'documenti_richiesti',
        ['stato'],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        'ix_attendances_collaborator_project_date',
        'attendances',
        ['collaborator_id', 'project_id', 'date'],
        unique=False,
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index('ix_attendances_collaborator_project_date', table_name='attendances', if_exists=True)
    op.drop_index('ix_documenti_richiesti_stato', table_name='documenti_richiesti', if_exists=True)
    op.drop_index('ix_email_inbox_items_created_at', table_name='email_inbox_items', if_exists=True)
