"""
Migration script per aggiungere il campo assignment_id alla tabella attendances
"""

from sqlalchemy import create_engine, Column, Integer, ForeignKey, MetaData, Table, inspect, text
from database import DATABASE_URL
import sys

def add_assignment_column():
    """
    Aggiunge la colonna assignment_id alla tabella attendances se non esiste già
    """
    try:
        # Connessione al database
        engine = create_engine(DATABASE_URL)
        metadata = MetaData()

        # Ispeziona la tabella esistente
        inspector = inspect(engine)

        # Verifica se la colonna esiste già
        columns = [col['name'] for col in inspector.get_columns('attendances')]

        if 'assignment_id' in columns:
            print("OK - La colonna 'assignment_id' esiste gia nella tabella 'attendances'")
            return True

        print("Aggiunta colonna 'assignment_id' alla tabella 'attendances'...")

        # Esegui l'ALTER TABLE
        with engine.connect() as conn:
            # Per SQLite usa questo comando
            conn.execute(text("""
                ALTER TABLE attendances
                ADD COLUMN assignment_id INTEGER
                REFERENCES assignments(id) ON DELETE SET NULL
            """))
            conn.commit()

        print("OK - Colonna 'assignment_id' aggiunta con successo!")

        # Crea indice per performance
        print("Creazione indice per assignment_id...")
        with engine.connect() as conn:
            try:
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS ix_attendances_assignment_id
                    ON attendances(assignment_id)
                """))
                conn.commit()
                print("OK - Indice creato con successo!")
            except Exception as e:
                print(f"WARNING - Errore nella creazione dell'indice (potrebbe gia esistere): {e}")

        return True

    except Exception as e:
        print(f"ERROR - Errore durante la migration: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = add_assignment_column()
    sys.exit(0 if success else 1)
