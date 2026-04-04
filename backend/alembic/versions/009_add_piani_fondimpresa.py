"""add piani fondimpresa

Revision ID: 009
Revises: 008
Create Date: 2026-04-01

"""

from alembic import op

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE projects ADD COLUMN IF NOT EXISTS fondo VARCHAR(50);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_projects_fondo ON projects (fondo);")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS piani_finanziari_fondimpresa (
            id SERIAL PRIMARY KEY,
            progetto_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            anno INTEGER NOT NULL,
            fondo VARCHAR(100) NOT NULL DEFAULT 'Fondimpresa',
            tipo_conto VARCHAR(50) NOT NULL DEFAULT 'conto_formazione',
            totale_preventivo FLOAT NOT NULL DEFAULT 0.0,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE
        );
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_piano_fondimpresa_progetto_anno
        ON piani_finanziari_fondimpresa (progetto_id, anno);
        CREATE INDEX IF NOT EXISTS idx_piani_fondimpresa_progetto ON piani_finanziari_fondimpresa (progetto_id);
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS voci_fondimpresa (
            id SERIAL PRIMARY KEY,
            piano_id INTEGER NOT NULL REFERENCES piani_finanziari_fondimpresa(id) ON DELETE CASCADE,
            sezione VARCHAR(1) NOT NULL,
            voce_codice VARCHAR(20) NOT NULL,
            descrizione VARCHAR(255) NOT NULL,
            note_temporali TEXT,
            totale_voce FLOAT NOT NULL DEFAULT 0.0,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE
        );
        CREATE INDEX IF NOT EXISTS idx_voci_fondimpresa_sezione ON voci_fondimpresa (piano_id, sezione);
        CREATE INDEX IF NOT EXISTS idx_voci_fondimpresa_codice ON voci_fondimpresa (piano_id, voce_codice);
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS righe_nominativo_fondimpresa (
            id SERIAL PRIMARY KEY,
            voce_id INTEGER NOT NULL REFERENCES voci_fondimpresa(id) ON DELETE CASCADE,
            nominativo VARCHAR(255) NOT NULL,
            ore FLOAT NOT NULL DEFAULT 0.0,
            costo_orario FLOAT NOT NULL DEFAULT 0.0,
            totale FLOAT NOT NULL DEFAULT 0.0,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE
        );
        CREATE INDEX IF NOT EXISTS idx_righe_nominativo_fondimpresa_voce ON righe_nominativo_fondimpresa (voce_id);
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS documenti_fondimpresa (
            id SERIAL PRIMARY KEY,
            voce_id INTEGER NOT NULL REFERENCES voci_fondimpresa(id) ON DELETE CASCADE,
            tipo_documento VARCHAR(100),
            numero_documento VARCHAR(100),
            data_documento TIMESTAMP,
            importo_totale FLOAT NOT NULL DEFAULT 0.0,
            importo_imputato FLOAT NOT NULL DEFAULT 0.0,
            data_pagamento TIMESTAMP,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE
        );
        CREATE INDEX IF NOT EXISTS idx_documenti_fondimpresa_voce ON documenti_fondimpresa (voce_id);
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS dettaglio_budget_fondimpresa (
            id SERIAL PRIMARY KEY,
            piano_id INTEGER NOT NULL UNIQUE REFERENCES piani_finanziari_fondimpresa(id) ON DELETE CASCADE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE
        );
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS budget_consulenti_fondimpresa (
            id SERIAL PRIMARY KEY,
            budget_id INTEGER NOT NULL REFERENCES dettaglio_budget_fondimpresa(id) ON DELETE CASCADE,
            nominativo VARCHAR(255) NOT NULL,
            ore FLOAT NOT NULL DEFAULT 0.0,
            costo_orario FLOAT NOT NULL DEFAULT 0.0,
            totale FLOAT NOT NULL DEFAULT 0.0,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE
        );
        CREATE TABLE IF NOT EXISTS budget_costi_fissi_fondimpresa (
            id SERIAL PRIMARY KEY,
            budget_id INTEGER NOT NULL REFERENCES dettaglio_budget_fondimpresa(id) ON DELETE CASCADE,
            tipologia VARCHAR(255) NOT NULL,
            parametro VARCHAR(255),
            totale FLOAT NOT NULL DEFAULT 0.0,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE
        );
        CREATE TABLE IF NOT EXISTS budget_margine_fondimpresa (
            id SERIAL PRIMARY KEY,
            budget_id INTEGER NOT NULL REFERENCES dettaglio_budget_fondimpresa(id) ON DELETE CASCADE,
            tipologia VARCHAR(255) NOT NULL,
            percentuale FLOAT NOT NULL DEFAULT 0.0,
            totale FLOAT NOT NULL DEFAULT 0.0,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS budget_margine_fondimpresa;")
    op.execute("DROP TABLE IF EXISTS budget_costi_fissi_fondimpresa;")
    op.execute("DROP TABLE IF EXISTS budget_consulenti_fondimpresa;")
    op.execute("DROP TABLE IF EXISTS dettaglio_budget_fondimpresa;")
    op.execute("DROP TABLE IF EXISTS documenti_fondimpresa;")
    op.execute("DROP TABLE IF EXISTS righe_nominativo_fondimpresa;")
    op.execute("DROP TABLE IF EXISTS voci_fondimpresa;")
    op.execute("DROP TABLE IF EXISTS piani_finanziari_fondimpresa;")
