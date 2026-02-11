# 📋 Changelog

Tutte le modifiche significative al progetto sono documentate qui.

Il formato è basato su [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
e questo progetto aderisce a [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Pianificate
- Sistema notifiche email
- Export dati in Excel/PDF
- Dashboard con grafici interattivi
- Sistema permessi granulari
- API GraphQL (opzionale)

---

## [3.0.0] - 2025-01-06

### 🚀 Refactoring Completo Production-Ready

Questa versione rappresenta un refactoring totale del sistema per renderlo robusto, sicuro e production-ready.

### ✨ Aggiunte

**DevOps & Tooling:**
- Aggiunto `pyproject.toml` con configurazione completa toolchain moderna
- Implementato CI/CD pipeline con GitHub Actions
- Creato Makefile completo con 30+ comandi per sviluppo
- Aggiunto `.dockerignore` per ottimizzazione build
- Dockerfile multi-stage per immagini più leggere e sicure

**Sicurezza:**
- Rimossi secret hardcodati da `docker-compose.yml`
- Migliorato `.env.example` con warning sicurezza espliciti
- Aggiunto `.gitignore` completo per prevenire commit di dati sensibili
- Implementato security scanning con Bandit
- Aggiunto audit dipendenze con pip-audit

**Testing & Quality:**
- Configurato Ruff per linting moderno
- Setup MyPy per type checking
- Configurato pytest con coverage minima 85%
- Aggiunto supporto test paralleli (pytest-xdist)
- Report coverage HTML e XML

**Documentazione:**
- Creato `CONTRIBUTING.md` con guide per contributori
- Aggiunto `CHANGELOG.md` (questo file)
- Migliorato README con istruzioni complete
- Documentazione in-code in italiano per principianti

**Infrastructure:**
- Entrypoint Docker robusto con retry e health checks
- Resource limits su container Docker
- Healthcheck automatici per tutti i servizi
- Volume persistence per uploads, logs, backups

### 🔧 Modifiche

- **Breaking**: docker-compose ora richiede file `.env` per secrets
- Aggiornato Python minimum a 3.11
- Logging più strutturato con correlation ID
- CORS configurabile via environment variables
- Database pool connection ottimizzato

### 🐛 Fix

- Risolti race conditions in startup container
- Fix permission issues in Docker (user non-root)
- Corretto timeout migrazioni Alembic
- Fix memory leaks in Redis cache

### 🔒 Sicurezza

- Rimozione completa password hardcoded
- Container eseguito come utente non-root
- Validazione input più stringente
- Rate limiting configurabile
- CORS origins whitelist

---

## [2.0.0] - 2024-10-05

### ✨ Aggiunte

- Sistema di autenticazione JWT completo
- Gestione Enti Attuatori
- Associazioni Progetto-Mansione-Ente
- Upload documenti (CV, documento identità)
- Sistema backup automatico
- Performance monitoring con metriche
- Error handling centralizzato
- Validatori avanzati per business logic

### 🔧 Modifiche

- Migrazione a PostgreSQL (da SQLite)
- Aggiunto Redis per caching
- Refactoring struttura app/ modulare
- Logging avanzato con structlog

### 🐛 Fix

- Validazione sovrapposizioni presenze
- Calcolo ore rimanenti assegnazioni
- Race conditions su creazioni multiple

---

## [1.0.0] - 2024-09-30

### ✨ Prima Release

**Features Principali:**
- Gestione Collaboratori (CRUD completo)
- Gestione Progetti formativi
- Calendario Presenze con React Big Calendar
- Associazioni Collaboratori-Progetti
- Tracking orario e note
- API REST con FastAPI
- Frontend React responsive
- Database SQLite
- Docker Compose setup

**Tech Stack:**
- Backend: Python 3.11, FastAPI, SQLAlchemy
- Frontend: React 18, Axios, Moment.js
- Database: SQLite (dev), PostgreSQL (prod)
- Deploy: Docker & Docker Compose

---

## Tipi di Cambiamenti

- `✨ Aggiunte` - Nuove funzionalità
- `🔧 Modifiche` - Modifiche a funzionalità esistenti
- `🐛 Fix` - Bug fix
- `🔒 Sicurezza` - Fix vulnerabilità sicurezza
- `⚡ Performance` - Miglioramenti performance
- `📝 Documentazione` - Solo documentazione
- `♻️ Refactoring` - Refactoring senza cambiare funzionalità
- `🧪 Testing` - Aggiunta o modifica test
- `🔨 Chore` - Manutenzione e build

---

## Link

- [Unreleased](https://github.com/yourusername/pythonpro/compare/v3.0.0...HEAD)
- [3.0.0](https://github.com/yourusername/pythonpro/compare/v2.0.0...v3.0.0)
- [2.0.0](https://github.com/yourusername/pythonpro/compare/v1.0.0...v2.0.0)
- [1.0.0](https://github.com/yourusername/pythonpro/releases/tag/v1.0.0)
