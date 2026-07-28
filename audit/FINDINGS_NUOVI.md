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
- Stato: CHIUSO 2026-07-22. `healthCheck` in
  `frontend/src/services/apiService.js` ora fa
  `http.get('/health', { baseURL: apiRootUrl })`: axios usa `apiRootUrl` al
  posto del baseURL `/api/v1` dell'istanza. Same-origin (`apiRootUrl=''`) →
  hit su origin `/health`; LAN (`apiRootUrl='http://IP:8001'`) →
  `http://IP:8001/health`. Test in
  `frontend/src/services/apiService.test.js` coprono entrambi gli scenari
  (same-origin: url `/health` e non `/api/v1/health`; LAN: baseURL assoluto).

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
- Decisione utente (2026-07-20): **resta admin-only**. L'export massivo è
  un'estrazione bulk dei dati economici di tutti i collaboratori: la
  restrizione esplicita è deliberata e viene mantenuta. Nessun cambio a
  codice o matrice; la matrice Ondata 1 va letta come "timesheet
  individuale: sì operatore; export massivo: solo admin".
- Stato: **chiuso 2026-07-20 (decisione: nessun cambio)**.

## 2026-07-20 | NEW-027 | Documento obbligatorio scaduto considerato valido dal contract_agent

- Area: piattaforma agenti / contract_agent (Task E2.2)
- Severità stimata: media
- Emerso durante: Task E2.2, test negativi della catena contratto
  (`test_documento_scaduto_pratica_non_completa`, RED osservato prima del fix)
- Descrizione: `ai_agents/contract_agent.py::_pratica_completa` considerava
  la pratica documentale completa guardando SOLO `stato == "validato"`,
  ignorando `data_scadenza`. Un documento obbligatorio caricato con
  `data_scadenza` passata e poi validato (la `POST /valida` non blocca i
  documenti scaduti, e `crud.marca_scaduti` gira solo periodicamente)
  rendeva la pratica "completa": il collector proponeva la suggestion
  `contract_ready` e il contratto risultava generabile su documentazione
  scaduta.
- Fix applicato (commit dedicato `fix(E2-NEW-027)`): nuovo helper
  `_documento_valido(richiesta, now)` in `ai_agents/contract_agent.py` —
  un documento copre il requisito solo se `stato == "validato"` E
  (`data_scadenza` assente O `>= now`). Convenzione temporale allineata a
  `crud.marca_scaduti` (`datetime.now()` naive).
- Verifica: `backend/tests/test_e2e_catena_contratto.py::
  test_documento_scaduto_pratica_non_completa` (upload con data_scadenza
  passata + valida via API reali, trigger reale dell'agente → nessuna
  suggestion contract_ready). RED→GREEN osservato.
- Stato: **chiuso il 2026-07-20** nell'ambito del Task E2.2.

## 2026-07-20 | NEW-028 | Suite di test non isolata dal rate limiter in-memory: 429 nondeterministici

- Area: test infrastructure / request_middleware (Task E2.2)
- Severità stimata: media (affidabilità suite, nessun impatto runtime prod)
- Emerso durante: Task E2.2 — l'aggiunta di 3 test E2E (~45 richieste HTTP)
  ha fatto fallire con 429 sei test NON correlati in `test_listini_api.py` e
  `test_main.py` nella run completa; gli stessi test passano in isolamento e
  la baseline senza i nuovi test è verde (655 passed). Riproduzione doppia.
- Descrizione: `request_middleware.RateLimitingMiddleware` tiene lo stato
  per-IP in-memory sull'istanza; l'app FastAPI è un singleton di modulo,
  quindi il budget (120 req/min sul bucket "*" per l'IP "testclient") è
  CONDIVISO fra tutti i test del processo pytest. La suite era già al limite
  del budget: qualunque nuovo test che aggiunga richieste HTTP fa fallire
  test lontani con 429 in modo dipendente dal timing (flakiness strutturale).
- Fix applicato (commit dedicato `fix(E2-NEW-028)`): nuovo
  `backend/tests/conftest.py` con fixture autouse che azzera
  `client_requests` del middleware prima di ogni test (traversal dello
  middleware_stack). Ogni test riparte con budget pieno; il comportamento
  del limiter entro il singolo test resta verificabile (oggi nessun test
  asserisce un 429 cross-test).
- Verifica: run completa `docker exec pythonpro_backend python -m pytest
  tests/ -q` verde con i 3 nuovi test E2.2 inclusi.
- Stato: **chiuso il 2026-07-20** nell'ambito del Task E2.2.

## 2026-07-20 | NEW-029 | piani_finanziari.legacy_template_id contiene ancora dati: colonna relitto non droppabile

- Area: modello dati / piani finanziari (Task E1.2.a)
- Severità stimata: bassa (relitto censito, nessun impatto funzionale)
- Emerso durante: Task E1.2, verifica pre-drop dei relitti sul DB reale
  (`information_schema` + conteggi via `docker exec pythonpro_db psql`).
- Descrizione: la bonifica prevedeva il drop di `legacy_template_id` e
  `legacy_avviso_id` se vuote. Verifica sul DB reale (2026-07-20):
  `legacy_avviso_id` tutta NULL → droppata in migration 060;
  `legacy_template_id` ha 1 riga valorizzata — piano id=4 ("Piano
  Finanziario - poppi - FAPI - Avviso 4/2025") → valore 14, che su
  `contract_templates` è "Piano FAPI Standard" (traccia del vecchio uso
  improprio dei contract_templates come template di piani). Da regola di
  ondata i dati non si droppano: colonna mantenuta (modello e DB) con
  commento nel modello.
- Da fare (fuori scope E1.2): decidere se migrare il riferimento del piano 4
  verso la nuova entità `PianoFinanziarioTemplate` (una volta seedata) o
  azzerarlo con consenso utente; poi drop della colonna in una migration
  successiva.
- Risoluzione (2026-07-22 | decisione utente "droppa migrando"): applicata
  migration **062** (`062_drop_piani_finanziari_legacy_template_id.py`).
  Stadio "migrando" (preserva): per ogni piano con `legacy_template_id`
  non-null si scrive una riga append-only in `audit_logs` (modello `AuditLog`,
  audit di dominio) — `entity='PianoFinanziario'`,
  `action='legacy_template_id_dropped'`,
  `old_value='{"piano_id": 4, "legacy_template_id": 14}'`. Scelto `audit_logs`
  come target perché è il contenitore di dominio pensato per entity/action/
  old_value, senza inquinare i campi utente (`note`/`note_ente`);
  l'immutabilità del modello è solo a livello ORM, quindi l'INSERT SQL da
  migration è lecito. Stadio drop: `DROP COLUMN legacy_template_id`. Downgrade
  ricrea la colonna VUOTA (il valore resta in `audit_logs`, non ripristinato).
  Rimosso anche l'attributo dal modello `PianoFinanziario` (`models.py:~1092`).
  Nota: sul DB reale al 2026-07-22 `contract_templates.id=14` esiste ancora
  (la nota di contesto "id 14 non esiste più" era imprecisa); resta comunque un
  riferimento senza valore semantico (non era una FK dichiarata).
  Prova su clone (pg_dump gestionale → gestionale_new029_test): upgrade
  061→062 (colonna droppata, pf=4 invariato, audit_logs 345→346 con la riga di
  preservazione), downgrade→061 (colonna ricreata vuota), re-upgrade→062 OK;
  clone droppato. Migration reale: `alembic upgrade head` → head=062,
  colonna assente, piano 4 preservato in `audit_logs` (id 51821), /health 200.
  Test: `tests/test_new029_legacy_template_id_dropped.py` (modello senza
  `legacy_template_id` + regressione creazione piano).
- Stato: **chiuso** (2026-07-22, migration 062, valore preservato in `audit_logs`).

## 2026-07-20 | NEW-030 | POST/PUT /projects: azienda_ids e allievo_ids inviati dal frontend ma scartati in silenzio dallo schema

- Area: API progetti / schemi Pydantic (Task E1.2.d, scoperto durante l'analisi
  degli scarti silenziosi in `crud._resolve_project_financial_refs`)
- Severità stimata: alta (funzionalità di collegamento aziende/allievi alla
  creazione progetto di fatto inerte via API)
- Descrizione: `frontend/src/components/ProjectManager.js` invia
  `azienda_ids` e `allievo_ids` nel payload di create/update progetto e
  `crud.create_project`/`update_project` fanno `payload.pop("azienda_ids")` +
  `_sync_project_azienda_links`/`_sync_project_allievi`, MA gli schemi
  `ProjectCreateExtended`/`ProjectUpdateExtended` NON dichiarano quei campi:
  Pydantic (extra=ignore) li scarta prima che crud li veda, quindi i pop
  ricevono sempre il default e i link non vengono mai creati/aggiornati da
  questi endpoint. Il ramo di sync in crud è codice morto.
- Nota: fix NON applicato in E1.2 (dichiarare i campi cambia il comportamento
  API e va coperto con test dedicati; è una scelta funzionale, non una
  bonifica relitti). Candidato a task dedicato.
- Ricognizione (2026-07-21): confermato. Il frontend invia davvero
  `azienda_ids`/`allievo_ids` (`ProjectManager.js`, righe 456-457 nel payload di
  create/update; 536-537 li rilegge da `project.*` per pre-popolare il form in
  modifica). Il sync in `crud._sync_project_azienda_links`/`_sync_project_allievi`
  (crud.py:639-700) era già corretto e con semantica None/[] giusta
  (`create_project` pop default `[]`; `update_project` usa `exclude_unset` + pop
  default `None`, sincronizza solo se `not None`) — mancava solo la dichiarazione
  dei campi negli schemi. Modelli di associazione reali:
  `AziendaClienteProjectLink` (link azienda↔progetto) e la secondary
  `allievo_project` via relationship `Project.allievi_coinvolti`. Le @property
  `Project.azienda_ids`/`allievo_ids` (models.py:319-328) esistono già.
- Fix applicato (commit `fix(NEW-030): ...`):
  - `schemas.ProjectBaseExtended` (→ `ProjectCreateExtended`) e
    `schemas.ProjectUpdateExtended`: dichiarati `azienda_ids: Optional[List[int]]
    = None` e `allievo_ids: Optional[List[int]] = None` (i nomi combaciano già con
    il frontend, nessuna modifica frontend necessaria).
  - `schemas.Project` (schema di lettura): esposti `azienda_ids: List[int] = []` e
    `allievo_ids: List[int] = []` (letti dalle @property del modello via
    `from_attributes`), così la GET pre-popola il form in modifica ed evita il
    footgun di cancellare i link a un salvataggio successivo.
  - Il validator NEW-021 (`_no_legacy_keys`) rifiuta solo
    `template_piano_finanziario_id`/`avviso_pf_id`: non confligge con i nuovi
    campi, che restano accettati.
- Codice morto risolto: prima del fix, con dati reali il ramo di sync non veniva
  mai raggiunto (Pydantic scartava i campi → i pop ricevevano sempre il default).
- Verifica: nuovo `backend/tests/test_projects_sync_ids.py` (create con id → link
  creati; update aggiunge/rimuove; None invariato; [] svuota; azienda inesistente
  → 400; legacy key → 422; RBAC create/update admin+operatore, consultazione 403;
  read exposure). RED→GREEN dimostrato (5 test di sync rossi senza la modifica
  schema, verdi dopo). Suite backend completa verde.
- Stato: **chiuso il 2026-07-21**.

## 2026-07-20 | NEW-031 | Nessuna UI di consultazione/navigazione dei piani finanziari; POST /piani-finanziari/ libero senza chiamante frontend

- Area: frontend / piani finanziari (Task E1.4 — wizard piano da template)
- Severità stimata: media (gap funzionale UI, nessun dato a rischio)
- Emerso durante: aggancio del bottone "Nuovo piano da template" — la
  ricognizione del "percorso libero" ha mostrato che:
  1. `apiService.createPianoFinanziario` (POST /api/v1/piani-finanziari/,
     percorso libero) esiste in `frontend/src/services/apiService.js` ma
     NON ha alcun chiamante nei componenti: l'unica creazione piano da UI
     è l'upload XLSX per progetto (`FapiUpload.js::PianoFinanziarioModal`,
     FAPI/Formazienda) che passa da /projects/{id}/upload-piano-finanziario.
  2. Non esiste alcun componente che navighi/apra un piano finanziario
     (zero chiamanti di getVociPianoFinanziario/getRiepilogoPianoFinanziario/
     exportPianoFinanziarioExcel; AssignmentModal legge le voci solo come
     opzioni mansione). Il "redirect al piano creato" previsto dal piano
     E1.4 non ha quindi una destinazione esistente: il wizard mostra il
     piano creato con le sue voci nella vista finale del wizard stesso.
- Da fare (fuori scope E1.4): valutare una sezione/vista piani finanziari
  (elenco, dettaglio voci, riepilogo, export) che dia una casa sia al
  percorso libero sia ai piani creati da template.
- **Decisione utente (2026-07-22): è una feature UI vera, SCHEDULATA** come
  lavoro dedicato (non fix rapido). Scope previsto: nuova sezione "Piani
  finanziari" con elenco per progetto/anno, dettaglio voci per macrovoce,
  riepilogo massimali con fonte, export Excel (endpoint `exportPianoFinanziarioExcel`
  già esistente lato backend), deep-link dal wizard e dalle citazioni. RBAC:
  lettura ai 3 ruoli, scrittura admin+operatore. Richiede piano dedicato
  (backend endpoint listing già presente `GET /api/v1/piani-finanziari/`;
  manca solo il frontend). Nel frattempo il wizard mostra il piano inline.
- Stato: **SCHEDULATA** (backlog roadmap, non bloccante; wizard E1.4 con vista inline).

## 2026-07-20 | NEW-032 | from-template senza avviso_id eredita comunque l'avviso dal progetto

- Area: backend / piani da template (demo GATE E1)
- Severità stimata: media (comportamento potenzialmente inatteso, nessun dato errato)
- Emerso durante: demo GATE E1 su clone (caso 4c "piano senza avviso")
- Descrizione: `POST /api/v1/piani-finanziari/from-template` senza `avviso_id`
  nel body valorizza comunque `avviso_pf_id`/`avviso_revisione_id` ereditandoli
  dal progetto (`crud.create_piano_finanziario`, crud.py:3977-3978). L'utente
  del wizard può credere di creare un piano "senza avviso" mentre il piano
  risulta agganciato all'avviso del progetto (e alle sue regole validate).
- Nota: l'enforcement resta corretto (revisione senza regole → fallback fondo).
- Decisione utente (2026-07-21): comportamento VOLUTO, backend invariato;
  l'ereditarietà va esplicitata nella UI del wizard.
- Fix applicato: `PianoTemplateWizard.js` — al passo 3, se nessun avviso è
  stato scelto al passo 1 e il progetto selezionato ha `avviso_id`, nota
  informativa sull'ereditarietà (titolo avviso risolto dall'elenco avvisi già
  caricato); nella vista finale mostrato l'avviso effettivo del piano creato
  da `avviso_pf_id` (fallback "avviso #id" se non risolvibile), con suffisso
  "(ereditato dal progetto)" quando non scelto esplicitamente. 6 test jest.
- Stato: **chiuso** (2026-07-21, commit `fix(E1-NEW-032): wizard esplicita
  ereditarietà avviso dal progetto`).

## 2026-07-20 | NEW-033 | VocePianoFinanziario API non espone voce_codice/macrovoce

- Area: backend / schemi piani finanziari (demo GATE E1)
- Severità stimata: media
- Emerso durante: demo GATE E1, verifica risposta 201 from-template
- Descrizione: `schemas.VocePianoFinanziario` (schemas.py:~1650) non espone
  `voce_codice` e `macrovoce`: in DB sono valorizzati (29/29 voci dei piani
  da template), ma nelle risposte API escono assenti/null. La UI non può
  mostrare i codici voce (A.1…D.4) né raggruppare per macrovoce dagli
  endpoint piani.
- Fix applicato: `schemas.VocePianoFinanziario` espone `voce_codice` e
  `macrovoce` (Optional in lettura; in DB NOT NULL). Tutti gli endpoint con
  response_model VocePianoFinanziario/PianoFinanziarioWithVoci li
  restituiscono. Test estesi in `test_piano_templates_api.py` (201
  from-template con/senza avviso, GET piano).
- Stato: **chiuso** (2026-07-21, commit `fix(E1-NEW-033/034): API piani
  espone voce_codice, macrovoce e anno`).

## 2026-07-20 | NEW-034 | PianoFinanziarioWithVoci non include anno

- Area: backend / schemi piani finanziari (demo GATE E1)
- Severità stimata: bassa
- Emerso durante: demo GATE E1
- Descrizione: la risposta `PianoFinanziarioWithVoci` non include il campo
  `anno` (presente in DB). Il wizard lo conosce dal form, ma qualunque altra
  vista futura dei piani non potrà mostrarlo senza query aggiuntiva.
- Fix applicato: `anno` aggiunto allo schema di lettura
  `schemas.PianoFinanziario` (quindi anche `PianoFinanziarioWithVoci`);
  asserzioni su `anno` nelle risposte 201/GET in
  `test_piano_templates_api.py`.
- Stato: **chiuso** (2026-07-21, commit `fix(E1-NEW-033/034): API piani
  espone voce_codice, macrovoce e anno`).

## 2026-07-20 | NEW-035 | Messaggio dedup piani cita l'avviso del piano esistente

- Area: backend / piani finanziari UX (demo GATE E1)
- Severità stimata: bassa
- Emerso durante: demo GATE E1 (400 su progetto con piano esistente)
- Descrizione: il 400 di dedup ("Esiste già un piano finanziario FORMAZIENDA /
  avviso 2/2022 per questo progetto e anno") cita l'avviso del piano GIÀ
  esistente, non quello richiesto: con avvisi diversi il messaggio confonde.
- Fix suggerito: esplicitare entrambi ("richiesto avviso X; esiste già un
  piano per avviso Y, anno Z").
- Stato: **chiuso** (2026-07-22). `create_piano_finanziario` in
  `backend/crud.py` ora emette: "Esiste già un piano finanziario per questo
  progetto e anno {anno} ({esistente_desc}); richiesta rifiutata per {ente}
  avviso {avviso_richiesto}.". `esistente_desc` risolve l'avviso del piano
  esistente dalla relazione `avviso_rel` (numero/codice), con fallback
  `piano {codice_piano}` o "senza avviso" (PianoFinanziario non ha un campo
  `avviso` scalare). Il messaggio distingue esplicitamente richiesta vs piano
  esistente e cita l'anno. Test:
  `test_agent_audit_fixes.py::
  test_create_piano_finanziario_dedup_message_cites_requested_and_existing_avviso`
  asserisce che il detail cita sia l'avviso richiesto (AV-2025-RICHIESTO) sia
  quello esistente (AV-2024-ESISTENTE) sia l'anno.

## 2026-07-21 | NEW-036 | Le 3 fonti DB della ricerca archivio sono vuote sul DB reale

- Area: dati / archivio avvisi (Task E3.1 — ricerca FTS)
- Severità stimata: media (la feature "Chiedi all'archivio" non ha nulla da
  restituire finché le fonti non vengono popolate; nessun difetto di codice)
- Emerso durante: verifica empirica preliminare post-migration 061 sul DB
  reale: `avviso_regole` = 0 righe (nessuna regola, né validata né proposta),
  `avviso_conoscenze` = 0, `avviso_esiti_progetto` = 0, a fronte di 6 avvisi
  e 6 revisioni presenti. Tutte le query realistiche provate ("massimale
  docenza", "rendicontazione", "scadenza presentazione", "tutoraggio")
  restituiscono 0 risultati.
- Il percorso PostgreSQL (tsvector + indici GIN 061) è stato dimostrato
  funzionante con un dato transiente in transazione (flush + search +
  ROLLBACK, nessuna scrittura): 1 risultato con rank ts_rank e citazione.
- Da fare (fuori scope E3.1): estrarre/validare regole dagli avvisi caricati
  e/o inserire conoscenze operative, altrimenti al gate E3.4 la verifica
  empirica delle 10 query darà "non_presente" ovunque per assenza dati.
- Nota già nel piano E3: i markdown puliti delle revisioni stanno su file
  (`cleaned_md_path`), fuori dal DB: non sono una fonte della ricerca v1.
- Stato: **aperto** (dato, non codice). Confermato al gate E3.4 (2026-07-21):
  DB reale ancora 0/0/0, i 3 ruoli su `/chiedi` danno `non_presente`; motore FTS
  provato su clone seedato (vedi `audit/E3_GATE_REPORT.md`).

## 2026-07-21 | NEW-037 | `/chiedi` passa la domanda in linguaggio naturale grezza a websearch_to_tsquery (AND) → domande verbose recuperano 0

- Area: ricerca archivio / "Chiedi all'archivio" (Task E3.1/E3.2)
- Severità stimata: media (usabilità: `/chiedi` è progettato per domande in
  linguaggio naturale, ma le penalizza)
- Emerso durante: verifica empirica FTS del gate E3.4 su clone seedato.
- Dettaglio: `search_archivio` sul percorso PostgreSQL usa
  `websearch_to_tsquery('italian', q)`, che mette in **AND** tutti i lessemi
  content della stringa. `chiedi_archivio` passa la domanda **grezza** a questa
  funzione. Esempio verificato: `Qual è il massimale orario per la docenza?` →
  `'qual' & 'massimal' & 'orar' & 'docenz'` → **0 risultati** (nessun documento
  contiene "qual"), quindi `stato="non_presente"` **anche se il contenuto
  pertinente esiste**. La stessa domanda in forma keyword
  `massimale orario docenza` → 2 risultati. Quindi più parole "di contorno" nella
  domanda ⇒ più facile lo zero-result ingiustificato.
- Impatto: `/chiedi` (che riceve domande intere) ne soffre più della `search`
  (parole chiave). Amplifica la percezione di "archivio vuoto" quando invece è
  solo un problema di formulazione della query.
- Mitigazione a basso costo (indipendente da pgvector): pre-processare la
  domanda prima della FTS — estrazione parole chiave / rimozione stopword / uso
  di `to_tsquery` con OR tra i termini invece dell'AND implicito, oppure
  soglia/fallback su OR quando l'AND dà 0.
- Nota: distinto dal limite di recall semantico inter-fondo (sinonimi
  docenza/formatori), che invece richiede il layer pgvector raccomandato.
- Risoluzione (2026-07-21): retrieval a **due stadi** in `search_archivio`
  (nuovo parametro `or_fallback`, usato solo da `chiedi_archivio`/`/chiedi`;
  `GET /search` invariato → nessuna regressione sulla keyword pura). Primo
  stadio AND (precisione: `websearch_to_tsquery` su PG, `AND` di ILIKE su
  SQLite); se rende 0, secondo stadio OR sui **soli termini della domanda**
  (`plainto_tsquery` uniti da `|` su PG, `OR` di ILIKE su SQLite). Le 3 regole
  di onesta' restano intatte: se anche l'OR e' vuoto → `non_presente` senza
  interpellare l'LLM; citazioni sempre validate; LLM giu' → degradato. Il
  fallback allarga solo il match lessicale su termini realmente presenti nella
  domanda: non inventa risultati. Test: caso letterale del finding PG-only
  (`test_pg_new_037_domanda_naturale_and_zero_or_recupera`, AND=0 → OR>0) +
  copertura portabile SQLite in `test_archivio_search.py` e `test_archivio_chiedi.py`
  (domanda NL recuperata, tema assente resta `non_presente`, OR non "sballa").
- Stato: **chiuso** (2026-07-21, commit `fix(E3-NEW-037)`).

## 2026-07-24 | NEW-038 | create_avviso: ValueError di validazione codice fuoriesce come 500

- Area: backend / routers avvisi / robustezza API
- Severità stimata: media (blocca la creazione avvisi; UX ingannevole)
- Emerso durante: uso reale utente (creazione avviso da Archivio Risorse)
- Descrizione: `crud.create_avviso` (crud.py:918) solleva `ValueError("Il codice
  avviso deve avere formato numero/anno")` quando il codice non è `numero/anno`.
  Il router `create_avviso` (routers/avvisi.py) catturava solo `IntegrityError`
  → il `ValueError` propagava come **500 Internal Server Error**. Il 500 (errore
  non gestito) NON riceve gli header CORS → dal browser appariva come "errore di
  connessione / CORS" (No Access-Control-Allow-Origin), mascherando la vera causa.
- Fix: `create_avviso`/`update_avviso` traducono `ValueError` → `HTTPException 422`
  con `detail=str(exc)` + `db.rollback()`. Il campo codice frontend aveva anche un
  `pattern` regex invalido (`[^/]+/20[0-9]{2}`, la `/` in `[...]` va escapata sotto
  flag `v`) → corretto in `[^\/]+/[0-9]{4}`.
- Commit: `fix(avvisi): codice malformato ritorna 422, non 500` + `fix(UI): pattern
  codice avviso valido`. Test: test_avvisi_v2_api.py (422 su codice errato, 201 su valido).
- Nota architetturale: pattern ricorrente — molti `crud.*` sollevano `ValueError`
  di dominio; i router dovrebbero tradurli sistematicamente in 4xx (non 500). Da
  valutare un exception handler globale ValueError→422 in un giro di igiene.
- Stato: **chiuso il 2026-07-24** (router avvisi); pattern globale ValueError→4xx aperto per igiene.

## 2026-07-27 | NEW-039 | Suite backend rossa a HEAD: i doppi di test dell'estrattore avvisi non accettano i kwargs provider/model

- Area: backend / test / ai_agents estrazione avvisi
- Severità stimata: alta (baseline rossa: nessun lavoro successivo verificabile)
- Emerso durante: verifica prerequisiti Ondata UX OPERATIVA (run suite a HEAD `bf4f153`)
- Descrizione: il commit `757e83c` (provider LLM anthropic per estrazione avvisi)
  ha aggiunto i kwargs `provider=` e `model=` alla chiamata
  `call_ollama_json(...)` in `ai_agents/avviso_extractor.py:118`, ma NON ha
  aggiornato i sei doppi di test in `tests/test_avvisi_v2_extractor.py`, la cui
  firma era `(*, system_prompt, user_prompt)`. Ogni invocazione sollevava
  `TypeError: unexpected keyword argument 'provider'` **prima** di entrare nel
  corpo del doppio → il contatore `calls` restava vuoto e
  `assert len(calls) == 5` falliva. 6 test rossi, presenti già a HEAD e NON
  causati dal lavoro non committato in working tree (verificato con stash).
- Fix: firme dei doppi estese a `(*, system_prompt, user_prompt, **_kwargs)`.
  Il codice di produzione era corretto: la regressione era solo nei test.
- Nota architetturale (aperta): il `try/except Exception` che avvolge la chiamata
  LLM (`avviso_extractor.py:126`) ha mascherato un errore di programmazione
  (`TypeError`) come "sezione fallita", declassando un bug a degrado funzionale.
  Lo stesso meccanismo in produzione trasformerebbe un errore di firma/SDK in
  estrazioni silenziosamente vuote. Da valutare: distinguere le eccezioni di
  trasporto/LLM (degrado legittimo) da `TypeError`/`AttributeError` (rilancio).
- Commit: `fix(UX-0): doppi di test estrattore avvisi accettano provider/model`
- Stato: **chiuso il 2026-07-27** (suite verde); nota architetturale APERTA.

## 2026-07-27 | UX-6 | Atto/convenzione caricato dentro un progetto crea un progetto gemello

- Area: backend routers upload + frontend FapiUpload / dominio progetti
- Severità stimata: **alta** (corruzione dati in uso reale, in corso)
- Emerso durante: uso reale della piattaforma (Ondata UX OPERATIVA, punto 6)
- Sintomo riferito: caricando l'atto di concessione dentro un progetto, il
  sistema crea un nuovo "piano" invece di associare il documento a quello
  esistente.

### Diagnosi (percorso completo)

1. `ProjectManager.js:1438` monta `<FapiUploadSection project={project}/>` nella
   scheda del progetto.
2. `FapiUpload.js` mostra lì il pulsante primario "Carica Convenzione" (FAPI) /
   "Carica Lettera Ammissione" (Fondimpresa) e apre `ConvenzioneModal` /
   `AmmissioneFondimpresaModal` **senza passare il progetto**.
3. Quei modali chiamano gli endpoint *project-less*
   `POST /api/v1/projects/upload-convenzione` + `confirm-convenzione` (e
   l'omologo `fondimpresa/confirm-ammissione`).
4. `confirm_convenzione` esegue **incondizionatamente**
   `db.add(models.Project(...))`: non riceve alcun `project_id`, quindi
   l'associazione al progetto corrente era **strutturalmente impossibile**.

Non era quindi "il parser che crea sempre un piano nuovo" né "un lookup
mancante": mancava del tutto il percorso project-scoped.

**Seconda causa, indipendente.** L'unico argine era la guardia 409 su
`codice_fapi`, condizionata a `if codice_fapi:`. L'atto di concessione caricato
dall'utente non è una convenzione FAPI: rieseguendo il parser sul file reale
(`157055a1-…pdf`) restituisce `codice_fapi=None`, `titolo=None`, warning
"Codice piano non trovato". Guardia saltata → progetto creato col nome di
fallback `"Piano FAPI"`.

### Danno reale osservato

Progetto **13 "Piano FAPI"** creato il 2026-07-27 11:15:11, con il solo PDF
allegato e 5 link azienda copiati, cinque minuti dopo il progetto **12**
(creazione manuale dell'utente, doppione di 11 ma con il CUP che 11 non ha).
Censimento completo e query correttive proposte: GATE UX-6, non eseguite.

### Fix

- Nuovi endpoint project-scoped `POST /api/v1/projects/{id}/upload-convenzione`
  e `confirm-convenzione` (+ omologhi Fondimpresa): associano il documento al
  progetto corrente e **non creano mai** un secondo progetto.
- `services/documento_progetto.py`: diff campo per campo. I campi vuoti sono
  arricchiti; quelli già valorizzati e discordanti restano invariati salvo
  scelta esplicita dell'operatore (`campi_da_applicare`). Nessuna
  sovrascrittura silenziosa di dati già validati.
- Guardia sul percorso di creazione: senza codice piano né titolo il documento
  non è riconosciuto → 422, nessun progetto fantasma.
- Frontend: dentro un progetto il modale passa in modalità "allega", mostra il
  diff con spunta per ogni conflitto e dichiara nell'esito cosa è rimasto
  invariato. Il percorso di creazione resta solo dalla toolbar (nessun progetto
  in contesto).
- Sottoprodotto: la schermata di esito dei modali era codice morto (`onSuccess`
  chiudeva il modale prima di mostrarla). Ora la chiusura è un gesto
  dell'operatore.
- 14 test backend (RED→GREEN, incluso RBAC 3 ruoli) + 6 frontend.
- Commit: `fix(UX-6): ...`
- Stato: **codice chiuso il 2026-07-27**; bonifica dati **APERTA al GATE UX-6**.

## 2026-07-27 | UX-7 | Associazioni aziende/allievi salvate ma mai restituite dall'API

- Area: backend schemas / lettura progetto + frontend scheda progetto
- Severità stimata: **alta** (l'operatore crede di aver perso i dati)
- Emerso durante: uso reale della piattaforma (Ondata UX OPERATIVA, punto 7)
- Sintomo riferito: dopo aver associato aziende e allievi a un progetto e
  salvato, la scheda continua a mostrare "Nessuna azienda associata" e
  "Nessun allievo associato".

### Diagnosi — scrittura o lettura?

**Lettura.** I dati ci sono e sono sulla relazione giusta.

Query sul DB reale (sola lettura): `azienda_cliente_projects` ha 5 righe per il
progetto 11, 5 per il 12, 5 per il 13, 2 per il 5; `allievo_project` ha 4 righe
per il progetto 12. Scrittura (`_sync_project_azienda_links` /
`_sync_project_allievi`) e lettura (`Project.aziende_coinvolte` /
`allievi_coinvolti`) usano **le stesse due tabelle**, e `crud.get_project(s)`
fa già il `selectinload` di entrambe. Nessun contatore denormalizzato, nessuna
cache, nessuna relazione alternativa in uso.

Il difetto è nella **serializzazione**: `schemas.Project` dichiarava solo
`azienda_ids` / `allievo_ids` (interi). La scheda progetto
(`ProjectManager.js:1415-1426`) legge invece `project.aziende_coinvolte` e
`project.allievi_coinvolti`, campi che l'API non ha mai restituito: Pydantic li
scartava perché non dichiarati. `Array.isArray(undefined)` è `false`, quindi il
ramo "nessun associato" scattava **a prescindere dai dati**.

### Relazioni ridondanti

Censite, nessuna migrazione necessaria:

- `azienda_cliente_projects` — canonica, in uso in scrittura e lettura.
- `allievo_project` — canonica, in uso in scrittura e lettura.
- `progetto_beneficiario` — **relitto**: 0 righe sul DB reale, nessun
  riferimento nel codice applicativo (solo la classe in `models.py`, senza
  relazioni). Da droppare in un giro di igiene, non in questa ondata.

### Fix

- `schemas.Project` espone `aziende_coinvolte` e `allievi_coinvolti` in forma
  compatta (`AziendaCoinvolta`, `AllievoCoinvolto`). `AllievoCoinvolto` porta
  `azienda_cliente_id`, così l'albero azienda→allievi di UX-9 non richiede una
  seconda chiamata.
- **N+1 corretto per strada**: `Project.azienda_ids` leggeva `azienda_links`
  (`lazy="select"`, non eager-caricata) invece di `aziende_coinvolte` — stessa
  tabella, ma solo la seconda è in `selectinload`. Il listing progetti faceva
  una query per riga. Introdotto con NEW-030, coperto ora da un test che conta
  le query eseguite.
- Frontend: la scheda dichiara il conteggio e nomina i primi 5
  (`riepilogoAssociati`). L'elenco esteso con centinaia di allievi è
  illeggibile: l'albero per azienda arriva con UX-9.
- 10 test backend + 6 frontend.
- Commit: `fix(UX-7): ...`
- Stato: **codice chiuso il 2026-07-27**. Nessun recupero dati necessario: le
  associazioni erano già sulla relazione canonica. Resta però l'interazione con
  il GATE UX-6 — vedi sotto.

### ⚠️ Interazione con il GATE UX-6

Il progetto 12 (doppione da eliminare secondo UX-6) è **l'unico dell'intero
sistema ad avere allievi associati**: 4 su 4. `allievo_project.project_id` ha
`ON DELETE CASCADE`, quindi eliminarlo porterebbe via quelle righe in silenzio.
La proposta di bonifica (`audit/UX6_BONIFICA_PROPOSTA.md`) è stata aggiornata:
il travaso degli allievi al progetto 11 è ora parte obbligatoria del blocco A.

---

## 2026-07-28 | UX-8 | Chiuso: la dissociazione dal progetto passa dalle guardie

Il PUT progetto dissociava in silenzio (replace secco della lista di id in
`crud._sync_project_allievi` / `_sync_project_azienda_links`): bastava omettere
un id per staccare un allievo con l'attestato già emesso, senza controlli e
senza traccia. Chiuso con `99213df` (backend) e `dd834a0` (UI).

Guardie, decise con l'utente: `attestato_emesso` blocca in modo **assoluto**;
`ore_frequentate > 0` e righe in `dati_retributivi` bloccano ma sono
**forzabili** dal solo admin con motivo ≥ 10 caratteri; un'azienda che porta
ancora suoi allievi sul progetto **non si stacca** (nessuna cascata implicita).

**Confutazione live eseguita il 2026-07-28** su due progetti di prova creati e
poi cancellati (id 14 e 15; DB riportato a 7 progetti / 8 righe
`allievo_project`, stato identico a prima). Non bastava una prova sul dato
reale: tutti gli 8 link hanno `ore_frequentate = 0`, `attestato_emesso = false`
e `dati_retributivi` è vuota, quindi **nessuna guardia sarebbe scattata** e il
"passa" non avrebbe dimostrato nulla.

| Prova live | Esito |
|---|---|
| DELETE allievo con attestato | 409, `forzabile: false` |
| DELETE allievo con attestato **con `forza`** da admin | 409 lo stesso |
| DELETE allievo con 12 ore, senza forza | 409, `forzabile: true` |
| Forzatura tentata da **operatore** | 403 |
| DELETE da **consultazione** | 403 (GET progetto: 200) |
| Forzatura con motivo di 5 caratteri | 422 |
| Forzatura con motivo valido, da admin | 200, riga rimossa |
| DELETE azienda con 2 suoi allievi sul progetto | 409, elenca i due nomi |
| PUT che omette l'allievo con attestato (porta laterale) | 409 |
| **Stesso allievo su un altro progetto senza attestato** | **200** |

L'ultima riga è quella che conta: prova che la guardia legge il link
`(progetto, allievo)` e non l'allievo in assoluto. Audit verificato in
`audit_log`: 5 righe `esito='blocked'` e 1 `esito='success'` con il motivo.

### Nuovo — il 403 sulla forzatura non lascia traccia

`_valida_forzatura` in `backend/routers/projects.py` risponde 403 **prima**
delle guardie, quindi un operatore che prova a forzare una dissociazione non
compare in `audit_log`. Gli esiti bloccati dalle guardie sono invece registrati.
Un tentativo di superare un limite di ruolo è esattamente ciò che un audit di
sicurezza vuole vedere: va aggiunta la riga `esito="denied"`. Non urgente
(l'azione è respinta), non corretto qui per non allargare il commit.

### Nuovo — `DELETE /projects/{id}` è un soft-delete che si annuncia come eliminazione

`crud.delete_project` imposta `is_active = False` e il router risponde
*"Progetto eliminato con successo"*. Il progetto sparisce dagli elenchi (che
filtrano `is_active`) ma **conserva tutte le associazioni**: allievi e aziende
restano attaccati a un progetto che l'operatore crede eliminato, e le guardie
UX-8 non vengono mai interrogate. Osservato in questa sessione: i due progetti
di prova "eliminati" via API erano ancora lì con i loro link, ed è servito un
DELETE mirato in SQL per rimuoverli davvero.

Due cose da decidere (non fatte): il messaggio deve dire *disattivato*, e va
stabilito se disattivare un progetto debba passare dalle stesse guardie o
dichiarare esplicitamente cosa resta attaccato.

### Da segnalare all'utente, non causato da UX-8

Il progetto **11** (quello "buono" secondo la bonifica UX-6 blocco A, che ha
ricevuto CUP e allievi) ha `is_active = false`, mentre il doppione **12** è
attivo. Nel gestionale l'elenco di default mostra quindi il doppione e nasconde
il progetto bonificato. Verificato in questa sessione, nessuna modifica fatta.

---

## 2026-07-28 | UX-9 | Chiuso: allievi raggruppati per azienda, in selezione e in lettura

Chiuso con `9ecf868`. Il form progetto sceglieva gli allievi con due select
"scegli → aggiungi → ripeti" e la scheda li riassumeva per nome: con quattro
allievi regge, con qualche centinaio no. `AlberoAllievi` raggruppa per
`Allievo.azienda_cliente_id` — che l'API espone già dentro `allievi_coinvolti`
(UX-7) — e serve sia la selezione sia la lettura dentro il pannello UX-8.

**Regola di dominio applicata**: spuntare un allievo associa anche la sua
azienda (un iscritto senza la sua azienda sul progetto non esiste); togliere
l'ultimo allievo **non** stacca l'azienda, che può restare coinvolta senza
iscritti. È lo stesso vincolo che UX-8 applica in uscita, dove l'azienda con
suoi allievi associati non si dissocia.

### Nuovo, corretto qui — il form mostrava solo i primi 100 allievi

`ProjectManager` chiamava `getAllievi({ limit: 100, page: 1 })` e **ignorava
`total`, `pages` e `has_next`** della risposta paginata. Oltre il centesimo
allievo, il form ne nascondeva l'esistenza senza dirlo: un operatore che non
trovava un nominativo non aveva modo di capire perché. Con 4 allievi in archivio
il difetto era invisibile.

`caricaTuttiGliAllievi` segue le pagine fino a `has_next`, si ferma a un tetto
di 20 pagine (2000 allievi) e restituisce `troncato`, che l'albero dichiara a
schermo invece di far finta di niente.

**Verifica live del contratto di paginazione** (2026-07-28, dati reali): con
`limit=100` l'API risponde `total=4, pages=1, has_next=false`; forzando
`limit=2`, pagina 1 → `has_next=true, ids [4,6]`, pagina 2 → `has_next=false,
ids [3,5]`. Il campo su cui si appoggia il caricamento è reale e disgiunto, non
dedotto dal conteggio.

### Confutazione

- **Mutation check**: rimossa l'auto-associazione dell'azienda in
  `toggleAllievo` ⇒ 1 test rosso. Ripristinato.
- **La build ha trovato ciò che i test non vedevano**: rimossi i due select, i
  setter `setAziendaToAdd`/`setAllievoToAdd` restavano chiamati in `resetForm` e
  `startEdit`; 206 test passavano lo stesso, `react-scripts build` è fallito con
  `no-undef`. Corretto prima del commit — la suite verde non basta come prova.
- **Bundle servito** (`main.1f332f0e.js`): contiene `albero-allievi`, il gruppo
  "Allievi senza azienda", l'avviso "Elenco parziale", il contatore
  `"".concat(t.scelti," di ").concat(t.totali," allievi")` e la chiamata
  paginata a `/allievi/`.
- **Limite dichiarato**: nessuna verifica con browser reale; il comportamento a
  centinaia di allievi è provato dai test unitari e dal contratto API, non
  dall'uso.

---

## 2026-07-28 | NEW-040 | Test frontend UX-6 verdi ma con aggiornamenti asincroni fuori da `act`

- Area: frontend / qualità test React
- Severità stimata: bassa (nessun difetto runtime dimostrato)
- Emerso durante: ripetizione confutativa del GATE UX-6.
- Descrizione: `FapiUpload.test.js` passa (`6 passed`), ma React segnala più
  aggiornamenti di stato di `ConvenzioneModal` e
  `AmmissioneFondimpresaModal` non racchiusi/attesi tramite `act(...)`.
  Compare anche il warning di deprecazione di `ReactDOMTestUtils.act`.
- Impatto: la copertura funzionale corrente resta verde e le asserzioni
  principali attendono il risultato, ma l'output rumoroso può nascondere
  warning nuovi e rende meno forte il test come prova di assenza di race UI.
- Proposta: aggiornare gli helper del test a interazioni asincrone
  `userEvent`/`waitFor` coerenti con React Testing Library e azzerare i warning,
  senza cambiare il codice di produzione.
- Stato: **chiuso in UX-6b**. Upload e conferme sono ora attesi tramite
  `React.act`; eliminati tutti i warning "update ... not wrapped in act".
  Resta un solo warning di deprecazione emesso internamente dalla versione
  installata di React Testing Library (`ReactDOMTestUtils.act`), non dal test
  applicativo.

---

## 2026-07-28 | NEW-041 | I codici progetto FAPI per beneficiaria non hanno un modello persistente

- Area: dominio formazione finanziata / dati progetto-beneficiaria
- Severità stimata: alta (perdita strutturata di dati estratti)
- Emerso durante: UX-6b, verifica della convenzione reale del progetto 11.
- Evidenza:
  - la convenzione contiene 5 codici progetto distinti, uno per riga
    beneficiaria, con partecipanti e totale;
  - `azienda_cliente_projects` rappresenta il coinvolgimento della beneficiaria
    e la compliance aiuti, ma non codice, partecipanti o totale;
  - `ModuloFormativo.codice_progetto_fapi` ripete il codice sui moduli, ma nel
    progetto 11 tutti i moduli hanno `azienda_beneficiaria_id = NULL`;
  - quindi non è possibile ricostruire in modo affidabile la relazione
    codice→beneficiaria→moduli.
- Rischio: salvare i valori direttamente sul link azienda-progetto imporrebbe
  artificialmente un solo codice per azienda. Il caso reale è 1:1, ma il
  modello non deve impedire più interventi/codici per la stessa beneficiaria.
- Proposta: nuova entità figlia `InterventoBeneficiario`, collegata al piano
  (`Project`) e al link beneficiaria, con codice esterno del fondo,
  partecipanti approvati, costo totale, metadati di fonte; i moduli puntano
  all'intervento. Specifica completa in
  `audit/UX6B_GATE_CODICI_PROGETTO.md`.
- Stato: **GATE DOMINIO aperto**. Nessuna migration o persistenza di questi
  valori implementata prima della decisione utente. La UI li mostra
  esplicitamente come estratti ma non salvati.

---

## 2026-07-28 | NEW-042 | Parser convenzione dipendeva dalla posizione fisica degli allegati

- Area: import documenti / FAPI
- Severità stimata: alta
- Emerso durante: confutazione UX-6b sul PDF reale già archiviato.
- Causa: il parser leggeva dati piano solo da pagina 1, Allegato A dalla
  penultima e Allegato B dall'ultima. Il file firmato reale ha due pagine firma
  vuote iniziali e Allegato C finale.
- Effetto osservato prima del fix: codice piano/delibera/ente assenti, 0 aziende
  e nomi azienda potenzialmente scambiati per codici.
- Fix: ricerca dei dati su tutto il testo e riconoscimento Allegati A/B tramite
  intestazioni semantiche; Allegato C escluso perché non ha
  `Codice Progetto`/partecipanti.
- Confutazione reale dopo il fix: piano `20250611CMIA001`, delibera 7 del
  24/03/2026, ente NEXT GROUP, 5 codici, 5 beneficiarie, tutti gli importi e
  partecipanti, zero warning.
- Stato: **chiuso**, coperto da due test dedicati.

---

## 2026-07-28 | NEW-043 | Cockpit emetteva un 401 transitorio prima del refresh

- Area: autenticazione frontend
- Severità stimata: media
- Evidenza: 401 su `/api/v1/cockpit/decisioni` con sessione apparentemente
  attiva.
- Diagnosi confutata:
  - `HomeCockpit` usa `http.get`, non una `fetch` diretta;
  - il grep di `frontend/src` trova una sola `fetch`, nel portale pubblico con
    magic token, non nel gestionale autenticato;
  - la matrice backend ammette GET cockpit ad admin, operatore e consultazione,
    quindi non è un 401 usato impropriamente al posto di 403;
  - il client rinnovava il token soltanto *dopo* la prima risposta 401.
- Fix: l'interceptor request controlla la scadenza JWT e condivide il refresh
  prima di inviare la richiesta applicativa; il retry 401 resta come rete di
  sicurezza.
- Stato: **chiuso**, test RED→GREEN specifico sul cockpit più prova delle
  richieste concorrenti.
