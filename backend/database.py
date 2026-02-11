# =================================================================
# FILE: database.py
# =================================================================
# SCOPO: Configurazione e gestione connessione database SQLAlchemy
#
# Questo modulo gestisce:
# - Creazione engine database (SQLite in dev, PostgreSQL in prod)
# - Connection pooling ottimizzato per performance
# - Session management con dependency injection
# - Health checks per monitoring
# - Event listeners per ottimizzazioni runtime
# =================================================================

# Importazioni SQLAlchemy per gestione database
from sqlalchemy import create_engine, event, pool  # Core engine e eventi
from sqlalchemy.ext.declarative import declarative_base  # Base per modelli ORM
from sqlalchemy.orm import sessionmaker  # Factory per creare sessioni
from sqlalchemy.pool import QueuePool  # Pool connessioni avanzato
import os  # Per leggere variabili ambiente
import logging  # Per logging errori e info

# Configurazione logging per questo modulo
# Level INFO registra operazioni importanti senza troppo dettaglio
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =================================================================
# CONFIGURAZIONE DATABASE URL
# =================================================================
# Legge l'URL del database da variabile d'ambiente DATABASE_URL
# Se non impostata, usa SQLite locale per sviluppo
#
# Formati supportati:
# - SQLite: "sqlite:///./database.db"
# - PostgreSQL: "postgresql://user:password@host:port/database"
#
# IMPORTANTE: In produzione Docker, questo viene impostato in docker-compose.yml
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./gestionale_new.db"  # Default per sviluppo locale
)

# =================================================================
# CREAZIONE DATABASE ENGINE
# =================================================================
# L'engine è il punto di accesso al database. Configurazione diversa
# per SQLite (dev) e PostgreSQL (prod) per ottimizzare performance.
# =================================================================

if "sqlite" in DATABASE_URL:
    # --------------------------------------------------
    # CONFIGURAZIONE SQLITE (Sviluppo)
    # --------------------------------------------------
    # SQLite è un database file-based, ideale per sviluppo e test.
    # Non richiede server separato.
    engine = create_engine(
        DATABASE_URL,
        # check_same_thread=False: Permette uso multithread
        # (necessario per FastAPI asincrono)
        connect_args={"check_same_thread": False},
        # echo=False: Non logga query SQL (migliori performance)
        echo=False
    )
else:
    # --------------------------------------------------
    # CONFIGURAZIONE POSTGRESQL (Produzione)
    # --------------------------------------------------
    # PostgreSQL è database enterprise con supporto per:
    # - Connection pooling
    # - Transazioni avanzate
    # - Scalabilità orizzontale
    engine = create_engine(
        DATABASE_URL,
        # QueuePool: Pool connessioni thread-safe con coda FIFO
        poolclass=QueuePool,

        # pool_size=20: Mantiene 20 connessioni aperte e riutilizzabili
        # Riduce overhead di apertura/chiusura connessione
        pool_size=20,

        # max_overflow=30: Permette altre 30 connessioni temporanee
        # se pool esaurito (totale max: 50 connessioni)
        max_overflow=30,

        # pool_pre_ping=True: Testa connessione prima di usarla
        # Evita errori "server has gone away" dopo idle prolungato
        pool_pre_ping=True,

        # pool_recycle=3600: Ricrea connessioni dopo 1 ora
        # Previene problemi con timeout server-side
        pool_recycle=3600,

        # echo=False: Disabilita log query SQL (performance)
        echo=False,

        # future=True: Usa SQLAlchemy 2.0 style (best practices)
        future=True,

        # connect_timeout=10: Timeout connessione iniziale (10 secondi)
        # Evita freeze se database irraggiungibile
        connect_args={"connect_timeout": 10}
    )

# =================================================================
# SESSION FACTORY
# =================================================================
# SessionLocal è una factory che crea nuove sessioni database.
# Ogni richiesta HTTP ottiene una sessione dedicata via dependency injection.
#
# PATTERN IMPORTANTE:
# - Ogni endpoint FastAPI riceve una sessione via Depends(get_db)
# - La sessione viene chiusa automaticamente al termine della richiesta
# - Garantisce isolamento transazionale tra richieste
# =================================================================
SessionLocal = sessionmaker(
    # autocommit=False: Transazioni esplicite (ACID compliance)
    # Richiede db.commit() manuale per salvare modifiche
    autocommit=False,

    # autoflush=False: Controllo manuale del flush
    # Migliori performance, meno query automatiche
    autoflush=False,

    # bind=engine: Lega sessione all'engine configurato sopra
    bind=engine,

    # expire_on_commit=False: Non ricarica oggetti dopo commit
    # IMPORTANTE per performance: oggetti rimangono usabili dopo commit
    # Utile per app read-heavy (più letture che scritture)
    expire_on_commit=False
)

# =================================================================
# BASE DICHIARATIVA
# =================================================================
# Base è la classe base per tutti i modelli ORM.
# Tutti i modelli in models.py ereditano da questa classe.
#
# Esempio:
# class Collaborator(Base):
#     __tablename__ = "collaborators"
#     id = Column(Integer, primary_key=True)
#     ...
# =================================================================
Base = declarative_base()

# =================================================================
# EVENT LISTENERS - OTTIMIZZAZIONI RUNTIME
# =================================================================
# Event listeners permettono di eseguire codice automaticamente
# quando si verificano eventi nel lifecycle delle connessioni.
# =================================================================

@event.listens_for(engine, "connect")
def set_postgres_pragma(dbapi_connection, connection_record):
    """
    Eseguito automaticamente quando si apre una nuova connessione PostgreSQL.

    Imposta timeout e parametri di sicurezza per evitare:
    - Query infinite (statement_timeout)
    - Lock eterni (lock_timeout)
    - Transazioni abbandonate (idle_in_transaction_session_timeout)

    IMPORTANTE: Questi setting proteggono il database da:
    - Query malevoli o buggate che consumano risorse
    - Deadlock che bloccano altre transazioni
    - Connessioni zombie che occupano slot del pool
    """
    # Esegui solo per PostgreSQL (non SQLite)
    if 'postgresql' in DATABASE_URL:
        with dbapi_connection.cursor() as cursor:
            # statement_timeout: Aborta query che impiegano > 30 secondi
            # Protegge da query inefficienti o infinite loops
            cursor.execute("SET statement_timeout = '30s'")

            # lock_timeout: Aborta se non riesce ad acquisire lock in 10s
            # Evita deadlock che bloccano altre transazioni
            cursor.execute("SET lock_timeout = '10s'")

            # idle_in_transaction_session_timeout: Chiude transazioni idle > 5 minuti
            # Previene leak di connessioni da codice bugato
            cursor.execute("SET idle_in_transaction_session_timeout = '5min'")

# =================================================================
# DEPENDENCY INJECTION - GESTIONE SESSIONI
# =================================================================

def get_db():
    """
    Dependency injection per sessioni database in FastAPI.

    PATTERN: Context manager con yield per gestire lifecycle sessione

    USO IN ENDPOINT:
    ```python
    @app.get("/collaborators/")
    def get_collaborators(db: Session = Depends(get_db)):
        # db è una sessione attiva
        collaborators = db.query(Collaborator).all()
        return collaborators
        # db viene chiusa automaticamente qui
    ```

    FLUSSO:
    1. Crea nuova sessione dal pool
    2. Yield sessione all'endpoint (esecuzione endpoint)
    3. Se tutto OK: commit implicito
    4. Se errore: rollback automatico
    5. Chiusura sessione e ritorno al pool

    VANTAGGI:
    - Gestione automatica apertura/chiusura
    - Rollback automatico su errori
    - Isolamento transazionale tra richieste
    - Riuso connessioni (pooling)

    IMPORTANTE: Ogni richiesta HTTP ha la propria sessione dedicata.
    Non c'è sharing di sessioni tra richieste diverse.
    """
    # Crea nuova sessione dal pool
    db = SessionLocal()
    try:
        # Yield sessione all'endpoint chiamante
        # L'esecuzione del codice endpoint avviene qui
        yield db

    except Exception as e:
        # Se si verifica un errore durante l'esecuzione endpoint:
        # 1. Logga l'errore per debugging
        logger.error(f"Database error: {e}")

        # 2. Rollback automatico delle modifiche non committate
        # Garantisce ACID: transazione atomica (tutto o niente)
        db.rollback()

        # 3. Re-raise exception per permettere gestione a livello superiore
        raise

    finally:
        # SEMPRE eseguito, anche in caso di errore
        # Chiude sessione e ritorna connessione al pool
        # Fondamentale per evitare connection leaks
        db.close()


# =================================================================
# HEALTH CHECK - MONITORING
# =================================================================

def check_db_health():
    """
    Verifica che il database sia raggiungibile e funzionante.

    Usato da:
    - Health check endpoint: GET /health
    - Monitoring tools (Prometheus, Grafana)
    - Startup checks per validare config

    LOGICA:
    1. Crea sessione temporanea
    2. Esegue query banale (SELECT 1)
    3. Se successo → database OK
    4. Se fallisce → database DOWN o irraggiungibile

    RETURNS:
        bool: True se database funzionante, False altrimenti

    ESEMPIO OUTPUT LOG:
        SUCCESS: (nessun log)
        FAILURE: "Database health check failed: could not connect to server"

    NOTA: Query "SELECT 1" è estremamente leggera e standard
    su tutti i database SQL. Non tocca tabelle reali.
    """
    try:
        # Import locale per evitare circular dependencies
        from sqlalchemy import text

        # Crea sessione temporanea per test
        db = SessionLocal()

        # Esegue query banale per testare connettività
        # text("SELECT 1") funziona su PostgreSQL, MySQL, SQLite
        db.execute(text("SELECT 1"))

        # Chiude sessione immediatamente (non serve più)
        db.close()

        # Ritorna True = database healthy
        return True

    except Exception as e:
        # Log errore per debugging (visibile in docker logs)
        logger.error(f"Database health check failed: {e}")

        # Ritorna False = database unhealthy
        # L'endpoint /health userà questo per rispondere con 503
        return False