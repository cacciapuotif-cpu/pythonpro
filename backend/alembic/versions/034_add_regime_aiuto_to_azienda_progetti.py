"""add regime aiuto to azienda_cliente_projects

Revision ID: 034
Revises: 033
Create Date: 2026-04-20
"""
from alembic import op
import sqlalchemy as sa

revision = '034'
down_revision = '033'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('azienda_cliente_projects',
        sa.Column('regime_aiuto', sa.String(30), nullable=True)
    )
    op.add_column('azienda_cliente_projects',
        sa.Column('cofinanziamento_perc', sa.Float, nullable=True)
    )
    op.add_column('azienda_cliente_projects',
        sa.Column('dichiarazione_de_minimis', sa.String(500), nullable=True)
    )
    op.add_column('azienda_cliente_projects',
        sa.Column('plafond_dichiarato', sa.Float, nullable=True)
    )
    op.add_column('azienda_cliente_projects',
        sa.Column('stato', sa.String(30), nullable=True, server_default='in_attesa')
    )
    op.add_column('azienda_cliente_projects',
        sa.Column('note', sa.Text, nullable=True)
    )
    op.create_index(
        'idx_azienda_cliente_projects_regime',
        'azienda_cliente_projects',
        ['regime_aiuto'],
    )


def downgrade() -> None:
    op.drop_index('idx_azienda_cliente_projects_regime', table_name='azienda_cliente_projects')
    op.drop_column('azienda_cliente_projects', 'note')
    op.drop_column('azienda_cliente_projects', 'stato')
    op.drop_column('azienda_cliente_projects', 'plafond_dichiarato')
    op.drop_column('azienda_cliente_projects', 'dichiarazione_de_minimis')
    op.drop_column('azienda_cliente_projects', 'cofinanziamento_perc')
    op.drop_column('azienda_cliente_projects', 'regime_aiuto')
