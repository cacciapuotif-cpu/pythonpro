"""add agenzie, consulenti, aziende_clienti

Revision ID: 004
Revises: 003
Create Date: 2026-03-30

"""
from alembic import op

revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS agenzie (
            id SERIAL PRIMARY KEY,
            nome VARCHAR(200) NOT NULL,
            telefono VARCHAR(20),
            email VARCHAR(100),
            note TEXT,
            attivo BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE
        );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_agenzia_nome ON agenzie (nome);
        CREATE INDEX IF NOT EXISTS idx_agenzia_attivo ON agenzie (attivo);
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS consulenti (
            id SERIAL PRIMARY KEY,
            nome VARCHAR(100) NOT NULL,
            cognome VARCHAR(100) NOT NULL,
            email VARCHAR(100) UNIQUE,
            telefono VARCHAR(20),
            partita_iva VARCHAR(11) UNIQUE,
            agenzia_id INTEGER REFERENCES agenzie(id) ON DELETE SET NULL,
            zona_competenza VARCHAR(200),
            provvigione_percentuale FLOAT,
            note TEXT,
            attivo BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE
        );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_consulente_cognome_nome ON consulenti (cognome, nome);
        CREATE INDEX IF NOT EXISTS idx_consulente_agenzia ON consulenti (agenzia_id);
        CREATE INDEX IF NOT EXISTS idx_consulente_attivo ON consulenti (attivo);
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS aziende_clienti (
            id SERIAL PRIMARY KEY,
            ragione_sociale VARCHAR(200) NOT NULL,
            partita_iva VARCHAR(11) UNIQUE,
            codice_fiscale VARCHAR(16),
            settore_ateco VARCHAR(10),
            indirizzo VARCHAR(200),
            citta VARCHAR(100),
            cap VARCHAR(5),
            provincia VARCHAR(2),
            email VARCHAR(100),
            pec VARCHAR(100),
            telefono VARCHAR(20),
            referente_nome VARCHAR(100),
            referente_email VARCHAR(100),
            consulente_id INTEGER REFERENCES consulenti(id) ON DELETE SET NULL,
            note TEXT,
            attivo BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE
        );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_azienda_ragione_sociale ON aziende_clienti (ragione_sociale);
        CREATE INDEX IF NOT EXISTS idx_azienda_citta ON aziende_clienti (citta);
        CREATE INDEX IF NOT EXISTS idx_azienda_consulente ON aziende_clienti (consulente_id);
        CREATE INDEX IF NOT EXISTS idx_azienda_attivo ON aziende_clienti (attivo);
        CREATE INDEX IF NOT EXISTS idx_azienda_partita_iva ON aziende_clienti (partita_iva);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS aziende_clienti;")
    op.execute("DROP TABLE IF EXISTS consulenti;")
    op.execute("DROP TABLE IF EXISTS agenzie;")
