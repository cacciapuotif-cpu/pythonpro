#!/usr/bin/env python3
"""
Script di inizializzazione database
- Attende che PostgreSQL sia pronto
- Esegue migrazioni Alembic automaticamente
- Crea tabelle se non esistono
"""

import sys
import time
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    logger.error("DATABASE_URL non configurata. Impossibile avviare init_db.")
    sys.exit(1)
MAX_RETRIES = 30
RETRY_INTERVAL = 2

def wait_for_db():
    """Attende che il database sia pronto."""
    logger.info("🔍 Attendo che PostgreSQL sia pronto...")

    for attempt in range(MAX_RETRIES):
        try:
            engine = create_engine(DATABASE_URL)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("✅ PostgreSQL è pronto!")
            return True
        except OperationalError as e:
            logger.warning(f"⏳ Tentativo {attempt + 1}/{MAX_RETRIES}: PostgreSQL non ancora pronto")
            time.sleep(RETRY_INTERVAL)

    logger.error("❌ Timeout: PostgreSQL non disponibile")
    return False

def run_migrations():
    """Esegue le migrazioni Alembic."""
    logger.info("🔄 Esecuzione migrazioni database...")

    try:
        from alembic.config import Config
        from alembic import command

        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option('sqlalchemy.url', DATABASE_URL)

        command.upgrade(alembic_cfg, "head")
        logger.info("✅ Migrazioni completate con successo")
        return True

    except Exception as e:
        logger.error(f"❌ Errore durante migrazioni: {e}")
        return False

def create_tables():
    """Crea le tabelle con SQLAlchemy se non esistono."""
    logger.info("🔄 Creazione tabelle se non esistono...")

    try:
        from database import Base, engine
        import models

        Base.metadata.create_all(bind=engine)
        logger.info("✅ Tabelle verificate/create")
        return True

    except Exception as e:
        logger.error(f"❌ Errore durante creazione tabelle: {e}")
        return False

def main():
    """Funzione principale di inizializzazione."""
    logger.info("🚀 Inizializzazione database...")

    if not wait_for_db():
        logger.error("❌ Impossibile connettersi al database")
        sys.exit(1)

    migrations_ok = run_migrations()

    if not migrations_ok:
        logger.warning("⚠️ Uso SQLAlchemy come fallback...")
        if not create_tables():
            logger.error("❌ Inizializzazione fallita")
            sys.exit(1)

    logger.info("✅ Inizializzazione database completata!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
