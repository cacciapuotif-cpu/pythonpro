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

## 2026-07-17 | NEW-011 | Secondo audit store legacy senza redazione e retention

- Area: sicurezza / GDPR / audit trail
- Severità stimata: alta
- Emerso durante: ONDATA S, punto S2
- Descrizione: oltre a `SecurityAuditLog` (`audit_log`) esiste `AuditLog` (`audit_logs`), append-only ma privo di redazione e retention. Alcuni apply agentici possono serializzare in `old_value/new_value` campi personali raw, incluso il codice fiscale.
- Impatto: il secondo store può diventare un archivio indefinito di PII non governato, nonostante la bonifica S2 sul security audit log.
- Decisione: non allargare silenziosamente S2, che richiede esplicitamente `SecurityAuditLog`; pianificare convergenza dei due audit store o applicare allo store legacy una policy coerente preservando l'append-only.
- Stato: aperto.

## 2026-07-17 | NEW-012 | Credenziali development deboli in worktree separata

- Area: segreti / igiene worktree
- Severità stimata: bassa
- Emerso durante: ONDATA S, punto S3
- Descrizione: la worktree separata `.worktrees/email-agent` conserva nel proprio `.env.development` i valori legacy `dev_password_123` e `dev_redis_123`. La worktree ha modifiche preesistenti e non è stata alterata.
- Impatto: nessun riuso rilevato nel runtime o nei file tracciati del branch corrente; resta rischio di copia-incolla se quella worktree viene riutilizzata.
- Mitigazione S3: branch corrente convertito a `.env.development.sample` con placeholder espliciti e controllo automatico; tutti i container runtime verificati puliti.
- Stato: aperto; bonificare o rimuovere la worktree solo nel suo filone, preservando le modifiche presenti.

## 2026-07-18 | NEW-013 | Monitor performance legacy non disponibile nel runtime

- Area: osservabilità / dipendenze backend
- Severità stimata: bassa
- Emerso durante: Ondata S, punto S6, attivazione test legacy
- Descrizione: `performance_monitor.py`, `monitoring.py` e `metrics_endpoint.py`
  dipendono da `psutil` e, per le metriche, dai pacchetti Prometheus; tali pacchetti
  non sono presenti nel runtime healthy corrente. L'app degrada esplicitamente con
  warning e i due test legacy di performance risultano skipped.
- Impatto: API principali, worker e suite applicativa restano operativi, ma il
  monitor performance legacy e le relative metriche non sono disponibili.
- Decisione S6: non introdurre nuove dipendenze fuori dallo stato runtime durante
  l'unificazione; `requirements.txt` replica in modo esatto il runtime verificato.
- Stato: aperto; decidere se riattivare e mantenere questo monitor oppure rimuovere
  il sottosistema legacy in Ondata F.

## 2026-07-18 | NEW-014 | Unicità playbook generico con ente nullo

- Area: attività predittive / PostgreSQL
- Severità stimata: bassa
- Emerso durante: confutazione finale ATT-07
- Descrizione: il vincolo univoco composto include `ente_erogatore`; PostgreSQL
  consente più righe con gli altri campi uguali quando tale colonna è `NULL`.
- Impatto: playbook generici duplicati renderebbero ambigua una selezione `.first()`.
- Stato: aperto; valutare indice univoco `NULLS NOT DISTINCT` o indice parziale.

## 2026-07-18 | NEW-015 | Apply e audit agentico non atomici

- Area: agenti / consistenza transazionale
- Severità stimata: media
- Emerso durante: confutazione finale ATT-07
- Descrizione: materializzazione, aggiornamento suggestion e review/audit possono
  eseguire commit separati; un errore tardivo può lasciare il side effect senza
  stato/audit finale coerente.
- Stato: aperto; racchiudere apply e registrazione review in una transazione unica.

## 2026-07-18 | NEW-016 | PATCH attività non azzera i campi opzionali

- Area: attività predittive / API
- Severità stimata: bassa
- Emerso durante: confutazione finale ATT-07
- Descrizione: `None` è interpretato come campo non aggiornato, quindi deadline,
  assegnatario e note non possono essere esplicitamente rimossi via PATCH.
- Stato: aperto; distinguere campo assente da `null` esplicito.

## 2026-07-18 | NEW-017 | Carry-forward non propaga il flag review

- Area: attività predittive / versionamento playbook
- Severità stimata: bassa
- Emerso durante: confutazione finale ATT-07
- Descrizione: la copia delle voci nella nuova versione non conserva
  `needs_careful_review`, perdendo un segnale editoriale della versione precedente.
- Stato: aperto; includere il flag nella clonazione delle voci.

## 2026-07-19 | NEW-018 | GATE UI non superato: ruoli, flussi e navigazione rotti

- Area: frontend / RBAC / flussi end-to-end
- Severità stimata: alta
- Emerso durante: Ondata UI, UI-1…UI-4
- Descrizione: la verifica completa ha confermato più blocker coordinati. I ruoli
  canonici `operatore` e `consultazione` non entrano nel frontend (UI-01);
  l'elenco piani finanziari e alcuni PDF timesheet rispondono 500 (UI-02/UI-04);
  il Cockpit non collega contatori e decisioni alle pagine operative (UI-15);
  il portale allievi tokenizzato è montato dopo il gate di login ERP (UI-16).
  Restano inoltre incoerenze RBAC/visibilità UI-05, UI-06 e UI-09 e uno stato
  estrazione troppo ottimistico in presenza di risultati parziali (UI-17).
- Impatto: non è possibile dichiarare tutte le pagine collegate e funzionanti,
  né scrivere/verificare onestamente il manuale operativo richiesto.
- Evidenze e decisioni puntuali: `audit/UI_VERIFICA_REPORT.md`.
- Stato: aperto; GATE UI non superato. Decidere e correggere i blocker prima
  dell'Ondata M, poi ripetere i flussi e la matrice sui tre ruoli canonici.
- Aggiornamento GATE v2 2026-07-19: i blocker UI-01/02/04/05/06/09/15/16/17
  sono chiusi e il crawl finale è pulito sui tre ruoli. NEW-018 resta aperto
  perché il protocollo richiesto include funzioni non implementate: piano da
  template (B4) e ricerca archivio con citazioni (L1); manca inoltre una prova
  E2E unica fino alla generazione del contratto. Dettaglio nel report v2.

## 2026-07-19 | NEW-019 | Dashboard consultazione chiamava reporting admin-only

- Area: frontend / RBAC / Dashboard
- Severità stimata: alta
- Emerso durante: GATE UI v2, crawl pagina × ruolo
- Descrizione: la Dashboard è correttamente visibile a `consultazione`, ma
  invocava sempre `GET /api/v1/reporting/timesheet`, protetto dal backend per
  admin/operatore. La pagina restava renderizzata grazie a `Promise.allSettled`,
  nascondendo un 403 in console e rete.
- Impatto: integrazione per ruolo incoerente e segnale di errore invisibile
  all'operatore; il precedente test Dashboard verificava il render, non le
  chiamate vietate per ruolo.
- Stato: **chiuso il 2026-07-19** con UI-20; richiesta timesheet omessa per
  consultazione e test regressione ruolo × chiamata aggiunto.

## 2026-07-19 | NEW-020 | Health check frontend non portabile su hostname pubblico

- Area: frontend / deploy / portabilità
- Severità stimata: media
- Emerso durante: GATE UI v2, primo harness Playwright su
  `host.docker.internal:3001`
- Descrizione: fuori dai rami localhost e reti IPv4 private, `apiBaseUrl` è
  `/api/v1`; la chiamata health costruita con lo stesso client axios diventa
  `/api/v1/health`, mentre il backend espone `/health`. L'accesso locale e LAN
  attuale usa correttamente backend `:8001` e non è coinvolto.
- Impatto: un futuro deploy same-origin su hostname pubblico può fermarsi alla
  schermata di connessione anche con backend sano.
- Stato: aperto; rendere il health check indipendente dal `baseURL` API o
  aggiungere un alias esplicito coperto da test di deploy same-origin.

## 2026-07-19 | NEW-021 | Accept umano rotto per suggerimenti non-collaboratore (contract_ready)

- Area: agenti / workflow review umana
- Severità stimata: alta
- Emerso durante: Task E2.1, test E2E catena contratto
  (`backend/tests/test_e2e_catena_contratto.py::test_catena_contratto_completa`)
- Descrizione: `POST /api/v1/agents/suggestions/{id}/accept` (endpoint
  primario per l'"apply umano" di una proposta agente) normalizza qualunque
  azione di accettazione in `approve_email` e in `agent_workflows.
  apply_workflow_action` richiede sempre un `AgentCommunicationDraft` per il
  canale selezionato. I draft vengono creati solo per suggerimenti con
  `entity_type == "collaborator"` (`_ensure_collaborator_draft`). Il
  `contract_agent` produce però suggerimenti `contract_ready` con
  `entity_type == "assignment"`: per queste, `draft` resta sempre `None` e
  l'endpoint risponde **400 "Nessuna comunicazione email disponibile per
  questo suggerimento"** — nessun umano può mai accettare la proposta tramite
  il canale ufficiale.
- Riprodotto (RED): flusso completo — anagrafica → progetto/assegnazione →
  documenti obbligatori → upload+valida → trigger reale contract_agent →
  `POST .../accept` → 400.
- Impatto: la catena "review umana → generazione contratto" documentata come
  canonica nel flusso agenti è di fatto irraggiungibile per il contract_agent
  (e per qualunque futuro agente con `entity_type` diverso da `collaborator`).
- Fix applicato (minimo, stesso commit E2 separato `fix(E2)`):
  `backend/agent_workflows.py::apply_workflow_action` — quando l'azione è
  `approve` e non esiste (né può esistere) un draft perché
  `suggestion.entity_type != "collaborator"`, l'accettazione diventa una
  conferma di stato diretta (`status="approved"` + `_review_log` +
  `create_audit_log`), senza tentare invio email/whatsapp. Il comportamento
  per i suggerimenti di comunicazione (`entity_type == "collaborator"`) non è
  cambiato.
- Verifica: `test_catena_contratto_completa` passa RED→GREEN dopo il fix;
  suite `test_agents_e2e.py`, `test_agents_registry_workflow.py`,
  `test_agent_audit_fixes.py`, `test_email_agent.py`,
  `test_inbox_reply_draft.py`, `test_agent_no_autosend.py` invariate (verde).
- Stato: **chiuso il 2026-07-19** nell'ambito del Task E2.1.

## 2026-07-19 | NEW-022 | Download contratto firmato raggiungibile dal ruolo consultazione

- Area: RBAC / documenti sensibili
- Severità stimata: media
- Emerso durante: Task E2.1, Step 3 (verifica sospetto ricognizione: endpoint
  contratto "senza dipendenza auth visibile")
- Descrizione: `GET /api/v1/assignments/{id}/contract` (`genera_contratto`,
  `backend/routers/sprint7.py:120`) **è già protetto da autenticazione**: il
  router `sprint7_router` è montato con `include_protected_router`, quindi
  ogni richiesta passa comunque per `Depends(require_role)` →
  `Depends(get_current_user)` (verificato con test dedicato: richiesta senza
  utente autenticato → 401/403). Il sospetto "endpoint del tutto
  sbloccato" della ricognizione era quindi impreciso — ma la verifica ha
  scoperto un problema reale collegato: il path `/api/v1/assignments/...`
  ricade nella regola generica `OPERATIONAL_PREFIXES` che per i metodi GET
  consente **tutti e tre i ruoli**, incluso `consultazione`. Questo permette
  a un utente di sola consultazione di scaricare il PDF del contratto
  firmato, che contiene PII sensibili (codice fiscale, indirizzo, compenso
  orario/totale) — stessa categoria di dato per cui esistono già le
  eccezioni `download-documento` / `download-curriculum` (solo admin).
- Fix applicato (commit dedicato `fix(E2-NEW-022)`):
  - `backend/auth.py::OPERATORE_ALLOWED_SENSITIVE_GET_SUFFIXES` — aggiunto
    suffisso `"/contract"` (nessun altro endpoint GET termina con questo
    suffisso), che restringe l'accesso a `{admin, operatore}` per il download
    del contratto, coerente con il meccanismo già usato per
    `/export-excel` / `/api/v1/reporting/timesheet`.
  - `backend/routers/sprint7.py::genera_contratto` — aggiunta dipendenza
    esplicita `current_user=Depends(get_current_user)` (parità con
    `routers/timesheet.py`), a scopo difensivo/documentale visto che la
    protezione reale passa dal router-level `require_role`.
- Verifica: nuovo test `test_contract_endpoint_nega_consultazione` (403 per
  ruolo consultazione) e `test_contract_endpoint_richiede_autenticazione`
  (401/403 senza utente autenticato), entrambi in
  `backend/tests/test_e2e_catena_contratto.py`.
- Stato: **chiuso il 2026-07-19** nell'ambito del Task E2.1.

## 2026-07-20 | NEW-023 | Approve diretto senza guardia di stato: doppio accept e ribaltamento di reject

- Area: agenti / workflow review umana
- Severità stimata: media (Important in review R0)
- Emerso durante: review R0 del diff E2.1 (finding I-1)
- Descrizione: il ramo di approvazione diretta introdotto con NEW-021 in
  `backend/agent_workflows.py::apply_workflow_action` (approve su suggestion
  con `entity_type != "collaborator"`, es. `contract_ready`) non verificava
  lo stato corrente della suggestion. Conseguenze: (1) un doppio accept
  creava due `AgentReviewAction` duplicate e due audit log per la stessa
  decisione; (2) un accept su una suggestion già `rejected` la riportava
  silenziosamente ad `approved`, ribaltando una decisione umana precedente
  senza traccia di conflitto.
- Fix applicato (minimo, confinato al ramo nuovo — il flusso
  collaborator/draft non è toccato): all'ingresso del ramo, se
  `suggestion.status in {"approved", "rejected", "completed"}` →
  `raise ValueError("Suggerimento già revisionato")`, che il router
  (`routers/agents.py::accept_suggestion`) trasforma in HTTP 400. Nello
  stesso intervento (N-1 della review) l'audit log del ramo diretto usa ora
  l'azione onesta `workflow_approve_direct` invece di `workflow_approve_email`
  (nessun invio email avviene in quel ramo; nessun test assertiva il valore
  precedente).
- Verifica: nuovo test
  `test_accept_diretto_idempotente_su_suggestion_gia_revisionata` in
  `backend/tests/test_e2e_catena_contratto.py`: secondo accept → 400,
  status resta `approved`, `review_actions` non duplicate.
- Stato: **chiuso il 2026-07-20** nell'ambito della review R0 su E2.1.

## 2026-07-20 | NEW-024 | PDF timesheet scaricabile dal ruolo consultazione

- Area: RBAC / endpoint file (Task R1, stessa classe di NEW-022)
- Severità stimata: media
- Emerso durante: Task R1, sweep sistematico degli endpoint file/export
- Descrizione: `GET /api/v1/assignments/{assignment_id}/timesheet`
  (`backend/routers/timesheet.py::genera_o_scarica_timesheet`) genera/scarica
  il PDF del timesheet (nome e cognome collaboratore, ruolo, righe presenze,
  ore totali — dato lavorativo individuale). Il path ricade nella regola
  generica `OPERATIONAL_PREFIXES` (`/api/v1/assignments`) che per i GET
  ammette tutti e tre i ruoli, quindi anche `consultazione`, in violazione
  della matrice Ondata 1 (timesheet: admin + operatore). Effetto collaterale:
  la prima GET su un assignment senza timesheet bloccato **genera e persiste**
  un nuovo `TimesheetGenerato` bloccato — un ruolo di sola lettura poteva
  quindi anche produrre side effect di scrittura.
- Fix applicato (commit dedicato `fix(RBAC-DL)`): aggiunto suffisso
  `"/timesheet"` a `auth.OPERATORE_ALLOWED_SENSITIVE_GET_SUFFIXES` (stesso
  meccanismo di NEW-022) e a `OPERATOR_SENSITIVE_GET_SUFFIXES` in
  `frontend/src/auth/permissions.js` (matrice speculare). Verificata la
  bidirezionalità della regola a suffisso (nota N-2, review R0): l'unico
  altro endpoint GET che termina con `/timesheet` è
  `/api/v1/reporting/timesheet`, già ristretto allo stesso insieme
  {admin, operatore} via `OPERATORE_ALLOWED_SENSITIVE_GET_PATHS` — nessuna
  concessione involontaria (test dedicato
  `test_suffisso_timesheet_non_concede_percorsi_admin_only`).
- Verifica: `backend/tests/test_rbac_download_endpoints.py` (matrice pura +
  HTTP con `RBAC_ENFORCE=True`: consultazione → 403, admin/operatore
  passano il gate).
- Stato: **chiuso il 2026-07-20** nell'ambito del Task R1.

## 2026-07-20 | NEW-025 | Allegato email inbox scaricabile dal ruolo consultazione

- Area: RBAC / endpoint file, piattaforma agenti (Task R1)
- Severità stimata: media
- Emerso durante: Task R1, sweep sistematico degli endpoint file/export
- Descrizione: `GET /api/v1/email-inbox/items/{item_id}/attachment`
  (`backend/routers/email_inbox.py::download_item_attachment`) serve il file
  allegato di un item della inbox. Il path ricade in
  `AGENT_PLATFORM_PREFIXES` la cui regola A5a "GET consultabili da tutti i
  ruoli" ammetteva anche `consultazione`. Gli allegati email hanno contenuto
  arbitrario e nel flusso reale sono spesso documenti del collaboratore
  (carte d'identità, CV, contratti in arrivo) — la stessa categoria di file
  che, una volta archiviata, è scaricabile **solo da admin** via
  `/download-documento`. Classe identica a NEW-022: la regola generica sui
  GET non deve estendersi ai file binari.
- Fix applicato (commit dedicato `fix(RBAC-DL)`): in
  `auth._agent_platform_allowed_roles` i GET che terminano con
  `"/attachment"` sono ristretti a {admin, operatore}; matrice speculare
  allineata in `frontend/src/auth/permissions.js` (ramo agent platform).
  Nota per decisione utente: la scelta {admin, operatore} (e non solo admin)
  privilegia il flusso operativo inbox (assign/followup sono azioni
  operatore per A5a); se si vuole parità piena con `/download-documento`
  (solo admin) va deciso esplicitamente.
- Verifica: `backend/tests/test_rbac_download_endpoints.py` (matrice pura +
  HTTP con `RBAC_ENFORCE=True`).
- Stato: **chiuso il 2026-07-20** nell'ambito del Task R1 (con nota di
  decisione utente sull'eventuale restrizione a solo admin).

## 2026-07-20 | NEW-026 | Export CSV timesheet negato all'operatore: possibile eccesso di restrizione

- Area: RBAC / endpoint file (Task R1) — finding UX, non di sicurezza
- Severità stimata: bassa
- Emerso durante: Task R1, confronto censimento vs matrice Ondata 1
- Descrizione: `POST /api/v1/reporting/timesheet/export` e
  `GET /api/v1/reporting/timesheet/export/{export_id}` (CSV massivo dei
  timesheet) sono **solo admin** per via del pattern esplicito
  `"/api/v1/reporting/timesheet/export"` in `auth.ADMIN_ONLY_PATTERNS`.
  La matrice Ondata 1 però recita "timesheet: sì operatore", e l'operatore
  può già scaricare il PDF del singolo timesheet e la vista
  `GET /api/v1/reporting/timesheet`. Le due letture sono in tensione:
  o l'export massivo è deliberatamente più restrittivo (admin-only) in
  quanto estrazione bulk, oppure è un residuo troppo restrittivo.
- Decisione richiesta all'utente: confermare admin-only per l'export CSV
  massivo (stato attuale, nessun cambio) oppure estenderlo all'operatore
  (rimozione del pattern + allineamento frontend). Nessuna modifica
  applicata in Task R1: ampliare un accesso è una scelta di prodotto, non
  di remediation.
- Stato: **aperto — decisione utente**.
