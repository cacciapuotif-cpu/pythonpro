"""
SCRIPT DI MIGRAZIONE DATABASE
Aggiunge la colonna ente_attuatore_id alla tabella projects
"""

import sqlite3
import os

# Path del database
DB_PATH = os.path.join(os.path.dirname(__file__), 'gestionale.db')

def migrate():
    """Aggiunge la colonna ente_attuatore_id alla tabella projects"""

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        print("=" * 60)
        print("MIGRAZIONE DATABASE: Aggiunta colonna ente_attuatore_id")
        print("=" * 60)
        print()

        # Verifica se la colonna esiste già
        cursor.execute("PRAGMA table_info(projects)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'ente_attuatore_id' in columns:
            print("[INFO] La colonna ente_attuatore_id esiste già")
            print()
            return

        # Aggiungi la colonna
        print("[MIGRAZIONE] Aggiunta colonna ente_attuatore_id...")
        cursor.execute("""
            ALTER TABLE projects
            ADD COLUMN ente_attuatore_id INTEGER
            REFERENCES implementing_entities(id)
        """)

        # Crea un indice sulla colonna per performance
        print("[MIGRAZIONE] Creazione indice ix_projects_ente_attuatore_id...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS ix_projects_ente_attuatore_id
            ON projects(ente_attuatore_id)
        """)

        conn.commit()

        print("[SUCCESS] Migrazione completata con successo!")
        print()
        print("Dettagli:")
        print("- Colonna ente_attuatore_id aggiunta a tabella projects")
        print("- Indice creato per performance")
        print("- Foreign key verso implementing_entities")
        print()

    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Errore durante la migrazione: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
