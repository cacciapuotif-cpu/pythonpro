# Stato Lavori PythonPro

Data aggiornamento: 2026-03-19

## Contesto

Il progetto reale da usare come riferimento operativo e di automazione e` `/DATA/progetti/pythonpro`.
Il backend attivo e` `backend/main.py` con entrypoint `main:app`.
La struttura `backend/app/main.py` esiste ancora ma non e` il riferimento principale corrente.

## Lavoro completato

### 1. Allineamento backend reale

- Aggiornato [`/DATA/progetti/pythonpro/Makefile`](/DATA/progetti/pythonpro/Makefile) per usare `main:app` in `dev`, `run`, `prod`
- Aggiornato [`/DATA/progetti/pythonpro/backend/Dockerfile`](/DATA/progetti/pythonpro/backend/Dockerfile) per usare `main:app`
- Allineato il `HEALTHCHECK` Docker su `/health`

### 2. Razionalizzazione CI

- Corretta [`/DATA/progetti/pythonpro/.github/workflows/ci.yml`](/DATA/progetti/pythonpro/.github/workflows/ci.yml) per puntare al backend reale
- Lint/typecheck/security/test non puntano piu` a `backend/app`
- La pipeline duplicata [`/DATA/progetti/pythonpro/.github/workflows/ci-cd.yml`](/DATA/progetti/pythonpro/.github/workflows/ci-cd.yml) e` stata lasciata come workflow legacy solo manuale

### 3. Automazione backup

- Aggiunta CLI backup in [`/DATA/progetti/pythonpro/backend/run_backup.py`](/DATA/progetti/pythonpro/backend/run_backup.py)
- Aggiornato [`/DATA/progetti/pythonpro/backend/backup_manager.py`](/DATA/progetti/pythonpro/backend/backup_manager.py):
  - parsing robusto di `DATABASE_URL`
  - supporto a `BACKUP_DIR`
  - retention configurabile
  - scheduler configurabile via env
  - nessuna dipendenza obbligatoria da `sqlalchemy` per la CLI
- Aggiunta dipendenza runtime `schedule` in [`/DATA/progetti/pythonpro/backend/requirements.txt`](/DATA/progetti/pythonpro/backend/requirements.txt)
- Aggiornato [`/DATA/progetti/pythonpro/Makefile`](/DATA/progetti/pythonpro/Makefile):
  - `make backup`
  - `make backup-list`
  - `make backup-schedule`
- Aggiornato [`/DATA/progetti/pythonpro/docker-compose.yml`](/DATA/progetti/pythonpro/docker-compose.yml):
  - `AUTO_BACKUP_ENABLED=false` sul backend web
  - nuovo servizio `backup_scheduler`
  - `backup_scheduler` usa `entrypoint: ["python", "run_backup.py", "schedule"]`
  - `healthcheck` disabilitato sul servizio backup

### 4. Documentazione backup

- Aggiornato [`/DATA/progetti/pythonpro/README.md`](/DATA/progetti/pythonpro/README.md)
- Aggiornato [`/DATA/progetti/pythonpro/docs/RUNBOOK_produzione.md`](/DATA/progetti/pythonpro/docs/RUNBOOK_produzione.md)
- Aggiornato [`/DATA/progetti/pythonpro/.env.example`](/DATA/progetti/pythonpro/.env.example) con:
  - `AUTO_BACKUP_ENABLED`
  - `BACKUP_RETENTION_COUNT`
  - `BACKUP_DAILY_TIME`
  - `BACKUP_WEEKLY_TIME`
  - `BACKUP_MONTHLY_INTERVAL_DAYS`

### 5. Smoke test operativo

- Aggiornato [`/DATA/progetti/pythonpro/scripts/smoke.js`](/DATA/progetti/pythonpro/scripts/smoke.js):
  - backend su porta `8001`
  - verifica servizio `backup_scheduler`
- Aggiornato [`/DATA/progetti/pythonpro/scripts/smoke_test.ps1`](/DATA/progetti/pythonpro/scripts/smoke_test.ps1):
  - container `pythonpro_*`
  - backend su `8001`
  - check `pythonpro_backup_scheduler`

### 6. Pulizia documentazione e script operativi

- Riallineati documenti operativi principali:
  - [`/DATA/progetti/pythonpro/README.md`](/DATA/progetti/pythonpro/README.md)
  - [`/DATA/progetti/pythonpro/PRODUZIONE_README.md`](/DATA/progetti/pythonpro/PRODUZIONE_README.md)
  - [`/DATA/progetti/pythonpro/GUIDA_PRODUZIONE.md`](/DATA/progetti/pythonpro/GUIDA_PRODUZIONE.md)
  - [`/DATA/progetti/pythonpro/GUIDA_ENTI_E_TIMESHEET.md`](/DATA/progetti/pythonpro/GUIDA_ENTI_E_TIMESHEET.md)
  - [`/DATA/progetti/pythonpro/ISTRUZIONI_AVVIO.txt`](/DATA/progetti/pythonpro/ISTRUZIONI_AVVIO.txt)
  - [`/DATA/progetti/pythonpro/ISTRUZIONI_RIAVVIO.txt`](/DATA/progetti/pythonpro/ISTRUZIONI_RIAVVIO.txt)
  - [`/DATA/progetti/pythonpro/docs/RUNBOOK_produzione.md`](/DATA/progetti/pythonpro/docs/RUNBOOK_produzione.md)
  - [`/DATA/progetti/pythonpro/docs/01_inventario.md`](/DATA/progetti/pythonpro/docs/01_inventario.md)
  - [`/DATA/progetti/pythonpro/docs/FASE_1_COMPLETATA.md`](/DATA/progetti/pythonpro/docs/FASE_1_COMPLETATA.md)
- Riallineati script e helper operativi:
  - [`/DATA/progetti/pythonpro/Makefile`](/DATA/progetti/pythonpro/Makefile)
  - [`/DATA/progetti/pythonpro/STATUS.bat`](/DATA/progetti/pythonpro/STATUS.bat)
  - [`/DATA/progetti/pythonpro/start.bat`](/DATA/progetti/pythonpro/start.bat)
  - [`/DATA/progetti/pythonpro/AVVIO_RAPIDO.bat`](/DATA/progetti/pythonpro/AVVIO_RAPIDO.bat)
  - [`/DATA/progetti/pythonpro/AVVIA_GESTIONALE.bat`](/DATA/progetti/pythonpro/AVVIA_GESTIONALE.bat)
  - [`/DATA/progetti/pythonpro/VERIFICA_SISTEMA.bat`](/DATA/progetti/pythonpro/VERIFICA_SISTEMA.bat)
  - [`/DATA/progetti/pythonpro/scripts/dev_up.ps1`](/DATA/progetti/pythonpro/scripts/dev_up.ps1)
  - [`/DATA/progetti/pythonpro/tools/avvio_pulito.ps1`](/DATA/progetti/pythonpro/tools/avvio_pulito.ps1)
  - [`/DATA/progetti/pythonpro/.env.production.template`](/DATA/progetti/pythonpro/.env.production.template)

### 7. Riduzione file ridondanti

Rimossi file non necessari al runtime o allo sviluppo corrente:

- directory [`/DATA/progetti/pythonpro/artifacts`](#/DATA/progetti/pythonpro/artifacts)
- report storici duplicati:
  - [`/DATA/progetti/pythonpro/99_report_finale.md`](/DATA/progetti/pythonpro/99_report_finale.md)
  - [`/DATA/progetti/pythonpro/FIX_REPORT.md`](/DATA/progetti/pythonpro/FIX_REPORT.md)
  - [`/DATA/progetti/pythonpro/FIX_REPORT_LOCAL.md`](/DATA/progetti/pythonpro/FIX_REPORT_LOCAL.md)
  - [`/DATA/progetti/pythonpro/PRODUCTION_READY_REPORT.md`](/DATA/progetti/pythonpro/PRODUCTION_READY_REPORT.md)
  - [`/DATA/progetti/pythonpro/REPORT_REVISIONE_CODICE.md`](/DATA/progetti/pythonpro/REPORT_REVISIONE_CODICE.md)
  - [`/DATA/progetti/pythonpro/REPORT_TEST_PROFONDO_2025-10-06.md`](/DATA/progetti/pythonpro/REPORT_TEST_PROFONDO_2025-10-06.md)
- backup e dump locali obsoleti:
  - [`/DATA/progetti/pythonpro/backup_db.sql`](/DATA/progetti/pythonpro/backup_db.sql)
  - [`/DATA/progetti/pythonpro/.env.__backup__20251024_103115`](/DATA/progetti/pythonpro/.env.__backup__20251024_103115)
  - [`/DATA/progetti/pythonpro/docker-compose.yml.__backup__20251024_102945`](/DATA/progetti/pythonpro/docker-compose.yml.__backup__20251024_102945)
  - [`/DATA/progetti/pythonpro/frontend/.env.local.__backup__20251024_103115`](/DATA/progetti/pythonpro/frontend/.env.local.__backup__20251024_103115)
- file diff/patch temporanei:
  - [`/DATA/progetti/pythonpro/CHANGES.diff`](/DATA/progetti/pythonpro/CHANGES.diff)
  - [`/DATA/progetti/pythonpro/PRODUCTION_DEPLOY.diff`](/DATA/progetti/pythonpro/PRODUCTION_DEPLOY.diff)
- copie codice backup non piu` utili:
  - [`/DATA/progetti/pythonpro/backend/main_backup_20251013_140255.py`](/DATA/progetti/pythonpro/backend/main_backup_20251013_140255.py)
  - [`/DATA/progetti/pythonpro/backend/main_backup_pre_refactor.py`](/DATA/progetti/pythonpro/backend/main_backup_pre_refactor.py)
- cache Python locale:
  - [`/DATA/progetti/pythonpro/backend/__pycache__`](#/DATA/progetti/pythonpro/backend/__pycache__)

## Verifiche eseguite

### Verifiche statiche

- `python3 -m py_compile` su:
  - [`/DATA/progetti/pythonpro/backend/run_backup.py`](/DATA/progetti/pythonpro/backend/run_backup.py)
  - [`/DATA/progetti/pythonpro/backend/backup_manager.py`](/DATA/progetti/pythonpro/backend/backup_manager.py)
  - [`/DATA/progetti/pythonpro/backend/main.py`](/DATA/progetti/pythonpro/backend/main.py)
- `docker compose config` OK su [`/DATA/progetti/pythonpro/docker-compose.yml`](/DATA/progetti/pythonpro/docker-compose.yml)
- `python3 run_backup.py list` OK in ambiente locale minimale

### Verifiche runtime Docker

- Avvio `db` e `backup_scheduler` riuscito
- Log del servizio `backup_scheduler` verificati
- Scheduler attivo con log:
  - `Backup automatici avviati`
  - `Scheduler backup attivo`
  - `Directory backup: /app/backups`
- Backup manuale reale eseguito con successo via:
  - `docker compose exec -T backup_scheduler python run_backup.py create --type manual`
- File verificati nel volume backup:
  - `gestionale_backup_manual_20260319_154825.sql.zip`
  - `gestionale_backup_manual_20260319_154825.sql.json`

### Verifiche smoke test

- Smoke test Node eseguito fuori sandbox su stack attivo: **6/6 passati**
- Verificati:
  - backend `/health`
  - root
  - API `projects`
  - API `collaborators`
  - docs `/docs`
  - servizio `backup_scheduler`

## Problemi trovati e corretti

- `Makefile` e `Dockerfile` puntavano a `app.main:app` invece di `main:app`
- `ci.yml` puntava a `backend/app` invece del backend reale
- `ci-cd.yml` duplicava la pipeline automatica
- `backup_scheduler` inizialmente ereditava `ENTRYPOINT` e `HEALTHCHECK` del backend
- `run_backup.py` falliva in ambienti senza `python-dotenv`
- `backup_manager.py` dipendeva da `schedule` e `sqlalchemy` anche per operazioni semplici

## Stato attuale

Il blocco automazioni base e backup e` funzionante e verificato.
La CI principale e` stata riallineata.
Il backup automatico e` stato testato end-to-end con Docker.
Lo smoke test operativo include anche `backup_scheduler`.
La maggior parte della documentazione e degli script operativi e` stata riallineata al backend reale e alle porte correnti.
Il repository e` stato alleggerito rimuovendo artifact, backup locali obsoleti e report ridondanti.
Gli script operativi e i template residui sono stati ulteriormente puliti:
- [`/DATA/progetti/pythonpro/AVVIO_LOCALE.bat`](/DATA/progetti/pythonpro/AVVIO_LOCALE.bat)
- [`/DATA/progetti/pythonpro/.env.sample`](/DATA/progetti/pythonpro/.env.sample)
- [`/DATA/progetti/pythonpro/scripts/test_backend.sh`](/DATA/progetti/pythonpro/scripts/test_backend.sh)
- [`/DATA/progetti/pythonpro/scripts/verify_fixes.bat`](/DATA/progetti/pythonpro/scripts/verify_fixes.bat)
- [`/DATA/progetti/pythonpro/scripts/simulate_restart.bat`](/DATA/progetti/pythonpro/scripts/simulate_restart.bat)
- [`/DATA/progetti/pythonpro/scripts/stress_test.py`](/DATA/progetti/pythonpro/scripts/stress_test.py)
- [`/DATA/progetti/pythonpro/scripts/diff_openapi.py`](/DATA/progetti/pythonpro/scripts/diff_openapi.py)
- [`/DATA/progetti/pythonpro/AVVIO_RAPIDO.bat`](/DATA/progetti/pythonpro/AVVIO_RAPIDO.bat)
- [`/DATA/progetti/pythonpro/AVVIA_GESTIONALE.bat`](/DATA/progetti/pythonpro/AVVIA_GESTIONALE.bat)
- [`/DATA/progetti/pythonpro/VERIFICA_SISTEMA.bat`](/DATA/progetti/pythonpro/VERIFICA_SISTEMA.bat)
- [`/DATA/progetti/pythonpro/ISTRUZIONI_AVVIO.txt`](/DATA/progetti/pythonpro/ISTRUZIONI_AVVIO.txt)
- [`/DATA/progetti/pythonpro/ISTRUZIONI_RIAVVIO.txt`](/DATA/progetti/pythonpro/ISTRUZIONI_RIAVVIO.txt)

Sono stati rimossi anche altri residui non utili allo sviluppo corrente:
- [`/DATA/progetti/pythonpro/backend/main_temp.py`](/DATA/progetti/pythonpro/backend/main_temp.py)
- [`/DATA/progetti/pythonpro/frontend/src/services/apiService.js.__backup__20251024_103156`](/DATA/progetti/pythonpro/frontend/src/services/apiService.js.__backup__20251024_103156)
- [`/DATA/progetti/pythonpro/VERIFICA_SISTEMA_COMPLETA_2025-10-07.md`](/DATA/progetti/pythonpro/VERIFICA_SISTEMA_COMPLETA_2025-10-07.md)
- [`/DATA/progetti/pythonpro/IMPLEMENTAZIONE_REQUISITI_2025-10-06.md`](/DATA/progetti/pythonpro/IMPLEMENTAZIONE_REQUISITI_2025-10-06.md)
- [`/DATA/progetti/pythonpro/CHANGELOG_POST_MIGRAZIONI.md`](/DATA/progetti/pythonpro/CHANGELOG_POST_MIGRAZIONI.md)
- [`/DATA/progetti/pythonpro/RIEPILOGO_FINALE_PROBLEMA_NUL.md`](/DATA/progetti/pythonpro/RIEPILOGO_FINALE_PROBLEMA_NUL.md)
- [`/DATA/progetti/pythonpro/FIX_FRONTEND_RIAVVIO.md`](/DATA/progetti/pythonpro/FIX_FRONTEND_RIAVVIO.md)
- [`/DATA/progetti/pythonpro/QUICK_FIX_FRONTEND.md`](/DATA/progetti/pythonpro/QUICK_FIX_FRONTEND.md)
- [`/DATA/progetti/pythonpro/PRODUCTION_READINESS_COMPLETE.md`](/DATA/progetti/pythonpro/PRODUCTION_READINESS_COMPLETE.md)

### Ultimo avanzamento prima della pausa

- pulizia conservativa completata sui launcher e sugli helper piu` usati
- rimossi ulteriori file temporanei, backup locali e report non necessari allo sviluppo corrente
- verificato che nei file operativi puliti non restano riferimenti a `localhost:8000`, `5433` o `docker-compose`
- il repository e` ora piu` leggero e pronto per proseguire con sviluppo e automazioni aggiuntive

## Prossimi passi consigliati

1. Valutare monitoraggio e alert minimi su:
   - stato backup
   - fallimento scheduler
   - spazio disco backup
2. Eventualmente consolidare i file `backend/app/*` o dichiararli formalmente legacy
3. Eventualmente rendere la CI capace di eseguire anche smoke test controllati post-build
4. In alternativa, fare un'ultima revisione dei documenti storici rimasti e decidere se archiviarli o rimuoverli

## Nota importante

La working tree conteneva gia` modifiche locali utente in diversi file.
Le modifiche fatte sono state applicate senza ripristinare lavoro preesistente.
