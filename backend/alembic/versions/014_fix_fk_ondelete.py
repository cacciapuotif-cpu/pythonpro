"""Fix FK ondelete: ente_attuatore_id SET NULL, collaborator_project CASCADE

Revision ID: 014
Revises: 013
Create Date: 2026-04-03

"""
from alembic import op
import sqlalchemy as sa

revision = '014'
down_revision = '013'
branch_labels = None
depends_on = None


def upgrade():
    # Fix 1: Project.ente_attuatore_id → ondelete="SET NULL"
    op.drop_constraint('projects_ente_attuatore_id_fkey', 'projects', type_='foreignkey')
    op.create_foreign_key(
        'projects_ente_attuatore_id_fkey',
        'projects', 'implementing_entities',
        ['ente_attuatore_id'], ['id'],
        ondelete='SET NULL'
    )

    # Fix 2: collaborator_project M2M → ondelete="CASCADE" su entrambe le colonne
    op.drop_constraint('collaborator_project_collaborator_id_fkey', 'collaborator_project', type_='foreignkey')
    op.drop_constraint('collaborator_project_project_id_fkey', 'collaborator_project', type_='foreignkey')
    op.create_foreign_key(
        'collaborator_project_collaborator_id_fkey',
        'collaborator_project', 'collaborators',
        ['collaborator_id'], ['id'],
        ondelete='CASCADE'
    )
    op.create_foreign_key(
        'collaborator_project_project_id_fkey',
        'collaborator_project', 'projects',
        ['project_id'], ['id'],
        ondelete='CASCADE'
    )


def downgrade():
    op.drop_constraint('collaborator_project_project_id_fkey', 'collaborator_project', type_='foreignkey')
    op.drop_constraint('collaborator_project_collaborator_id_fkey', 'collaborator_project', type_='foreignkey')
    op.create_foreign_key(
        'collaborator_project_project_id_fkey',
        'collaborator_project', 'projects',
        ['project_id'], ['id']
    )
    op.create_foreign_key(
        'collaborator_project_collaborator_id_fkey',
        'collaborator_project', 'collaborators',
        ['collaborator_id'], ['id']
    )

    op.drop_constraint('projects_ente_attuatore_id_fkey', 'projects', type_='foreignkey')
    op.create_foreign_key(
        'projects_ente_attuatore_id_fkey',
        'projects', 'implementing_entities',
        ['ente_attuatore_id'], ['id']
    )
