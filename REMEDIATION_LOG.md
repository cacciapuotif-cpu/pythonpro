# PythonPro Remediation Log

Formato: data | finding ID | cosa fatto | file toccati | test/verifiche eseguiti

> AVVISO PERMANENTE: VIETATO push su remote finche history git non ripulita da `.env`/`.env*` in Ondata 2 con procedura dedicata.

## 2026-07-05 | PASSO-ZERO | Avvio remediation controllata

- Cosa fatto:
  - Letto integralmente `audit/AUDIT_REPORT.md`.
  - Letti i report pertinenti alla pianificazione dell'Ondata 1: `audit/FASE_1_inventario.md`, `audit/FASE_2_funzionale.md`, `audit/FASE_3_qualita.md`, `audit/FASE_6_sicurezza.md`, `audit/FASE_7_gdpr.md`.
  - Verificato che il progetto e' gia' un repository git sul branch `claude/platform-audit-compliance-XnH86`.
  - Verificato che il worktree e' gia' sporco prima della remediation; nessun reset/revert eseguito.
  - Verificato `.gitignore`: `.env`, `.env.*`, `uploads/`, `backups/`, `__pycache__/`, `node_modules/` sono ignorati.
  - Verificato che `.env`/`.env*` risultano presenti nella history git: commit `9bc8c77`, `9a9c1ff`, `c6de7d7`, `8c3474c`. Conseguenza: rotazione completa segreti obbligatoria.
  - Verificati file env presenti nel workspace: `.env`, `.env.bak_20260525_135533`, `.env.bak_20260622_cors`, `.env.sample`, `.env.example`, `.env.production.template`, `.env.development`.
  - Creato backup fresco pre-remediation fuori dal progetto.

- File toccati:
  - `REMEDIATION_LOG.md`

- Backup creato:
  - Directory: `/DATA/progetti/pythonpro_remediation_backups/20260705_121039`
  - Dump PostgreSQL completo: `pythonpro_pg_dumpall_20260705_121039.sql.gz`
  - Tar progetto: `pythonpro_project_20260705_121039.tar.gz`
  - Checksum: `SHA256SUMS`
  - Note: il tar esclude `.git`, `node_modules`, `__pycache__`, `frontend/build`, `backups`, `db_backups`.

- Test/verifiche eseguiti:
  - `docker ps --format ...`: container PythonPro principali attivi; `pythonpro_db`, `pythonpro_backend`, `pythonpro_frontend` healthy.
  - `pg_dumpall` dentro `pythonpro_db`: completato.
  - `gzip -t` sul dump: OK.
  - `tar -tzf ... | wc -l`: archivio ispezionabile, 1135 entry.
  - controllo tar per `node_modules|__pycache__`: nessuna occorrenza stampata.
  - `git log --all --oneline -- .env '.env*'`: history contiene file env in commit passati.
  - `git check-ignore -v`: ignore attivo per `.env`, `.env.*`, `uploads`, `backups`, `node_modules`, `__pycache__`.

- Decisioni:
  - Nessuna modifica applicativa prima della conferma esplicita sul piano di Ondata 1.
  - La rotazione segreti dovra' includere anche segreti storicamente presenti in git, non solo file attuali.

## 2026-07-05 | SEC-01 / F1-001 / GDPR-04 / SAAS-03 | Segreti ruotati e template ripuliti

- Cosa fatto:
  - Ruotati i segreti runtime presenti in `.env` senza stampare valori.
  - Aggiornata la password del ruolo PostgreSQL live `admin` in modo coerente con `.env`.
  - Ricreati `pythonpro_redis`, `pythonpro_backend`, `pythonpro_arq_worker`, `pythonpro_backup_scheduler` per caricare DB/Redis/segreti aggiornati.
  - Rimossi i file `.env.bak_*` dal workspace.
  - Sostituito `.env.example` con template senza valori segreti reali.
  - `BACKUP_ENCRYPTION_KEY` resa obbligatoria in `validate_env.sh` e passata a backend/backup scheduler.
  - Aggiunto `scripts/check_secret_remediation.sh` come check automatico root-level.
  - Registrato `audit/FINDINGS_NUOVI.md` per la mancata propagazione runtime della backup key rilevata durante la remediation.

- Variabili ruotate:
  - `ADMIN_DEFAULT_PASSWORD`
  - `BACKUP_ENCRYPTION_KEY`
  - `DB_APP_PASSWORD`
  - `DB_MIGRATION_PASSWORD`
  - `DB_PASSWORD`
  - `GMAIL_IMAP_APP_PASSWORD`
  - `JWT_SECRET_KEY`
  - `SECRET_KEY` runtime, mappata da `JWT_SECRET_KEY`
  - `OPENCLAW_API_KEY`
  - `OPERATOR_DEFAULT_PASSWORD`
  - `REDIS_PASSWORD`
  - `SMTP_PASSWORD`
  - `WHATSAPP_META_APP_SECRET`
  - `WHATSAPP_META_WEBHOOK_VERIFY_TOKEN`

- File toccati:
  - `.env` ignorato da git
  - `.env.example`
  - `docker-compose.yml`
  - `backend/scripts/validate_env.sh`
  - `scripts/check_secret_remediation.sh`
  - `audit/FINDINGS_NUOVI.md`
  - `REMEDIATION_LOG.md`

- Test/verifiche eseguiti:
  - `/usr/lib/docker/cli-plugins/docker-compose config` OK.
  - `/usr/lib/docker/cli-plugins/docker-compose ps`: backend, db, redis, arq worker, frontend healthy; backup scheduler up.
  - `curl -fsS http://127.0.0.1:8001/health` -> OK.
  - `docker exec pythonpro_backend ./scripts/validate_env.sh` -> OK.
  - `docker exec pythonpro_db ... select 1` -> OK.
  - `./scripts/check_secret_remediation.sh` -> OK.

- Note operative:
  - Email/IMAP/SMTP, OpenClaw e WhatsApp ora hanno valori locali ruotati; le integrazioni esterne devono essere aggiornate con nuovi valori validi prima di affidarsi a quei canali.
  - La history git non e' stata riscritta per decisione esplicita; non fare push finche non sara' ripulita in Ondata 2.

## 2026-07-05 | SEC-02 / F3-001 | Reset password admin reso monouso

- Cosa fatto:
  - Rimosso il valore hardcoded `Admin2026!` da `backend/reset_password.py`.
  - Lo script genera ora una password casuale monouso con `secrets.token_urlsafe(24)` e la stampa una sola volta come `PASSWORD_MONOUSO=...`.
  - Aggiunto test container per impedire regressioni sullo script e sulla validazione della backup key.

- File toccati:
  - `backend/reset_password.py`
  - `backend/tests/test_secret_remediation.py`
  - `REMEDIATION_LOG.md`

- Test/verifiche eseguiti:
  - `python3 -m py_compile backend/reset_password.py backend/tests/test_secret_remediation.py` -> OK.
  - `docker exec pythonpro_backend ... pytest -q tests/test_secret_remediation.py -p no:cacheprovider` -> 2 passed.
