"""add fondo partecipazione dati_retributivi

Revision ID: 035
Revises: 034
Create Date: 2026-04-20
"""
from alembic import op
import sqlalchemy as sa

revision = '035'
down_revision = '034'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'fondi',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('nome', sa.String(100), nullable=False, unique=True),
        sa.Column('tipo', sa.String(50), nullable=True),
        sa.Column('descrizione', sa.Text, nullable=True),
        sa.Column('attivo', sa.Boolean, nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )

    op.add_column('allievo_project',
        sa.Column('id', sa.Integer, nullable=True)
    )
    op.add_column('allievo_project',
        sa.Column('ore_frequentate', sa.Float, nullable=True, server_default=sa.text('0'))
    )
    op.add_column('allievo_project',
        sa.Column('stato', sa.String(30), nullable=True, server_default=sa.text("'iscritto'"))
    )
    op.add_column('allievo_project',
        sa.Column('attestato_emesso', sa.Boolean, nullable=True, server_default=sa.text('false'))
    )
    op.add_column('allievo_project',
        sa.Column('note', sa.Text, nullable=True)
    )
    op.add_column('allievo_project',
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'))
    )

    op.create_table(
        'dati_retributivi',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('allievo_id', sa.Integer, sa.ForeignKey('allievi.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('project_id', sa.Integer, sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('ral_annua', sa.Float, nullable=True),
        sa.Column('costo_orario', sa.Float, nullable=True),
        sa.Column('ore_1720', sa.Float, nullable=True, server_default=sa.text('1720')),
        sa.Column('busta_paga_path', sa.String(500), nullable=True),
        sa.Column('busta_paga_filename', sa.String(255), nullable=True),
        sa.Column('periodo_riferimento', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('allievo_id', 'project_id', name='uq_dati_retributivi_allievo_project'),
    )
    op.create_index('idx_dati_retributivi_project', 'dati_retributivi', ['project_id'])


def downgrade() -> None:
    op.drop_table('dati_retributivi')
    op.drop_column('allievo_project', 'created_at')
    op.drop_column('allievo_project', 'note')
    op.drop_column('allievo_project', 'attestato_emesso')
    op.drop_column('allievo_project', 'stato')
    op.drop_column('allievo_project', 'ore_frequentate')
    op.drop_column('allievo_project', 'id')
    op.drop_table('fondi')
