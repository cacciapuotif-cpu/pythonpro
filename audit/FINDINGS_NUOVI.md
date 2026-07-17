# Finding nuovi emersi durante remediation

## 2026-07-05 | NEW-001 | Backup encryption key non propagata ai container

- Area: segreti / backup runtime
- Severita stimata: alta
- Emerso durante: Ondata 1, punto 1.1 segreti/credenziali
- Descrizione: `BACKUP_ENCRYPTION_KEY` era presente in `.env` e usata da `backend/backup_manager.py`, ma `docker-compose.yml` non la passava esplicitamente ai container backend/backup scheduler.
- Impatto: backup manuali/schedulati potevano fallire o non usare la chiave runtime attesa dopo rotazione.
- Stato: corretto nello stesso intervento SEC-01/GDPR-04 perche necessario a rendere effettiva la rotazione della chiave backup.

## 2026-07-05 | NEW-002 | Volume backup non scrivibile dopo recreate container

- Area: backup runtime / continuita operativa
- Severita stimata: alta
- Emerso durante: Ondata 1, punto 4 RBAC enforcement
- Descrizione: un backup di emergency shutdown falliva con `Permission denied` su `/app/backups/...`; il volume era `0755` con owner `999:1000` mentre l'app gira come `1000:999`.
- Impatto: backup manuali o schedulati potevano fallire in modo silenzioso dopo recreate dei container.
- Cause correlate: home GPG runtime non inizializzata per `appuser`; immagine `backup_scheduler` non ricreata con `gpg` disponibile.
- Fix applicato: owner live volume corretto a `1000:999`, permessi `0775`; cifratura/decifratura backup usa una GNUPGHOME temporanea sicura; ricreate immagini/container backend e backup scheduler.
- Verifica: backup manuale e backup scheduler creati come `.sql.zip.gpg` e verificati con `verify_backup_integrity(...) == True`.
- Stato: corretto nello stesso intervento prima dell'enforcement RBAC reale.


## 2026-07-05 | NEW-003 | Catena Alembic greenfield non completa

- Area: database / deploy governance
- Severita stimata: alta
- Emerso durante: Ondata 1, punto 6 allineamento schema/Alembic
- Descrizione: la catena Alembic da DB vuoto arriva a head ma non produce uno schema completo rispetto al runtime storico; alcune colonne storicamente aggiunte fuori migration, ad esempio `projects.avviso`, richiedono migration difensive o baseline.
- Impatto: un deploy greenfield o restore strutturale da sole migration puo' risultare incompleto anche se il DB live e' allineato e `alembic check` e' pulito.
- Stato: non corretto in Ondata 1; da pianificare in Ondata 2 con baseline migration o consolidamento controllato della catena.

## 2026-07-05 | NEW-004 | Residui npm moderate/low richiedono uscita da react-scripts

- Area: dipendenze frontend / toolchain
- Severita stimata: media
- Emerso durante: Ondata 1, punto 7 dipendenze
- Descrizione: dopo il fix SEC-08, `npm audit` reale segnala ancora 2 moderate e 9 low, tutte nella catena dev/tooling `react-scripts` -> Jest/jsdom/webpack-dev-server/http-proxy-agent/@tootallnate/once.
- Stato audit: `critical=0`, `high=0`, `moderate=2`, `low=9`.
- Fixability: non fixabile in modo minimale senza major/breaking upgrade o migrazione toolchain (es. uscita da CRA/react-scripts verso stack mantenuto). `npm audit fix` propone una risoluzione major/non sicura (`react-scripts` 0.0.0) e quindi non e' stata applicata in Ondata 1.
- Impatto: residuo principalmente dev-server/test tooling; la build production e' riuscita. Resta debito da pianificare in Ondata 2.

## 2026-07-15 | NEW-005 | Endpoint apply-fix fittizio: marcava "implemented" senza applicare nulla

- Area: piattaforma agenti / integrita' del flusso di revisione
- Severita stimata: alta
- Emerso durante: ONDATA AGENTI, punto A1 (task A1.4)
- Descrizione: `POST /api/v1/agents/suggestions/{id}/apply-fix` non applicava alcuna modifica: creava una `AgentReviewAction` con `result_success=True` e marcava la suggestion "implemented" limitandosi a fare eco del payload. L'operatore riceveva conferma di un'applicazione mai avvenuta.
- Impatto: falso senso di completamento; dati proposti dagli agenti mai realmente applicati; audit trail fuorviante (`auto_fix_applied=True` su azione inesistente).
- Stato: corretto in AGENT-04 — `services/agent_apply_service.py` applica davvero il diff con whitelist campi per entity_type, ricontrollo dei valori attuali (skip campi stantii) e `AuditLog` per campo; payload non strutturati vengono rifiutati con 400 invece di essere "confermati".

## 2026-07-15 | NEW-006 | data_retention_cleanup: anonimizzazione e invio email automatici fuori dal flusso agenti

- Area: piattaforma agenti / side effect non revisionati
- Severita stimata: alta
- Emerso durante: ONDATA AGENTI, censimento trigger (A1.1)
- Descrizione: il cron ARQ `data_retention_cleanup` (pre-esistente, untracked in `arq_worker.py`) anonimizza collaboratori e invia una email di report automaticamente ogni domenica alle 03:00, senza AgentRun/AgentSuggestion ne' revisione umana.
- Impatto: modifica irreversibile di dati personali e invio email fuori dal flusso canonico trigger -> proposta -> approvazione.
- Mitigazione: in AGENT-01 il job e' stato messo dietro kill switch globale (`agents_enabled()`).
- Stato: **chiuso il 2026-07-17** — collector puro `data_retention`, cron via `run_agent_workflow`, `AgentSuggestion` pending deduplicata e anonimizzazione solo dopo apply-fix umano con ricontrollo della retention. Nessuna email automatica. Kill switch `AGENT_DATA_RETENTION_ENABLED=false` mantenuto.

## 2026-07-15 | NEW-007 | /email-inbox/status legge stato in-process: dato stantio cross-process

- Area: piattaforma agenti / osservabilita' inbox IMAP
- Severita stimata: media
- Emerso durante: ONDATA AGENTI, analisi A2.3
- Descrizione: `GET /api/v1/email-inbox/status` legge `_WORKER_STATUS`, un dict in-process di `services/email_inbox_worker.py`. Il polling reale gira nel processo worker ARQ: il backend API risponde con uno stato che non viene mai aggiornato (sempre "mai eseguito"/vuoto).
- Impatto: dashboard e operatori vedono uno stato inbox non veritiero; errori IMAP (es. credenziali scadute) invisibili dal backend.
- Stato: chiuso in AGENT-08 (`eff29b7`) — `services/inbox_status_store.py` condivide lo stato su Redis (fallback in-memory), `/status` legge lo store, backoff esponenziale sugli errori di login e `POST /email-inbox/imap/test` (admin) per la verifica manuale senza esporre credenziali.

## 2026-07-16 | NEW-008 | Suite rotta dal fix runtime pannello inbox post-gate (hunk non committato)

- Area: piattaforma agenti / igiene worktree
- Severita stimata: media
- Emerso durante: ONDATA DOMINIO Wave 1, suite completa di chiusura W1.1
- Descrizione: il "fix runtime pannello inbox" applicato durante l'attivazione runtime agenti del 2026-07-15 (dopo il GATE finale a 374 passed) ha modificato `services/email_inbox_worker.get_worker_status` e `services/inbox_status_store.status_message` nel worktree SENZA commit e senza rieseguire la suite: con kill switch email_intake spento lo status endpoint risponde `disabled` e `test_imap_resilience.py::test_status_endpoint_reads_shared_store` fallisce (`'disabled' != 'auth_failed'`).
- Impatto: baseline suite non più verde (373/374); il fallimento maschera regressioni vere nelle ondate successive.
- Fix applicato (Wave 1, fuori perimetro ma necessario per i gate): il test abilita esplicitamente i kill switch (`AGENTS_ENABLED=true`, `AGENT_EMAIL_INTAKE_ENABLED=true`) — testa lo store condiviso, non il kill switch; passa sia con l'hunk pre-esistente sia a HEAD pulito.
- Residuo: gli hunk runtime di `email_inbox_worker.py`/`inbox_status_store.py` restano non committati (adozione da valutare nel filone agenti, non nel filone dominio).

## 2026-07-17 | NEW-009 | Suite rossa da WIP NEW-006 non committato (flusso proposta data_retention)

- Area: piattaforma agenti / igiene worktree
- Severita stimata: media
- Emerso durante: ONDATA DOMINIO Wave 1, suite completa di chiusura W1.6
- Descrizione: file untracked `ai_agents/data_retention.py` e `tests/test_data_retention_proposal.py` (creati 16/07 ~20:55, dopo il commit DOM-21, in altra sessione) implementano a metà il flusso proposta per NEW-006. Effetti: (1) l'agente `data_retention` registrato nel registry rompe `test_agents_system_health.py::test_system_health_shape` (set atteso di 5 agenti, ne trova 6); (2) `test_apply_anonymizes_after_review` fallisce da solo con `sqlite3.OperationalError: no such table: audit_log` (setup del test incompleto). Include anche hunk non committato su `test_agents_registry_workflow.py` (set esteso con data_retention).
- Impatto: suite completa 418 passed / 2 failed — baseline non verde; i 2 fail mascherano regressioni vere nelle ondate successive.
- Stato: **chiuso il 2026-07-17** — fixture SQLite completato con `SecurityAuditLog`, health allineato al registry, aggiunto test cron proposal-only/no-email. Gate mirato 28 passed; suite completa 415 passed, 1 skipped, 0 failed.

## 2026-07-17 | NEW-010 | Collegamenti avviso dei piani assenti e metadati discordanti

- Area: archivio avvisi / dominio finanziario / qualità dati
- Severità stimata: media
- Emerso durante: ONDATA ARCHIVIO AVVISI, V1 e prova migration 057 su copia
- Descrizione: nel DB 4 piani su 4 hanno `avviso_pf_id` nullo; alcuni metadati testuali del piano indicano inoltre un fondo diverso dall'avviso collegato direttamente al progetto.
- Impatto: un backfill dedotto dal progetto o dal testo potrebbe associare al piano regole normative errate.
- Decisione: la migration 057 valorizza la revisione del piano solo quando `avviso_pf_id` è già presente; non esegue inferenze. Nello stato attuale i piani restano scollegati.
- Stato: **chiuso il 2026-07-17**.
- Aggiornamento 2026-07-17: piano 1 collegato a Formazienda 2/2022; progetto 5 e piano 4 corretti a FAPI 4/2025 dopo conferma. Restano aperti piano 2 (contraddizione FAPI/Formazienda) e piano 7 (avviso non identificato).
- Chiusura 2026-07-17: dopo decisione utente, piano 2 collegato a Formazienda 2/2025 (avviso 1, rev. 2) con ente/tipo_fondo allineati; piano 7 e progetto 11 MAXI COMMUNICATION collegati a FAPI 2/2025 (avviso 6, rev. 6). Script con guardie e censimento post in `scripts/bonifiche/2026-07-17_new010_bonifica.sql`; backup pre-bonifica verificato `gestionale_backup_manual_new010_pre_bonifica_20260717_105546.sql.zip.gpg`; censimenti post = 0 anomalie, 0 mismatch fondo.
