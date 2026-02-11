"""
Migrazione: Aggiunta tabella progetto_mansione_ente

Questa migrazione crea la nuova tabella di associazione tra progetti, enti attuatori e mansioni.
La tabella collega un progetto a un ente attuatore specificando la mansione, le ore, i costi, ecc.
"""

import sqlite3
from pathlib import Path

# Path al database
DB_PATH = Path(__file__).parent / "gestionale_new.db"

print(f"[MIGRATION] Creating progetto_mansione_ente table")
print(f"[DATABASE] {DB_PATH}")

# Connessione al database
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

try:
    # Crea la tabella progetto_mansione_ente
    print("\n[CREATE] Creating progetto_mansione_ente table...")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS progetto_mansione_ente (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            progetto_id INTEGER NOT NULL,
            ente_attuatore_id INTEGER NOT NULL,
            mansione VARCHAR(100) NOT NULL,
            descrizione_mansione TEXT,
            data_inizio DATETIME NOT NULL,
            data_fine DATETIME NOT NULL,
            ore_previste FLOAT NOT NULL,
            ore_effettive FLOAT DEFAULT 0.0,
            tariffa_oraria FLOAT,
            budget_totale FLOAT,
            tipo_contratto VARCHAR(50),
            is_active BOOLEAN DEFAULT 1,
            note TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME,

            -- Foreign keys
            FOREIGN KEY (progetto_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (ente_attuatore_id) REFERENCES implementing_entities(id) ON DELETE CASCADE
        )
    """)

    # Crea gli indici
    print("[INDEX] Creating indices...")

    # Indice su progetto_id
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_pme_progetto_id
        ON progetto_mansione_ente(progetto_id)
    """)

    # Indice su ente_attuatore_id
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_pme_ente_attuatore_id
        ON progetto_mansione_ente(ente_attuatore_id)
    """)

    # Indice su mansione
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_pme_mansione
        ON progetto_mansione_ente(mansione)
    """)

    # Indice su is_active
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_pme_is_active
        ON progetto_mansione_ente(is_active)
    """)

    # Indice su created_at
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_pme_created_at
        ON progetto_mansione_ente(created_at)
    """)

    # Indice su data_inizio
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_pme_data_inizio
        ON progetto_mansione_ente(data_inizio)
    """)

    # Indice su data_fine
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_pme_data_fine
        ON progetto_mansione_ente(data_fine)
    """)

    # Indice composito progetto + ente
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_pme_progetto_ente
        ON progetto_mansione_ente(progetto_id, ente_attuatore_id)
    """)

    # Indice composito periodo (data_inizio, data_fine)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_pme_periodo
        ON progetto_mansione_ente(data_inizio, data_fine)
    """)

    # Indice composito mansione + is_active
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_pme_mansione_attiva
        ON progetto_mansione_ente(mansione, is_active)
    """)

    # Indice UNIQUE per evitare duplicati
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_pme_unique_progetto_ente_mansione_data
        ON progetto_mansione_ente(progetto_id, ente_attuatore_id, mansione, data_inizio)
    """)

    # Commit delle modifiche
    conn.commit()

    print("\n[SUCCESS] Migration completed successfully!")
    print("\n[TABLE] Created: progetto_mansione_ente")
    print("[INDEX] Created: 11 indices")

    # Verifica che la tabella sia stata creata
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='progetto_mansione_ente'
    """)

    result = cursor.fetchone()
    if result:
        print(f"\n[VERIFY] Table 'progetto_mansione_ente' verified in database")

        # Mostra la struttura della tabella
        cursor.execute("PRAGMA table_info(progetto_mansione_ente)")
        columns = cursor.fetchall()
        print(f"\n[SCHEMA] Table structure (columns: {len(columns)}):")
        for col in columns:
            print(f"  - {col[1]}: {col[2]} {'NOT NULL' if col[3] else ''}")
    else:
        print("\n[ERROR] Table not found after creation!")

except sqlite3.Error as e:
    print(f"\n[ERROR] Migration failed: {e}")
    conn.rollback()
    raise

finally:
    conn.close()
    print("\n[CLOSE] Database connection closed")
