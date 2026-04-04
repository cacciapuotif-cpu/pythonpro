"""add preventivi, preventivo_righe, ordini

Revision ID: 007
Revises: 006
Create Date: 2026-03-30

"""
from alembic import op

revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS preventivi (
            id SERIAL PRIMARY KEY,
            numero VARCHAR(20) NOT NULL UNIQUE,
            anno INTEGER NOT NULL,
            numero_progressivo INTEGER NOT NULL,
            azienda_cliente_id INTEGER REFERENCES aziende_clienti(id) ON DELETE RESTRICT,
            listino_id INTEGER REFERENCES listini(id) ON DELETE SET NULL,
            consulente_id INTEGER REFERENCES consulenti(id) ON DELETE SET NULL,
            stato VARCHAR(20) NOT NULL DEFAULT 'bozza',
            data_scadenza DATE,
            oggetto VARCHAR(300),
            note TEXT,
            attivo BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE,
            CONSTRAINT chk_preventivo_stato CHECK (stato IN ('bozza','inviato','accettato','rifiutato'))
        );
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_preventivo_stato ON preventivi (stato);
        CREATE INDEX IF NOT EXISTS idx_preventivo_azienda ON preventivi (azienda_cliente_id);
        CREATE INDEX IF NOT EXISTS idx_preventivo_anno ON preventivi (anno);
        CREATE INDEX IF NOT EXISTS idx_preventivo_attivo ON preventivi (attivo);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_preventivo_anno_prog ON preventivi (anno, numero_progressivo);
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS preventivo_righe (
            id SERIAL PRIMARY KEY,
            preventivo_id INTEGER NOT NULL REFERENCES preventivi(id) ON DELETE CASCADE,
            prodotto_id INTEGER REFERENCES prodotti(id) ON DELETE RESTRICT,
            descrizione_custom VARCHAR(400),
            quantita FLOAT NOT NULL DEFAULT 1.0,
            prezzo_unitario FLOAT NOT NULL DEFAULT 0.0,
            sconto_percentuale FLOAT NOT NULL DEFAULT 0.0,
            importo FLOAT NOT NULL DEFAULT 0.0,
            ordine INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE
        );
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_riga_preventivo ON preventivo_righe (preventivo_id);
        CREATE INDEX IF NOT EXISTS idx_riga_prodotto ON preventivo_righe (prodotto_id);
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS ordini (
            id SERIAL PRIMARY KEY,
            numero VARCHAR(20) NOT NULL UNIQUE,
            anno INTEGER NOT NULL,
            numero_progressivo INTEGER NOT NULL,
            preventivo_id INTEGER REFERENCES preventivi(id) ON DELETE SET NULL,
            azienda_cliente_id INTEGER REFERENCES aziende_clienti(id) ON DELETE RESTRICT,
            stato VARCHAR(30) NOT NULL DEFAULT 'in_lavorazione',
            note TEXT,
            progetto_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE,
            CONSTRAINT chk_ordine_stato CHECK (stato IN ('in_lavorazione','completato','annullato'))
        );
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_ordine_stato ON ordini (stato);
        CREATE INDEX IF NOT EXISTS idx_ordine_azienda ON ordini (azienda_cliente_id);
        CREATE INDEX IF NOT EXISTS idx_ordine_preventivo ON ordini (preventivo_id);
        CREATE INDEX IF NOT EXISTS idx_ordine_anno ON ordini (anno);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_ordine_anno_prog ON ordini (anno, numero_progressivo);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ordini;")
    op.execute("DROP TABLE IF EXISTS preventivo_righe;")
    op.execute("DROP TABLE IF EXISTS preventivi;")
