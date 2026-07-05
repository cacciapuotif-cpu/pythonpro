from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

config = context.config

database_url = os.getenv('ALEMBIC_DATABASE_URL') or os.getenv('DATABASE_URL')
if not database_url:
    raise RuntimeError(
        "DATABASE_URL/ALEMBIC_DATABASE_URL non configurata. Imposta la variabile d'ambiente prima di eseguire Alembic."
    )
config.set_main_option('sqlalchemy.url', database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

from database import Base
import auth
import models

target_metadata = Base.metadata

# Indici PostgreSQL-only mantenuti fuori dai modelli perche' non
# rappresentabili cross-dialect (i test creano lo schema su SQLite).
# Vengono esclusi dal confronto autogenerate: esistono nel DB by design.
DB_MANAGED_INDEX_NAMES = {
    "idx_collab_fulltext_search",  # lower(first_name::text), lower(last_name::text)
}


def include_name(name, type_, parent_names):
    if type_ == "index" and name in DB_MANAGED_INDEX_NAMES:
        return False
    return True

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_name=include_name,
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_name=include_name,
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
