from __future__ import annotations
import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool, create_engine
from alembic import context

# Configura Alembic
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Qui dovremo dire ad Alembic dove trovare la definizione del database (Base)
# La Base è la classe che riunisce tutti i modelli SQLAlchemy
# Esempio tipico: from app.db.base import Base
# Per ora lasciamo un tentativo generico, poi lo correggeremo dopo:
try:
    from database import Base
    target_metadata = Base.metadata
except Exception:
    target_metadata = None

# Prende la stringa di connessione dal Docker Compose
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL non definita nell'ambiente Docker.")

def run_migrations_offline():
    """Esegue le migrazioni in modalità 'offline'."""
    url = DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    """Esegue le migrazioni in modalità 'online'."""
    connectable = create_engine(DATABASE_URL, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
