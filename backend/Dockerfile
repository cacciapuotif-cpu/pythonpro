# ============================================================
# 🐳 DOCKERFILE MULTI-STAGE per Backend Python
# ============================================================
# Build ottimizzato con layer separati per:
# 1. Builder stage: compilazione dipendenze
# 2. Runtime stage: immagine finale minimale
# ============================================================

# --- STAGE 1: Builder ---
# Usa immagine completa per compilare dipendenze native
FROM python:3.11-slim as builder

# Variabili d'ambiente per ottimizzazione build
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Installa dipendenze di sistema necessarie per compilazione
# (build-essential per compilare pacchetti con estensioni C)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copia e installa dipendenze Python
# (separato per sfruttare cache Docker se requirements.txt non cambia)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# --- STAGE 2: Runtime (immagine finale) ---
FROM python:3.11-slim

# Metadata immagine
LABEL maintainer="Gestionale Team <info@gestionale.local>" \
      version="3.0.0" \
      description="Backend API Gestionale Collaboratori"

# Variabili d'ambiente per produzione
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/home/appuser/.local/bin:$PATH"

# Installa solo dipendenze runtime (NO build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    netcat-traditional \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Crea utente non-root per sicurezza
# (NON eseguire mai container come root in produzione!)
RUN groupadd -r appuser && useradd -r -g appuser -u 1000 appuser

# Crea directory di lavoro
WORKDIR /app

# Copia dipendenze Python da builder stage
COPY --from=builder /usr/local /usr/local

# Copia codice applicazione
COPY --chown=appuser:appuser . .
RUN chmod +x /app/entrypoint.sh


# Crea directory necessarie con permessi corretti
RUN mkdir -p /app/logs /app/uploads /app/backups && \
    chown -R appuser:appuser /app

# Cambia a utente non-root
USER appuser

# Health check per Docker
# Verifica che l'applicazione risponda su /health ogni 30s
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Esponi porta applicazione
EXPOSE 8000

# Entrypoint script per inizializzazione
ENTRYPOINT ["./entrypoint.sh"]

# Comando di default (può essere sovrascritto)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

# ============================================================
# BUILD INSTRUCTIONS:
# ------------------------------------------------------------
# Build:   docker build -t gestionale-backend:latest .
# Run:     docker run -p 8000:8000 gestionale-backend:latest
# Dev:     docker run -v $(pwd):/app -p 8000:8000 gestionale-backend:latest
# ============================================================
