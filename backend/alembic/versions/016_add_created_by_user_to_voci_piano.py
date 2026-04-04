"""Add created_by_user to voci_piano_finanziario and collaborator_id to consulenti

Revision ID: 016
Revises: 015
Create Date: 2026-04-03
"""
from alembic import op
import sqlalchemy as sa

revision = '016'
down_revision = '015'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('voci_piano_finanziario', sa.Column('created_by_user', sa.String(100), nullable=True))

    op.add_column('consulenti', sa.Column('collaborator_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'consulenti_collaborator_id_fkey', 'consulenti', 'collaborators',
        ['collaborator_id'], ['id'], ondelete='SET NULL'
    )
    op.create_index('ix_consulenti_collaborator_id', 'consulenti', ['collaborator_id'], unique=True)

def downgrade():
    op.drop_index('ix_consulenti_collaborator_id', table_name='consulenti')
    op.drop_constraint('consulenti_collaborator_id_fkey', 'consulenti', type_='foreignkey')
    op.drop_column('consulenti', 'collaborator_id')

    op.drop_column('voci_piano_finanziario', 'created_by_user')
