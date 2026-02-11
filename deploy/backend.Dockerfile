# ============================================================
# 🐳 DOCKERFILE - Backend Python/FastAPI
# ------------------------------------------------------------
# Questo file definisce come costruire l'immagine Docker
# del backend. Usa un'immagine Python leggera (Alpine)
# e installa tutte le dipendenze necessarie.
# ============================================================

# Immagine base: Python 3.11 su Alpine Linux (leggera)
FROM python:3.11-slim

# Metadata immagine
LABEL maintainer="team@gestionale.local"
LABEL description="Gestionale Collaboratori e Progetti - Backend FastAPI"
LABEL version="1.0.0"

# Imposta directory di lavoro
WORKDIR /app

# Variabili d'ambiente
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Installa dipendenze di sistema necessarie
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copia file requirements
COPY requirements.txt .

# Installa dipendenze Python
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copia tutto il codice sorgente
COPY . .

# Crea directory necessarie
RUN mkdir -p logs uploads backups

# Esponi porta 8000
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Comando di avvio (può essere sovrascritto in docker-compose)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
