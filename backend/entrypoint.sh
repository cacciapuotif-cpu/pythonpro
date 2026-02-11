#!/usr/bin/env bash
# ============================================================
# 🚀 ENTRYPOINT SCRIPT per Container Backend
# ============================================================
# Script di inizializzazione container che:
# 1. Attende disponibilità database e redis
# 2. Esegue migrazioni Alembic
# 3. Avvia server Gunicorn con uvicorn workers
# ============================================================

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# === VARIABILI D'AMBIENTE CON VALORI DI DEFAULT ===
: "${DB_HOST:=db}"
: "${DB_PORT:=5432}"
: "${DB_USER:=admin}"
: "${REDIS_HOST:=redis}"
: "${REDIS_PORT:=6379}"
: "${PORT:=8000}"
: "${WORKERS:=2}"
: "${TIMEOUT:=60}"
: "${GRACEFUL_TIMEOUT:=20}"
: "${MAX_REQUESTS:=1000}"
: "${MAX_REQUESTS_JITTER:=50}"
: "${LOG_LEVEL:=info}"

# === FUNZIONE DI LOG CON TIMESTAMP ===
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] [entrypoint] $*"
}

log_error() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] [entrypoint] ERROR: $*" >&2
}

# === ATTESA DATABASE POSTGRES ===
log "Waiting for PostgreSQL at ${DB_HOST}:${DB_PORT}..."

MAX_RETRIES=60
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if command -v pg_isready >/dev/null 2>&1; then
        if pg_isready -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" >/dev/null 2>&1; then
            log "PostgreSQL is ready!"
            break
        fi
    else
        # Se pg_isready non è disponibile, prova netcat
        if nc -z "${DB_HOST}" "${DB_PORT}" 2>/dev/null; then
            log "PostgreSQL port is open (pg_isready not available)"
            break
        fi
    fi

    RETRY_COUNT=$((RETRY_COUNT + 1))

    if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
        log_error "PostgreSQL did not become ready in time. Exiting."
        exit 1
    fi

    sleep 1
done

# === ATTESA REDIS (opzionale, non blocca avvio) ===
if [ -n "${REDIS_HOST:-}" ]; then
    log "Checking Redis at ${REDIS_HOST}:${REDIS_PORT}..."

    for i in {1..30}; do
        if nc -z "${REDIS_HOST}" "${REDIS_PORT}" 2>/dev/null; then
            log "Redis is ready!"
            break
        fi

        if [ $i -eq 30 ]; then
            log "WARNING: Redis not available. Continuing anyway..."
        fi

        sleep 1
    done
fi

# === ESECUZIONE MIGRAZIONI DATABASE ===
if command -v alembic >/dev/null 2>&1; then
    log "Running Alembic migrations..."

    if alembic upgrade head; then
        log "Migrations completed successfully"
    else
        log_error "Migrations failed. Check database connection and migration files."
        exit 1
    fi
else
    log "WARNING: Alembic not found. Skipping migrations."
fi

# === VERIFICA FILE APPLICAZIONE ===
if [ ! -f "main.py" ] && [ ! -f "app/main.py" ]; then
    log_error "Application file not found (main.py or app/main.py)"
    exit 1
fi

# === AVVIO SERVER GUNICORN ===
log "Starting Gunicorn server on 0.0.0.0:${PORT}"
log "Configuration:"
log "  - Workers: ${WORKERS}"
log "  - Timeout: ${TIMEOUT}s"
log "  - Graceful timeout: ${GRACEFUL_TIMEOUT}s"
log "  - Max requests: ${MAX_REQUESTS}"
log "  - Log level: ${LOG_LEVEL}"

# Determina il modulo app corretto
# NOTA: Forziamo l'uso di main.py (non app/main.py che è un template vuoto)
if [ -f "main.py" ]; then
    APP_MODULE="main:app"
else
    APP_MODULE="app.main:app"
fi

log "Using app module: ${APP_MODULE}"

# Avvia Gunicorn con exec per sostituire il processo shell
exec gunicorn ${APP_MODULE} \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:${PORT} \
  --workers ${WORKERS} \
  --timeout ${TIMEOUT} \
  --graceful-timeout ${GRACEFUL_TIMEOUT} \
  --max-requests ${MAX_REQUESTS} \
  --max-requests-jitter ${MAX_REQUESTS_JITTER} \
  --access-logfile - \
  --error-logfile - \
  --log-level ${LOG_LEVEL} \
  --forwarded-allow-ips '*'

# ============================================================
# FINE ENTRYPOINT SCRIPT
# ============================================================
