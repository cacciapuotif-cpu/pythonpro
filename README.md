# 🚀 Gestionale Collaboratori e Progetti

Sistema completo per la gestione di collaboratori, progetti formativi, presenze e documenti.

**Versione:** 3.0.0
**Stack:** FastAPI + React + PostgreSQL + Redis + Docker
**Windows Ready:** Testato su Windows 11 con Docker Desktop + WSL2

---

## 📋 Indice

- [Quick Start](#-quick-start)
- [Requisiti](#-requisiti)
- [Installazione](#-installazione)
- [Configurazione](#️-configurazione)
- [Avvio](#-avvio)
- [Sviluppo](#-sviluppo)
- [Produzione](#-produzione)
- [Testing](#-testing)
- [Troubleshooting](#-troubleshooting)
- [Documentazione](#-documentazione)

---

## ⚡ Quick Start

```powershell
# 1. Clona e naviga
cd C:\pythonpro

# 2. Avvio rapido (con script automatico)
.\tools\avvio_pulito.ps1

# 3. Apri browser
# Frontend: http://localhost:3001
# API Docs: http://localhost:8001/docs
```

**Stato attuale:** ✅ Tutti i container funzionanti e healthy

---

## 📦 Requisiti

### Windows
- **OS:** Windows 10/11 (build 19041+)
- **WSL2:** Abilitato e aggiornato
- **Docker Desktop:** 4.20+ con WSL2 backend
- **PowerShell:** 5.1+ (pre-installato)
- **RAM:** 8GB minimo, 16GB consigliato
- **Spazio disco:** 10GB libero

### Verifica requisiti
```powershell
# Docker
docker --version
docker compose version

# WSL
wsl --status
wsl --list --verbose
```

---

## 🔧 Installazione

### 1. Docker Desktop (se non installato)

1. Scarica da: https://www.docker.com/products/docker-desktop
2. Installa con impostazioni predefinite
3. Abilita WSL2 backend nelle impostazioni
4. Riavvia Windows

### 2. Clona o sposta progetto

```powershell
# Se già presente, verifica path
cd C:\pythonpro

# Se da clonare (esempio)
git clone <repo-url> C:\pythonpro
cd C:\pythonpro
```

### 3. Verifica struttura

```
C:\pythonpro/
├── backend/          # FastAPI + Python
├── frontend/         # React + Nginx
├── docker-compose.yml
├── docker-compose.prod.yml
├── tools/            # Script PowerShell
└── docs/             # Documentazione
```

---

## ⚙️ Configurazione

### File .env (Sviluppo)

Il progetto include `.env.development` preconfigurato. Per personalizzare:

```powershell
# Copia template
cp .env.sample .env

# Modifica con editor
notepad .env
```

**Variabili principali:**
- `DB_PASSWORD`: Password PostgreSQL (cambia in produzione!)
- `REDIS_PASSWORD`: Password Redis
- `JWT_SECRET_KEY`: Chiave JWT (genera con `openssl rand -hex 32`)
- `BACKEND_CORS_ORIGINS`: Origini CORS permesse

### File .env (Produzione)

```powershell
cp .env.production.template .env
# Modifica con password sicure!
```

**⚠️ IMPORTANTE:**
- Mai committare `.env` su Git
- Usa password complesse in produzione
- Genera JWT secret con: `openssl rand -hex 32`

---

## 🚀 Avvio

### Metodo 1: Script Automatico (Consigliato)

```powershell
# Avvio pulito con cleanup WSL
.\tools\avvio_pulito.ps1 -Clean

# Avvio rapido sviluppo
.\scripts\dev_up.ps1

# Avvio produzione
.\scripts\prod_up.ps1
```

### Metodo 2: Docker Compose Manuale

```powershell
# Sviluppo
docker compose up -d --build

# Produzione
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Stop
docker compose down

# Reset completo (ATTENZIONE: elimina dati!)
docker compose down -v
```

### Verifica Stato

```powershell
# Status container
docker compose ps

# Logs
docker compose logs -f

# Logs singolo servizio
docker compose logs -f backend
```

**Tutti i container devono essere `healthy`:**
```
pythonpro_db               healthy
pythonpro_redis            healthy
pythonpro_backend          healthy
pythonpro_frontend         healthy
pythonpro_backup_scheduler running
```

---

## 💻 Sviluppo

### Accesso Servizi

| Servizio | URL | Credenziali |
|----------|-----|-------------|
| **Frontend** | http://localhost:3001 | - |
| **Backend API** | http://localhost:8001 | - |
| **API Docs** | http://localhost:8001/docs | - |
| **PostgreSQL** | localhost:5434 | `admin` / vedi .env |
| **Redis** | localhost:6381 | vedi .env |

### Sviluppo Backend (standalone)

```powershell
cd backend

# Crea virtual environment
python -m venv venv
venv\Scripts\activate

# Installa dipendenze
pip install -r requirements.txt

# Configura .env (usa SQLite)
cp .env.sample .env

# Avvia server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Sviluppo Frontend (standalone)

```powershell
cd frontend

# Installa dipendenze
npm install

# Configura .env.local
cp .env.sample .env.local
# Setta REACT_APP_API_URL=http://localhost:8001

# Avvia dev server
npm start
```

### Database Migrations (Alembic)

```powershell
# Dentro container backend
docker compose exec backend alembic upgrade head

# Crea nuova migration
docker compose exec backend alembic revision --autogenerate -m "descrizione"

# Storico migrations
docker compose exec backend alembic history
```

### Backup Automatico

Il progetto usa un servizio separato `backup_scheduler`, verificato runtime, che esegue i backup fuori dal processo web.

```powershell
# Stato scheduler
docker compose ps backup_scheduler

# Log scheduler
docker compose logs -f backup_scheduler

# Backup manuale
make backup

# Elenco backup disponibili
make backup-list
```

**Variabili configurabili in `.env`:**
- `BACKUP_DIR`
- `BACKUP_RETENTION_COUNT`
- `BACKUP_DAILY_TIME`
- `BACKUP_WEEKLY_TIME`
- `BACKUP_MONTHLY_INTERVAL_DAYS`

**Output backup:**
- archivio ZIP nella directory backup
- file JSON con metadata e checksum

Esempio:
```text
gestionale_backup_manual_20260319_154825.sql.zip
gestionale_backup_manual_20260319_154825.sql.json
```

---

## 🏭 Produzione

### Preparazione

1. **Genera password sicure:**
   ```powershell
   # JWT Secret
   openssl rand -hex 32

   # Database password (esempio)
   openssl rand -base64 24
   ```

2. **Configura .env produzione:**
   ```powershell
   cp .env.production.template .env
   # Modifica con password generate
   ```

3. **Build immagini:**
   ```powershell
   docker compose build --no-cache
   ```

### Deploy

```powershell
# Avvio stack produzione
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Verifica health
docker compose ps

# Smoke test
.\scripts\smoke_test.ps1
```

### Backup Database

```powershell
# Backup manuale tramite scheduler
docker compose exec -T backup_scheduler python run_backup.py create --type manual

# Elenco backup disponibili
docker compose exec -T backup_scheduler python run_backup.py list
```

I backup vengono salvati nel volume `backend_backups` come file ZIP più metadata JSON.
Per il restore applicativo usare l'endpoint admin o una procedura di restore SQL in finestra di manutenzione.

### Monitoraggio

```powershell
# Logs produzione
docker compose logs -f --tail=100

# Metriche container
docker stats

# Health check
curl http://localhost:8001/health
```

Vedi `docs/RUNBOOK_produzione.md` per procedure complete.

---

## 🧪 Testing

### Smoke Test

```powershell
# Test completo stack
.\scripts\smoke_test.ps1
```

Output atteso:
```
✅ TUTTI I TEST PASSATI!
   Tests Passed: 9 / 9
```

### Test Backend

```powershell
# Dentro container
docker compose exec backend pytest

# Con coverage
docker compose exec backend pytest --cov=app --cov-report=html
```

### Test Endpoint Manualmente

```powershell
# Health
curl http://localhost:8001/health

# API Docs
start http://localhost:8001/docs

# Frontend
start http://localhost:3001
```

---

## 🔧 Troubleshooting

### Container non parte

```powershell
# 1. Cleanup completo
docker compose down -v
wsl --shutdown

# 2. Riavvia Docker Desktop
# Vai su icona Docker Desktop → Quit → Riapri

# 3. Usa script pulito
.\tools\avvio_pulito.ps1 -Clean -Build
```

### Backend in crash loop

```powershell
# Verifica logs
docker compose logs backend --tail=50

# Problemi comuni:
# - pydantic-settings mancante: rebuilda (.\tools\avvio_pulito.ps1 -Build)
# - CORS origins: verifica .env BACKEND_CORS_ORIGINS
# - Database non pronto: attendi 30s per healthcheck
```

### Frontend unhealthy

```powershell
# Rebuilda frontend
docker compose build frontend
docker compose up -d frontend

# Verifica healthcheck
docker inspect pythonpro_frontend --format='{{json .State.Health}}'

# Test manuale
curl http://localhost:3001/healthz
```

### Errori WSL

```powershell
# Reset WSL
wsl --shutdown
wsl --unregister docker-desktop
wsl --unregister docker-desktop-data

# Riavvia Docker Desktop
# Il sistema ricrea le distribuzioni automaticamente
```

### Database connection refused

```powershell
# Verifica container DB
docker compose ps db
docker compose logs db

# Verifica porta
netstat -an | findstr 5433

# Reset DB (ATTENZIONE: perde dati)
docker compose down -v
docker compose up -d
```

### Porta già in uso

```powershell
# Identifica processo su porta 8000
netstat -ano | findstr :8000

# Termina processo (sostituisci PID)
taskkill /PID <PID> /F

# Oppure avvia backend su porta alternativa
cd backend
PORT=8002 venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8002

# Poi aggiorna frontend/.env.local
# REACT_APP_API_URL=http://localhost:8002
```

### React Error #31 (Objects are not valid as a React child)

Se vedi questo errore in console:

**Causa**: Rendering diretto di oggetti in JSX invece di stringhe

**Soluzione**: Usa il component `ErrorBanner` per gestire errori:

```jsx
import ErrorBanner from './components/ErrorBanner';

// ❌ ERRATO
{error && <div>{error}</div>}

// ✅ CORRETTO
{error && <div><ErrorBanner error={error} /></div>}
```

Il component `ErrorBanner` è già implementato e gestisce:
- AxiosError (errori API)
- Error standard JavaScript
- Stringhe
- Oggetti generici (con stringify fallback)

---

## 🧪 Testing

### Smoke Test (Verifica Connettività FE↔BE)

Per verificare che backend e frontend siano configurati correttamente:

```powershell
# Con porta standard (8000)
node scripts/smoke.js

# Con porta custom
$env:BACKEND_PORT=8002; node scripts/smoke.js
```

**Output atteso:**
```
✅ Test passati:   5
   Success rate:   100.0%
```

**Test eseguiti:**
- Backend Health Check (`/health`)
- Root Endpoint (`/`)
- Projects API (`/api/v1/projects/`)
- Collaborators API (`/api/v1/collaborators/`)
- API Docs (`/docs`)

**Log salvato in:** `artifacts/smoke.log`

---

## 📚 Documentazione

### File Documentazione

- **[RUNBOOK_produzione.md](docs/RUNBOOK_produzione.md)** - Procedure produzione
- **[01_inventario.md](docs/01_inventario.md)** - Inventario completo progetto
- **[CHANGELOG.md](CHANGELOG.md)** - Storico modifiche
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Guida contribuzione

### API Documentation

- **Swagger UI:** http://localhost:8001/docs
- **ReDoc:** http://localhost:8001/redoc

### Script Utili

| Script | Descrizione |
|--------|-------------|
| `tools/avvio_pulito.ps1` | Avvio completo con cleanup WSL |
| `scripts/dev_up.ps1` | Quick start sviluppo |
| `scripts/prod_up.ps1` | Avvio produzione |
| `scripts/smoke_test.ps1` | Suite test minimale |

---

## 🤝 Supporto

### Problemi Comuni

Vedi sezione [Troubleshooting](#-troubleshooting)

### Log e Debug

```powershell
# Tutti i servizi
docker compose logs -f

# Solo backend
docker compose logs -f backend | Select-String "ERROR"

# Esporta logs
docker compose logs > full_logs.txt
```

### Reset Completo

```powershell
# 1. Stop e rimuovi tutto
docker compose down -v

# 2. Pulisci immagini (opzionale)
docker system prune -a --volumes

# 3. Riavvia da zero
.\tools\avvio_pulito.ps1 -Clean -Build
```

---

## 📄 Licenza

Proprietario. Uso interno.

---

## 👨‍💻 Autore

Gestionale Team
Versione: 3.0.0
Data: 2025-10-09

---

**🎯 Status Progetto: PRODUCTION READY**

✅ Backend healthy
✅ Frontend healthy
✅ Database migrations OK
✅ Tests passing
✅ Documentation complete
