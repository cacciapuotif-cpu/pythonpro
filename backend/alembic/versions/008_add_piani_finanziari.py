"""add piani finanziari

Revision ID: 008
Revises: 007
Create Date: 2026-04-01

"""

from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS piani_finanziari (
            id SERIAL PRIMARY KEY,
            progetto_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            anno INTEGER NOT NULL,
            fondo VARCHAR(100) NOT NULL DEFAULT 'Formazienda',
            avviso VARCHAR(100) NOT NULL DEFAULT '2/2022',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE
        );
        """
    )
    op.execute(
        """
        DROP INDEX IF EXISTS idx_unique_piano_progetto_anno;
        CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_piano_progetto_anno_fondo
        ON piani_finanziari (progetto_id, anno, fondo);
        CREATE INDEX IF NOT EXISTS idx_piani_finanziari_progetto ON piani_finanziari (progetto_id);
        CREATE INDEX IF NOT EXISTS idx_piani_finanziari_anno ON piani_finanziari (anno);
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS voci_piano_finanziario (
            id SERIAL PRIMARY KEY,
            piano_id INTEGER NOT NULL REFERENCES piani_finanziari(id) ON DELETE CASCADE,
            macrovoce VARCHAR(1) NOT NULL,
            voce_codice VARCHAR(10) NOT NULL,
            descrizione VARCHAR(255) NOT NULL,
            progetto_label VARCHAR(100),
            edizione_label VARCHAR(100),
            ore FLOAT NOT NULL DEFAULT 0.0,
            importo_consuntivo FLOAT NOT NULL DEFAULT 0.0,
            importo_preventivo FLOAT NOT NULL DEFAULT 0.0,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_voci_piano_piano ON voci_piano_finanziario (piano_id);
        CREATE INDEX IF NOT EXISTS idx_voci_piano_macrovoce ON voci_piano_finanziario (piano_id, macrovoce);
        CREATE INDEX IF NOT EXISTS idx_voci_piano_codice ON voci_piano_finanziario (piano_id, voce_codice);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS voci_piano_finanziario;")
    op.execute("DROP TABLE IF EXISTS piani_finanziari;")
