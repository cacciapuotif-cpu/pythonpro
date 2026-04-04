"""add prodotti, listini, listino_voci

Revision ID: 006
Revises: 005
Create Date: 2026-03-30

"""
from alembic import op

revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS prodotti (
            id SERIAL PRIMARY KEY,
            codice VARCHAR(50) UNIQUE,
            nome VARCHAR(200) NOT NULL,
            descrizione TEXT,
            tipo VARCHAR(30) NOT NULL DEFAULT 'altro',
            prezzo_base FLOAT NOT NULL DEFAULT 0.0,
            unita_misura VARCHAR(50) DEFAULT 'ora',
            attivo BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE
        );
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_prodotto_nome ON prodotti (nome);
        CREATE INDEX IF NOT EXISTS idx_prodotto_tipo ON prodotti (tipo);
        CREATE INDEX IF NOT EXISTS idx_prodotto_attivo ON prodotti (attivo);
        CREATE INDEX IF NOT EXISTS idx_prodotto_codice ON prodotti (codice);
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS listini (
            id SERIAL PRIMARY KEY,
            nome VARCHAR(200) NOT NULL,
            descrizione TEXT,
            tipo_cliente VARCHAR(30) NOT NULL DEFAULT 'standard',
            attivo BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE
        );
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_listino_nome ON listini (nome);
        CREATE INDEX IF NOT EXISTS idx_listino_tipo_cliente ON listini (tipo_cliente);
        CREATE INDEX IF NOT EXISTS idx_listino_attivo ON listini (attivo);
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS listino_voci (
            id SERIAL PRIMARY KEY,
            listino_id INTEGER NOT NULL REFERENCES listini(id) ON DELETE CASCADE,
            prodotto_id INTEGER NOT NULL REFERENCES prodotti(id) ON DELETE CASCADE,
            prezzo_override FLOAT,
            sconto_percentuale FLOAT DEFAULT 0.0,
            note TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE,
            UNIQUE (listino_id, prodotto_id)
        );
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_voce_listino ON listino_voci (listino_id);
        CREATE INDEX IF NOT EXISTS idx_voce_prodotto ON listino_voci (prodotto_id);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS listino_voci;")
    op.execute("DROP TABLE IF EXISTS listini;")
    op.execute("DROP TABLE IF EXISTS prodotti;")
