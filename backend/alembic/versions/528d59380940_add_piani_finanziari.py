"""add_piani_finanziari

Revision ID: 528d59380940
Revises: 028
Create Date: 2026-04-04 14:26:47.275166+00:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '528d59380940'
down_revision = '028'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # === piani_finanziari: aggiungi nuovi campi ===
    op.add_column('piani_finanziari', sa.Column('nome', sa.String(length=200), nullable=False, server_default=''))
    op.add_column('piani_finanziari', sa.Column('tipo_fondo', sa.String(length=50), nullable=False, server_default='formazienda'))
    op.add_column('piani_finanziari', sa.Column('budget_totale', sa.Float(), nullable=False, server_default='0'))
    op.add_column('piani_finanziari', sa.Column('budget_utilizzato', sa.Float(), nullable=True, server_default='0'))
    op.add_column('piani_finanziari', sa.Column('data_inizio', sa.DateTime(), nullable=False, server_default=sa.text('now()')))
    op.add_column('piani_finanziari', sa.Column('data_fine', sa.DateTime(), nullable=False, server_default=sa.text('now()')))
    op.add_column('piani_finanziari', sa.Column('stato', sa.String(length=20), nullable=True, server_default='bozza'))
    op.add_column('piani_finanziari', sa.Column('note', sa.Text(), nullable=True))
    op.create_index('idx_piano_date', 'piani_finanziari', ['data_inizio', 'data_fine'], unique=False)
    op.create_index('idx_piano_fondo_stato', 'piani_finanziari', ['tipo_fondo', 'stato'], unique=False)
    op.create_index('idx_piano_progetto_stato', 'piani_finanziari', ['progetto_id', 'stato'], unique=False)
    op.create_index(op.f('ix_piani_finanziari_stato'), 'piani_finanziari', ['stato'], unique=False)
    op.create_index(op.f('ix_piani_finanziari_tipo_fondo'), 'piani_finanziari', ['tipo_fondo'], unique=False)

    # === voci_piano_finanziario: aggiungi categoria, promuovi descrizione a Text ===
    op.add_column('voci_piano_finanziario', sa.Column('categoria', sa.String(length=100), nullable=True))
    op.alter_column('voci_piano_finanziario', 'descrizione',
                    existing_type=sa.VARCHAR(length=255),
                    type_=sa.Text(),
                    nullable=True)
    op.create_index('idx_voci_piano_categoria', 'voci_piano_finanziario', ['piano_id', 'categoria'], unique=False)
    op.create_index(op.f('ix_voci_piano_finanziario_categoria'), 'voci_piano_finanziario', ['categoria'], unique=False)


def downgrade() -> None:
    # === voci_piano_finanziario ===
    op.drop_index(op.f('ix_voci_piano_finanziario_categoria'), table_name='voci_piano_finanziario')
    op.drop_index('idx_voci_piano_categoria', table_name='voci_piano_finanziario')
    op.alter_column('voci_piano_finanziario', 'descrizione',
                    existing_type=sa.Text(),
                    type_=sa.VARCHAR(length=255),
                    nullable=False)
    op.drop_column('voci_piano_finanziario', 'categoria')

    # === piani_finanziari ===
    op.drop_index(op.f('ix_piani_finanziari_tipo_fondo'), table_name='piani_finanziari')
    op.drop_index(op.f('ix_piani_finanziari_stato'), table_name='piani_finanziari')
    op.drop_index('idx_piano_progetto_stato', table_name='piani_finanziari')
    op.drop_index('idx_piano_fondo_stato', table_name='piani_finanziari')
    op.drop_index('idx_piano_date', table_name='piani_finanziari')
    op.drop_column('piani_finanziari', 'note')
    op.drop_column('piani_finanziari', 'stato')
    op.drop_column('piani_finanziari', 'data_fine')
    op.drop_column('piani_finanziari', 'data_inizio')
    op.drop_column('piani_finanziari', 'budget_utilizzato')
    op.drop_column('piani_finanziari', 'budget_totale')
    op.drop_column('piani_finanziari', 'tipo_fondo')
    op.drop_column('piani_finanziari', 'nome')
