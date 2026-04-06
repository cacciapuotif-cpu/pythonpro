"""add_documenti_richiesti

Revision ID: d3de21183882
Revises: 528d59380940
Create Date: 2026-04-04 14:55:36.284373+00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func


# revision identifiers, used by Alembic.
revision = 'd3de21183882'
down_revision = '528d59380940'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'documenti_richiesti',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('collaboratore_id', sa.Integer(), nullable=False),
        sa.Column('tipo_documento', sa.String(length=100), nullable=False),
        sa.Column('descrizione', sa.Text(), nullable=True),
        sa.Column('obbligatorio', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('data_richiesta', sa.DateTime(), nullable=False, server_default=func.now()),
        sa.Column('data_scadenza', sa.DateTime(), nullable=True),
        sa.Column('data_caricamento', sa.DateTime(), nullable=True),
        sa.Column('stato', sa.String(length=20), nullable=False, server_default=sa.text("'richiesto'")),
        sa.Column('file_path', sa.String(length=500), nullable=True),
        sa.Column('file_name', sa.String(length=255), nullable=True),
        sa.Column('note_operatore', sa.Text(), nullable=True),
        sa.Column('validato_da', sa.String(length=100), nullable=True),
        sa.Column('validato_il', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['collaboratore_id'], ['collaborators.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_documenti_richiesti_collaboratore_id'), 'documenti_richiesti', ['collaboratore_id'], unique=False)
    op.create_index(op.f('ix_documenti_richiesti_data_scadenza'), 'documenti_richiesti', ['data_scadenza'], unique=False)
    op.create_index(op.f('ix_documenti_richiesti_id'), 'documenti_richiesti', ['id'], unique=False)
    op.create_index(op.f('ix_documenti_richiesti_stato'), 'documenti_richiesti', ['stato'], unique=False)
    op.create_index(op.f('ix_documenti_richiesti_tipo_documento'), 'documenti_richiesti', ['tipo_documento'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_documenti_richiesti_tipo_documento'), table_name='documenti_richiesti')
    op.drop_index(op.f('ix_documenti_richiesti_stato'), table_name='documenti_richiesti')
    op.drop_index(op.f('ix_documenti_richiesti_id'), table_name='documenti_richiesti')
    op.drop_index(op.f('ix_documenti_richiesti_data_scadenza'), table_name='documenti_richiesti')
    op.drop_index(op.f('ix_documenti_richiesti_collaboratore_id'), table_name='documenti_richiesti')
    op.drop_table('documenti_richiesti')
