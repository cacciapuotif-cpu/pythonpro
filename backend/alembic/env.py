from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from sqlalchemy import inspect, text
from alembic import context
from alembic.script import ScriptDirectory
import os
import sys

# Aggiungi la directory parent al path per importare i modelli
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Import dei modelli
from database import Base
import models

# Configurazione Alembic
config = context.config

# Sovrascrivi URL da variabile d'ambiente — DATABASE_URL è obbligatoria
database_url = os.getenv('DATABASE_URL')
if not database_url:
    raise RuntimeError(
        "DATABASE_URL non configurata. Imposta la variabile d'ambiente prima di eseguire Alembic."
    )
config.set_main_option('sqlalchemy.url', database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _bootstrap_empty_database(connection) -> bool:
    """Initialize a pristine database from metadata and stage the final Alembic step.

    The legacy migration chain starts with ALTER-based revisions and cannot build the
    schema from absolute zero. On an actually empty database we use the current model
    metadata as baseline, stamp the DB to the parent of the latest revision, and let
    Alembic run the last step normally. This preserves migration-owned indexes and
    constraints without replaying the full legacy chain.
    """
    inspector = inspect(connection)
    existing_tables = [name for name in inspector.get_table_names() if name != "alembic_version"]
    if existing_tables:
        return False

    script = ScriptDirectory.from_config(config)
    head_revision = script.get_current_head()
    if not head_revision:
        return False

    revision = script.get_revision(head_revision)
    target_versions = revision.down_revision
    if not target_versions:
        target_versions = (head_revision,)
    elif isinstance(target_versions, str):
        target_versions = (target_versions,)

    target_metadata.create_all(bind=connection)
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS alembic_version (
                version_num VARCHAR(255) NOT NULL PRIMARY KEY
            )
            """
        )
    )
    connection.execute(text("DELETE FROM alembic_version"))
    for version_num in target_versions:
        connection.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:version_num)"),
            {"version_num": version_num},
        )
    return True

def run_migrations_offline() -> None:
    """Esegui migrazioni in modalità offline."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Esegui migrazioni in modalità online."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        with connection.begin():
            _bootstrap_empty_database(connection)

        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
