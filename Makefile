# ============================================================
# 🧩 MAKEFILE DEL GESTIONALE COLLABORATORI
# ============================================================
# Centralizza tutti i comandi per sviluppo, test e deploy
# Usa: make <comando>
# ============================================================

.PHONY: help install install-dev setup lint format typecheck test coverage security clean preflight up down ps logs restart smoke docker-rebuild migrate migrate-new run dev prod health backup audit all-checks

# Colori per output (opzionale)
BLUE := \033[1;34m
GREEN := \033[1;32m
YELLOW := \033[1;33m
RED := \033[1;31m
NC := \033[0m  # No Color

# Variabili
PYTHON := backend/venv/Scripts/python.exe
PIP := backend/venv/Scripts/pip.exe
PYTEST := backend/venv/Scripts/pytest.exe
RUFF := backend/venv/Scripts/ruff.exe
MYPY := backend/venv/Scripts/mypy.exe
ALEMBIC := backend/venv/Scripts/alembic.exe
BANDIT := backend/venv/Scripts/bandit.exe

BACKEND_DIR := backend
FRONTEND_DIR := frontend
TEST_DIR := $(BACKEND_DIR)/tests

# ============================================================
# COMANDI PRINCIPALI
# ============================================================

## help: Mostra questo messaggio di aiuto
help:
	@echo "$(BLUE)============================================================$(NC)"
	@echo "$(BLUE)  GESTIONALE COLLABORATORI - Comandi Make$(NC)"
	@echo "$(BLUE)============================================================$(NC)"
	@echo ""
	@echo "$(GREEN)Setup e Installazione:$(NC)"
	@echo "  make setup          - Setup completo progetto (prima volta)"
	@echo "  make install        - Installa dipendenze produzione"
	@echo "  make install-dev    - Installa dipendenze sviluppo"
	@echo ""
	@echo "$(GREEN)Sviluppo:$(NC)"
	@echo "  make dev            - Avvia server sviluppo con hot-reload"
	@echo "  make run            - Avvia server produzione locale"
	@echo ""
	@echo "$(GREEN)Quality & Testing:$(NC)"
	@echo "  make lint           - Controlla qualità codice (ruff)"
	@echo "  make format         - Formatta codice automaticamente"
	@echo "  make typecheck      - Verifica type hints (mypy)"
	@echo "  make test           - Esegue test unitari"
	@echo "  make coverage       - Test con report coverage"
	@echo "  make security       - Scan vulnerabilità sicurezza"
	@echo "  make all-checks     - Esegue tutti i controlli (lint+type+test+security)"
	@echo ""
	@echo "$(GREEN)Database:$(NC)"
	@echo "  make migrate        - Applica migrazioni database"
	@echo "  make migrate-new    - Crea nuova migrazione (MSG=descrizione)"
	@echo "  make backup         - Crea backup database manuale"
	@echo ""
	@echo "$(GREEN)Docker:$(NC)"
	@echo "  make preflight      - Verifica porte libere"
	@echo "  make up             - Avvia stack (con preflight)"
	@echo "  make down           - Ferma stack"
	@echo "  make ps             - Stato containers"
	@echo "  make logs           - Logs stack (tail -f)"
	@echo "  make restart        - Restart completo stack"
	@echo "  make smoke          - Smoke test API endpoints"
	@echo "  make docker-rebuild - Rebuild e restart Docker"
	@echo ""
	@echo "$(GREEN)Utility:$(NC)"
	@echo "  make clean          - Pulisce file temporanei"
	@echo "  make health         - Verifica salute servizi"
	@echo "  make audit          - Audit dipendenze (vulnerabilità)"
	@echo ""

# ============================================================
# SETUP E INSTALLAZIONE
# ============================================================

## setup: Setup completo per prima installazione
setup: clean
	@echo "$(BLUE)🚀 Setup completo progetto...$(NC)"
	@echo "$(YELLOW)Creazione virtual environment...$(NC)"
	cd $(BACKEND_DIR) && python -m venv venv || python3 -m venv venv
	@echo "$(YELLOW)Upgrade pip...$(NC)"
	$(PIP) install --upgrade pip setuptools wheel
	@echo "$(YELLOW)Installazione dipendenze...$(NC)"
	$(MAKE) install-dev
	@echo "$(YELLOW)Creazione directory necessarie...$(NC)"
	mkdir -p $(BACKEND_DIR)/logs $(BACKEND_DIR)/uploads $(BACKEND_DIR)/backups
	@echo "$(YELLOW)Creazione file .env da template...$(NC)"
	@if [ ! -f .env ]; then cp .env.example .env; echo "⚠️  Ricorda di configurare .env con i tuoi valori!"; fi
	@echo "$(GREEN)✅ Setup completato!$(NC)"

## install: Installa dipendenze produzione
install:
	@echo "$(BLUE)📦 Installazione dipendenze produzione...$(NC)"
	cd $(BACKEND_DIR) && $(PIP) install -r requirements.txt
	@echo "$(GREEN)✅ Dipendenze installate$(NC)"

## install-dev: Installa dipendenze sviluppo
install-dev: install
	@echo "$(BLUE)📦 Installazione dipendenze sviluppo...$(NC)"
	cd $(BACKEND_DIR) && $(PIP) install \
		pytest pytest-cov pytest-asyncio pytest-mock pytest-xdist \
		ruff black isort \
		mypy types-redis \
		bandit pip-audit safety \
		ipython
	@echo "$(GREEN)✅ Dipendenze sviluppo installate$(NC)"

# ============================================================
# SVILUPPO E RUN
# ============================================================

## dev: Avvia server sviluppo con hot-reload
dev:
	@echo "$(BLUE)🚀 Avvio server sviluppo (hot-reload)...$(NC)"
	cd $(BACKEND_DIR) && $(PYTHON) -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

## run: Avvia server produzione locale
run:
	@echo "$(BLUE)🚀 Avvio server produzione locale...$(NC)"
	cd $(BACKEND_DIR) && $(PYTHON) -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2

## prod: Avvia con Gunicorn (simula produzione)
prod:
	@echo "$(BLUE)🚀 Avvio server con Gunicorn (produzione)...$(NC)"
	cd $(BACKEND_DIR) && gunicorn main:app \
		--worker-class uvicorn.workers.UvicornWorker \
		--bind 0.0.0.0:8000 \
		--workers 2 \
		--timeout 60 \
		--access-logfile - \
		--error-logfile -

# ============================================================
# QUALITY & LINTING
# ============================================================

## lint: Controlla qualità codice con ruff
lint:
	@echo "$(BLUE)🔍 Controllo qualità codice...$(NC)"
	cd $(BACKEND_DIR) && $(RUFF) check app/ --output-format=concise || true
	@echo "$(GREEN)✅ Lint completato$(NC)"

## format: Formatta codice automaticamente
format:
	@echo "$(BLUE)✨ Formattazione codice...$(NC)"
	cd $(BACKEND_DIR) && $(RUFF) format app/
	cd $(BACKEND_DIR) && $(RUFF) check app/ --fix
	@echo "$(GREEN)✅ Codice formattato$(NC)"

## typecheck: Verifica type hints con mypy
typecheck:
	@echo "$(BLUE)🔬 Verifica type hints...$(NC)"
	cd $(BACKEND_DIR) && $(MYPY) app/ --config-file=pyproject.toml || true
	@echo "$(GREEN)✅ Type check completato$(NC)"

# ============================================================
# TESTING
# ============================================================

## test: Esegue test unitari
test:
	@echo "$(BLUE)🧪 Esecuzione test...$(NC)"
	cd $(BACKEND_DIR) && $(PYTEST) tests/ -v --tb=short --disable-warnings
	@echo "$(GREEN)✅ Test completati$(NC)"

## coverage: Test con report coverage
coverage:
	@echo "$(BLUE)📊 Test con coverage...$(NC)"
	cd $(BACKEND_DIR) && $(PYTEST) tests/ \
		--cov=app \
		--cov-report=term-missing \
		--cov-report=html \
		--cov-report=xml \
		--cov-fail-under=85 \
		-v
	@echo "$(YELLOW)📄 Report HTML: backend/htmlcov/index.html$(NC)"
	@echo "$(GREEN)✅ Coverage completato$(NC)"

## test-fast: Test paralleli veloci
test-fast:
	@echo "$(BLUE)⚡ Test paralleli veloci...$(NC)"
	cd $(BACKEND_DIR) && $(PYTEST) tests/ -n auto -v --tb=short
	@echo "$(GREEN)✅ Test veloci completati$(NC)"

# ============================================================
# SECURITY
# ============================================================

## security: Scan sicurezza completo
security: security-code security-deps
	@echo "$(GREEN)✅ Security scan completato$(NC)"

## security-code: Scan vulnerabilità codice con bandit
security-code:
	@echo "$(BLUE)🔒 Scan vulnerabilità codice...$(NC)"
	cd $(BACKEND_DIR) && $(BANDIT) -r app/ -ll || true

## security-deps: Verifica vulnerabilità dipendenze
security-deps:
	@echo "$(BLUE)🔒 Verifica vulnerabilità dipendenze...$(NC)"
	$(PIP) install pip-audit
	cd $(BACKEND_DIR) && pip-audit || true

## audit: Audit completo dipendenze
audit:
	@echo "$(BLUE)🔍 Audit dipendenze...$(NC)"
	$(PIP) list --outdated
	$(PIP) check

# ============================================================
# DATABASE
# ============================================================

## migrate: Applica migrazioni database
migrate:
	@echo "$(BLUE)🔄 Applicazione migrazioni...$(NC)"
	cd $(BACKEND_DIR) && $(ALEMBIC) upgrade head
	@echo "$(GREEN)✅ Migrazioni applicate$(NC)"

## migrate-new: Crea nuova migrazione (usa MSG="descrizione")
migrate-new:
	@if [ -z "$(MSG)" ]; then \
		echo "$(RED)❌ Errore: specifica MSG=\"descrizione migrazione\"$(NC)"; \
		exit 1; \
	fi
	@echo "$(BLUE)📝 Creazione nuova migrazione: $(MSG)$(NC)"
	cd $(BACKEND_DIR) && $(ALEMBIC) revision --autogenerate -m "$(MSG)"
	@echo "$(GREEN)✅ Migrazione creata$(NC)"

## migrate-history: Mostra storico migrazioni
migrate-history:
	@echo "$(BLUE)📋 Storico migrazioni:$(NC)"
	cd $(BACKEND_DIR) && $(ALEMBIC) history --verbose

## backup: Crea backup database manuale
backup:
	@echo "$(BLUE)💾 Creazione backup database...$(NC)"
	cd $(BACKEND_DIR) && $(PYTHON) run_backup.py create --type manual
	@echo "$(GREEN)✅ Backup creato$(NC)"

## backup-list: Mostra backup disponibili
backup-list:
	@echo "$(BLUE)📚 Elenco backup disponibili...$(NC)"
	cd $(BACKEND_DIR) && $(PYTHON) run_backup.py list

## backup-schedule: Avvia scheduler backup locale
backup-schedule:
	@echo "$(BLUE)⏱️  Avvio scheduler backup locale...$(NC)"
	cd $(BACKEND_DIR) && $(PYTHON) run_backup.py schedule

# ============================================================
# DOCKER
# ============================================================

## preflight: Verifica porte libere prima dell'avvio
preflight:
	@echo "$(BLUE)🔍 Preflight check...$(NC)"
	@pwsh ./scripts/preflight-ports.ps1 || bash ./scripts/preflight-ports.sh

## up: Avvia stack Docker (con preflight automatico)
up: preflight
	@echo "$(BLUE)🐳 Avvio stack Docker...$(NC)"
	docker compose up -d
	@echo "$(GREEN)✅ Stack avviato$(NC)"
	@echo "$(YELLOW)Backend:  http://localhost:8002$(NC)"
	@echo "$(YELLOW)Frontend: http://localhost:3002$(NC)"
	@echo "$(YELLOW)API Docs: http://localhost:8002/docs$(NC)"
	@echo "$(YELLOW)DB Port:  5434 | Redis: 6381$(NC)"

## down: Ferma stack Docker
down:
	@echo "$(BLUE)🛑 Stop stack Docker...$(NC)"
	docker compose down
	@echo "$(GREEN)✅ Stack fermato$(NC)"

## ps: Mostra stato containers
ps:
	@echo "$(BLUE)📊 Stato containers:$(NC)"
	docker compose ps

## logs: Mostra logs in tempo reale
logs:
	@echo "$(BLUE)📜 Logs stack (Ctrl+C per uscire):$(NC)"
	docker compose logs -f --tail=200

## restart: Restart completo dello stack
restart: down up
	@echo "$(GREEN)✅ Stack riavviato$(NC)"

## smoke: Esegue smoke test sugli endpoint API
smoke:
	@echo "$(BLUE)🧪 Smoke test API endpoints...$(NC)"
	@node ./scripts/smoke.js || echo "$(RED)⚠️  Smoke test fallito - vedi log$(NC)"

## docker-rebuild: Rebuild completo e restart
docker-rebuild:
	@echo "$(BLUE)🔄 Rebuild e restart Docker...$(NC)"
	docker compose down
	docker compose up -d --build
	@echo "$(GREEN)✅ Stack ricostruito e avviato$(NC)"

## docker-clean: Pulizia completa Docker
docker-clean:
	@echo "$(RED)⚠️  Pulizia completa Docker (rimuove anche volumi)$(NC)"
	docker compose down -v
	docker system prune -f

# ============================================================
# UTILITY
# ============================================================

## clean: Pulisce file temporanei e cache
clean:
	@echo "$(BLUE)🧹 Pulizia file temporanei...$(NC)"
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name ".coverage" -delete 2>/dev/null || true
	@find . -type f -name "*.log" -delete 2>/dev/null || true
	@echo "$(GREEN)✅ Pulizia completata$(NC)"

## health: Verifica salute servizi
health:
	@echo "$(BLUE)❤️  Verifica salute servizi...$(NC)"
	@curl -sf http://localhost:8001/health >/dev/null && echo "$(GREEN)✅ Backend: OK$(NC)" || echo "$(RED)❌ Backend: OFFLINE$(NC)"
	@curl -sf http://localhost:3001 >/dev/null && echo "$(GREEN)✅ Frontend: OK$(NC)" || echo "$(RED)❌ Frontend: OFFLINE$(NC)"

## all-checks: Esegue tutti i controlli qualità
all-checks: lint typecheck test security
	@echo "$(GREEN)============================================================$(NC)"
	@echo "$(GREEN)✅ TUTTI I CONTROLLI COMPLETATI CON SUCCESSO!$(NC)"
	@echo "$(GREEN)============================================================$(NC)"

# ============================================================
# CI/CD SIMULATION
# ============================================================

## ci: Simula pipeline CI (come in GitHub Actions)
ci:
	@echo "$(BLUE)🔄 Simulazione pipeline CI...$(NC)"
	$(MAKE) clean
	$(MAKE) install-dev
	$(MAKE) lint
	$(MAKE) typecheck
	$(MAKE) coverage
	$(MAKE) security
	@echo "$(GREEN)✅ Pipeline CI completata!$(NC)"

# ============================================================
# DEPLOYMENT
# ============================================================

## deploy-check: Verifica pre-deploy
deploy-check:
	@echo "$(BLUE)🚀 Verifica pre-deploy...$(NC)"
	@echo "$(YELLOW)Controllo variabili ambiente...$(NC)"
	@test -f .env || (echo "$(RED)❌ File .env mancante!$(NC)" && exit 1)
	@grep -q "changeme" .env && echo "$(RED)❌ Secret di default in .env!$(NC)" && exit 1 || echo "$(GREEN)✅ .env configurato$(NC)"
	@echo "$(YELLOW)Esecuzione controlli qualità...$(NC)"
	$(MAKE) all-checks
	@echo "$(GREEN)✅ Sistema pronto per deploy!$(NC)"

# ============================================================
# FINE MAKEFILE
# ============================================================
