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

## 2026-07-05 | WORKTREE / SEC-04 | Censimento worktree e logging sicuro

- Cosa fatto:
  - Fotografato il worktree sporco prima del punto 3 in `audit/WORKTREE_PREESISTENTE.md` con `git status --untracked-files=all`, `git diff --stat` e valutazione riga-per-riga dei file preesistenti.
  - Non sono stati committati, scartati o ripuliti file preesistenti.
  - Segnalato prima dell'edit che `backend/error_handler.py` aveva gia' una modifica preesistente (`import re`); la modifica e' stata preservata e integrata.
  - Implementata redazione log per `ErrorHandler.log_error`: niente URL completo con query string, niente header completi, header sensibili redatti, token/password/segreti redatti da messaggio errore e traceback.
  - Aggiornato `backend/main.py` per evitare log di `request.url` completo nei validation error e per redigere il messaggio dell'eccezione non gestita.
  - `error_handler.py` ora crea `LOG_DIR` prima del `FileHandler`, evitando failure se la directory non esiste.
  - Aggiunti test mirati per impedire regressioni su header/token/cookie/query string nei log.

- File toccati:
  - `audit/WORKTREE_PREESISTENTE.md`
  - `backend/error_handler.py`
  - `backend/main.py`
  - `backend/tests/test_logging_safety.py`
  - `REMEDIATION_LOG.md`
  - `STATUS.md`

- Test/verifiche eseguiti:
  - `python3 -m py_compile backend/error_handler.py backend/main.py backend/tests/test_logging_safety.py` -> OK.
  - Host: `pytest -q tests/test_logging_safety.py tests/test_secret_remediation.py -p no:cacheprovider` -> 4 passed, 1 warning coverage/config preesistente.
  - Container: `docker exec pythonpro_backend pytest -q tests/test_logging_safety.py tests/test_secret_remediation.py -p no:cacheprovider` -> 4 passed, 1 warning coverage/config; warning Docker host su `/DATA/.docker/config.json` non bloccante.

- Note operative:
  - Non sono stati attivati flussi email/IMAP/SMTP, OpenClaw o WhatsApp.
  - Email/IMAP/SMTP, OpenClaw e WhatsApp restano da allineare manualmente prima di usare quei canali.
  - Nessun commit e nessun push eseguito. Resta il divieto di push finche' la history git non sara' ripulita in Ondata 2.

## 2026-07-05 | SEC-03 fase A | RBAC minimo log-only

- Cosa fatto:
  - Verificato utenti live prima della migration: 2 utenti attivi, `admin` con ruolo `admin`, `operatore` con ruolo legacy `user`.
  - Proposta e confermata migration sicura: `user`/`manager` -> `operatore`, `readonly` -> `consultazione`, `dpo` -> `admin`, sconosciuti/NULL -> `consultazione`.
  - Aggiunta migration Alembic `052_normalize_user_roles.py` e applicata su DB live.
  - Dopo migration: `admin` resta `admin`, `operatore` diventa `operatore`, colonna `users.role` NOT NULL con default DB `consultazione`.
  - Implementato `require_role` centrale in `auth.py`, agganciato agli include protetti in `main.py`.
  - Modalita' attuale: log-only (`RBAC_ENFORCE=False`), quindi i 403 potenziali vengono loggati come `RBAC WOULD_DENY` senza bloccare.
  - Aggiunta matrice test parametrizzata per ruoli `admin`, `operatore`, `consultazione` in `backend/tests/test_rbac_minimo_log_only.py`.
  - Generato report blocchi potenziali in `audit/RBAC_LOG_ONLY_REPORT.md`.
  - Ricreato `pythonpro_backend` per caricare enum/dependency aggiornati; compose ha ricreato anche `pythonpro_db` mantenendo il volume dati.

- File toccati:
  - `backend/auth.py`
  - `backend/main.py`
  - `backend/alembic/versions/052_normalize_user_roles.py`
  - `backend/tests/test_rbac_minimo_log_only.py`
  - `scripts/rbac_log_only_report.py`
  - `audit/RBAC_LOG_ONLY_REPORT.md`
  - `REMEDIATION_LOG.md`
  - `STATUS.md`

- Test/verifiche eseguiti:
  - `python3 -m py_compile backend/auth.py backend/main.py backend/tests/test_rbac_minimo_log_only.py scripts/rbac_log_only_report.py backend/alembic/versions/052_normalize_user_roles.py` -> OK.
  - Host: `pytest -q tests/test_rbac_minimo_log_only.py tests/test_logging_safety.py tests/test_secret_remediation.py -p no:cacheprovider` -> 75 passed, 1 warning coverage/config preesistente.
  - `docker exec pythonpro_backend alembic upgrade head` -> upgrade `051 -> 052` OK.
  - DB post-migration: `admin/admin`, `operatore/operatore`, `role` NOT NULL default `consultazione`.
  - Backend health `curl http://127.0.0.1:8001/health` -> OK.
  - Container: `docker exec pythonpro_backend pytest -q tests/test_rbac_minimo_log_only.py tests/test_logging_safety.py tests/test_secret_remediation.py -p no:cacheprovider` -> 75 passed, 1 warning coverage/config.
  - Runtime smoke log-only con JWT temporaneo locale per `operatore`: `GET /api/v1/reporting/timesheet` -> 200 e log `RBAC WOULD_DENY ... allowed_roles=admin`.

- Report blocchi potenziali principali:
  - `consultazione` verrebbe bloccato su tutte le scritture operative CRUD.
  - `operatore` e `consultazione` verrebbero bloccati su admin/security logs, GDPR export, agenti, export Excel piano finanziario, report timesheet sensibile.
  - Letture operative base restano 200 per tutti e tre i ruoli.

- Note operative:
  - Enforcement reale NON attivato. `RBAC_ENFORCE=False`.
  - Nessun flusso email/IMAP/SMTP, OpenClaw o WhatsApp attivato.
  - Il login `operatore` con la password bootstrap runtime non e' valido per l'utente esistente; non sono state modificate password utenti in questa fase.
  - Durante recreate e' ricomparso nei log un errore backup emergency shutdown su `/app/backups/... Permission denied`; non bloccante per RBAC ma da censire in seguito.
  - Nessun commit e nessun push eseguito.

## 2026-07-05 | SEC-03 fase B | RBAC minimo enforcement reale

- Cosa fatto:
  - Applicate le due correzioni matrice decise dopo il log-only: `GET /api/v1/reporting/timesheet` consentito anche a `operatore`; export Excel piano finanziario consentito anche a `operatore`.
  - Generata password monouso per l'utente `operatore` tramite `backend/reset_password.py`; password non registrata nei log permanenti.
  - Verificato login reale `operatore@gestionale.local`: HTTP 200, ruolo restituito `operatore`.
  - Attivato enforcement reale con `RBAC_ENFORCE=True` nel runtime backend.
  - Rieseguiti smoke test sui ruoli `admin`, `operatore`, `consultazione` con 200/403 attesi secondo matrice corretta.

- File toccati:
  - `backend/auth.py`
  - `backend/main.py`
  - `backend/alembic/versions/052_normalize_user_roles.py`
  - `backend/tests/test_rbac_minimo_log_only.py`
  - `scripts/rbac_log_only_report.py`
  - `audit/RBAC_LOG_ONLY_REPORT.md`
  - `docker-compose.yml`
  - `REMEDIATION_LOG.md`
  - `STATUS.md`

- Test/verifiche eseguiti:
  - Host: `pytest -q tests/test_rbac_minimo_log_only.py tests/test_logging_safety.py tests/test_secret_remediation.py -p no:cacheprovider` -> 75 passed, 1 warning coverage/config preesistente.
  - Container: stesso pytest dentro `pythonpro_backend` -> 75 passed, 1 warning coverage/config preesistente.
  - Runtime smoke enforcement: letture operative 200 per i ruoli previsti; security/GDPR/agenti/config admin-only; scritture bloccate a `consultazione`; timesheet ed export Excel piano finanziario consentiti ad `operatore`.

- Note operative:
  - Nessun flusso email/IMAP/SMTP, OpenClaw o WhatsApp attivato.
  - Non fare push finche' la history git non sara' ripulita in Ondata 2.

## 2026-07-05 | NEW-002 | Backup runtime ripristinato e verificato

- Cosa fatto:
  - Diagnosticato `Permission denied` su `/app/backups` dopo recreate: volume `0755` owner `999:1000`, processo applicativo `1000:999`.
  - Corretto live il volume backup a owner `1000:999` e permessi `0775` per backend e backup scheduler.
  - Corretto `backend/backup_manager.py` per usare una GNUPGHOME temporanea sicura in cifratura e decifratura, evitando failure quando `/home/appuser/.gnupg` non esiste.
  - Aggiornata la verifica integrita per decriptare i `.zip.gpg` in una directory temporanea prima di testare lo ZIP.
  - Ricreate immagini/container backend e backup scheduler, verificando `gpg` presente in entrambi.
  - Registrato il finding in `audit/FINDINGS_NUOVI.md`.

- File toccati:
  - `backend/backup_manager.py`
  - `audit/FINDINGS_NUOVI.md`
  - `REMEDIATION_LOG.md`
  - `STATUS.md`

- Test/verifiche eseguiti:
  - Backend: `/app/backups` owner `1000:999`, permessi `775`, test write OK, `gpg` disponibile.
  - Backup scheduler: `/app/backups` owner `1000:999`, permessi `775`, test write OK, `gpg` disponibile.
  - Backup manuale creato come `.sql.zip.gpg` e `verify_backup_integrity(...)` -> True.
  - Backup scheduler verificato con creazione `.sql.zip.gpg` e `verify_backup_integrity(...)` -> True.

- Note operative:
  - Fix applicato prima dell'enforcement RBAC reale per evitare un rischio backup silenzioso.


## 2026-07-05 | Ondata 1 punto 5 | Rotture funzionali F2-001/002/003/004

- Cosa fatto:
  - F2-001 (commit `2ac218b`): implementate in `backend/crud.py` le funzioni mancanti `get_listini`, `get_listino`, `create_listino`, `update_listino`, `delete_listino` che il router `listini.py` chiamava (causa dei 500). RBAC invariata: `/api/v1/listini` era gia' prefisso operativo sotto `require_role`. Pagine frontend listini gia' sul client `http` con endpoint combacianti: nessuna modifica frontend necessaria.
  - F2-002 (commit `0665b4f`): implementati `GET /api/v1/projects/{id}/beneficiari` e `PATCH /api/v1/projects/{id}/beneficiari/{azienda_id}/regime` in `routers/projects.py` + schemi dedicati. SCELTA: endpoint backend invece di rimozione frontend, perche' il modello `azienda_cliente_projects` (regime_aiuto, plafond_dichiarato) esiste ed e' popolato dagli import FAPI/formulario/Fondimpresa, e il cockpit genera gia' decisioni "Regime aiuto non definito" risolvibili solo da questa UI: senza endpoint non esisteva alcun write-path manuale. `regime_aiuto` accetta `non_definito|de_minimis|esenzione` (`non_definito` salvato come NULL, coerente con la query cockpit). Endpoint nati sotto `require_role` (prefisso projects: GET tutti i ruoli, PATCH admin/operatore).
  - F2-003 (commit `5c1c615`): censite 14 fetch dirette in 6 file. Migrate 13 al client `http` (Bearer automatico): HomeCockpit (1), App.js ProjectSelect (1), ContractTemplateModal (3), ProgettoMansioneEnteManager (7), apiService healthCheck (1). La 14ma (PortaleAllievi) e' flusso token pubblico, gestita in F2-004. `http.js`: un 401 senza refresh token ora pulisce i token e reindirizza al login; i 401 di `/auth/login|refresh|register` propagati senza redirect (evita loop su login fallito).
  - F2-004 (commit `7cc2b81`): estratto `GET /portale-allievi/profilo` da `sprint7.py` (protetto) nel nuovo router pubblico `routers/portale_allievi.py`. SCELTA: endpoint pubblico senza `require_role` perche' gli allievi esterni non hanno account applicativo; l'auth e' la validazione del magic token a scadenza giornaliera (401 proprio del portale). Il generatore magic-link resta protetto JWT (funzione staff). `PortaleAllievi.js` resta su fetch senza Bearer (corretto per flusso pubblico) ma ora usa `apiRootUrl`.

- File toccati:
  - `backend/crud.py` (solo hunk listini, staging selettivo: hunks preesistenti `utc_now`/`avviso_pf_id` lasciati fuori)
  - `backend/schemas.py`, `backend/routers/projects.py`
  - `backend/routers/portale_allievi.py` (nuovo), `backend/routers/sprint7.py`
  - `backend/main.py` (solo hunk include portale, staging selettivo: hunks redaction preesistenti lasciati fuori)
  - `backend/tests/test_listini_api.py`, `backend/tests/test_project_beneficiari_api.py`, `backend/tests/test_portale_allievi_api.py` (nuovi)
  - `frontend/src/lib/http.js`, `frontend/src/lib/http.test.js` (nuovo)
  - `frontend/src/App.js`, `frontend/src/components/HomeCockpit.js`, `frontend/src/components/ContractTemplateModal.js`, `frontend/src/components/ProgettoMansioneEnteManager.js`, `frontend/src/components/PortaleAllievi.js`, `frontend/src/services/apiService.js`
  - `REMEDIATION_LOG.md`, `STATUS.md`

- Test/verifiche eseguiti (TDD: ogni fix scritto test-first, RED verificato prima dell'implementazione):
  - Container: `tests/test_listini_api.py` -> 31 passed (prima: 13 failed per AttributeError crud).
  - Container: `tests/test_project_beneficiari_api.py` -> 14 passed (prima: 5 failed per endpoint mancanti).
  - Container: `tests/test_portale_allievi_api.py` -> 4 passed (prima: 3 failed, endpoint dietro JWT).
  - Frontend: `src/lib/http.test.js` -> 5 passed (Bearer injection, 401 senza refresh -> clear+redirect, 401 auth -> no redirect).
  - Container regressione mirata: listini+routers_api_v1+rbac+logging+secret -> 128 passed.
  - Runtime smoke con JWT admin locale: `/api/v1/listini/` 200, `/api/v1/listini/999999` 404, `/api/v1/projects/1/beneficiari` 200, `/api/v1/projects/999999/beneficiari` 404.
  - Runtime smoke portale senza Bearer: token invalido -> 401 `Token non valido o scaduto` (logica portale raggiunta); `/api/v1/allievi/1/magic-link` senza Bearer -> 401 `Not authenticated` (resta protetto).
  - `npm run build` -> OK, unico warning preesistente `HomeCockpit.js CATEGORIA_COLORE unused`.

- Rotture preesistenti trovate (NON causate da questo punto, da censire):
  - Suite backend su host: `Base.metadata.create_all` fallisce su SQLite host (sqlalchemy host rende `DEFAULT now()` per `email_inbox_items`); in container tutto ok. Test eseguiti in container.
  - Test frontend jest: TUTTI i test jsdom falliscono per conflitto hoisted `@tootallnate/once@3` (ESM) vs `http-proxy-agent@4` (richiede v1) nel `package-lock.json` preesistente non committato. Workaround: `http.test.js` gira in env node con shim. Fix vero = sistemare il lockfile (file censito, decidere in Ondata 2).

- Note operative:
  - 4 commit atomici: `2ac218b`, `0665b4f`, `5c1c615`, `7cc2b81`.
  - Nessun flusso email/IMAP/SMTP, OpenClaw o WhatsApp attivato.
  - NON fare push finche' la history git non sara' ripulita in Ondata 2.

## 2026-07-05 | Ondata 1 punto 6 | Allineamento schema/Alembic F1-002/F1-008/F2-007

- Cosa fatto:
  - Rilevato drift attuale con autogenerate API (a head 052): 139 operazioni (1 add_table, 53 add_index, 58 remove_index, 5 remove_column, 12 modify_nullable, 4 modify_type, 4 add_fk, 2 remove_constraint).
  - PROVA GENERALE (obbligatoria): dump fresco `pg_dump -F c` del DB live -> restore in `gestionale_p6copy` -> `alembic upgrade head` (052->053) -> `alembic check` = "No new upgrade operations detected". Solo dopo: DB reale.
  - BACKUP: dump pre-053 salvato fuori progetto in `/DATA/progetti/pythonpro_remediation_backups/20260705_150819_punto6/` con SHA256SUMS (in aggiunta al backup Passo Zero).
  - DB reale: `alembic upgrade head` -> 053; `alembic check` -> PULITO. Backend riavviato, health OK.
  - Commit `f43822b` (F1-002/F2-007): migration `053_reconcile_schema_drift.py` + allineamenti modello. Criterio: modelli fonte di verita'; dove il DB era piu' severo (NOT NULL con default) o piu' ricco (indici funzionali: overlap guards, compositi, regime, city, active_created DESC) si sono adeguati i modelli. Dettagli completi nel docstring della migration e nel commit message.
  - Colonne legacy agenti droppate SOLO dopo verifica dati live: 0 valori divergenti (agent_name==agent_type, agent_suggestions.agent_name tutti NULL, confidence==confidence_score); 2 reviewed_at NULL backfillati da created_at prima del NOT NULL.
  - Indice PG-only `idx_collab_fulltext_search` (cast `::text` invalido su SQLite dei test): mantenuto solo nel DB, escluso dal confronto autogenerate via allowlist `include_name` in `alembic/env.py`, documentato in models.py.
  - Commit `d6810c1` (F1-008): rimossi i 4 script manuali `migrate_*.py` DOPO check pulito. Verifica preventiva: tutti e 4 sono SQLite-era (sqlite3/PRAGMA), non eseguibili su Postgres; i loro effetti risultano gia' presenti nello schema live (colonne documenti, ente_attuatore_id, tabella progetto_mansione_ente, fiscal_code NOT NULL + unique). Nessuna migration "applicativa" necessaria: la 053 e' la reconciliation del drift residuo. Unico riferimento residuo agli script: docs/AUDIT.md (storico, lasciato).

- Checklist drift censito (audit/FASE_2_alembic_check.txt), regola 3 - tutte le voci risolte:
  - `giustificativo_spesa` mancante -> tabella creata con i 4 indici. VERIFICATO live.
  - colonne rimosse `agent_runs.agent_name`, `agent_suggestions.confidence`, `agent_suggestions.agent_name` (+ `agent_review_actions.created_at/reviewed_by`) -> droppate. VERIFICATO live.
  - indici rimossi su collaborators/projects/listini/preventivi ecc. -> 38 duplicati droppati, 4 rinominati, i funzionali preservati e dichiarati a modello (overlap guards presenti, fulltext presente). VERIFICATO live.
  - type change `projects.ente_erogatore` -> VARCHAR(100). VERIFICATO live (max len dati: 11).
  - `alembic check` exit 0 su DB reale = nessuna voce residua.

- Test/verifiche eseguiti:
  - Copia: upgrade+check puliti (2 iterazioni: fix nome constraint `uq_allievi_codice_fiscale` trovato per colonna, non per nome).
  - DB reale: `alembic current` = 053 (head); `alembic check` = pulito; health OK.
  - Suite completa in container: 239 passed (identica al punto 5).
  - Catena intera su DB VUOTO (`gestionale_p6empty`): upgrade head OK con 053 difensiva.
  - DB temporanei di prova droppati a fine lavoro.

- Rilievo preesistente NUOVO (da censire per Ondata 2):
  - La catena Alembic su DB vuoto NON produce lo schema completo: colonne storicamente aggiunte fuori migration (es. `projects.avviso`) mancano dopo `upgrade head` da zero. La 053 e' difensiva (salta cio' che non esiste). Un deploy greenfield oggi richiederebbe una baseline migration rigenerata dai modelli.

- Note operative:
  - 2 commit atomici: `f43822b` (drift), `d6810c1` (script manuali).
  - Nessun flusso email/IMAP/SMTP, OpenClaw o WhatsApp attivato.
  - NON fare push finche' la history git non sara' ripulita in Ondata 2.

## 2026-07-05 | Ondata 1 punto 7 / SEC-08 | Dipendenze frontend e Python

- Cosa fatto:
  - Ricostruito stato reale dopo interruzione: nessun commit punto 7 presente; `frontend/package.json` e `frontend/package-lock.json` erano modificati ma non committati.
  - Verificato npm reale: `critical=0`, `high=0`, `moderate=2`, `low=9` dopo il lavoro npm rimasto pendente.
  - Verificato frontend: `npm run build` OK con solo warning preesistente `HomeCockpit.js CATEGORIA_COLORE unused`; test mirato workaround `src/lib/http.test.js` OK, 5 passed.
  - Commit `f7a1782` (`fix(SEC-08): npm dependency vulnerabilities`): salvato fix npm che azzera critical/high, rimuove `xlsx`, aggiorna/normalizza dipendenze e override, e sposta `react-scripts` in devDependencies.
  - Verificato che `pip-audit` non era installato nel container backend e non era mai documentato nel remediation log.
  - Installato `pip-audit` nel container solo come strumento di audit.
  - Primo audit Python runtime: 6 vulnerabilita note in 2 pacchetti toolchain, non applicative:
    - `pip 24.0`: `PYSEC-2026-196` / `CVE-2026-8643`, `CVE-2025-8869`, `CVE-2026-1703`, `CVE-2026-3219`, `CVE-2026-6357`; fix non breaking a `pip 26.1.2`.
    - `wheel 0.45.1`: `CVE-2026-24049`, severita High dichiarata dall'advisory; fix non breaking a `wheel 0.46.2`.
  - Corretto `backend/Dockerfile` per fissare `pip==26.1.2` e `wheel==0.46.2`; aggiunta pulizia dei dist-info stale in final stage per evitare falsi positivi/metadata doppi dopo `COPY --from=builder /usr/local /usr/local`.
  - Rebuild immagine backend e force-recreate `backend`, `arq_worker`, `backup_scheduler`.
  - Verificato runtime metadata: `pip 26.1.2`, `wheel 0.46.2`, `setuptools 83.0.0`, senza dist-info vecchi.
  - Audit finale Python: `pip-audit --cache-dir /tmp/pip-audit-cache -f json` -> `No known vulnerabilities found`.
  - Commit `d4b40bc` (`fix(SEC-08): pin backend packaging toolchain`): salvato fix Python toolchain.

- Residui censiti:
  - `NEW-004`: npm moderate/low residui nella catena `react-scripts`/Jest/jsdom/webpack-dev-server; richiedono major/toolchain migration, quindi rimandati a Ondata 2.
  - `NEW-003`: catena Alembic greenfield non completa, emersa nel punto 6 e censita ora in `audit/FINDINGS_NUOVI.md`.

- File toccati:
  - `frontend/package.json`
  - `frontend/package-lock.json`
  - `backend/Dockerfile`
  - `audit/FINDINGS_NUOVI.md`
  - `REMEDIATION_LOG.md`
  - `STATUS.md`

- Test/verifiche eseguiti:
  - `npm audit --json` -> `critical=0`, `high=0`, `moderate=2`, `low=9`.
  - `npm audit --audit-level=high` -> exit 0; residui moderate/low non bloccanti censiti.
  - `npm run build` -> OK, warning preesistente `HomeCockpit.js CATEGORIA_COLORE unused`.
  - `npm test -- --runInBand --watchAll=false src/lib/http.test.js` -> 5 passed.
  - `pip-audit --cache-dir /tmp/pip-audit-cache -f json` nel container backend -> No known vulnerabilities found.
  - Backend health dopo recreate -> OK.

## 2026-07-05 | ONDATA-1-GATE | Gate finale e verdetto uso interno

- Gate eseguiti:
  1. Pytest completo in container: `239 passed, 3 warnings in 414.88s`.
  2. `alembic check`: pulito, `No new upgrade operations detected`.
  3. `npm audit --audit-level=high`: exit 0, zero critical/high; residui `2 moderate / 9 low` censiti in `NEW-004`.
  4. Scansione segreti su file tracciati con `git grep -nEI '(password\s*=|secret\s*=|api_key\s*=|token\s*=|postgres://)'`: nessun segreto runtime reale nuovo nel codice tracciato; risultati classificati come accessi a env var, hash/password di test o documentazione storica. Nota residua: `STATUS.md` contiene una vecchia password runtime storica (`Admin123!RuntimeLocal`) gia ruotata ma da ripulire nella normalizzazione documentale/Ondata 2. `gitleaks` non installato nel sistema.
  5. `RBAC_ENFORCE=true` verificato nel container runtime.
  6. `/health` runtime OK: `{"status":"ok"}`.
  7. Backup manuale completo creato e verificato: `/app/backups/gestionale_backup_ondata1_gate_20260705_144714.sql.zip.gpg`, `verify_backup_integrity(...) == True`.
  8. Build frontend finale: OK, warning preesistente `HomeCockpit.js CATEGORIA_COLORE unused`.

- Commit Ondata 1 creati/locali, nessun push:
  - `31a7cc5` fix(SEC-01): rotate exposed runtime secrets
  - `98f5878` fix(SEC-02): remove hardcoded admin reset password
  - `f3dae89` fix(SEC-03): add minimal RBAC migration
  - `9fcfa2a` fix(SEC-03): enforce minimal RBAC matrix
  - `38d158f` fix(NEW-002): repair encrypted backup creation
  - `2ac218b` fix(F2-001): add missing listini CRUD functions
  - `0665b4f` fix(F2-002): implement project beneficiari endpoints
  - `5c1c615` fix(F2-003): route all frontend API calls through the shared http client
  - `7cc2b81` fix(F2-004): make portale allievi coherent with its public token flow
  - `f43822b` fix(F1-002,F2-007): reconcile schema/model drift, alembic check clean
  - `d6810c1` chore(F1-008): remove one-shot manual migration scripts
  - `f7a1782` fix(SEC-08): npm dependency vulnerabilities
  - `d4b40bc` fix(SEC-08): pin backend packaging toolchain

- Finding audit chiusi/mitigati in Ondata 1:
  - Segreti/config: `F1-001`, `SEC-01`, `GDPR-04`, `SAAS-03` mitigati con rotazione runtime, rimozione backup env, template `.env.example` pulito e blocco push fino a pulizia history.
  - Reset admin hardcoded: `F3-001`, `SEC-02` chiusi.
  - Logging/token/header: `F3-003`, `SEC-04` chiusi per redazione log richiesta da Ondata 1.
  - RBAC minimo uso interno: `SEC-03`, `GDPR-02`, `SAAS-02` mitigati con enforcement reale admin/operatore/consultazione; tenant scope SaaS resta Ondata 2.
  - Rotture funzionali: `F2-001`, `F2-002`, `F2-003`, `F2-004` chiuse.
  - Schema/Alembic live: `F1-002`, `F2-007`, `F1-008` chiusi sul DB reale; greenfield baseline censita come `NEW-003`.
  - Backup runtime: `NEW-001`, `NEW-002` corretti.
  - Dipendenze: `SEC-08` chiuso per critical/high npm e vulnerabilita Python note; moderate/low npm censiti come `NEW-004`.

- Finding nuovi emersi durante Ondata 1:
  - `NEW-001` alta: `BACKUP_ENCRYPTION_KEY` non propagata ai container. Stato: corretto.
  - `NEW-002` alta: volume backup non scrivibile/GPG runtime non pronto. Stato: corretto.
  - `NEW-003` alta: catena Alembic greenfield non completa. Stato: aperto per Ondata 2.
  - `NEW-004` media: residui npm moderate/low richiedono uscita da `react-scripts`/major toolchain. Stato: aperto per Ondata 2.

- Dichiarazione finale:
  - ONDATA 1 COMPLETATA — piattaforma idonea all'uso interno con dati reali: SÌ CON RISERVE.
  - Motivazione: i gate minimi per uso interno controllato sono verdi (segreti runtime ruotati, RBAC enforcement, logging redatto, schema live allineato, backup verificato, test completi verdi, critical/high dependency risk azzerato). Le riserve sono: nessun push finche la history git non viene ripulita; usare solo in contesto interno/trusted; non attivare flussi email/OpenClaw/WhatsApp finche i sistemi esterni non sono allineati; non considerare la piattaforma SaaS-ready; pianificare Ondata 2 per tenancy, history cleanup, baseline Alembic greenfield, toolchain frontend e hardening residuo.

## 2026-07-05 | ONDATA-1-CHIUSURA | Ripresa sessione, verifica indipendente e completamento

- Contesto: la sessione precedente si e' interrotta per limite di contesto. Le sezioni "punto 7" e "ONDATA-1-GATE" qui sopra risultavano scritte nel worktree ma NON committate. Questa sessione ha riverificato tutto sul campo senza fidarsi della sintesi.

- Stato reale ricostruito all'avvio:
  - Lavoro punto 7 GIA' committato: `f7a1782` (npm) e `d4b40bc` (pin pip/wheel Dockerfile). Nessun pending su `package.json`/`package-lock.json`.
  - Non committati: aggiornamenti `REMEDIATION_LOG.md`/`STATUS.md`/`audit/FINDINGS_NUOVI.md`, riga `gnupg` in `backend/Dockerfile`, 2 righe `.gitignore`.
  - Rilevata dipendenza critica: la riga `gnupg` (preesistente, censita in WORKTREE_PREESISTENTE.md) e' richiesta dal fix backup `38d158f`; le righe `.gitignore` (`.env.*`, `secrets.yml`, preesistenti) sostengono la garanzia SEC-01. Entrambe committate in questa sessione per rendere i fix riproducibili da checkout pulito.

- Verifica indipendente gate (riesecuzione completa 2026-07-05 pomeriggio):
  1. Pytest completo in container: `239 passed, 4 warnings in 416.03s (0:06:56)`.
  2. `alembic check`: "No new upgrade operations detected", `alembic current` = 053 (head).
  3. `npm audit`: `critical=0, high=0, moderate=2, low=9` (residui = NEW-004: webpack-dev-server moderate, catena @tootallnate/once low; fix solo via `--force`/major, non applicato).
  4. Scansione segreti `git grep` da root repo su tutti i file tracciati: nessun segreto letterale nel codice; soli accessi env/valori computati. `gitleaks` non installato nel sistema. La password storica gia' ruotata presente in `STATUS.md` e' stata REDATTA in questa sessione (`[REDACTED-password-storica-ruotata]`).
  5. `RBAC_ENFORCE=true` verificato nel runtime del container backend.
  6. `curl /health` -> `{"status":"ok"}`.
  7. Ciclo backup fresco: `create_backup('ondata1_gate_final')` -> `/app/backups/gestionale_backup_ondata1_gate_final_20260705_162703.sql.zip.gpg`, `verify_backup_integrity(...) == True`.
  - Extra: `pip-audit` rieseguito nel container -> "No known vulnerabilities found"; `npm run build` -> OK (warning preesistente HomeCockpit); test frontend `src/lib/http.test.js` -> 5 passed.

- Commit aggiunti in questa sessione:
  - `38c903e` fix(NEW-002): install gnupg in backend image
  - `d605b09` fix(SEC-01): ignore all .env variants and secrets.yml

- Nota anomalia sanata: la sezione ONDATA-1-GATE precedente riportava un backup gate delle 14:47, anteriore ai commit punto 7 delle 16:25/16:35; il ciclo backup e tutti i gate sono stati rieseguiti in questa sessione a punto 7 interamente committato.

- La dichiarazione finale "SÌ CON RISERVE" della sezione precedente e' CONFERMATA da questa verifica indipendente.

## 2026-07-14 | ONDATA AGENTI | A1 in corso (kill switch, no auto-send, reply draft)

- Contesto: filone dedicato piattaforma agenti. Piano completo in `docs/superpowers/plans/2026-07-14-ondata-agenti.md`. Baseline pre-lavoro: 245 test passed (suite container). Backup DB creato e verificato: `gestionale_backup_manual_20260714_174348.sql.zip.gpg`.
- Politica worktree pre-esistente (censito in audit/WORKTREE_PREESISTENTE.md): gli hunk agentici conformi alla spec vengono verificati, testati e adottati nei commit atomici; il resto resta non committato.
- Commit chiusi:
  - `2387e0c` fix(AGENT-01): kill switch AGENTS_ENABLED + AGENT_<NOME>_ENABLED su tutti i trigger (manuale, sync evento, cron ARQ incluso data_retention_cleanup). Adottato control.py pre-esistente + gate in agent_workflows. 12 test (test_agent_kill_switch.py).
  - `98b2945` fix(AGENT-02): rimosso percorso auto-send mail_recovery (rami morti auto_send, contatore auto_sent_emails); ogni comunicazione nasce draft e parte solo da apply_workflow_action. Adottato consent-gate con audit in run_mail_recovery_agent. 4 test (test_agent_no_autosend.py).
  - `91fb9a4` fix(AGENT-03): reply automatica email intake (documento invalido / allegato non supportato) sostituita da AgentRun+Suggestion+Draft approvabile; InboxReplyComposer.compose separato dall'invio; INSERT email_inbox_items con created_at esplicito. 4 test (test_inbox_reply_draft.py).
- A1 restante: A1.4 (auto-validazione LLM e update anagrafici → proposta con diff campo per campo + apply-fix reale con audit; trigger contract_agent spostato su validazione umana) e A1.5 (FINDINGS_NUOVI: apply-fix finto, data_retention_cleanup side effect automatici, /email-inbox/status cross-process stantio). Poi suite completa e chiusura punto.
- Nessun push (vincolo Ondata 2 invariato).

## 2026-07-15 | ONDATA AGENTI | A1 CHIUSO (A1.4 proposta+apply reale, A1.5 findings)

- **A1.4 — `cc98924` fix(AGENT-04)**: documenti e anagrafiche solo per proposta, apply-fix reale con audit.
  - `document_processor.py`: rimossi override `False->True` in `_parse_llm_result_dict` e auto-validazione `confidence>=0.85` in `_apply_confidence_decision`.
  - `document_intake_agent.py`: `apply_document_result` non scrive più campi collaboratore/azienda (fix AI-01) e non valida documenti; documento resta `caricato`, proposte come diff campo per campo (AgentSuggestion `document_field_updates`, `auto_fix_payload` = field_diff JSON); trigger contract_agent parte solo da validazione umana (`routers/documenti_richiesti.py`).
  - `email_inbox_worker.py`: dati dal body email diventano proposta nello stesso diff (`_build_body_proposals`); rimossi stato `auto_processed` e `_create_auto_update_suggestion`.
  - `services/agent_apply_service.py` (nuovo): `apply_field_update_suggestion` con whitelist campi per entity_type, skip valori stantii (ricontrollo valore attuale), `AuditLog` per campo, risoluzione follow-up `request_missing_collaborator_data` pendenti.
  - `routers/agents.py`: apply-fix applica DAVVERO il diff (chiude NEW-005); payload non strutturato → 400. Adottati nello stesso commit gli hunk RBAC pre-esistenti del worktree (`require_agents_execute/write` = ADMIN|MANAGER, nota: più restrittivi degli endpoint prima aperti; riconciliazione con matrice RBAC al GATE A5a).
  - Test: `test_document_intake_proposal.py` nuovo (11 test), `test_email_agent.py` aggiornato al comportamento a proposta.
- **A1.5**: `audit/FINDINGS_NUOVI.md` aggiornato con NEW-005 (apply-fix fittizio, alta — chiuso da AGENT-04), NEW-006 (data_retention_cleanup anonimizza+invia email automaticamente, alta — mitigato dal kill switch AGENT-01, conversione a proposta rinviata ad A3), NEW-007 (/email-inbox/status legge stato in-process stantio, media — fix pianificato A2.3).
- Gate di chiusura A1: suite completa in container **276 passed** (baseline 245; +31 dai test AGENT-01..04).
- Nessun push (vincolo Ondata 2 invariato).

## 2026-07-15 | ONDATA AGENTI | A2 CHIUSO (metadata users ARQ, cron via workflow, IMAP resiliente)

- **A2.1 — `ad63663` fix(AGENT-06)**: il processo ARQ importava solo `models` via `agent_workflows`, quindi la tabella `users` (dichiarata in `auth.py`) non entrava nella Base metadata e ogni flush di `AgentReviewAction` (FK `reviewed_by_user_id -> users.id`) falliva con `NoReferencedTableError` in `promote_agent_followups`. Fix: `import auth` in `arq_worker.py`. Test `test_arq_worker_context.py`: subprocess con interprete pulito verifica `users` in metadata + test funzionale follow-up (2 test).
- **A2.2 — `4b88a74` fix(AGENT-07)**: `run_mail_recovery_cron` chiamava `run_mail_recovery_agent` direttamente (nessun AgentRun tracciato, esecuzioni invisibili in dashboard). Ora passa da `run_agent_workflow(agent_type="mail_recovery", auto_mode=True)` con `trigger_mode=automatic`. Test `test_mail_recovery_cron.py` con guardia anti-bypass (2 test). **Bypass residui censiti** (migrazione in A3, GATE): `run_contract_agent_cron`, `run_certification_agent_cron`, `routers/sprint7.py`, `jobs/run_agents.py`, `DocumentIntakeAgent._trigger_contract_agent`.
- **A2.3 — `eff29b7` fix(AGENT-08)**: chiude NEW-007. Nuovo `services/inbox_status_store.py`: stato inbox condiviso su Redis (fallback in-memory) con `{state connected|auth_failed|error|disabled, last_error, failed_attempts, next_retry_at, last_success_at, last_poll_at}`. Worker: errori login classificati, backoff esponenziale (5m, x2, cap 6h), skip finché `now < next_retry_at`, reset su login ok. Router: `/email-inbox/status` legge lo store con messaggio sintetico; nuovo `POST /email-inbox/imap/test` (solo admin, nessuna credenziale in risposta). Test `test_imap_resilience.py` (10 test).
- Gate di chiusura A2: suite completa in container **290 passed**.
- Prossimo: **A3 registry unico — GATE**: presentare mappa migrazione agente-per-agente all'utente prima di toccare `registry.py` legacy.
- Nessun push (vincolo Ondata 2 invariato).

## 2026-07-15 | ONDATA AGENTI | A3 CHIUSO (registry unico, legacy eliminato) — GATE superato

- GATE A3: mappa migrazione presentata all'utente e confermata ("procedi A3"), inclusa rimozione `jobs/run_agents.py` e refactor AgentRun interno di contract/certification.
- **A3 — `0361391` fix(AGENT-09)**: registry unico dichiarativo, contract/certification via workflow, rimozione legacy.
  - `_AGENT_DEFINITIONS` esteso: name, description, supported_entity_types, triggers, kill_switch_env, allowed_roles, version, runner. 4 agenti: data_quality, mail_recovery, contract_agent, certification. Dashboard `/agents/` legge solo il registry unico.
  - `contract_agent.py`/`certification_agent.py` → collector puri `collect_*_suggestions` (nessuna scrittura DB; AgentRun creato solo da `run_agent_workflow`).
  - Cron ARQ contract/certification → workflow (`auto_mode=True`). Endpoint sprint7 → workflow + gate `require_agents_execute` (prima SENZA auth). Trigger da validazione umana documento → workflow (`entity_type=collaborator`).
  - Eliminati `ai_agents/registry.py` e `jobs/run_agents.py` (verificato non referenziato da Makefile/compose/main).
  - Hunk pre-esistente adottato con nota: `is_valid_codice_fiscale` in data_quality.py (validazione check digit CF) — verificato e coperto da test dedicato.
  - `AGENTS_PLATFORM.md` (backend root): guida flusso canonico + esempio minimale per nuovi agenti.
  - Grep di guardia: nessuna chiamata `run_*_agent(` fuori dal dispatch del workflow; `agent_registry`/`BaseAgent` assenti dal codice applicativo.
  - Test: `test_agents_registry_workflow.py` nuovo (9), `test_document_intake_proposal.py` aggiornato.
- Gate di chiusura A3: suite completa in container **299 passed**.
- Prossimo: A4 robustezza LLM; poi A5 (GATE matrice RBAC su A5a), A6 e2e, GATE finale.
- Nessun push (vincolo Ondata 2 invariato).
