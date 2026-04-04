# 📋 Inventario Completo - Gestionale Pythonpro

**Data**: 2025-10-09
**Percorso**: `C:\pythonpro` (spostato da `C:\Users\cacci\OneDrive\Desktop\pythonpro`)

---

## 🎯 Stack Tecnologico

### Backend
- **Framework**: FastAPI
- **Server**: Gunicorn + Uvicorn workers
- **Database**: PostgreSQL 15 (in Docker), SQLite (sviluppo locale)
- **ORM**: SQLAlchemy
- **Migrazioni**: Alembic
- **Cache**: Redis 7
- **Linguaggio**: Python 3.11

### Frontend
- **Framework**: React 18.2
- **Build Tool**: react-scripts (Create React App)
- **HTTP Client**: Axios
- **Web Server**: Nginx 1.27 (produzione)
- **Node**: 18

### Orchestrazione
- **Docker Compose**: Stack completo con 5 servizi
- **Containerizzazione**: Docker Desktop per Windows

---

## 📂 Struttura Progetto

```
C:\pythonpro/
├── backend/              # Backend FastAPI
│   ├── app/             # Directory app (struttura alternativa)
│   │   ├── core/        # Settings, config
│   │   └── main.py      # Entry point alternativo
│   ├── alembic/         # Migrations framework
│   ├── migrations/      # Directory migrations Alembic
│   │   └── env.py       # Config Alembic
│   ├── tests/           # Suite test backend
│   ├── uploads/         # File caricati
│   ├── logs/            # Log applicazione
│   ├── venv/            # Virtual environment Python
│   ├── main.py          # Entry point principale (root level)
│   ├── models.py        # Modelli SQLAlchemy
│   ├── schemas.py       # Schemi Pydantic
│   ├── crud.py          # Operazioni database
│   ├── database.py      # Configurazione DB
│   ├── auth.py          # Sistema autenticazione
│   ├── Dockerfile       # Immagine Docker multi-stage
│   ├── entrypoint.sh    # Script inizializzazione container
│   ├── requirements.txt # Dipendenze Python
│   ├── alembic.ini      # Config Alembic
│   └── .env             # Configurazione locale (SQLite)
│
├── frontend/            # Frontend React
│   ├── src/
│   │   ├── components/  # Componenti React
│   │   ├── services/    # API client (api.js)
│   │   ├── context/     # Context providers
│   │   └── utils/       # Utilities
│   ├── build/           # Build di produzione
│   ├── node_modules/    # Dipendenze npm
│   ├── Dockerfile       # Immagine Docker multi-stage
│   ├── nginx.conf       # Configurazione Nginx
│   ├── package.json     # Dipendenze npm
│   └── .env.local       # Configurazione sviluppo
│
├── deploy/              # Configurazioni deployment
├── docs/                # Documentazione
├── monitoring/          # Stack monitoring (compose separato)
├── scripts/             # Script utility
├── migrations/          # Directory migrations (root)
│
├── docker-compose.yml   # Stack principale
├── .env.example         # Template variabili ambiente
├── .env.production.template
├── Makefile             # Task automation
├── README.md
└── CHANGELOG.md
```

---

## 🐳 Stack Docker

### Servizi Attivi (docker-compose.yml)

1. **db** (PostgreSQL 15)
   - Container: `pythonpro_db`
   - Porta: `5434:5432`
   - Status: **HEALTHY** ✅
   - Volume: `pythonpro_db_data`

2. **redis** (Redis 7)
   - Container: `pythonpro_redis`
   - Porta: `6381:6379`
   - Status: **HEALTHY** ✅
   - Volume: `pythonpro_redis_data`

3. **backend** (FastAPI)
   - Container: `pythonpro_backend`
   - Porta: `8001:8000`
   - Status: **HEALTHY** ✅
   - Volume bind: `./backend:/app`

4. **frontend** (React + Nginx)
   - Container: `pythonpro_frontend`
   - Porta: `3001:80`
   - Status: **HEALTHY** ✅
   - Build: Multi-stage (node build + nginx serve)
   - Proxy: `/api/` → `backend:8000`

5. **backup_scheduler** (CLI scheduler)
   - Container: `pythonpro_backup_scheduler`
   - Status: **RUNNING** ✅
   - Directory backup: `/app/backups`

---

## 🔍 File Chiave Individuati

### Configurazione
- `docker-compose.yml` - Stack completo (principale)
- `deploy/docker-compose.yml` - Deployment alternativo
- `monitoring/docker-compose-monitoring.yml` - Stack monitoring

### Backend
- `backend/Dockerfile` - Multi-stage build
- `backend/entrypoint.sh` - Init script (wait-for-db, migrate, start)
- `backend/main.py` - Entry point principale
- `backend/app/main.py` - Entry point alternativo (non primario)
- `backend/requirements.txt` - **INCOMPLETO** (manca pydantic-settings)
- `backend/alembic.ini` - Configurazione migrazioni
- `backend/.env` - Config locale (usa SQLite, non PostgreSQL!)

### Frontend
- `frontend/Dockerfile` - Multi-stage (build + nginx)
- `frontend/nginx.conf` - Reverse proxy config
- `frontend/src/services/api.js` - API client
- `frontend/.env.local` - Config dev (REACT_APP_API_URL=http://localhost:8001)
- `frontend/package.json` - Dipendenze npm

### Migrations
- `backend/migrations/` - Directory Alembic vuota (solo env.py)
- Nessuna migration versioned presente

---

## ⚠️ Problemi Identificati

### 🔴 CRITICI (bloccanti)

1. **Nota storica su backend/app**
   - La struttura `backend/app` esiste ancora ma non e` il target operativo principale
   - Il backend reale attivo e` `backend/main.py`
   - L'automazione e la documentazione operativa sono state riallineate a `main:app`

2. **Confusione entry point backend**
   - Esistono DUE main.py: `backend/main.py` e `backend/app/main.py`
   - L'entrypoint operativo usa `main:app`
   - `backend/app/main.py` e` da considerare struttura alternativa

3. **Migrations Alembic mancanti**
   - Directory `backend/migrations/` quasi vuota
   - Nessun file di migrazione versioned
   - `alembic.ini` punta a `migrations/` ma senza versioni

4. **Discrepanza configurazioni DB**
   - `backend/.env`: usa `DATABASE_URL=sqlite:///./gestionale.db`
   - `docker-compose.yml`: usa PostgreSQL con `postgresql+psycopg://...`
   - Mismatch tra dev locale e Docker

### 🟡 IMPORTANTI (da risolvere)

5. **Frontend unhealthy**
   - Problema storico: attualmente il frontend risulta operativo nello stack principale

6. **API base URL inconsistente**
   - Frontend .env.local: `http://localhost:8001` (sviluppo diretto)
   - api.js: usa `/api` come fallback (corretto per produzione Docker)
   - nginx.conf proxy: `/api/` → `backend:8000`
   - Funziona in produzione Docker, ma confuso per dev locale

7. **Volume mount backend problematico**
   - `./backend:/app` monta TUTTO, incluso venv locale (Windows)
   - Può causare conflitti dipendenze container vs host
   - Best practice: mount selettivo o solo codice sorgente

8. **Riferimenti path OneDrive**
   - 22 file contengono riferimenti a `OneDrive` o `Users\cacci`
   - Prevalentemente in:
     - Documentazione (*.md)
     - Log/report generati
     - Script utility
   - Da ripulire per evitare confusione

### 🟢 MINORI (non bloccanti)

9. **Favicon 404**
   - Frontend non ha favicon.ico
   - Nginx log riporta 404 (non critico)

10. **File "nul" spurii**
    - `backend/nul` e `nul` nella root
    - File vuoti generati da errori Windows (reserved name)
    - Da rimuovere

11. **Dipendenze requirements.txt minimali**
    - Solo 9 pacchetti base
    - Mancano: pydantic-settings, python-multipart, email-validator, etc.
    - Da completare con tutte le dipendenze effettive

12. **CORS configurato su porta 3001**
    - `BACKEND_CORS_ORIGINS=http://localhost:3001`
    - Corretto per Docker (frontend su 3001)
    - Da verificare che funzioni anche dev locale

---

## 📊 Stato Corrente Container

```bash
CONTAINER                   STATUS              PORTS
pythonpro_db               Up (healthy)        5434:5432
pythonpro_redis            Up (healthy)        6381:6379
pythonpro_backend          Up (healthy)        8001:8000
pythonpro_frontend         Up (healthy)        3001:80
pythonpro_backup_scheduler Up                  -
```

---

## 🎯 Endpoint Previsti

### Backend API
- Base URL: `http://localhost:8001`
- Health: `GET /health` (presente in main.py:1373)
- Docs: `GET /docs` (Swagger UI)
- API endpoints: `/collaborators/`, `/projects/`, `/attendances/`, `/assignments/`, ecc.

### Frontend
- URL: `http://localhost:3001`
- Proxy API: `/api/*` → `http://backend:8000/*`
- Healthcheck: `/healthz` (risponde 200 'ok')

---

## 📝 Note Tecniche

### Backend
- Usa Gunicorn con 2 workers Uvicorn (configurabile)
- Entrypoint script gestisce:
  - Wait-for-db (pg_isready)
  - Wait-for-redis (netcat)
  - Alembic migrations (upgrade head)
  - Start Gunicorn
- Sistema avanzato: error handler, validators, backup manager, monitoring

### Frontend
- Build produzione serve da Nginx
- SPA routing con fallback `try_files $uri /index.html`
- Gzip compression abilitata
- Cache assets statici (1 anno)

### Database
- PostgreSQL con encoding UTF8, locale it_IT.utf8
- Healthcheck ogni 5s
- Resource limits: 1 CPU, 1GB RAM max

### Redis
- Modalità AOF persistence
- MaxMemory 256MB con policy LRU
- Password protected

---

## 🔧 Prossimi Passi

Vedi tasks nella todo list per l'ordine di esecuzione dei fix.

---

**Generato automaticamente - Inventario Fase 1**
