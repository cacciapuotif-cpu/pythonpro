"""
MIGRAZIONE: Rendi il codice fiscale obbligatorio per i collaboratori

Questo script aggiorna il database per rendere il campo fiscal_code obbligatorio
nella tabella collaborators.

ATTENZIONE: Prima di eseguire questa migrazione, assicurati che tutti i
collaboratori esistenti abbiano un codice fiscale valido!
"""

import sqlite3
import os

# Path del database
DB_PATH = os.getenv('DATABASE_PATH', './gestionale_new.db')

def check_null_fiscal_codes():
    """Controlla se ci sono collaboratori senza codice fiscale"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, first_name, last_name, email
        FROM collaborators
        WHERE fiscal_code IS NULL OR fiscal_code = ''
    """)

    null_codes = cursor.fetchall()
    conn.close()

    return null_codes

def migrate_fiscal_code():
    """Rende il campo fiscal_code obbligatorio"""

    # Controlla prima se ci sono record senza codice fiscale
    null_codes = check_null_fiscal_codes()

    if null_codes:
        print("[!] ATTENZIONE: Ci sono collaboratori senza codice fiscale:")
        for row in null_codes:
            print(f"  - ID {row[0]}: {row[1]} {row[2]} ({row[3]})")

        print("\n[X] Non posso procedere con la migrazione!")
        print("   Aggiungi un codice fiscale a tutti i collaboratori prima di continuare.")
        return False

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        print("[*] Inizio migrazione...")

        # SQLite non supporta ALTER COLUMN direttamente
        # Dobbiamo ricreare la tabella

        # 1. Crea una tabella temporanea con la nuova struttura
        print("[*] Creazione tabella temporanea...")
        cursor.execute("""
            CREATE TABLE collaborators_new (
                id INTEGER PRIMARY KEY,
                first_name VARCHAR(50) NOT NULL,
                last_name VARCHAR(50) NOT NULL,
                email VARCHAR(100) NOT NULL UNIQUE,
                phone VARCHAR(20),
                position VARCHAR(100),
                birthplace VARCHAR(100),
                birth_date DATETIME,
                gender VARCHAR(10),
                fiscal_code VARCHAR(16) NOT NULL UNIQUE,
                city VARCHAR(100),
                address VARCHAR(200),
                education VARCHAR(50),
                is_active BOOLEAN DEFAULT 1,
                last_login DATETIME,
                documento_identita_filename VARCHAR(255),
                documento_identita_path VARCHAR(500),
                documento_identita_uploaded_at DATETIME,
                curriculum_filename VARCHAR(255),
                curriculum_path VARCHAR(500),
                curriculum_uploaded_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME
            )
        """)

        # 2. Copia i dati dalla tabella vecchia a quella nuova
        print("[*] Copia dati...")
        cursor.execute("""
            INSERT INTO collaborators_new
            SELECT * FROM collaborators
        """)

        # 3. Elimina la tabella vecchia
        print("[*] Elimina tabella vecchia...")
        cursor.execute("DROP TABLE collaborators")

        # 4. Rinomina la tabella nuova
        print("[*] Rinomina tabella...")
        cursor.execute("ALTER TABLE collaborators_new RENAME TO collaborators")

        # 5. Ricrea gli indici
        print("[*] Ricreazione indici...")
        cursor.execute("CREATE INDEX idx_collaborators_first_name ON collaborators(first_name)")
        cursor.execute("CREATE INDEX idx_collaborators_last_name ON collaborators(last_name)")
        cursor.execute("CREATE INDEX idx_collaborators_email ON collaborators(email)")
        cursor.execute("CREATE INDEX idx_collaborators_position ON collaborators(position)")
        cursor.execute("CREATE INDEX idx_collaborators_fiscal_code ON collaborators(fiscal_code)")
        cursor.execute("CREATE INDEX idx_collaborators_is_active ON collaborators(is_active)")
        cursor.execute("CREATE INDEX idx_collaborators_created_at ON collaborators(created_at)")

        # Commit delle modifiche
        conn.commit()
        conn.close()

        print("[OK] Migrazione completata con successo!")
        print("     Il campo fiscal_code e' ora obbligatorio.")
        return True

    except sqlite3.Error as e:
        print(f"[ERROR] Errore durante la migrazione: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("MIGRAZIONE: Codice Fiscale Obbligatorio")
    print("=" * 60)
    print()

    # Verifica che il database esista
    if not os.path.exists(DB_PATH):
        print(f"[ERROR] Database non trovato: {DB_PATH}")
        print("        Assicurati che il path sia corretto.")
        exit(1)

    print(f"[*] Database: {DB_PATH}")
    print()

    # Esegui la migrazione
    success = migrate_fiscal_code()

    if success:
        print()
        print("[OK] Tutto fatto! Il database e' stato aggiornato.")
    else:
        print()
        print("[!] La migrazione non e' stata completata.")
        exit(1)
