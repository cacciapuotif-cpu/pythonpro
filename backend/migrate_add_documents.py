"""
Migrazione database: Aggiunge colonne per documenti collaboratore

Questo script aggiunge le seguenti colonne alla tabella collaborators:
- documento_identita_filename
- documento_identita_path
- documento_identita_uploaded_at
- curriculum_filename
- curriculum_path
- curriculum_uploaded_at
"""

import sqlite3
import sys
from pathlib import Path

# Path del database
DB_PATH = Path(__file__).parent / "gestionale.db"

def check_column_exists(cursor, table, column):
    """Verifica se una colonna esiste gia"""
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns

def migrate_database():
    """Applica la migrazione"""

    if not DB_PATH.exists():
        print(f"Database non trovato: {DB_PATH}")
        return False

    print(f"Database: {DB_PATH}")

    try:
        # Connetti al database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        print("Verifico colonne esistenti...")

        # Colonne da aggiungere
        columns_to_add = [
            ("documento_identita_filename", "VARCHAR(255)"),
            ("documento_identita_path", "VARCHAR(500)"),
            ("documento_identita_uploaded_at", "DATETIME"),
            ("curriculum_filename", "VARCHAR(255)"),
            ("curriculum_path", "VARCHAR(500)"),
            ("curriculum_uploaded_at", "DATETIME"),
        ]

        added_count = 0

        # Aggiungi ogni colonna se non esiste
        for column_name, column_type in columns_to_add:
            if check_column_exists(cursor, "collaborators", column_name):
                print(f"Colonna '{column_name}' gia esistente, skip")
            else:
                print(f"Aggiungo colonna '{column_name}' ({column_type})...")
                cursor.execute(f"ALTER TABLE collaborators ADD COLUMN {column_name} {column_type}")
                added_count += 1

        # Commit delle modifiche
        conn.commit()

        print(f"\nMigrazione completata!")
        print(f"   - Colonne aggiunte: {added_count}")
        print(f"   - Colonne gia esistenti: {len(columns_to_add) - added_count}")

        # Verifica finale
        print("\nVerifica finale dello schema...")
        cursor.execute("PRAGMA table_info(collaborators)")
        columns = cursor.fetchall()

        doc_columns = [col for col in columns if 'documento' in col[1] or 'curriculum' in col[1]]
        if doc_columns:
            print(f"\nColonne documenti trovate ({len(doc_columns)}):")
            for col in doc_columns:
                print(f"   - {col[1]} ({col[2]})")

        conn.close()
        return True

    except Exception as e:
        print(f"\nErrore durante la migrazione: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("MIGRAZIONE DATABASE - Aggiunta Colonne Documenti")
    print("=" * 60)
    print()

    success = migrate_database()

    print()
    print("=" * 60)

    if success:
        print("Migrazione completata con successo!")
        print("Puoi ora avviare il backend e utilizzare la funzionalita upload documenti.")
    else:
        print("Migrazione fallita!")
        sys.exit(1)

    print("=" * 60)
