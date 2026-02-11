"""
============================================================
🚀 FILE: main.py
------------------------------------------------------------
Entry point principale dell'applicazione FastAPI.

SCOPO:
Questo file crea e configura l'intera applicazione web del gestionale.
Qui definiamo:
- La creazione dell'istanza FastAPI
- Il ciclo di vita (startup/shutdown) per inizializzare/chiudere risorse
- I middleware globali (CORS, logging, sicurezza)
- Gli endpoint di base (/health, /version)
- Il montaggio dei router per le varie funzionalità

NOTA PER CHI INIZIA:
FastAPI è un framework moderno per creare API REST in Python.
L'"app" qui sotto è l'oggetto principale su cui registriamo
endpoint (rotte) e middleware (comportamenti applicati a tutte le richieste).

COLLEGAMENTI:
- Impostazioni: app/core/settings.py
- Router API: app/api/* (da creare)
- Modelli: app/domain/* (da creare)
============================================================
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator
from datetime import datetime
import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Importazioni dai moduli interni del nostro progetto
from app.core.settings import get_settings

# IMPORTAZIONI ROUTERS IN-MEMORY API
from app.api import (
    collaborators,
    projects,
    entities,
    assignments,
    attendances,
    reporting,
    contracts
)

# ============================================================
# CONFIGURAZIONE LOGGING
# ============================================================
# Il logging ci permette di tracciare eventi, errori e debug info.
# Configuriamo il formato e il livello di dettaglio.

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format=settings.LOG_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout),  # Output su console
        # TODO: Aggiungere FileHandler per log su file in produzione
        # logging.FileHandler(settings.LOG_FILE),
    ]
)

logger = logging.getLogger(__name__)

# ============================================================
# LIFESPAN DELL'APPLICAZIONE
# ============================================================
# Il "lifespan" è il ciclo di vita completo dell'app:
#
# STARTUP (prima parte):
# - Viene eseguito quando l'app si avvia
# - Qui inizializziamo risorse: DB, cache, connessioni esterne
#
# SHUTDOWN (parte finally):
# - Viene eseguito quando l'app si spegne
# - Qui chiudiamo in modo pulito tutte le risorse aperte
#
# VANTAGGI:
# - Garantisce che le risorse vengano sempre chiuse correttamente
# - Migliore gestione degli errori rispetto ai vecchi eventi on_event
# - È lo standard moderno di FastAPI (raccomandato dalla documentazione)
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Gestisce il ciclo di vita dell'applicazione.

    FASE STARTUP (prima del yield):
    - Inizializza connessioni database
    - Inizializza cache (Redis, se abilitata)
    - Configura sistemi di monitoraggio
    - Avvia task in background (backup, cleanup, etc.)

    FASE SHUTDOWN (dopo il yield, nel finally):
    - Chiude connessioni database
    - Salva cache su disco
    - Crea backup di emergenza
    - Ferma task in background

    Args:
        app: Istanza FastAPI

    Yields:
        None: L'app resta attiva tra startup e shutdown
    """
    # ========================================
    # FASE STARTUP
    # ========================================
    logger.info("="*70)
    logger.info(f"[AVVIO] {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"[AMBIENTE] {settings.APP_ENV}")
    logger.info(f"[DEBUG] {settings.DEBUG}")
    logger.info("="*70)

    # TODO: Inizializza connessione database
    # Esempio:
    # from app.core.database import init_db
    # await init_db(settings.DATABASE_URL)
    # logger.info("[OK] Database connesso")

    # TODO: Inizializza cache Redis (se abilitata)
    # if settings.ENABLE_REDIS:
    #     from app.core.cache import init_cache
    #     await init_cache(settings.REDIS_URL)
    #     logger.info("[OK] Cache Redis connessa")

    # TODO: Avvia sistema di backup automatico
    # if settings.ENABLE_AUTO_BACKUP:
    #     from app.utils.backup import start_backup_scheduler
    #     start_backup_scheduler()
    #     logger.info("[OK] Backup automatico avviato")

    # TODO: Avvia monitoraggio performance
    # if settings.ENABLE_MONITORING:
    #     from app.utils.monitoring import start_monitoring
    #     start_monitoring()
    #     logger.info("[OK] Monitoraggio performance attivo")

    logger.info("[OK] Applicazione avviata con successo")
    logger.info("="*70)

    # ========================================
    # L'app rimane attiva qui (yield)
    # ========================================
    try:
        yield  # L'applicazione gira finché non viene fermata
    finally:
        # ========================================
        # FASE SHUTDOWN
        # ========================================
        logger.info("="*70)
        logger.info("[SHUTDOWN] Arresto applicazione in corso...")
        logger.info("="*70)

        # TODO: Chiudi connessioni database
        # from app.core.database import close_db
        # await close_db()
        # logger.info("[OK] Database disconnesso")

        # TODO: Salva cache su disco (se necessario)
        # if settings.ENABLE_REDIS:
        #     from app.core.cache import close_cache
        #     await close_cache()
        #     logger.info("[OK] Cache chiusa")

        # TODO: Crea backup di emergenza allo shutdown
        # if settings.ENABLE_AUTO_BACKUP:
        #     from app.utils.backup import create_emergency_backup
        #     create_emergency_backup()
        #     logger.info("[OK] Backup di emergenza creato")

        # TODO: Ferma task in background
        # from app.utils.scheduler import stop_scheduler
        # stop_scheduler()
        # logger.info("[OK] Task in background fermati")

        logger.info("[OK] Applicazione arrestata correttamente")
        logger.info("="*70)


# ============================================================
# CREAZIONE APPLICAZIONE FASTAPI
# ============================================================
# Creiamo l'istanza principale di FastAPI.
# Qui configuriamo:
# - Titolo e versione (per documentazione OpenAPI)
# - Lifespan (gestione startup/shutdown)
# - URL della documentazione (Swagger/ReDoc)
# ============================================================

app = FastAPI(
    title=settings.APP_NAME,
    description="""
    Sistema gestionale completo per:
    - 👥 Collaboratori (anagrafica, ruoli, tariffe)
    - 📋 Progetti (budget, ente attuatore, stato)
    - 📝 Incarichi (assegnazioni ai progetti con mansioni)
    - ⏰ Presenze (rilevazioni orarie con validazioni)
    - 📄 Contratti (collaborazione, P.IVA, subordinato)
    - 💰 Rendicontazione (FSE+, Fondimpresa, PNRR)
    """,
    version=settings.APP_VERSION,
    lifespan=lifespan,  # Collega il ciclo di vita definito sopra
    docs_url="/docs" if settings.ENABLE_SWAGGER_DOCS else None,      # Documentazione Swagger UI
    redoc_url="/redoc" if settings.ENABLE_SWAGGER_DOCS else None,    # Documentazione ReDoc
    openapi_url="/openapi.json" if settings.ENABLE_SWAGGER_DOCS else None,  # Schema OpenAPI
    debug=settings.DEBUG,
)

# ============================================================
# CONFIGURAZIONE MIDDLEWARE
# ============================================================
# I middleware sono "strati" che processano ogni richiesta/risposta.
# Vengono eseguiti in ordine per TUTTE le richieste.
# ============================================================

# --- CORS Middleware ---
# CORS (Cross-Origin Resource Sharing) permette al frontend
# (es. React su porta 3000) di chiamare il backend (porta 8000)
# anche se sono su domini/porte diversi.
#
# SICUREZZA:
# - In sviluppo: permettiamo tutti i domini (comodo per test)
# - In produzione: specifica SOLO i domini autorizzati in .env
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,  # Domini autorizzati (da settings)
    allow_credentials=True,  # Permette invio cookies/auth headers
    allow_methods=["*"],     # Permette tutti i metodi HTTP (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],     # Permette tutti gli headers
)

# TODO: Aggiungere altri middleware quando necessario
# Esempi:
# - Rate limiting (limitare richieste per IP)
# - Compression (comprimere risposte grandi)
# - Security headers (aggiungere header di sicurezza)
# - Request logging (loggare tutte le richieste)

# ============================================================
# ENDPOINT DI SISTEMA
# ============================================================
# Endpoint base per verificare stato e informazioni del server.
# Utili per monitoring, health check, debugging.
# ============================================================

@app.get("/", tags=["Sistema"])
async def root():
    """
    **Endpoint Root** - Benvenuto e informazioni base

    Questo endpoint fornisce informazioni generali sull'API.
    Utile per:
    - Verificare che il server sia attivo
    - Vedere la versione corrente
    - Sapere dove trovare la documentazione

    Returns:
        dict: Informazioni generali sull'applicazione

    Example:
        ```bash
        curl http://localhost:8000/
        ```

        Response:
        ```json
        {
          "app": "Gestionale Collaboratori e Progetti",
          "version": "1.0.0",
          "status": "online",
          "docs": "/docs"
        }
        ```
    """
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "status": "online",
        "docs": "/docs" if settings.ENABLE_SWAGGER_DOCS else "disabled",
        "health": "/health",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/health", tags=["Sistema"])
async def health_check():
    """
    **Health Check** - Verifica stato del sistema

    Endpoint per monitorare lo stato dell'applicazione e delle sue dipendenze.

    UTILIZZO:
    - Load balancer: verificare se instradare traffico a questo server
    - Monitoring: Prometheus, Grafana, Datadog
    - CI/CD: verificare che il deploy sia riuscito
    - Docker/Kubernetes: health check automatici

    CHECKS ESEGUITI:
    - API: sempre "ok" se l'endpoint risponde
    - Database: (TODO) verifica connessione
    - Cache: (TODO) verifica Redis
    - Storage: (TODO) verifica spazio disco

    Returns:
        JSONResponse: Stato dettagliato del sistema

    Status Codes:
        - 200: Sistema completamente sano
        - 503: Sistema parzialmente degradato (Service Unavailable)

    Example:
        ```bash
        curl http://localhost:8000/health
        ```

        Response (tutto ok):
        ```json
        {
          "status": "healthy",
          "timestamp": "2025-01-05T10:30:00",
          "version": "1.0.0",
          "checks": {
            "api": "ok",
            "database": "ok",
            "cache": "ok"
          }
        }
        ```
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "checks": {
            "api": "ok",
            # TODO: Aggiungere check database
            # "database": await check_database(),
            # TODO: Aggiungere check cache
            # "cache": await check_redis() if settings.ENABLE_REDIS else "disabled",
            # TODO: Aggiungere check storage
            # "storage": check_disk_space(),
        }
    }

    # Verifica se tutti i check sono "ok"
    all_healthy = all(
        check == "ok" or check == "disabled"
        for check in health_status["checks"].values()
    )

    # Status code HTTP:
    # - 200 se tutto ok
    # - 503 (Service Unavailable) se c'è qualche problema
    status_code = 200 if all_healthy else 503

    logger.debug(f"Health check eseguito: {health_status}")

    return JSONResponse(
        content=health_status,
        status_code=status_code
    )


@app.get("/version", tags=["Sistema"])
async def version_info():
    """
    **Informazioni Versione** - Dettagli ambiente e configurazione

    Restituisce informazioni dettagliate su versione, ambiente e configurazione.

    UTILITÀ:
    - Debugging: capire in quale ambiente sta girando l'app
    - Deploy: verificare che la versione deployata sia quella corretta
    - Support: fornire info tecniche per supporto utenti

    Returns:
        dict: Informazioni dettagliate su versione e configurazione

    Example:
        ```bash
        curl http://localhost:8000/version
        ```

        Response:
        ```json
        {
          "app_name": "Gestionale Collaboratori e Progetti",
          "version": "1.0.0",
          "environment": "development",
          "debug": true,
          "features": {
            "swagger_docs": true,
            "monitoring": true,
            "auto_backup": false
          }
        }
        ```
    """
    return {
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "debug": settings.DEBUG,
        "features": {
            "swagger_docs": settings.ENABLE_SWAGGER_DOCS,
            "monitoring": settings.ENABLE_MONITORING,
            "audit_log": settings.ENABLE_AUDIT_LOG,
            "auto_backup": settings.ENABLE_AUTO_BACKUP,
        },
        "database": {
            "type": "postgresql" if "postgresql" in settings.DATABASE_URL else "sqlite",
            "pool_size": settings.DB_POOL_SIZE if "postgresql" in settings.DATABASE_URL else None,
        }
    }


# ============================================================
# REGISTRAZIONE ROUTER API
# ============================================================
# Qui monteremo i router per le varie funzionalità del gestionale.
# Ogni router gestisce un'area funzionale (es. collaboratori, progetti).
#
# PATTERN:
# 1. Importa il router dal modulo
# 2. Registralo con app.include_router()
# 3. Specifica un prefix (es. /api/v1/collaborators)
# 4. Specifica tag per raggruppare nella documentazione
#
# ESEMPIO (da decommentare quando i router saranno creati):
# ============================================================

# ============================================================
# ROUTER API v1 - In-Memory Implementation
# ============================================================
# I router hanno già i prefix definiti internamente (/api/v1/...)
# quindi si montano direttamente senza specificare prefix qui

# Router gestione risorse principali
app.include_router(collaborators.router)
app.include_router(projects.router)
app.include_router(entities.router)

# Router gestione assegnazioni e presenze
app.include_router(assignments.router)
app.include_router(attendances.router)

# Router reporting e contratti
app.include_router(reporting.router)
app.include_router(contracts.router)

logger.info("[OK] Router API v1 montati: collaborators, projects, entities, assignments, attendances, reporting, contracts")


# ============================================================
# HANDLER ERRORI GLOBALI
# ============================================================
# Qui possiamo definire gestori personalizzati per vari tipi di errore.
# Questo garantisce risposte consistenti e informative agli utenti.
#
# TODO: Aggiungere quando necessario
# ============================================================

# Esempio:
# from fastapi import HTTPException
# from sqlalchemy.exc import SQLAlchemyError
#
# @app.exception_handler(HTTPException)
# async def http_exception_handler(request, exc):
#     return JSONResponse(
#         status_code=exc.status_code,
#         content={"error": exc.detail}
#     )
#
# @app.exception_handler(SQLAlchemyError)
# async def database_exception_handler(request, exc):
#     logger.error(f"Database error: {exc}")
#     return JSONResponse(
#         status_code=500,
#         content={"error": "Errore database"}
#     )


# ============================================================
# ESECUZIONE DIRETTA (SOLO PER SVILUPPO/TEST)
# ============================================================
# Questo blocco permette di avviare il server con:
#   python backend/app/main.py
#
# NOTA: In produzione NON si usa questo metodo!
# Si usa invece:
#   - uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
#   - gunicorn backend.app.main:app -w 4 -k uvicorn.workers.UvicornWorker
#   - make run (che usa uvicorn)
#   - Docker (che usa uvicorn nel Dockerfile)
# ============================================================

if __name__ == "__main__":
    """
    Esecuzione diretta del server (solo per sviluppo locale rapido).

    AVVERTENZA:
    Questo metodo è comodo per test rapidi, ma in produzione
    si dovrebbe usare uvicorn o gunicorn per migliori performance
    e gestione dei worker.

    Uso:
        python backend/app/main.py
    """
    import uvicorn

    logger.info("[DEV] Avvio server in modalità sviluppo diretto")
    logger.info(f"[INFO] Per produzione usare: uvicorn backend.app.main:app")

    uvicorn.run(
        "app.main:app",         # Path al modulo (relativo)
        host=settings.HOST,     # Host da settings (default: 0.0.0.0)
        port=settings.PORT,     # Porta da settings (default: 8000)
        reload=settings.DEBUG,  # Auto-reload se in debug mode
        log_level=settings.LOG_LEVEL.lower(),
    )
