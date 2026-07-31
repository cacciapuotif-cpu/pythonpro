# PythonPro Remediation Log

Formato: data | finding ID | cosa fatto | file toccati | test/verifiche eseguiti

## 2026-07-31 | UX-NOMINATIVI | Formato e ordinamento uniforme

- Aggiunta utility frontend `formatPersonName`/`comparePeople` e applicata a
  liste e selettori di collaboratori, allievi, consulenti, utenti, referenti,
  documenti, dashboard, agenti, calendario, timesheet e contratti.
- Ordinamento backend case/accent-insensitive con `unaccent`, indici funzionali
  Alembic 070, paginazione server-side preservata.
- Censiti record anomali e `Codex Runtime Test`; nessuna modifica dati.
- Test frontend 41/327 verdi; backend completo 986 passed / 6 skipped;
  migration provata su copia e applicata al DB reale.

## 2026-07-31 | DEL-UI-03 | Eliminazione aziende senza fallimenti silenziosi

- Dialog UI con stato di verifica, conferma esplicita, errore leggibile e
  elenco collegamenti; menu azioni per riga per evitare sovrapposizione.
- Eliminati sul DB reale gli isolati `Azienda 06615351217` e
  `Azienda 97294390584`, audit presenti. `Ccccc` e `Maximercato uno srl`
  bloccate con collegamenti espliciti.
- Frontend build/recreate live; 40 suite, 325 test, 0 fallimenti.

## 2026-07-31 | DEL-01 / DOC-01 | Eliminazione aziende e documenti resa operativa

- Implementati hard-delete aziende/documenti, archiviazione documenti, impatto,
  RBAC, doppia conferma, audit, chiusura suggerimenti collegati, ripristino
  versione precedente e rimozione file fisico.
- Commit: `a22e381`, `52dc15f`, `9f2f9b3`, `03cb9fe`.
- Verifica su DB copia: azienda isolata eliminata e auditata; azienda collegata
  bloccata con collegamenti; documento bozza eliminato con file; documento in
  rendicontazione archiviato. Backup verificato e copia poi rimossa.
- Test: backend 986 passed / 6 skipped; frontend 40 suite / 325 test.

> AVVISO PERMANENTE: VIETATO push su remote finche history git non ripulita da `.env`/`.env*` in Ondata 2 con procedura dedicata.

## 2026-07-30 | MOB-3 / NEW-046…049 | Liste, card, filtri e paginazione mobile

- Creato un contratto condiviso per gli elenchi: stessa collezione, una sola
  resa montata (desktop denso oppure card mobile), selettori E2E per lista,
  layout ed entità.
- Applicato a nove domini: collaboratori, allievi, progetti, aziende, ordini,
  preventivi, avvisi, proposte agenti e documenti mancanti.
- Aggiunti “Carica altri” mobile con append/deduplica e paginazione numerica
  desktop; proposte agenti a blocchi di 20 su telefono.
- Filtri secondari spostati in bottom sheet mobile con contatore, azzera,
  focus trap, Escape e Back; ricerca lasciata sempre accessibile.
- Correzioni emerse: allievi oltre pagina 1 raggiungibili (`NEW-046`);
  caricamento progetto completo in batch (`NEW-047`); contratto test backup
  SQLite corretto (`NEW-049`). `NEW-048` resta aperto per consolidamento cache
  in MOB-6.
- Verifiche: test frontend completi e build verdi; test backup mirato 1/1;
  gate Playwright 4 profili × 21 sezioni + 4 flussi pubblici, zero overflow,
  nessuna doppia resa o ID duplicato. Suite backend completa rieseguita come
  gate finale.
- Evidenze: `audit/MOB3_ELENCHI_REPORT.md` e artefatti locali
  `frontend/test-results/responsive-layout/`.
- Runtime frontend ricostruito localmente; nessun push.

## 2026-07-30 | MOB-2 / NEW-045 | Navigazione mobile e routing canonico

- Introdotti header mobile compatto, bottom navigation per ruolo e menu
  full-screen “Altro” ricercabile con focus, Escape, Back e safe area.
- Assegnati path canonici alle 21 sezioni; BrowserRouter, guardia RBAC
  pre-mount, push/Back/Forward e filtri conservativi.
- Aggiunta destinazione `/presenze` che riusa Calendario in modalità
  operativa; corretti deep-link collaboratore/documenti e link delle proposte
  agente.
- Back chiude prima i layer Livello 1: menu, Area personale, presenza e
  dettaglio proposta.
- Test: frontend 33 suite / 311 test / 3 snapshot; build verde; gate browser
  MOB-2 21/19/18 sezioni sui tre ruoli, zero diagnostica; regressione MOB-1
  4 profili × 21 sezioni + 4 flussi pubblici verde; desktop
  1280/1440/1920 verificato.
- Runtime frontend ricostruito e ricreato; nessun push.

## 2026-07-17 | ONDATA S S5 completato / stop prima di S6

- Dopo conferma del GATE S5, `rendicontazione_generator.py` è stato spostato in `services/rendicontazione.py` e collegato a `POST /api/v1/reporting/projects/{project_id}/rendicontazione`.
- Hardening applicato: fondo da `Project.avviso_rel.fondo` con fallback legacy; filtro `DatiRetributivi.project_id + Allievo.azienda_cliente_id`; sanitizzazione unificata delle componenti ZIP; risposta in memoria senza persistenza.
- RBAC: POST sotto prefisso reporting, matrice admin/operatore=200 e consultazione=403; test HTTP effettivo sugli stessi ruoli.
- Test mirati S5 + RBAC: **81 passed, 0 failed**. Commit locale `b5173e1 feat(S5): expose secure project rendicontazione package`. Nessun push.
- S6 solo analizzato, nessuna modifica:
  - DB live verificato read-only: `attendances.assignment_id`, FK `attendances_assignment_id_fkey` e indice `ix_attendances_assignment_id` presenti;
  - script ad hoc può essere eliminato senza migration;
  - costante documenti morta e tre shim parser confermati;
  - otto test root esclusi da `testpaths=tests` attiveranno circa 38 test legacy dopo lo spostamento e richiedono bonifica fixture/test, non workaround in produzione;
  - requirements divergenti confermati; runtime corrente acquisito come riferimento per pin esatti;
  - `CLAUDE.md` contiene ancora la descrizione errata.
- Stop immediato richiesto dall'utente prima di S6. Worktree applicativo pulito al momento dello stop; suite completa post-S5 non ancora eseguita.

## 2026-07-17 | ONDATA S S1-S4 + GATE S5 | Fix rapidi sicurezza

- Prerequisiti:
  - letti `REMEDIATION_LOG.md`, stato sintetico, findings, analisi architetturale e ultimi 20 commit;
  - backup fresco `/app/backups/gestionale_backup_ondata_s_pre_20260717_162634.sql.zip.gpg` verificato con `INTEGRITY=True`;
  - nessuna migration e nessuna modifica al DB.
- S1 (`41b6048`, `80d4b01`): sostituito il token giornaliero prevedibile con nonce CSPRNG, HMAC-SHA256 domain-separated e scadenza firmata a 24 ore; `compare_digest` su digest binari; token Unicode/malformati ora diventano 401, non 500. Test CSPRNG, scadenza, manomissione, legacy rifiutato e timing-safe valido/invalido.
- S2 (`c423669`): redazione ricorsiva estesa a CF con alias composti e campi retributivi; nuovo servizio `security_audit_retention` con default 24 mesi di calendario configurabili, collector aggregato e batch massimo 1000. Integrato nell'agente `data_retention`: cron e run producono solo `AgentSuggestion`; cancellazione solo dopo apply umano autenticato, con ricalcolo live del cutoff e audit di sintesi. `AGENT_DATA_RETENTION_ENABLED=false` invariato. Nessuna migration: indice timestamp già presente.
- S3 (`26ff969`): `.env.development` rinominato `.env.development.sample`, secret sostituiti da placeholder espliciti, controllo automatico aggiornato. I valori legacy non sono presenti in `.env` né nei sette container PythonPro. La worktree separata e già sporca `.worktrees/email-agent` conserva una copia: preservata e censita come NEW-012. Backup env riemerso archiviato senza cancellazione in `/DATA/progetti/pythonpro-local-archive/2026-07-17_ondata_s/` con directory 0700 e file 0600.
- S4 (`3683d48`): confermata firma Meta sul raw body con `WHATSAPP_META_APP_SECRET`; confronto HMAC-SHA256 constant-time reso fail-closed anche per header non hex, lunghezza errata e non ASCII; test firma valida/invalida/mancante, payload alterato e configurazione assente.
- Findings nuovi: NEW-011 (secondo store `AuditLog` legacy senza redazione/retention, aperto) e NEW-012 (credenziali dev deboli nella worktree separata, aperto).
- Verifiche:
  - test mirati S1-S4 e retention: 35 passed;
  - regressione registry/agent retention: 24 passed;
  - `scripts/check_secret_remediation.sh`: OK;
  - `docker compose config --quiet`: OK;
  - suite backend completa: **483 passed, 1 skipped, 0 failed** su 484 raccolti in 378.80s.
- GATE S5 — verifica architetturale:
  - `backend/rendicontazione_generator.py` è realmente orfano: zero importatori/endpoint/UI; `DOM-16` conferma che il deliverable finale non è producibile dalla piattaforma;
  - il generatore serve al giro completo e usa dati reali già modellati: timesheet, collaboratori, aziende beneficiarie, regimi aiuto e `DatiRetributivi`;
  - non va esposto nello stato attuale: per ogni azienda in esenzione include tutti i `DatiRetributivi` del progetto senza filtro `Allievo.azienda_cliente_id`, con rischio cross-company; usa inoltre `Project.ente_erogatore` legacy anziché la relazione avviso canonica;
  - raccomandazione: **SÌ, renderlo operativo**, ma prima spostare la logica in `services/rendicontazione`, filtrare i dati retributivi per azienda, risolvere il fondo dalla FK avviso con fallback legacy, aggiungere endpoint download sotto RBAC admin/operatore e test ZIP/isolamento aziende/mancanti;
  - stato: fermo al GATE S5, nessuna implementazione S5 o S6 senza conferma utente.

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

## 2026-07-15 | ONDATA AGENTI | A4 CHIUSO (robustezza LLM)

- **A4 — `2e82f0e` fix(AGENT-11)**: retry, schema, fallback, prompt versionati, log senza PII.
  - `call_llm_with_retry`: max 2 retry con backoff breve (0.5s/1s) su timeout/trasporto/5xx/output malformato; 4xx non ritentato.
  - Schemi Pydantic `MailCopySchema`/`DocumentResultSchema` (`ai_agents/llm_schemas.py`): output malformato → ValueError → retry → fallback. Mail: fallback deterministico del chiamante (invariato). Documenti: manual_review (valid=None), mai persi.
  - Prompt versionati in `ai_agents/prompts/` (`mail_recovery_v1`, `document_processor_v1`); `DocumentResult.prompt_version` registrata su ogni esito e salvata nel `llm_result` degli item inbox.
  - Log strutturato `agent_llm_call` per chiamata: agent, provider, model, prompt_version, attempt, outcome, duration_ms, error_class — mai contenuti prompt/documenti (test anti-PII).
  - Confidence < 0.60 (globale o per campo) → suggestion `priority/severity=high` + flag `needs_careful_review` nel payload field_diff.
  - Hunk pre-esistenti adottati con nota: `pseudonymize_prompt` (llm_privacy) sul percorso openclaw di `call_ollama_json`/`_call_openclaw` — coerente col requisito niente PII verso gateway esterni.
  - Test: `test_llm_robustness.py` (13 test).
- Gate di chiusura A4: suite completa in container **312 passed**.
- Prossimo: A5b system-health + A5c error surface (A5a matrice RBAC resta GATE utente), A6 e2e, GATE finale.
- Nessun push (vincolo Ondata 2 invariato).

## 2026-07-15 | ONDATA AGENTI | A5b/A5c + A6 CHIUSI — GATE finale parziale (resta A5a)

- **A5b/A5c — `b891922` fix(AGENT-12)**: `GET /api/v1/agents/system-health` — per agente enabled/kill switch/trigger/schedulazione cron + ultimo run con esito ed error_message (A5c); stato inbox IMAP dallo store condiviso; LLM health; coda ARQ (redis ping + depth, degradazione pulita). email_intake incluso. 3 test. Pannello frontend rinviato al GATE A5a (si integra con la matrice; AgentsManager.js ha inoltre lavoro pre-esistente non committato).
- **A6 — `b78bddb` fix(AGENT-13)**: `test_agents_e2e.py` con i 6 flussi canonici (mock smtplib.SMTP, IMAP fixture, LLM monkeypatch): mail_recovery proposta→approvazione→invio; intake valido→proposta→apply-fix reale con audit; intake invalido→reply bozza zero invii; validazione umana→contract_agent via workflow; certification senza side effect; kill switch globale blocca tutto.
- **Verifiche GATE finale eseguite**:
  - Suite completa container: **321 passed** (baseline ondata: 245).
  - Grep bypass: zero chiamate `run_*_agent(` fuori dal dispatch del workflow; `agent_registry`/`BaseAgent`/`registry.py` assenti dal codice applicativo.
  - Zero side effect non approvati: dimostrato dai test A1 (kill switch, no autosend, reply draft, proposta con diff) e dagli e2e A6.
- **Residuo per la dichiarazione finale di conformità: A5a (GATE utente)** — matrice RBAC proposta all'utente; dopo conferma: enforcement ruoli su agents/inbox/sprint7 + pannello system-health in AgentsManager.
- Nessun push (vincolo Ondata 2 invariato).

## 2026-07-15 | ONDATA AGENTI | A5a CHIUSO — ONDATA COMPLETATA, dichiarazione finale

- GATE A5a: matrice RBAC confermata dall'utente ("ok confermo").
- **A5a — `77d2406` fix(AGENT-14)**: enforcement matrice nel middleware `require_role` (`auth.rbac_allowed_roles`) e nelle dipendenze (`require_agents_execute`=ADMIN, `require_agents_write`=OPERATORE+ADMIN, normalize_role per i ruoli legacy). GET piattaforma agenti aperti a tutti i ruoli autenticati; review/inbox=OPERATORE+; run manuale/trigger-poll/imap-test=ADMIN. 53 test matrice (`test_agents_rbac_matrix.py`). Pannello "Stato sistema agenti" in AgentsManager (UI di A5b/A5c). Adottati hunk frontend pre-esistenti (guard anti-doppio-invio; DOMPurify su payload LLM).

### GATE FINALE — verifiche

1. Suite completa container: **374 passed, 0 failed** (baseline inizio ondata: 245).
2. Grep bypass: zero chiamate `run_*_agent(` fuori dal dispatch del workflow (`agent_workflows.run_registered_agent`); `agent_registry`/`BaseAgent`/`registry.py` assenti dal codice applicativo.
3. Zero side effect senza approvazione umana: dimostrato da test A1 (kill switch 12, no-autosend 4, reply draft 4, proposta con diff 11) + e2e A6 (6 flussi, mock SMTP/IMAP/LLM: nessun invio, nessuna scrittura anagrafica, nessuna validazione documento senza azione umana).
4. REMEDIATION_LOG completo: sezioni A1..A6 + GATE A3 e A5a documentati.
5. Build frontend compilata (warning pre-esistente HomeCockpit fuori scope).

### Dichiarazione finale di conformità

**SÌ** — la piattaforma agenti è conforme al flusso canonico
`trigger → AgentRun → AgentSuggestion → [Draft] → revisione umana → AgentReviewAction + audit → stato`,
con zero side effect esterni senza approvazione umana, kill switch globale e per-agente su tutti i trigger, registry unico dichiarativo, layer LLM robusto (retry/schema/fallback/prompt versionati/log senza PII), stato operativo osservabile (system-health, store IMAP condiviso) e RBAC secondo matrice confermata.

**Riserve (fuori scope ondata, già censite):**
- NEW-006: `data_retention_cleanup` resta side effect automatico mitigato dal kill switch — conversione a flusso proposta/approvazione da pianificare.
- Enforcement RBAC dipende da `RBAC_ENFORCE=true` a runtime (attivo da Ondata 1).
- I fix diventano attivi a runtime solo dopo `docker compose restart backend arq_worker` (worktree montato come volume) e rebuild immagine frontend per il pannello.
- Vincoli Ondata 2 invariati: NIENTE push finché la history non è ripulita.
- Nessun push eseguito.

## 2026-07-16 | ONDATA DOMINIO — WAVE 1 | Avvio "Il conto torna" (integrità del calcolo)

- Contesto: audit dominio finanziario COMPLETO (30 finding: 14 🔴, 8 🟠, 6 🟡, 2 🟢), report in `audit/DOMINIO_FINANZIARIO_REPORT.md`. Verdetto: motore di calcolo corretto ma numeri non stabili — non affidabile per rendicontazione. Wave 1 = integrità del calcolo.
- Perimetro Wave 1: W1.1 budget lag (DOM-01, DOM-14, DOM-06) · W1.2 regole percentuali (DOM-05, GATE utente) · W1.3 Decimal ovunque (DOM-11) · W1.4 massimali/budget enforcement (DOM-10) · W1.5 vincoli coerenza strutturali (DOM-02, DOM-21, GATE bonifiche) · W1.6 sblocco multiprogetto (DOM-04).
- Regole di ingaggio: commit atomici `fix(DOM-NN)`, MAI push; test RED→GREEN obbligatorio sui bug di calcolo; suite completa verde a fine punto; migration solo Alembic provate su DB copia; problemi nuovi in `audit/FINDINGS_NUOVI.md`.
- Backup pre-wave creato e verificato: `/app/backups/gestionale_backup_dominio_wave1_pre_20260716_074447.sql.zip.gpg`, `verify_backup_integrity=True`.

## 2026-07-16 | ONDATA DOMINIO W1.1 | Budget lag e atomicità presenze (DOM-01, DOM-14)

- **Diagnosi DOM-01 (confermata nel codice, come da D4 S1-AUTOFLUSH):** sessione di produzione con `autoflush=False` (database.py); `VocePianoFinanziario.aggiorna_da_presenze` modifica `importo_consuntivo` solo in memoria e la SUM SQL immediatamente successiva di `PianoFinanziario.aggiorna_budget_utilizzato` non vede la modifica non flushata → `budget_utilizzato` sistematicamente indietro dell'ultima presenza. Stesso meccanismo su `update_voce_piano` (setattr + SUM senza flush).
- **`c34522a` fix(DOM-01):** `db.flush()` esplicito prima delle SUM in `aggiorna_da_presenze` e `aggiorna_budget_utilizzato` (models.py). Copre tutti i chiamanti (presenze, voci manuali, bulk upsert, collega_assegnazione_a_piano).
- **`cd12859` fix(DOM-14):** create/update/delete presenza in transazione UNICA. Prima: 3-4 commit separati con errori dei ricalcoli degradati a warning (meccanismo di D2 A8). Ora: flush + helper di ricalcolo senza commit (`_recalc_project_progress`, `_recalc_assignment_hours`, `_recalc_voce_e_budget`) + un solo commit; errore = rollback totale, nessun warning-degradation. Wrapper pubblici con commit conservati per i chiamanti esterni (`scripts/recalculate_progress.py`, endpoint ricalcolo voce).
- **Test RED→GREEN (`tests/test_dom01_budget_lag.py`, 6 test):** riprodotto il numero sbagliato PRIMA del fix (budget_utilizzato=0.00 vs 240.00 atteso dopo la prima presenza; 6 failed su config di sessione identica alla produzione). Dopo: sequenza di presenze con totale esatto dopo OGNUNA, modifica 4h→2h, cancellazione, voce manuale, residuo coerente, atomicità (ricalcolo fallito simulato → presenza NON persistita).
- **`21a4f30` test(NEW-008):** rottura pre-esistente scoperta dalla suite completa — il "fix runtime pannello inbox" del 15/07 (hunk non committato, post-gate agenti) faceva fallire `test_imap_resilience.py::test_status_endpoint_reads_shared_store` ('disabled' != 'auth_failed'). Non causato da Wave 1. Test corretto (kill switch espliciti nello scenario), censito in `audit/FINDINGS_NUOVI.md` come NEW-008.
- Staging selettivo: hunk pre-esistente `avviso_pf_id` in `create_piano_finanziario` (crud.py) lasciato fuori dai commit, come da politica worktree.
- Gate di chiusura W1.1: suite completa in container **374 passed, 0 failed** (374 collected, inclusi i 6 nuovi test DOM-01/14; il totale coincide numericamente con la baseline agenti per variazioni di parametrizzazione nei test pre-esistenti del worktree, verificato: nessun test rimosso).
- Nessun push (vincolo invariato).

## 2026-07-16 | ONDATA DOMINIO W1.2 | Regole percentuali (DOM-05) — GATE superato

- **GATE W1.2 presentato e confermato dall'utente** ("Proposta come descritta"): le due regole erano MACROVOCE_LIMITS A≤20/B≤50/C≤30 (Formazienda, alert-only nel riepilogo, committata) vs `validate_sezioni_percentuali` A≥70/C≤20/D≤10 (bloccante 422 su create/update/delete voce, hunk PRE-ESISTENTE NON COMMITTATO, validata post-commit). Inconciliabili sulle stesse chiavi macrovoce: A≥70 appartiene a uno schema in cui A=erogazione (pattern FAPI/Fondimpresa), il template del modulo è Formazienda con A=progettazione. Effetto: piani col template standard (docenza in B) immodificabili via API + corruzione da validazione post-commit (D4 S3.4).
- **Risoluzione implementata:**
  - Eliminata la regola bloccante A≥70 (hunk mai committato scartato: funzione, import e 3 chiamate router `_validate_percentuali_piano`).
  - MACROVOCE_LIMITS resta regola Formazienda **alert-only in costruzione piano**; il blocco vero scatterà alla transizione di stato inviato/rendicontato (Wave 2.2, macchina a stati).
  - Predisposto aggancio per-fondo: `MACROVOCE_LIMITS_BY_FONDO` + `get_macrovoce_limits(tipo_fondo)`; il riepilogo usa i limiti del fondo del piano; fondi non censiti = default Formazienda (nessun cambio di comportamento fino all'estensione tassonomia in Wave 2.3, dove si configureranno le regole FAPI verificate con l'ufficio).
  - DOM-06 si dissolve per il percorso percentuali (non c'è più blocco post-commit); il massimale pre-esistente `_validate_massimale_voce` resta non committato, sarà adottato/esteso in W1.4.
- **Test RED→GREEN (`tests/test_dom05_regole_percentuali.py`, 7 test):** RED riproduce D4 S3.4 esatto (`422: Sezione A fuori limite: 0.00% < 70%` su aggiunta voce a piano solo-docenza); GREEN: create/update/delete voce liberi in costruzione, alert `macrovoce_b_over_limit` presente nel riepilogo, lookup per-fondo, regola A≥70 assente.
- Adottato e ripulito `tests/test_phase_2_4_compliance.py` (file untracked pre-esistente): rimossi i 2 test della regola eliminata, conservati i test validi codice fiscale + llm_privacy.
- Staging selettivo: hunk `avviso_pf_id` (crud.py) di nuovo lasciato fuori.
- Nessun push.

## 2026-07-16 | ONDATA DOMINIO W1.3 | Decimal ovunque (DOM-11)

- **`9487f5f` fix(DOM-11):** regola unica ROUND_HALF_UP a 2 decimali centralizzata in `money_utils.py`; catena di calcolo in Decimal (voci, budget, riepilogo, righe effettive, ricalcoli presenze, listini/preventivi); 43 colonne Float→Numeric a modello (importi 12,2 · tariffe 10,2 · ore 6-8,2 · percentuali economiche 5,2; progress/confidence restano Float); `completed_hours` NOT NULL default 0 + guard sulla property.
- **Migration 054** provata su DB copia `gestionale_w13copy` (dump fresco → restore → upgrade → confronto pre/post riga per riga: **0 differenze inattese, 1 backfill NULL→0 atteso** su assignment 47 → `alembic check` pulito) e poi applicata al DB reale: `alembic current`=054, check pulito, spot check ok (tipo `numeric`, tariffa 1000.00 intatta, completed 0.00). Copia e dump eliminati.
- Backend e arq_worker riavviati (schema e codice devono combaciare a runtime); health OK, log puliti.
- I casi di deriva D3 ora tornano al centesimo: 10,5h×33,33 = **349,97** (prima 349,96); 2,675 → 2,68; 0,1×3 = 0,30 esatto. Test RED→GREEN in `tests/test_dom11_decimal.py` (13 test).
- La suite ha scovato un mix Decimal/float latente in `ListinoVoce.prezzo_finale` + 2 helper prezzi (`calcola_prezzo_finale`, `_calcola_importo_riga`): normalizzati a Decimal con quantizzazione unica (il round(...,4) precedente scriveva comunque su colonne a 2 decimali).
- Gate di chiusura W1.3: suite completa in container **387 passed, 0 failed**.
- Nessun push.

## 2026-07-16 | ONDATA DOMINIO W1.4 | Massimali e budget enforcement (DOM-10) — GATE superato

- **GATE W1.4 presentato e confermato** (4 decisioni): tariffa oltre massimale = BLOCCO · tassonomia tipo_fondo estesa subito (formazienda, fapi) · consuntivo oltre budget su presenze = WARNING mai blocco · preventivo oltre budget = BLOCCO.
- **`297078c` fix(DOM-10):** massimale su assignment create/update (categoria derivata dal ruolo, blocco pre-commit con messaggio); tassonomia estesa (prerequisito: prima 4/4 piani 'altro' → lookup mai match); blocco preventivo>budget su voci e assignment (`_check_budget_preventivo_piano`, budget 0 = non configurato); warning `X-Budget-Warning` + alert danger `budget_superato` nel riepilogo per consuntivo oltre budget; report `GET /piani-finanziari/violazioni-massimali` (violazioni + non verificabili). Adottati hunk pre-esistenti verificati: tetto ore voce (attendances, provato D4 S3.1) e `_validate_massimale_voce` (piani). ValueError su update assignment ora 400 invece di 500.
- **Test RED→GREEN** (`tests/test_dom10_massimali_budget.py`, 12 test): 900 €/h prima accettati (D4 S3.6) ora bloccati; dato legacy 1000 €/h censito dal report.
- Nota: i massimali mordono solo dove esiste la riga in `massimali_fondo` (oggi: fondimpresa 2024). Valori Formazienda/FAPI da inserire quando forniti dall'ufficio; la bonifica `tipo_fondo` dei piani esistenti (B4) passa dal GATE W1.5.
- Gate di chiusura W1.4: suite completa in container **399 passed, 0 failed**.
- Nessun push.

## 2026-07-17 | ONDATA DOMINIO W1.6 | Sblocco multiprogetto (DOM-04) — CHIUSA

- **`f51c96d` fix(DOM-04):** rimosso `check_assignment_overlap` (veto di periodo cross-progetto) e i due blocchi in `create_assignment`/`update_assignment`. Il flusso d'ufficio D4-S4 (stesso docente su 2 progetti/fondi nello stesso mese) ora è possibile. Restano: veto cross-ente (`_validate_assignment_date_overlap_by_ente`, pre-esistente, fuori perimetro DOM-04), anti-overlap ORARIO presenze (`check_attendance_overlap` + constraint DB 055).
- Test: nuovo `test_dom04_multiprogetto.py` (overlap consentito su create/update stesso ente, cross-ente ancora bloccato); `test_assignment_overlap.py` riscritto (via i test del veto rimosso, restano stesso-progetto e range presenza).
- **Punto aperto per GATE FINALE**: il veto cross-ente blocca ancora un docente su progetti di enti attuatori diversi con periodi sovrapposti (dati reali: Next Group srl 3 progetti, PIEMMEI SCARL 2). Regola committata da aprile, non segnalata dall'audit — decisione dominio da confermare al gate.
- Gate di chiusura W1.6: suite completa in container **418 passed, 2 failed, 1 skipped** — i 2 fail NON riguardano il dominio: sono WIP NEW-006 non committato (vedi NEW-009 in `audit/FINDINGS_NUOVI.md`). Perimetro dominio verde.
- **NEW-009 censito**: file untracked `ai_agents/data_retention.py` + `tests/test_data_retention_proposal.py` (creati 16/07 sera, dopo il commit DOM-21, altra sessione — flusso proposta NEW-006 a metà): l'agente `data_retention` registrato nel registry rompe `test_agents_system_health.py::test_system_health_shape` (atteso set di 5 agenti); `test_apply_anonymizes_after_review` fallisce da solo (`sqlite3.OperationalError: no such table: audit_log`, setup test incompleto). Hunk `test_agents_registry_workflow.py` (set con data_retention) fa parte dello stesso WIP. Non toccato.
- Nessun push.

## 2026-07-16 | ONDATA DOMINIO W1.5 | Vincoli strutturali (DOM-02, DOM-21) — CHIUSA

- **`338cd63` fix(DOM-02):** vincoli applicativi in crud: V1 presenza ⊂ date progetto + date obbligatorie, V2 blocco presenze su progetto non-active, V4 guard `assigned_hours ≥ completed_hours` + ricalcolo `ore_totali` da CRUD assignment (DOM-19). Test RED/GREEN `test_dom02_vincoli_strutturali.py`.
- **`3f35a34` fix(DOM-21):** migration 055 `CREATE EXTENSION btree_gist` + `EXCLUDE USING gist (collaborator_id WITH =, tsrange(start_time,end_time) WITH &&)` su attendances + `test_dom21_attendance_exclusion_pg.py` (PG-only). Applicata al DB reale: `alembic current` = 055 (head), constraint `excl_attendances_collaborator_time_overlap` verificato via `pg_constraint`.
- Suite di chiusura verificata insieme a W1.6 (vedi sopra).

## 2026-07-16 | ONDATA DOMINIO W1.5 | Bonifiche — GATE superato ed eseguite

- **GATE W1.5 bonifiche presentato e confermato dall'utente** (4 decisioni): progetto 1 date estese 2025-10-01→2026-04-30 · presenze 1-2 collegate ad assignment 1 · assignment 46 corretta assigned_hours=20 · batch B1/B2/B4/B5 + date piani tutte approvate.
- **Bonifica ESEGUITA**: backup pre-bonifica verificato (`gestionale_backup_dominio_w15_pre_bonifica_20260716_135756.sql.zip.gpg`); script provato su copia `gestionale_w15copy` (censimento post: tutti 0) e applicato al DB reale; ricalcoli applicativi (voci/budget assignment 1 e 46, progress progetti 1 e 11, budget piani). Censimento post su DB reale: **0 violazioni su tutte le classi** (A4, A1, A7, tipo_fondo altro, ore stale). Script conservato in `scripts/bonifiche/2026-07-16_w15_bonifica.sql`. Copia e dump eliminati.
- **RESTA DA FARE (W1.5 codice)**: V1 vincolo presenza ⊂ date progetto + date obbligatorie (app, in crud create/update attendance) · V2 blocco presenze su progetto non-active · V3 già esistente (blocco residuo ore, confermato) · V4 guard `assigned_hours ≥ completed_hours` su update assignment + ricalcolo `ore_totali` progetto anche da CRUD assignment (DOM-19) · V5 migration 055 `CREATE EXTENSION btree_gist` + `EXCLUDE USING gist (collaborator_id WITH =, tsrange(start_time,end_time) WITH &&)` su attendances (0 overlap esistenti, provata su copia prima del reale) + test concorrenza PG-only · test RED/GREEN `test_dom02_vincoli_strutturali.py` · suite completa · commit `fix(DOM-02)`/`fix(DOM-21)`.
- Poi: W1.6 sblocco multiprogetto (DOM-04) e GATE FINALE Wave 1 (scenari D4 1/3/4 su DB copia, query D2, alembic check, dichiarazione).
- Nessun push.

## 2026-07-15 | ATTIVAZIONE RUNTIME AGENTI APPROVATA

- Conformita approvata dall utente e runtime attivato.
- Pre-restart: creato backup DB verificato `gestionale_backup_agent_activation_20260715_20260715_125425.sql.zip.gpg` con `verify_backup_integrity=True`.
- `.env`: `AGENTS_ENABLED=true`; attivi `data_quality`, `mail_recovery`, `contract_agent`, `certification`; disattivi `AGENT_EMAIL_INTAKE_ENABLED=false` e `AGENT_DATA_RETENTION_ENABLED=false`; `ENABLE_WHATSAPP=false`. NEW-006 resta pianificato per Ondata 3 GDPR punto 3.3, mitigato dal kill switch retention.
- `docker-compose.yml`: esportati i kill switch agenti a backend e arq_worker; aggiunti `SECRET_KEY/JWT_SECRET_KEY` ad arq_worker per l import `auth`; `HOME=/tmp` per evitare errore Gunicorn control socket; `AUTO_BACKUP_ENABLED=false` nel solo backend web process, con `backup_scheduler` separato ancora attivo.
- Restart eseguiti: `docker compose restart backend arq_worker`, rebuild frontend (`main.bf731227.js`, warning ESLint preesistente su HomeCockpit), recreate frontend, poi recreate backend/arq_worker dopo allineamento env.
- Fix runtime pannello inbox: se `email_intake` e disabilitato, `/agents/system-health` e `/email-inbox/status` mostrano `Inbox: disconnessa -- Agente email_intake disabilitato da AGENT_EMAIL_INTAKE_ENABLED=false` invece di `unknown`/errore generico.
- Verifiche post-restart: `/health` OK; backend, arq_worker, frontend, backup_scheduler healthy; ARQ cron registrati (`contract_agent` ogni 2h, `certification` 09:00 daily, email_intake/data_retention registrati ma skipped via kill switch); system-health popolato con agenti e inbox disconnessa; LLM Ollama raggiungibile; Redis ARQ reachable queue_depth=0.
- RBAC runtime verificato con utenti temporanei poi rimossi: login admin/operatore/consultazione OK; operatore non esegue agenti (`POST /agents/run` -> 403); admin esegue `data_quality` su collaboratore test id 33 (`run_id=557`, completed, 28 suggestions); operatore vede suggestion e ne revisiona una (`suggestion 625` deferred); resta una suggestion pendente visibile in review (`suggestion 624`).
- Log finali: backend senza ERROR/Traceback nel tail post-fix; ARQ senza Traceback e cron avviati; warning residui `performance_monitor non disponibile` preesistenti/non bloccanti.
- Nessun push eseguito.

## 2026-07-17 | NEW-006 chiuso — data retention solo su proposta revisionata

- data_retention_cleanup non anonimizza e non invia email: esegue il collector puro tramite run_agent_workflow e crea proposte pending deduplicate.
- L apply-fix umano ricontrolla nel DB che la retention sia ancora soddisfatta e solo allora invoca l anonimizzazione GDPR con audit.
- AGENT_DATA_RETENTION_ENABLED=false resta invariato e il runtime non e stato attivato.
- Gate mirato: 28 passed. Suite backend completa: 415 passed, 1 skipped, 0 failed.
- NEW-006 e NEW-009 chiusi. Nessun push eseguito.

## 2026-07-17 | ONDATA ARCHIVIO AVVISI | V2 pipeline ingestione CHIUSA

- Completati AVVISI-02..AVVISI-10: pulizia e segmentazione markdown, storage sorgente/pulito, schemi e prompt LLM versionati, collector puro `avviso_extractor`, orchestrazione stati revisione, apply umano di regole/scadenze validate, endpoint ingest con RBAC/dedup SHA-256 e lista revisioni, directory di staging documentata.
- Il collector non scrive sul DB: `AgentRun` e `AgentSuggestion` sono persistiti esclusivamente da `run_agent_workflow`. La materializzazione richiede sempre un `user_id` umano e produce dati validati tramite `crud_avvisi`.
- Kill switch dedicato: `AGENT_AVVISO_EXTRACTOR_ENABLED`; registry verificato a runtime con `avviso_extractor` presente.
- Nessuna migration necessaria: la pipeline usa lo schema 057 già applicato.
- Gate finale backend: **468 passed, 1 skipped, 0 failed** su 469 test raccolti. Primo run: una sola aspettativa registry obsoleta in system-health, corretta e poi suite completa rieseguita integralmente verde.
- Prossimo punto esclusivamente su autorizzazione: GATE V3 architettura ricerca full-text vs pgvector. V4/V5 non avviate.
- Solo commit atomici locali; nessun push.
# 2026-07-17 — Wave 2.1 timesheet snapshot immutabile CHIUSA

- Implementato snapshot persistente per versione (`timesheet_righe`, totali e conteggio), generazione auditata con utente autenticato e ricostruzione PDF mancante esclusivamente dallo snapshot.
- Rigenerazione vietata con HTTP 409 mentre la versione è bloccata; unlock riservato ad admin/operatore con motivo obbligatorio e attore derivato dal token. Update/delete delle presenze incluse restano bloccati fino all'unlock.
- Frontend aggiornato: rimosso username `admin` hardcoded e richiesta motivazione prima dello sblocco.
- Migration 056 provata su copia `gestionale_w21copy` e poi applicata al reale dopo conferma utente. Backfill legacy: 2 versioni, 3 righe e 24 ore ciascuna; mismatch righe/totali/conteggi = 0. Copia e dump temporanei rimossi.
- Backup pre-migration verificato: `/app/backups/gestionale_backup_timesheet_w21_pre_20260717_091129.sql.zip.gpg` (`verify_backup_integrity=True`).
- Gate finale: Alembic `056 (head)` e check senza drift; 8 test W2.1 passati; suite completa post-migration 423 passed, 1 skipped, 0 failed; build e deploy frontend OK; backend/frontend healthy, `/health` e frontend HTTP 200.
- Riserva non correlata già presente nei log: il record test `codex.runtime.test.20260715@example.invalid` non supera la validazione EmailStr e può causare ResponseValidationError su `GET /api/v1/collaborators/`. Nessuna bonifica dati eseguita in questa Wave.
- Nessun push.

---

## 2026-07-19 | ONDATA UI-FIX | FIX-1…8 completati — GATE v2 NON SUPERATO

- Backup DB reale creato e verificato prima dei fix:
  `gestionale_backup_ui_fix_pre_20260719_103215.sql.zip.gpg`.
- **UI-01** (`cbb255a`): ruoli canonici/legacy, menu, route e azioni centralizzati
  in `frontend/src/auth/permissions.js`; snapshot navigazione admin/operatore/
  consultazione.
- **UI-09** (`396765c`): azioni sensibili allineate al backend e endpoint
  cross-resource protetti; test parametrizzati ruolo×azione.
- **UI-02** (`c63ebdd`): schema piani compatibile con fondi reali e budget in
  sforamento; 4/4 piani del clone apribili.
- **UI-04** (`1e027c1`): normalizzazione numerica PDF; 9/9 assignment e snapshot
  congelati verificati sul clone.
- **UI-15** (`c06ae57`): tutte le card/decisioni Home navigano con filtro; click
  Playwright reali senza errori.
- **UI-16** (`23ad325`): portale magic-token montato prima del login ERP; valido
  e no-token coperti in test e browser.
- **UI-17** (`53e6e39`): stati estrazione `completata/parziale/fallita`, progresso
  sezioni/categorie, scarti e retry mirato. Migration Alembic 059 provata su
  clone e applicata al reale; sei revisioni reali `caricato`, nessun backfill
  inventato.
- **UI-11** (`8058f57`): rimosso il link API hardcoded/non operativo dalla UI.
- Il crawl v2 ha scoperto **UI-20/NEW-019**: Dashboard consultazione chiamava
  reporting timesheet admin-only. Corretto in `6065fe5` con test ruolo×chiamata;
  nuovo crawl integrale: 3/3 ruoli autenticati, menu 18/17/16, 0 errori console,
  0 errori network, 0 spinner.
- UI-3: 123 test d'integrazione verdi; clone 4/4 piani, 9/9 PDF e snapshot 1/1;
  card Home e decisione 5/5 destinazioni corrette.
- Gate finali: backend **578 passed, 3 skipped, 0 failed** su 581; frontend
  **96 passed, 0 failed**, 3 snapshot; build production riuscita; Alembic
  `059 (head)`; stack reale healthy.
- Report completo prima/dopo: `audit/UI_VERIFICA_REPORT.md`, sezione GATE UI v2.
- **Verdetto: GATE UI v2 NON SUPERATO. TUTTE LE PAGINE COLLEGATE E FUNZIONANTI:
  NO.** Le pagine esistenti sono pulite, ma il protocollo comprende ancora:
  piano da template assente (B4), catena contratto senza una singola prova E2E
  fino alla generazione, ricerca archivio con citazioni assente (L1).
- NEW-020 censisce il health check non portabile su hostname pubblico.
- Ondata M resta congelata; nessun push.

---
# 2026-07-17 — ONDATA ARCHIVIO AVVISI | V1 design gate

## 2026-07-17 — Stabilizzazione post-V1
- W2.1 salvata nel commit atomico `70104d9`; NEW-006 salvata separatamente in `2c8de57`. Nessun push.
- Test mirati rispettivamente 8/8 e 28/28; suite complessiva finale 434 passed, 1 skipped.
- Backup verificato prima della bonifica DB: `/app/backups/gestionale_backup_pre_fix_test_email_20260717_101807.sql.zip.gpg`.
- Corretto il solo record test collaboratore id 33 sostituendo il dominio email riservato `.invalid` con `example.com`.
- NEW-010 bonificato solo nel caso certo: piano 1 → avviso 2/revisione 1. Piani 2, 4 e 7 restano sospesi per verifica umana, senza inferenze automatiche.
- Dopo autorizzazione, corretto anche il caso documentato dal nome del piano: progetto 5 `poppi` e piano 4 → FAPI 4/2025, avviso 5/revisione 5. Operazione transazionale preceduta da backup verificato `gestionale_backup_pre_new010_piano4_20260717_102714.sql.zip.gpg`.
- Piani 2 e 7 restano nulli: il primo ha dati contraddittori, il secondo non identifica il numero dell'avviso.
- Igiene worktree completata con mappa `audit/WORKTREE_CLASSIFICATION_2026-07-17.md`: 6 gruppi applicativi indipendenti, documentazione storica e artefatti locali separati. Gate mirato 38 passed, Compose config valido, frontend build riuscita. Nessuna cancellazione o inclusione automatica di artefatti sensibili.
- Hardening runtime attivato con rebuild/recreate backend, worker e frontend: container healthy, health backend/frontend 200, frontend non-root su 8080 interno, Alembic 057 senza drift e log ARQ puliti. DB e Redis non esposti sull'host; backup scheduler separato invariato.
- Pulizia locale eseguita in modo recuperabile: chiave OpenSSH accidentale, relativa pubblica, due `.bak` e due backup `.env` spostati fuori repo in `/DATA/progetti/pythonpro-local-archive/2026-07-17_worktree_cleanup`, con directory `0700` e file `0600`. Nessuna cancellazione e nessun push.
- Applicata conservazione audit mista: report finali generale e dominio finanziario versionati; 28 evidenze grezze/intermedie archiviate fuori Git in `/DATA/progetti/pythonpro-local-archive/2026-07-17_audit_raw` con permessi restrittivi. Nessuna cancellazione.

## Stato allo stop richiesto dall'utente
- Migration 057 applicata al reale: head e Alembic check puliti; invarianti backfill senza mismatch.
- Runtime backend/worker healthy e test V1 post-migration 11 passed.
- Suite completa post-migration interrotta su richiesta circa al 58%, senza failure fino a quel punto; da rieseguire integralmente per chiudere il gate V1.
- Nessun push.

## V1 implementata dopo approvazione del GATE
- Modello versionato completo, schemi e CRUD con separazione proposta/validazione umana e provenienza verificabile.
- Migration 057 provata su copia con upgrade/downgrade/re-upgrade; DB reale non modificato.
- Backfill copia: 6 avvisi/revisioni e 4 progetti; 0 piani, senza inferenze per la discordanza censita come NEW-010.
- Gate: 11 test V1; suite completa **434 passed, 1 skipped**.
- Backup verificato: `/app/backups/gestionale_backup_archivio_avvisi_v1_pre_20260717_094933.sql.zip.gpg`.
- Pendente autorizzazione esplicita per la 057 reale. Nessun push.

- Letti stato e remediation; svolta analisi read-only del modello esistente con prospettive architettura, dominio fondi e QA.
- Confermato che `avvisi`, `projects.avviso_id` e `piani_finanziari.avviso_pf_id` esistono già e vanno evoluti in modo additivo.
- Rilevato che il vero `PianoFinanziarioTemplate` non esiste più (rimosso dalla migration 043) e che non esiste una Agenda generica; nessuna inferenza distruttiva o falsa integrazione effettuata.
- Definito modello proposto basato su identità Avviso stabile, revisioni immutabili, provenienza puntuale, regole/scadenze revisionate, conoscenza ed esiti normalizzati, applicazione umana atomica via flusso AgentRun/AgentSuggestion.
- Nessuna migration, modifica applicativa, commit o push eseguiti prima del GATE V1.

## 2026-07-17 | ONDATA ARCHIVIO AVVISI | V1 CHIUSA — gate post-migration completato

- Suite completa post-migration rieseguita integralmente: **434 passed, 1 skipped, 0 failed** (435 raccolti, 5m36s), identica alla baseline pre-migration 434 passed / 1 skipped.
- Verifiche runtime su finestra post-riavvio: Alembic `057 (head)`, nessun drift; backend, arq_worker, frontend, db, redis tutti healthy; `/healthz` HTTP 200; log ARQ senza errori.
- Unico errore nei log backend: riserva nota non correlata a V1 — il record test `codex.runtime.test.20260715@example.invalid` provoca ResponseValidationError su `GET /api/v1/collaborators/` (~828 errori/ora per polling frontend). Bonifica dati NON eseguita: richiede gate utente.
- NEW-010 resta aperto: 0 piani collegati ad avviso, nessun intervento automatico sui piani (bonifica umana).
- Commit V1: `440cee4 feat(AVVISI-01): introduce modello dati archivio versionato`.
- **V1 dichiarata CHIUSA.** Prossimo punto: V2 pipeline di ingestione, previa autorizzazione. Nessun push.

## 2026-07-17 | NEW-010 CHIUSO + archiviazione script initdb sperimentale

- **NEW-010 bonifica finale** (decisioni utente al gate): piano 2 → Formazienda 2/2025 (avviso 1, rev. 2, ente/tipo_fondo allineati); piano 7 + progetto 11 MAXI COMMUNICATION → FAPI 2/2025 (avviso 6, rev. 6). Backup pre-bonifica verificato `gestionale_backup_manual_new010_pre_bonifica_20260717_105546.sql.zip.gpg`; script transazionale con guardie di stato atteso e censimento post in `scripts/bonifiche/2026-07-17_new010_bonifica.sql`; post: 0 anomalie, 0 mismatch fondo piano/avviso. NEW-010 chiuso.
- **Script `docker-entrypoint-initdb.d/010_create_app_user.sh`** (esperimento least-privilege del 29/05, mai montato in docker-compose, `.env` con `DB_APP_USER=admin` quindi inefficace anche se eseguito): archiviato in `/DATA/progetti/pythonpro-local-archive/2026-07-17_initdb_experiment/` (0700/0600). Il DB reale resta con solo ruolo `admin` superuser: il passaggio a utente applicativo dedicato è backlog hardening (richiede strategia grants + DDL per Alembic), non attività di questa ondata.
- Worktree ora pulito. Nessun push.

## 2026-07-18 | ONDATA S | S6 CHIUSO — GATE ONDATA SUPERATO

- **`ccebe9e` fix(S6):** eliminato lo script schema manuale già assorbito da
  Alembic; rimossa la costante morta del contract agent; backfill FAPI spostato
  sull'import canonico; eliminati tre shim parser; `CLAUDE.md` corretto come ERP
  per formazione finanziata italiana.
- **`6f77534` fix(S6):** spostati gli 8 `backend/test_*.py` dormienti sotto
  `backend/tests/`; aggiornate esclusivamente fixture SQLite, autenticazione/RBAC,
  date progetto e aspettativa backup cifrato. Produzione invariata. Gate legacy:
  **36 passed, 2 skipped, 0 failed** su 38.
- **`b335d1d` fix(S6):** `backend/requirements.txt` è la sola fonte dipendenze,
  con versioni esatte allineate al runtime; rimossi `requirements_local.txt`,
  `requirements_simple.txt` e la duplicazione da `pyproject.toml`.
- Verifiche: test mirati S5/S6 verdi; `docker compose config --quiet` valido;
  build backend e ARQ worker riuscita; immagini nuove create il 2026-07-18;
  `pip check` pulito; import `main`/`arq_worker` OK.
- Gate finale: **532 raccolti, 530 passed, 2 skipped, 0 failed**; cache
  `lastfailed={}`. I due skip sono il monitor performance legacy non disponibile,
  censito come NEW-013.
- Alembic: `057 (head)`, `alembic check` → `No new upgrade operations detected`.
- Ondata S dichiarata **CHIUSA**. Prossimo punto: V5, ingestione dei quattro avvisi
  reali. Nessun push; worktree separata `.worktrees/email-agent` preservata.

## 2026-07-18 | ONDATA V5 | Riparazione upload UI e disattivazione avvisi

- Diagnosi su tentativo reale Formazienda: `GET /avvisi/{id}/revisioni` falliva
  con `ResponseValidationError` sulle revisioni legacy prive di sorgente, generando
  nel browser un apparente errore CORS; `POST .../ingest` arrivava invece come
  `application/json`, quindi FastAPI rispondeva 422 per `file` e `titolo` mancanti.
- **`70713f1` fix(V5):** schema read tollera i soli campi sorgente nulli delle
  revisioni V1 legacy, mentre lo schema create resta rigoroso; upload frontend
  inviato esplicitamente multipart; test regressione backend/frontend aggiunti.
- **`03457e1` fix(V5):** aggiunto in Archivio Risorse il comando “Disattiva avviso”
  con conferma esplicita. Operazione logica (`is_active=false`), storico intatto,
  liste operative solo attive; DELETE protetta per Admin/Manager anche lato API.
- Gate mirati finali: backend V2 API 7 passed; frontend ResourceArchive/apiService
  5 passed. Build e recreate backend/frontend riusciti; entrambi healthy; health API
  e pagina `/resources` HTTP 200.
- Verifica read-only DB: Formazienda 2/2025 = ID 1 attivo; omonimo FAPI 2/2025 =
  ID 6 attivo. Nessuna disattivazione automatica eseguita.

---

## 2026-07-18 | ONDATA V5 | Cancellazione definitiva protetta degli avvisi

- **`d7e710f` fix(V5):** aggiunto hard-delete riservato esclusivamente al ruolo
  Admin. La UI richiede due azioni distinte: conferma dell'anteprima di impatto e
  digitazione della frase esatta `ELIMINA <ENTE> <CODICE>`.
- L'anteprima elenca progetti, piani finanziari e nomi di revisioni/documenti che
  risultano collegati. Progetti e piani non vengono cancellati: le FK verso avviso e
  revisione sono azzerate nella stessa transazione.
- La cancellazione rimuove avviso, revisioni, regole, scadenze, documenti,
  conoscenza, esiti e file sorgente confinati sotto la upload root. AgentRun e
  AgentSuggestion sono conservati con riferimento entità azzerato; SecurityAuditLog
  registra `avviso_hard_delete` con snapshot redatto dal writer audit canonico.
- Verifica distruttiva eseguita solo su clone PostgreSQL temporaneo del DB reale:
  Formazienda 2/2025 ID 1 eliminato nel clone; progetto 2 `pinco` e piano 2 rimasti
  presenti e scollegati; audit presente. Upload root sostituita con directory isolata
  durante la prova. Database clone eliminato al termine.
- **`c9ce6fd` fix(V5):** l'archivio Admin include anche i record disattivati e li
  evidenzia esplicitamente; il pulsante di disattivazione risulta bloccato, mentre
  l'hard-delete resta accessibile. Manager e altri ruoli mantengono la lista active-only.
- Gate: backend V2 API **8 passed**; frontend ResourceArchive/apiService **9 passed**.
  Build e recreate backend/frontend riusciti; backend healthy, `/health` HTTP 200 e
  frontend HTTP 200. Nessun hard-delete applicato al database reale.

---

## 2026-07-19 | ONDATA UI | UI-1…UI-4 completati — GATE NON SUPERATO

- Completati censimento route/componenti/API, runtime sui ruoli, otto flussi
  trasversali e report finale `audit/UI_VERIFICA_REPORT.md`.
- Esito dichiarato: **TUTTE LE PAGINE COLLEGATE E FUNZIONANTI: NO**. I ruoli
  canonici `operatore` e `consultazione` non entrano nel frontend; restano inoltre
  rotti piani finanziari, alcuni PDF timesheet, azioni Cockpit e portale allievi.
- UI-3 su clone: massimale docenza provato (101 contro limite 100 → 422; 100 →
  201); apply umano di una suggestion strutturata → `implemented` con effetto
  visibile; estrazione Ollama ripetuta con rete corretta → 6 proposte, 1/5 gruppi
  in timeout e una data non ISO scartata.
- Fix piccoli chiusi: `4b226d6` UI-03 alias `/api/v1` per assegnazione
  collaboratore↔progetto; `c9b9059` UI-19 riallineamento test frontend.
- Finding ombrello: NEW-018. UI-10 non confermato: hard-delete correttamente
  renderizzato soltanto agli admin.
- Gate tecnici: backend completo **569 passed, 3 skipped, 0 failed** su 572;
  frontend **54 passed, 0 failed**; build production completata con warning non
  bloccanti.
- Teardown clone completato: rimosso `pythonpro_backend_uiverifica` con i volumi
  anonimi e droppato `gestionale_ui_verifica`; stack reale rimasto healthy e
  `/health` HTTP 200.
- Ondata M **NON AVVIATA**. CRM e “Chiedi all'archivio” non esistono ancora;
  il manuale resta fermo finché i blocker UI non vengono decisi e corretti.
- Nessun push.

---

## 2026-07-21 — Ondata UI-COMPLETAMENTO (E2 → E1 → E3 → GATE UI v3)

Ripresa dopo interruzione post-E2.1. Team subagent (QA e2e, frontend, backend,
data engineer, UX reviewer). Piano: `docs/superpowers/plans/2026-07-19-ui-completamento.md`.
Ledger: `.superpowers/sdd/progress.md`. Commit atomici locali, **nessun push**.

**Fase E2 — catena contratto (GATE superato):**
- E2.1 test E2E fino al PDF (`3274988`); review R0 APPROVE-CON-FIX.
- Fix reali: NEW-021 accept non-collaborator (`2039703`), NEW-022 RBAC
  contratto (`7f6b170`), NEW-023 guardia stato accept (`78d40a3`), matrice
  RBAC frontend `/contract` (`20c35e5`), NEW-027 doc scaduto (`fa75b30`),
  NEW-028 isolamento rate limiter (`137fecd`); E2.2 test negativi (`ad256cc`).
- Sweep RBAC R1 su 12 endpoint file/export: NEW-024 PDF timesheet (`b107046`),
  NEW-025 allegato email (`beeb22c`), test parametrizzato (`2bb0468`).
  NEW-026 export CSV massivo: resta admin-only per decisione utente (`1021d31`).

**Fase E1 — piano da template (GATE confermato dall'utente):**
- Modello `PianoFinanziarioTemplate` + migration 060 + bonifica relitti
  (`937ef24`, `dc7ff31`); seed 3 template reali (`3d5c822`); massimali con
  precedenza regola avviso (`ccc6a92`); endpoint (`e1b6927`); wizard UI + fix
  UX review (`9ecb5bf`, `e207650`). Fix decisi dall'utente: NEW-033/034 API
  espone voce_codice/macrovoce/anno (`e89c970`), NEW-032 ereditarietà avviso
  esplicitata in UI (`20163b7`). Demo GATE E1 su clone: enforcement 422 "Art.
  12", DB reale intatto. Finding: NEW-029/031/032…035.

**Fase E3 — Chiedi all'archivio (GATE dimostrato):**
- FTS dialect-aware + migration 061 (`24b1402`); endpoint search/chiedi con
  onestà non negoziabile + RBAC 3 ruoli (`9f94598`, `3bd68f4`); UI 3 stati
  (`b6ece41`); report gate con verifica empirica (`5620825`,
  `audit/E3_GATE_REPORT.md`). NEW-036: corpus produzione vuoto; pgvector
  raccomandato (non implementato).

**GATE UI v3 — SUPERATO** (codice/suite/demo su clone): matrice pagina×ruolo
20/19/18, flussi 1–8 tutti OK (le 3 eccezioni v2 chiuse), report v3 in
`audit/UI_VERIFICA_REPORT.md`. Gate tecnici: backend **725 passed, 5 skipped**;
frontend **123 passed**; build verde; Alembic head **061**.

- Ondata M **NON AVVIATA**: attende decisione utente al GATE v3 e attivazione
  runtime (rebuild+redeploy+restart) per il crawl live di conferma.
- Nessun push.

---
## 2026-07-31 | DATE-1 | Regole durata avviso — GATE aperto

- Verificati STATUS, findings, B2, ultimi 15 commit, schema live 070 e dati
  reali prima delle modifiche.
- Backup cifrato fresco verificato:
  `gestionale_backup_pre_date1_20260731_140410.sql.zip.gpg`, SHA-256
  `a754cd0beebf21c0ad1ad1208cf1af206307cc315340de8de3487bfbe16f1c58`.
- UX-5 esistente è incompleto rispetto al nuovo dominio: termini liberi,
  nessuna sottoscrizione, provenienza, calcolo o proroga. PRJ-2 non iniziato.
- Esteso il valore JSONB `AvvisoRegola` con `durata_termine` schema v2, domini
  chiusi e fonti obbligatorie; formati v1 invariati.
- Estrattore gestione aggiornato per proporre ancoraggio/durata/unità in forma
  strutturata, senza deduzioni silenziose. Correzione umana sottoposta allo
  stesso schema per impedire bypass prima della validazione.
- RED→GREEN documentato in `audit/DATE_PROGETTO_REPORT.md`; regressione avvisi
  35/35 e smoke B2 mirato verdi.
- Nessuna migration, deploy o modifica dati. Stop al GATE DATE-1 in attesa di
  conferma utente.

### Addendum confutazione DATE-1

- Gate struttura confermato dall'utente.
- Confutatore indipendente inizialmente **NO-OK**: durata strutturata invalida
  degradata a testo applicabile, regressione delle sottocategorie
  delega/variazioni nel formato richiesto al modello e approvazione di JSONB
  persistito senza rivalidazione.
- Correzione RED→GREEN: durata invalida scartata senza suggestion/autofix;
  applicazione payload invalido atomica con zero regole create; formato prompt
  completo; ogni approvazione rivalida contratto e metadati correnti.
- Verifiche: test mirati 4/4, suite Avvisi 38/38, verifica indipendente
  Avvisi+B2 49/49. Verdetto finale confutatore **OK**, nessun blocker residuo.
  DATE-2 autorizzato con vincolo fail-closed sulle regole multiple ambigue.
