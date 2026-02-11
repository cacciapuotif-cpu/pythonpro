"""enforce fiscal_code unique and not null

Revision ID: 002
Revises: 001
Create Date: 2025-10-06

IMPORTANTE:
Questa migrazione assicura che il codice fiscale sia:
- NOT NULL (obbligatorio)
- UNIQUE (univoco nel sistema)
- INDEX (indicizzato per performance)

Questo previene la creazione di collaboratori duplicati con lo stesso CF
e migliora le performance delle query di ricerca per CF.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    APPLICA I VINCOLI AL CAMPO FISCAL_CODE

    Step eseguiti:
    1. Assicura che tutti i record esistenti abbiano un fiscal_code (richiesto prima di NOT NULL)
    2. Aggiunge constraint NOT NULL se non esiste
    3. Crea indice UNIQUE se non esiste
    4. Crea indice normale per performance se non esiste
    """

    # Per sicurezza, prima verifichiamo se ci sono record senza fiscal_code
    # Se esistono, la migrazione fallirebbe. Questo è intenzionale per forzare la correzione manuale
    op.execute("""
        DO $$
        DECLARE
            missing_count INTEGER;
        BEGIN
            -- Conta record senza fiscal_code
            SELECT COUNT(*) INTO missing_count
            FROM collaborators
            WHERE fiscal_code IS NULL OR fiscal_code = '';

            IF missing_count > 0 THEN
                RAISE EXCEPTION 'Trovati % collaboratori senza codice fiscale. Correggi manualmente prima di applicare la migrazione.', missing_count;
            END IF;
        END $$;
    """)

    # Aggiungi vincolo NOT NULL (se non esiste già)
    op.execute("""
        ALTER TABLE collaborators
        ALTER COLUMN fiscal_code SET NOT NULL;
    """)

    # Crea indice UNIQUE (previene duplicati)
    # Se esiste già, DROP INDEX fallisce silenziosamente con IF EXISTS
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_collaborators_fiscal_code_unique
        ON collaborators(fiscal_code);
    """)

    # Il modello SQLAlchemy ha già index=True, ma assicuriamoci che esista
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_collaborators_fiscal_code
        ON collaborators(fiscal_code);
    """)

    print("✅ Vincoli fiscal_code applicati con successo")


def downgrade() -> None:
    """
    RIMUOVE I VINCOLI DAL CAMPO FISCAL_CODE

    ATTENZIONE: Questo rimuove le protezioni contro duplicati!
    Usare solo in caso di rollback necessario.
    """

    # Rimuovi vincolo NOT NULL
    op.execute("""
        ALTER TABLE collaborators
        ALTER COLUMN fiscal_code DROP NOT NULL;
    """)

    # Rimuovi indice UNIQUE
    op.execute("""
        DROP INDEX IF EXISTS idx_collaborators_fiscal_code_unique;
    """)

    # Mantieni l'indice normale per performance (opzionale)
    # op.execute("""
    #     DROP INDEX IF EXISTS idx_collaborators_fiscal_code;
    # """)

    print("⚠️ Vincoli fiscal_code rimossi - ATTENZIONE: duplicati ora possibili!")
