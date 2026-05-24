"""add timesheet_generati table

Revision ID: 033
Revises: 032
Create Date: 2026-04-20
"""
from alembic import op
import sqlalchemy as sa

revision = '033'
down_revision = '032'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'timesheet_generati',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('assignment_id', sa.Integer, sa.ForeignKey('assignments.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('pdf_path', sa.String(500), nullable=False),
        sa.Column('pdf_filename', sa.String(255), nullable=False),
        sa.Column('generato_il', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('generato_da', sa.String(100), nullable=True),
        sa.Column('bloccato', sa.Boolean, nullable=False, server_default=sa.text('true')),
        sa.Column('sbloccato_da', sa.String(100), nullable=True),
        sa.Column('sbloccato_il', sa.DateTime(timezone=True), nullable=True),
        sa.Column('note', sa.Text, nullable=True),
    )
    op.create_index(
        'idx_timesheet_generati_assignment',
        'timesheet_generati',
        ['assignment_id'],
    )


def downgrade() -> None:
    op.drop_table('timesheet_generati')
