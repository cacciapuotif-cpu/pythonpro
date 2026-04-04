"""Add collaborator_id FK to voci piano, righe nominativo, budget consulenti

Revision ID: 015
Revises: 014
Create Date: 2026-04-03
"""
from alembic import op
import sqlalchemy as sa

revision = '015'
down_revision = '014'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('voci_piano_finanziario', sa.Column('collaborator_id', sa.Integer(), nullable=True))
    op.create_foreign_key('voci_piano_finanziario_collaborator_id_fkey', 'voci_piano_finanziario', 'collaborators', ['collaborator_id'], ['id'], ondelete='SET NULL')
    op.create_index('ix_voci_piano_finanziario_collaborator_id', 'voci_piano_finanziario', ['collaborator_id'])

    op.add_column('righe_nominativo_fondimpresa', sa.Column('collaborator_id', sa.Integer(), nullable=True))
    op.create_foreign_key('righe_nominativo_fondimpresa_collaborator_id_fkey', 'righe_nominativo_fondimpresa', 'collaborators', ['collaborator_id'], ['id'], ondelete='SET NULL')
    op.create_index('ix_righe_nominativo_fondimpresa_collaborator_id', 'righe_nominativo_fondimpresa', ['collaborator_id'])

    op.add_column('budget_consulenti_fondimpresa', sa.Column('collaborator_id', sa.Integer(), nullable=True))
    op.create_foreign_key('budget_consulenti_fondimpresa_collaborator_id_fkey', 'budget_consulenti_fondimpresa', 'collaborators', ['collaborator_id'], ['id'], ondelete='SET NULL')
    op.create_index('ix_budget_consulenti_fondimpresa_collaborator_id', 'budget_consulenti_fondimpresa', ['collaborator_id'])


def downgrade():
    op.drop_index('ix_budget_consulenti_fondimpresa_collaborator_id', 'budget_consulenti_fondimpresa')
    op.drop_constraint('budget_consulenti_fondimpresa_collaborator_id_fkey', 'budget_consulenti_fondimpresa', type_='foreignkey')
    op.drop_column('budget_consulenti_fondimpresa', 'collaborator_id')

    op.drop_index('ix_righe_nominativo_fondimpresa_collaborator_id', 'righe_nominativo_fondimpresa')
    op.drop_constraint('righe_nominativo_fondimpresa_collaborator_id_fkey', 'righe_nominativo_fondimpresa', type_='foreignkey')
    op.drop_column('righe_nominativo_fondimpresa', 'collaborator_id')

    op.drop_index('ix_voci_piano_finanziario_collaborator_id', 'voci_piano_finanziario')
    op.drop_constraint('voci_piano_finanziario_collaborator_id_fkey', 'voci_piano_finanziario', type_='foreignkey')
    op.drop_column('voci_piano_finanziario', 'collaborator_id')
