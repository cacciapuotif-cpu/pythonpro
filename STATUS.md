# PythonPro — Status & Development Context
_Ultimo aggiornamento: 2026-04-04_

## Sessione 2026-04-06

### Fix creazione progetti
- Individuato blocco reale nel layer frontend context:
  - `frontend/src/context/AppContext.js` usava import dinamici errati del servizio API con `const { apiService } = await import(...)`
  - `apiService` e invece export `default`, quindi le CRUD via context potevano fallire prima di colpire l'API reale
- Corretto il wiring usando `const { default: apiService } = await import(...)` nei punti CRUD/auth coinvolti.
- Impatto atteso:
  - creazione progetto ripristinata
  - update/delete tramite context riallineati allo stesso fix

### Fix navigazione Piani Finanziari
- Verificato che la UI caricava ancora il modulo legacy `PianoFinanziarioManager`, che mostrava filtri `progetto/stato`.
- Corretto `frontend/src/App.js` per montare `frontend/src/components/PianiFinanziariHub.js` sulla sezione `piani-finanziari`.
- La logica attesa ora e:
  - prima `ente erogatore`
  - poi `avviso`
  - poi `progetto`

### Fix dashboard agenti e allineamento API agenti
- Individuato crash frontend in `frontend/src/components/AgentsDashboard.js`:
  - il componente trattava `apiService` come istanza axios (`apiService.get/post`)
  - il file `services/apiService.js` espone invece helper/metodi applicativi
- Corretto `AgentsDashboard.js` per usare:
  - `getAgentsCatalog()`
  - `getAgentRuns()`
  - `runAgentByType()`
- Allineato anche il backend agenti per compatibilita con il frontend esistente:
  - endpoint `GET /api/v1/agents/`
  - endpoint `GET /api/v1/agents/llm/health`
  - endpoint `POST /api/v1/agents/run`
  - alias/endpoint per `accept`, `reject`, `workflow`, update stato comunicazioni
- Aggiornati schema e export agenti per tollerare il mix tra campi workflow e campi legacy registry.

### Verifiche eseguite
- `python3 -m py_compile` passato su:
  - `backend/routers/agents.py`
  - `backend/ai_agents/__init__.py`
  - `backend/schemas.py`
- Non eseguita build frontend completa in questa sessione.
- Non eseguito test browser end-to-end in questa sessione.

### Stato dopo i fix di oggi
- Probabile blocco principale sulla creazione progetti frontend risolto.
- Modulo `Piani Finanziari` riallineato alla UX richiesta.
- `AgentsDashboard` non dovrebbe piu crashare per chiamate API errate lato frontend.
- Resta da verificare a runtime se gli endpoint agenti eliminano anche i `500` osservati nella console sulle liste `runs/suggestions`.

### Pendenti immediati
- [ ] Verificare da browser:
  - creazione nuovo progetto
  - percorso `Piani Finanziari`
  - schermata `Agents Dashboard`
  - schermata `Agenti`
- [ ] Validare che `GET /api/v1/agents/runs/` e `GET /api/v1/agents/suggestions/` non producano piu `500`
- [ ] Ripulire `backend/schemas.py`, ancora noto come file con duplicati e shadowing storico
- [ ] Valutare build frontend completa per intercettare eventuali regressioni residue
- [ ] Aggiornare eventualmente i test frontend/backend sui flussi agenti e piani finanziari

## Sessione 2026-04-05

### Audit completo repository e report certificazione
- Eseguito audit profondo su backend, frontend, database, test, migrazioni e dominio piani finanziari.
- Report salvato in `docs/AUDIT_REPORT_CERTIFICAZIONE.md`.

### Esito audit
- Stato generale classificato `CRITICAL`.
- Problemi critici principali emersi:
  - backend non avviabile per import error agentico: `get_agent_definition` non esportato da `ai_agents`
  - mismatch modello/database su `AgentReviewAction` (`reviewed_by` assente nel DB reale)
  - `backend/schemas.py` contiene duplicati reali con shadowing per blocchi `PianoFinanziario`, `VocePianoFinanziario`, `AgentRun`, `AgentSuggestion`, `AgentReviewAction`
  - frontend non compilabile: `App.js` importa `./components/AgentsDashboard` ma il file non esiste
  - test suite backend non eseguibile nel container per opzioni `--cov` presenti in `pytest.ini` senza plugin coverage installato

### Stato piani finanziari verificato
- I 3 template obbligatori sono presenti nel DB:
  - `formazienda`
  - `fapi`
  - `fondimpresa`
- Nessun `AvvisoPianoFinanziario` presente nel DB al momento dell'audit.
- Esistono 2 piani finanziari e 54 voci piano.
- Sui dati reali correnti il requisito `Assignment -> VocePianoFinanziario` non risulta ancora soddisfatto:
  - 4 assegnazioni attive sul progetto `Progetto Test`
  - 0 voci con `assignment_id` valorizzato
  - nessuna assegnazione esistente ha trovato una voce corrispondente nel piano
- Il nuovo codice di auto-collegamento e presente in `crud.create_assignment`, ma manca il backfill dei record gia esistenti.

### Verifiche runtime eseguite
- DB raggiungibile via container one-shot:
  - `SELECT 1` OK
  - tabelle principali presenti
- Integrita relazionale base verificata:
  - 0 presenze orfane
  - 0 assegnazioni orfane
  - 0 progetti con ente invalido
- Tutti i `curl` su `localhost:8000` falliscono per backend non in ascolto, coerente col crash in bootstrap agenti.
- `npm run build` frontend fallisce per modulo mancante `AgentsDashboard`.

### Prossimi passi consigliati dopo audit
- [ ] Sistemare il bootstrap agentico (`backend/ai_agents/__init__.py` / `agent_workflows.py`) per far ripartire il backend
- [ ] Allineare schema DB e modello `AgentReviewAction` con migration dedicata
- [ ] Ripulire `backend/schemas.py` eliminando i duplicati shadowed
- [ ] Ripristinare o rimuovere `AgentsDashboard` dal frontend per far tornare verde la build
- [ ] Rendere eseguibile la suite test installando `pytest-cov` oppure correggendo `pytest.ini`
- [ ] Creare uno script di backfill `Assignment -> VocePianoFinanziario` e ricalcolo `Attendance -> importo_rendicontato`
- [ ] Configurare almeno un avviso per ciascun template piano finanziario

### Sistema completo Piani Finanziari esteso
- Introdotti nel backend i nuovi modelli dedicati alla formazione finanziata:
  - `TemplatePianoFinanziario`
  - `AvvisoPianoFinanziario`
  - estensioni retrocompatibili su `PianoFinanziario`
  - estensioni retrocompatibili su `VocePianoFinanziario`
- I nuovi template sono separati dal dominio `ContractTemplate`, evitando di mescolare i template contrattuali con quelli economici.
- `PianoFinanziario` ora traccia anche:
  - `codice_piano`
  - `budget_approvato`
  - `budget_rimanente`
  - `data_approvazione`
  - `data_rendicontazione`
  - `note_ente`
- `VocePianoFinanziario` ora supporta automazione per mansioni/presenze con:
  - `assignment_id`
  - `mansione_riferimento`
  - `sottocategoria`
  - `ore_previste`
  - `ore_effettive`
  - `tariffa_oraria`
  - `importo_approvato`
  - `importo_validato`
  - `stato`
  - `note`

### Automazioni operative implementate
- `create_assignment` e `update_assignment` ora tentano il collegamento automatico dell'assegnazione alla voce del piano finanziario del progetto.
- Aggiunta in `crud.py` la funzione chiave `collega_assegnazione_a_piano(...)`:
  - trova il piano del progetto
  - mappa la mansione a categoria/macrovoce
  - collega o crea la voce piano
  - aggiorna importi previsti e consuntivi
- `create_attendance` e `update_attendance` ora ricalcolano automaticamente la voce piano collegata tramite `assignment_id`.
- Aggiunta `aggiorna_voce_da_presenze(...)` per riallineare `ore_effettive` e `importo_consuntivo`.

### API e bootstrap aggiunti
- Esteso `backend/routers/piani_finanziari.py` con:
  - CRUD Template Piani
  - CRUD Avvisi Piani
  - endpoint `assignments/{assignment_id}/collega-mansione`
  - endpoint `voci/{voce_id}/aggiorna-da-presenze`
  - alias `riepilogo-budget`
- Creato script `backend/scripts/init_templates.py`.
- Creati e inizializzati i 3 template obbligatori:
  - `FORMAZIENDA_STD`
  - `FAPI_STD`
  - `FONDIMPRESA_STD`

### Migrazione DB eseguita
- Creata migration manuale `029_add_complete_piani_finanziari_structure.py`.
- Corretto il revision id per compatibilita con il vincolo `alembic_version.version_num` del DB.
- Verificata applicazione migration tramite container one-shot: completata con successo.

### Verifiche eseguite
- `python3 -m py_compile` passato su:
  - `backend/models.py`
  - `backend/schemas.py`
  - `backend/crud.py`
  - `backend/routers/piani_finanziari.py`
  - `backend/scripts/init_templates.py`
  - migration Alembic nuova
- Verifica one-shot nel container:
  - import modelli nuovo dominio OK
  - `template-count = 3`
  - template presenti: Formazienda, FAPI, Fondimpresa

### Blocco residuo fuori perimetro piani
- Il test finale HTTP via API non e stato completabile per un problema gia presente e indipendente da questo lavoro:
  - import error in bootstrap app: `ImportError: cannot import name 'get_agent_definition' from 'ai_agents'`
- Il backend continua quindi a fallire in avvio Gunicorn/FASTAPI per il modulo agentico, anche se migration e verifiche one-shot DB sono andate a buon fine.

### Prossimi passi consigliati
- [ ] Sistemare il bootstrap agentico (`ai_agents` / `agent_workflows`) per ripristinare l'avvio dell'app
- [ ] Testare via HTTP gli endpoint nuovi `/api/v1/piani-finanziari/templates/` e `/api/v1/piani-finanziari/avvisi/`
- [ ] Collegare la UI React ai nuovi CRUD Template/Avvisi
- [ ] Aggiungere test backend dedicati per:
  - auto-collegamento assignment -> voce piano
  - aggiornamento attendance -> importo rendicontato
  - coerenza budget utilizzato/rimanente
- [ ] Valutare se migrare progressivamente la UI piano esistente dal modello legacy ai nuovi template/avvisi dedicati

### Modello `AgentReviewAction` riallineato (`backend/models.py`)
- Nel blocco AI agent e stato aggiornato il modello `AgentReviewAction` subito dopo `AgentSuggestion` per tracciare le azioni dell'operatore sui suggerimenti.
- Schema ora allineato ai campi richiesti:
  - `suggestion_id`
  - `action`
  - `reviewed_by`
  - `reviewed_at`
  - `notes`
  - `auto_fix_applied`
  - `result_success`
  - `result_message`
- Mantenuta la relazione `suggestion = relationship("AgentSuggestion", back_populates="review_actions")`.
- Aggiunto validatore `@validates("action")` con soli valori ammessi: `approved`, `rejected`, `deferred`, `implemented`.

### Pendente immediato
- Allineare o creare la migration Alembic relativa a `agent_review_actions`, perche il modello precedente usava campi diversi (`reviewed_by_user_id`, `created_at`) e il database potrebbe non riflettere ancora il nuovo schema.

## Sessione 2026-04-04

### Modello `PianoFinanziario` esteso (`models.py:596`)
- Il modello esistente era già presente ma incompleto. Aggiunti i campi mancanti:
  - `nome: String(200)` (default `""`)
  - `tipo_fondo: String(50)` con `@validates` — valori: `formazienda`, `fondimpresa`, `fse`, `altro`
  - `budget_totale: Float`, `budget_utilizzato: Float`
  - `data_inizio: DateTime`, `data_fine: DateTime`
  - `stato: String(20)` con `@validates` — valori: `bozza`, `approvato`, `in_corso`, `rendicontato`, `chiuso`
  - `note: Text`
- Aggiunti 3 nuovi indici: `(progetto_id, stato)`, `(tipo_fondo, stato)`, `(data_inizio, data_fine)`

### Modello `VocePianoFinanziario` esteso (`models.py:658`)
- Aggiunti al modello esistente:
  - `categoria: String(100)` con `@validates` — valori: `docenza`, `tutoraggio`, `coordinamento`, `materiali`, `aula`, `altro`
  - `descrizione` promossa da `String(255)` a `Text`
  - Proprietà Python: `importo_previsto` (alias `importo_preventivo`), `importo_rendicontato` (alias `importo_consuntivo`), `importo_rimanente`, `percentuale_utilizzo`
  - Relationship alias `collaboratore` → `collaborator`
  - Nuovo indice `(piano_id, categoria)`

### Migration `528d59380940` applicata
- Autogenerate Alembic aveva incluso operazioni pericolose non correlate (incluso `DROP TABLE users`).
- File riscritto manualmente per includere solo le modifiche effettive.
- `server_default` aggiunti ai campi NOT NULL per compatibilità con righe esistenti.
- `alembic upgrade head` applicato con successo — DB a head `528d59380940`.
- Verificata presenza colonne sul DB con `inspect(engine)`.

### Schemas Pydantic aggiunti (`schemas.py`, fondo file)
- **VocePianoFinanziario** (4 classi): `Base`, `Create`, `Update`, `VocePianoFinanziario` con 4 `@computed_field` (`importo_previsto`, `importo_rendicontato`, `importo_rimanente`, `percentuale_utilizzo`)
- **PianoFinanziario** (5 classi): `Base` con `field_validator` su `data_fine > data_inizio`, `Create`, `Update` (tutti Optional), `PianoFinanziario`, `PianoFinanziarioWithVoci`
- Usa `Literal` per `TIPO_FONDO`, `STATO_PIANO`, `CATEGORIA_VOCE`
- Verifica: `import schemas` + test istanziazione in container → OK

### Stato sistema fine sessione 2026-04-04
- Backend Docker: in esecuzione
- DB: migration head `528d59380940`
- Ultimo `py_compile` / import check: passato
- **Prossimi step suggeriti**:
  - Aggiungere router FastAPI `piani_finanziari` con endpoint CRUD + riepilogo budget
  - Aggiungere CRUD in `crud.py` per PianoFinanziario e VocePianoFinanziario
  - Collegare il campo `tipo_fondo` nella UI del `PianiFinanziariHub` (oggi usa solo `ente_erogatore`)

## Aggiornamento audit tecnico ERP
- Eseguito audit architetturale del repository con focus su schema dati, vincoli di business, maturita moduli e predisposizione agenti AI.
- Deliverable salvato in `docs/AUDIT_TECNICO_ERP_2026-04-04.md`.
- Creato anche backlog operativo eseguibile in `docs/BACKLOG_IMPLEMENTATIVO_ERP_2026-04-04.md`.
- Esito sintetico:
  - base dominio gia forte per ERP verticale formazione finanziata
  - moduli core piu maturi: collaboratori, progetti, enti, assegnazioni, presenze, template documentali, piani finanziari, reporting base, AI agent core
  - gap principali: workflow end-to-end, rendicontazione automatica, gestione documentale avanzata, integrazioni esterne robuste, test business-critical
  - agenti AI gia predisposti in modo reale, ma ancora da portare a piena autonomia governata tramite eventi, policy, scheduler e metriche
- Priorita tecniche emerse dall'audit:
  - chiudere workflow operativi tra moduli esistenti
  - centralizzare regole di business critiche
  - estendere test sulle regole di overlap/date/costi/budget
  - completare i connettori outbound e la macchina a stati dei workflow agentici
- Prossimo step raccomandato:
  - aprire Epic 1 del backlog: `Workflow Documentale Collaboratore`
  - primo flusso da chiudere a codice: `documenti mancanti -> task operatore -> richiesta -> sollecito -> chiusura automatica su upload`

## Dove siamo
- Progetto gestionale multi-modulo per collaboratori, progetti formativi, presenze, enti attuatori, associazioni progetto-mansione-ente, template contratti e reportistica.
- Stack confermato: backend FastAPI + SQLAlchemy/PostgreSQL + Redis, frontend React 18, mobile app Expo/React Native, deploy Docker Compose, monitoring dedicato.
- Repository in fase di sviluppo avanzata ma con worktree locale molto sporco: ci sono numerose modifiche non committate su backend, frontend, CI, deploy, documentazione e file ambiente.

## Architettura rilevata
- `backend/`: API FastAPI principale con router modulari in `backend/routers/`.
- Router presenti: `auth`, `collaborators`, `projects`, `attendances`, `assignments`, `implementing_entities`, `progetto_mansione_ente`, `contract_templates`, `reporting`, `admin`, `system`.
- `backend/main.py` include registrazione router, gestione errori centralizzata, CORS aperto, middleware dedicati e aggiornamenti schema runtime per colonne mancanti.
- `frontend/`: applicazione React con sezioni principali per calendario, collaboratori, progetti, enti, associazioni, timesheet, template contratti, dashboard; presente login con ruoli `admin`, `user`, `manager`.
- `mobile/`: app Expo separata, descritta come MVP iOS-first con autenticazione, lista/dettaglio item e client API tipizzato.
- `deploy/`, `docker-compose.yml`, `docker-compose.prod.yml`, `monitoring/`: infrastruttura di esecuzione e osservabilità già predisposta.

## Stato reale del repository
- `README.md` descrive una versione `3.0.0` con avvio Docker e ambiente Windows/WSL2.
- `backend/pyproject.toml` conferma Python `>=3.11`, dipendenze FastAPI/SQLAlchemy/Alembic/Redis e tool dev completi.
- `docs/IMPLEMENTATION_STATUS.json` dichiara una precedente milestone completata con 7 router e 29 test passati, ma oggi il codice reale va considerato oltre quella fotografia: i router attuali sono più numerosi e il worktree è cambiato molto.
- Ultimo commit visibile: `6c595e5 backup database`; non rappresenta uno stato applicativo pulito o pronto per rilascio.
- Sono presenti nuove aggiunte non tracciate o recenti in backend, inclusi:
  - `backend/alembic/versions/003_add_document_expiry_to_collaborators.py`
  - `backend/routers/auth.py`
  - `backend/run_backup.py`

## Modifiche locali già presenti
- Backend: toccati `main.py`, `crud.py`, `models.py`, `schemas.py`, `file_upload.py`, Dockerfile, requirements e vari router.
- Frontend: toccati `App.js`, `App.css`, modali, manager principali, hook upload documenti, layer API/HTTP.
- Infrastruttura: modificati `docker-compose.yml`, `deploy/docker-compose.yml`, workflow GitHub Actions e script di avvio/test/smoke.
- Documentazione e file `.env*`: molte variazioni locali, più numerose cancellazioni di report temporanei e backup.

## Decisioni prese in questa sessione
- Avviata una nuova estensione funzionale sul binomio `Piano Finanziario` + `Template` senza riesplorare il repo da zero.
- Decisione utente esplicita da mantenere: le voci del `Piano Finanziario` devono diventare la fonte delle mansioni selezionabili nelle assegnazioni collaboratore, cosi ore/costi/contratti vengono imputati alla corretta voce di piano.
- Avviato il refactor del modal assegnazioni: `AssignmentModal` non deve piu proporre una lista statica di mansioni ma leggere le righe attive da `/api/v1/project-assignments` del progetto selezionato.
- Avviato il refactor del `Piano Finanziario Progetto`: aggiunta aggregazione per mansione/tipo contratto a partire dalle `assignments` per confrontare pianificato vs contrattualizzato.
- Avviata l'estensione del dominio template da "solo contratti" a "template documentali": aggiunti nel backend campi opzionali `ambito_template`, `chiave_documento`, `ente_attuatore_id`, `progetto_id` su `contract_templates`, con supporto runtime schema in `backend/main.py`.
- Aggiornati naming e UX in corso su frontend: la voce di navigazione e la sezione admin devono convergere verso `Template` / `Template Documenti`, non solo `Template Contratti`.
- Ripreso il perimetro `Template Documenti` senza riesplorare il repo: corretto il modal frontend per distinguere davvero `contratto` vs ambiti documentali (`preventivo`, `ordine`, `generico`) pur mantenendo la compatibilita col backend attuale.
- Decisione operativa esplicita: finche backend/schema restano vincolati a `tipo_contratto` obbligatorio, i template non contrattuali devono usare tecnicamente `documento_generico`; la distinzione funzionale va affidata a `ambito_template` + `chiave_documento`.
- Disabilitato lato UI il flag `is_default` per i template non contrattuali, per evitare collisioni semantiche con il vincolo backend attuale che gestisce il default per `tipo_contratto`.
- Aggiunta validazione frontend: per template non contrattuali `chiave_documento` e ora richiesta; il campo tipo viene bloccato su `documento_generico` e la copy del modal e stata riallineata al concetto di documento, non solo contratto.
- Completato il riallineamento della lista `Template Documenti`: `ContractTemplatesManager` ora tratta i template non contrattuali come documenti classificati per `ambito_template` + `chiave_documento`, evita badge `default` fuorvianti fuori dal perimetro contratti, estende la ricerca alla chiave documento e rende coerenti i filtri tipo/ambito.
- Aggiunto adattamento automatico dei filtri in `ContractTemplatesManager`: passando da `contratto` agli altri ambiti, il filtro tipo converge su `documento_generico` invece di lasciare combinazioni incoerenti e liste apparentemente vuote.
- Verifica eseguita con `npm run build`: build frontend riuscita anche dopo il fix template documentali; restano solo warning dataset browser (`baseline-browser-mapping`, `caniuse-lite`) non bloccanti.
- Verifica rieseguita dopo l'allineamento del manager template: `npm run build` ancora OK.
- Implementato il nuovo modulo `Piano Finanziario` Formazienda end-to-end, senza riesplorare il repo da zero: aggiunti modello dati, migration `008`, CRUD, router FastAPI dedicato e pagina React operativa collegata alla sezione admin `Piano Finanziario`.
- Database/backend aggiunti:
  - `backend/piano_finanziario_config.py` con catalogo macrovoci/voci e template base del piano.
  - `backend/models.py` con `PianoFinanziario` e `VocePianoFinanziario`, relazione su `Project`.
  - `backend/schemas.py` con schemi piano/voci/riepilogo e `computed_field` per `% consuntivo` di riga.
  - `backend/crud.py` con create piano da template, bulk upsert voci, riepilogo e validazioni principali.
  - `backend/routers/piani_finanziari.py` con endpoint `GET/POST /api/v1/piani-finanziari`, `GET /{id}`, `PUT /{id}/voci`, `GET /{id}/riepilogo`, `GET /{id}/export-excel`.
  - `backend/alembic/versions/008_add_piani_finanziari.py`.
- Validazioni backend implementate:
  - soglie Macrovoce A/B/C sul totale consuntivo;
  - controllo C.6 sul 10% del totale preventivo;
  - Macrovoce D solo come cofinanziamento nel riepilogo;
  - limite max 15 edizioni per progetto su voci dinamiche `B.2` e `B.3`;
  - rimozione/aggiornamento bulk coerente delle voci del piano.
- Export Excel implementato con `openpyxl`: sezioni A/B/C/D, header dedicati, formule Excel per totali di macrovoce, totale generale, contributo richiesto, cofinanziamento e colonna percentuale.
- Frontend aggiunto:
  - `frontend/src/components/PianiFinanziariManager.js` + `.css`
  - integrazione in `App.js` sulla sezione `progetto-mansione-ente`
  - supporto API in `frontend/src/services/apiService.js`
- UX del nuovo modulo:
  - selezione progetto/piano
  - creazione piano base da template Formazienda
  - tabella editabile per macrovoci
  - gestione righe dinamiche `B.2 Docenza` e `B.3 Tutor` con `+ Aggiungi edizione`
  - riepilogo client/server con badge alert e pulsanti `Salva` / `Esporta Excel`
  - path leggero sincronizzato su `/piani-finanziari` e `/piani-finanziari/:pianoId` pur restando nell'architettura attuale senza `react-router`
- Verifiche eseguite sul nuovo modulo:
  - `python3 -m py_compile` su backend modificato → OK
  - `npm run build` frontend → OK
- Dipendenze aggiornate: aggiunto `openpyxl` a `backend/requirements.txt` e `backend/pyproject.toml`; resta da installare nell'ambiente runtime prima di usare davvero l'export Excel.
- Sessione chiusa prima della verifica finale: modifiche applicate ma non ancora validate con `py_compile`, `npm run build` e rebuild Docker frontend.
- Riallineata la UX commerciale alla decisione gia presa: `agenzie` e `consulenti` non devono piu apparire come elementi separati nella UI collaboratori; restano solo come attributi/spunte del collaboratore.
- Rimossi dalla summary strip di `CollaboratorsTable` i contatori separati `Agenzie` e `Consulenti`, che continuavano a suggerire un dominio separato non piu desiderato.
- Ricostruito e ridistribuito il frontend Docker `pythonpro_frontend`; il bundle servito su `http://localhost:3001` / `http://192.168.2.161:3001` e ora aggiornato al sorgente corrente.
- Non è stato fatto un riesplora totale del progetto: è stato usato `STATUS.md` esistente come entrypoint, poi è stato letto solo il necessario per costruire uno stato affidabile.
- Non sono state toccate le modifiche utente già presenti nel worktree.
- `STATUS.md` viene usato da ora come fonte di contesto operativa reale del progetto, non come placeholder.
- Eseguito audit full-stack profondo con prospettiva sia tecnica sia di project management.
- Eseguito test frontend disponibili: falliscono; test backend non eseguibili nell'ambiente corrente perché `pytest` non è installato.
- Completata la prima fase UX/UI suggerita: base design system leggero, shell applicativa più coerente, dashboard operativa reale e centro alert/compliance integrato nella sezione dashboard.
- La nuova dashboard usa solo endpoint verificati nel backend reale (`reporting/summary`, `reporting/timesheet`, dataset `collaborators/projects/assignments`, `admin/metrics` solo per admin) ed evita gli endpoint `analytics/*` non affidabili.
- Aggiornato `Dashboard.test.js` con test aderenti al nuovo cockpit operativo; esecuzione mirata passata con `npm test -- --watch=false --runInBand src/components/Dashboard.test.js`.
- Avviata la seconda fase UX/UI dal lato collaboratori: il vecchio form monolitico e stato convertito in wizard multi-step con progressive disclosure e checkpoint operativo laterale.
- Il wizard collaboratore mantiene compatibilita con il contratto dati esistente del manager e del flusso upload documenti; non e stato necessario riscrivere il submit backend/frontend.
- Verifica eseguita con `npm run build`: build frontend riuscita; restano solo warning ESLint preesistenti in `App.js`, `Calendar.js`, `ProgettoMansioneEnteManager.js`.
- Completato anche il wizard progetto: il form progetti e stato riorganizzato in step base, governance e delivery, mantenendo invariato il flusso CRUD esistente.
- Con wizard collaboratore + wizard progetto la seconda fase UX/UI e da considerarsi completata.
- Avviata e completata la terza fase UX/UI sul perimetro desktop principale: tabella collaboratori, cards progetto e calendario sono ora piu orientati a priorita operative e lettura rapida.
- Verifica eseguita con `npm run build`: build frontend riuscita anche dopo la terza fase; restano warning ESLint preesistenti in `App.js`, `Calendar.js`, `ProgettoMansioneEnteManager.js`.
- Ripresa la quarta fase sul perimetro collaboratori/contratti senza riesplorare il repo da zero: introdotto `contract preflight` prima della generazione PDF e prima differenziazione UX per ruolo nel manager collaboratori.
- Chiusa la prima parte del debt tecnico contratti: il frontend collaboratori ora genera dal `POST /api/v1/contracts/generate-contract` invece di usare il download legacy per assignment.
- Il contract preflight ora tratta l'assenza di `ente_attuatore_id` come blocco reale e non piu come semplice warning, coerentemente con il percorso template-based unico scelto per la UI.
- Esteso `ContractGenerationRequest` backend con `contract_signed_date` e aggiornato il router template-based per valorizzare davvero `data_firma_contratto`, `data_sottoscrizione_contratto` e `contract_signed_date` nei placeholder.
- Verifica eseguita dopo le modifiche di fase 4: `npm run build` passato; warning ESLint invariati e ancora preesistenti in `App.js`, `Calendar.js`, `ProgettoMansioneEnteManager.js`.
- Verifica aggiuntiva eseguita sul riallineamento contratti:
  - `npm run build` passato
  - `python3 -m py_compile backend/schemas.py backend/routers/contract_templates.py` passato
- Estesa la quarta fase UX/UI sul perimetro ruolo senza riesplorare il repo: shell applicativa e dashboard ora differenziano in modo piu netto amministratore vs operatore.
- La shell React imposta ora una home coerente col ruolo ripristinato o autenticato:
  - `admin` -> dashboard
  - `user` / `manager` -> collaboratori
- La navigazione espone ora un contesto operativo per ruolo con quick actions dedicate, riducendo il rumore per gli operatori.
- La dashboard include ora un pannello focus per ruolo:
  - `admin`: vista di governo del sistema con blocchi critici, metriche backend e distribuzione contratti
  - `operator`: vista operativa con documenti, preflight contratti e progetti da verificare
- Verifica eseguita dopo l'estensione UX per ruolo:
  - `npm test -- --watch=false --runInBand src/components/Dashboard.test.js` passato
  - `npm run build` passato
  - warning noti invariati: `frontend/src/App.js`, `frontend/src/components/Calendar.js`, `frontend/src/components/ProgettoMansioneEnteManager.js`
- Corretto il perimetro di visibilita della navigazione applicativa: i moduli commerciali `agenzie`, `consulenti`, `aziende-clienti`, `catalogo`, `listini`, `preventivi`, `ordini` sono ora esposti anche ai ruoli `user` e `manager`, non solo `admin`.
- Corretta anche la UX della barra di navigazione: il menu principale ora va a capo invece di nascondere le sezioni su overflow orizzontale, riducendo il rischio di tab non visibili su viewport medi o layout affollati.
- Rieseguita verifica di riallineamento sul repository reale senza riesplorazione completa: i blocchi commerciali `Catalogo`, `Listini`, `Preventivi`, `Ordini` risultano effettivamente implementati, registrati in `backend/main.py`, cablati in `frontend/src/App.js` e presenti in `frontend/src/services/apiService.js`.
- Verifica tecnica aggiuntiva eseguita nella sessione corrente:
  - `python3 -m py_compile backend/models.py backend/schemas.py backend/crud.py backend/routers/catalogo.py backend/routers/listini.py backend/routers/preventivi.py backend/routers/ordini.py backend/main.py` passato
  - `npm run build` passato
- Nessuna modifica applicativa eseguita in questa sessione: aggiornato solo il contesto di stato per allinearlo al codice realmente presente.
- Verifica eseguita dopo il fix di visibilita navigazione: `npm run build` passato.
- Migliorato il popup `Nuova Azienda Cliente`: ora usa box con altezza massima in viewport, body scrollabile interno, header/footer piu stabili e layout piu organizzato con sidebar guida + sezioni compatte.
- Riorganizzati i campi azienda per ridurre lo scroll verticale: dati legali in alto, sede e contatti affiancati, gestione finale compatta.
- Verifica eseguita dopo il refactor UX modal aziende: `npm run build` passato.
- Estesa l'anagrafica collaboratori con `is_agency` e `partita_iva`: un collaboratore puo ora essere marcato come agenzia e, se attivo, sincronizza automaticamente una voce in `agenzie`.
- Introdotta unicita sulla `partita_iva` dei collaboratori, allineata alla logica gia richiesta per il `codice_fiscale`; mantenuta unicita della `partita_iva` per aziende clienti e aggiunta anche per agenzie.
- Estesa la relazione commerciale aziende: `aziende_clienti` puo ora collegarsi sia a `agenzia` sia a `consulente`, coerentemente con il modello richiesto.
- Aggiornati frontend collaboratori/agenzie/aziende per esporre i nuovi campi e collegamenti.
- Migliorata la lista collaboratori con badge visivo `Agenzia` sia in vista tabellare sia in vista card, piu contatore sintetico delle agenzie nella summary strip.
- Riallineato il modello commerciale su richiesta utente: `Agenzie` e `Consulenti` non sono piu schede autonome in navigazione, ma attributi booleani del collaboratore.
- Esteso il dominio collaboratori con `is_consultant` lato backend/frontend; il wizard collaboratore espone ora due checkbox indipendenti (`agenzia`, `consulente`) e mantiene `partita_iva` obbligatoria solo quando e attivo il profilo agenzia.
- Riposizionata la vecchia schermata `Associazioni Progetto-Ente` come `Piano Finanziario Progetto` nella navigazione e nei testi UI.
- Aggiunto riepilogo autoalimentato nel piano finanziario quando si seleziona un progetto: ore pianificate, ore assegnate, ore effettive, budget pianificato, costo assegnato e numero righe piano.
- Il piano precompila ora l'ente dal progetto se gia presente, mantenendo comunque la possibilita di override per casi avanzati.
- Verifiche eseguite dopo questa estensione:
  - `python3 -m py_compile backend/models.py backend/schemas.py backend/crud.py backend/routers/collaborators.py backend/routers/aziende_clienti.py backend/main.py` passato
  - `npm run build` passato
- Verifiche eseguite dopo il riallineamento collaboratori/ruoli commerciali:
  - `python3 -m py_compile backend/models.py backend/schemas.py backend/main.py backend/crud.py` passato
  - `npm run build` passato
- Riallineato il dominio `Piani Finanziari` sul vincolo utente esplicito: ogni piano ha un solo fondo di riferimento, non un mix di enti/fondi nello stesso piano.
- Esteso il manager standard `Piani Finanziari` per selezionare esplicitamente il fondo del piano (`Formazienda`, `FAPI`, `Regione Campania`, `Altro`) e l'avviso, mantenendo `Fondimpresa` su modulo dedicato perche ha struttura diversa.
- Resa esplicita in UI la separazione tra piani standard e `Fondimpresa`: aggiunta voce di navigazione dedicata per `Piani Fondimpresa`, non piu solo route nascosta.
- Corretto il vincolo backend/db dei piani standard: l'unicita non e piu su solo `progetto + anno`, ma su `progetto + anno + fondo`, cosi piani distinti per fondo restano separati senza contaminare il modello.
- Aggiornati runtime index e migration `008` per riflettere il nuovo vincolo di unicita per fondo.
- Corretto il wizard `ProjectManager`: i progetti ora espongono un campo `fondo` esplicito e persistente, separato dal legacy `ente_erogatore`, cosi un progetto `FAPI` puo essere classificato correttamente e intercettato dai moduli piano.
- Migliorata la UX del salvataggio progetti: in caso di errore viene mostrato il `detail` reale del backend invece del messaggio generico frontend.
- Rivista la decisione UI sui piani: non devono esistere due maschere di navigazione separate (`standard` e `Fondimpresa`), ma una sola sezione `Piani Finanziari`.
- Implementato hub unico frontend `Piani Finanziari`: l'utente seleziona il progetto e il sistema sceglie automaticamente il layout corretto in base a `project.fondo`, con fallback a `project.ente_erogatore`.
- Rimossa dalla navigazione la separazione esplicita `Piani Fondimpresa`; il path legacy continua a convergere sulla stessa sezione unica.
- Verifiche eseguite in questa sessione:
  - `python3 -m py_compile backend/models.py backend/crud.py backend/main.py backend/alembic/versions/008_add_piani_finanziari.py` passato
  - `npm run build` passato
  - `python3 -m py_compile backend/schemas.py backend/routers/projects.py backend/crud.py` passato
  - `npm run build` passato dopo il fix `ProjectManager`
  - `npm run build` passato dopo l'unificazione della sezione `Piani Finanziari`
  - `docker compose up -d --build frontend` eseguito con successo; frontend Docker riallineato

## Sessione 2026-04-02

### Fix piani finanziari: avviso + template collegati
- Rimosso l'hardcode operativo `2/2022` dai nuovi piani standard: frontend e backend ora trattano `avviso` come dato esplicito, non come default fisso.
- Corretto il vincolo logico dei piani standard: l'unicita non e piu solo `progetto + anno + fondo`, ma `progetto + anno + fondo + avviso`, cosi lo stesso fondo puo avere piu piani distinti per avvisi diversi senza sovrascriversi o risultare invisibile.
- Esteso `PianoFinanziario` con `template_id` e aggancio automatico al template documentale di ambito `piano_finanziario`; se il template viene scelto a mano in UI viene salvato sul piano, altrimenti il backend prova a risolverlo per progetto/fondo(avviso)/ente.
- Esteso `ContractTemplate` con i nuovi campi `ente_erogatore` e `avviso`, piu il nuovo ambito `piano_finanziario`, per poter classificare i template caricati del piano finanziario e distinguerli anche quando lo stesso ente/fondo ha template diversi per avvisi diversi.
- Aggiornata la UI `Template Documenti`: nel modal template ora si possono impostare ambito `piano_finanziario`, ente erogatore e avviso; nella lista template questi dati sono visibili e ricercabili.
- Aggiornata la UI `Piani Finanziari`: aggiunta selezione `Template piano`, con autocompilazione di fondo/avviso dal template scelto e memorizzazione del collegamento sul piano.
- Migliorato l'autoselect del piano in contesto embedded/forzato: quando esistono piu piani dello stesso fondo, la scelta considera anche l'avviso e non solo il fondo.
- Verifiche eseguite:
  - `python3 -m py_compile backend/models.py backend/schemas.py backend/crud.py backend/main.py backend/routers/contract_templates.py backend/routers/piani_finanziari.py backend/alembic/versions/010_link_piani_templates_by_avviso.py` passato
  - `npm run build` passato
- Pendente residuo collegato:
  - verificare sul database reale se esistono piani/template storici creati con `avviso = 2/2022` di default da riallineare manualmente ai valori corretti, per evitare che dati vecchi continuino a mostrarsi con l'avviso sbagliato

### Pulizia navigazione e rimozione file morti
- Eliminati 7 file di componenti non piu usati: `AgenzieManager.js/css`, `ConsulentiManager.js/css`, `ProgettoMansioneEnteManager.js/css`, `CalendarSimple.js`.
- Navigazione App.js completamente rifatta: rimosso il `nav-role-strip` verboso (~80px inutili) e introdotto raggruppamento visuale per area con separatori verticali: `Dashboard | Attività [Calendario, Timesheet] | Persone [Collaboratori, Progetti] | Commerciale [Aziende, Catalogo, Listini, Preventivi, Ordini] | Config [Enti, Piani, Template]`.
- Rinominato ID sezione interno `progetto-mansione-ente` → `piani-finanziari` per coerenza con la UI.
- Header compattato (h1 da 2.2em a 1.6em), status API inline a destra, rimossa la riga separata api-status.
- Breadcrumb semplificato: rimosso "🏠 Home →" ridondante, ora mostra solo nome + descrizione sezione.
- Verifiche: `npm run build` passato + Docker frontend ricostruito.

### Fix dropdown mansione in AssignmentModal
- **Bug**: il modal leggeva le mansioni da `/api/v1/project-assignments/` (tabella `ProgettoMansioneEnte`, priva di UI dal lato utente e quindi sempre vuota per nuovi progetti). In piu la chiamata usava `fetch` grezzo senza header JWT.
- **Fix**: il modal ora carica `GET /piani-finanziari/?progetto_id=...` + `GET /piani-finanziari/{id}` per ottenere le voci. Le opzioni nel dropdown appaiono come `B.2 – Docenza`, `B.3 – Tutor`, ecc. La tariffa oraria viene calcolata da `importo_preventivo / ore` se disponibile.
- Messaggio di aiuto aggiornato: se nessun piano trovato, avvisa di creare prima il piano in "Piani Finanziari".
- Le nuove assegnazioni salvano il `role` nel formato `{voce_codice} – {descrizione}` (es. "B.2 – Docenza").

### Aggregazione ore presenze nel Piano Finanziario
- **Backend `schemas.py`**: aggiunto `OreRuoloPianoFinanziario` (role, n_presenze, ore_effettive, costo_effettivo, voce_codice) e esteso `PianoFinanziarioRiepilogo` con `ore_per_ruolo[]` + `ore_effettive_totali`.
- **Backend `crud.py`**: `build_piano_finanziario_riepilogo` accetta ora `db` opzionale. Quando presente, esegue query `assignments JOIN attendances` per progetto, raggruppa per `role + hourly_rate`, calcola ore e costo effettivo. Matching fuzzy: role "B.2 – ..." viene abbinato al badge "B.2".
- **Backend `routers/piani_finanziari.py`**: il riepilogo endpoint passa ora `db` alla funzione.
- **Frontend `PianiFinanziariManager.js/css`**: nuova tabella "Ore presenze effettive per ruolo" nel blocco serverSummary con badge voce, n. presenze, ore, costo e riga totale.
- Verifiche: `python3 -m py_compile` passato + `npm run build` passato + Docker backend/frontend ricostruiti.

### Note tecniche importanti
- Le presenze esistenti usano `role = "docente"/"tutor"` (formato legacy); il badge voce (`voce_codice`) appare `null` per queste. Le nuove assegnazioni create via dropdown avranno il badge corretto.
- Le ore appaiono nel riepilogo solo per presenze con `assignment_id` valorizzato; presenze senza assegnazione collegata non sono aggregabili per ruolo.

### Allineamento progetto/template su ente erogatore + avviso
- Esteso il dominio `Project` con il nuovo campo `avviso`: aggiunti modello SQLAlchemy, schemi Pydantic, runtime schema update in `backend/main.py` e migration Alembic `011_add_avviso_to_projects.py`.
- Aggiornato `ProjectManager` frontend: il wizard progetto ora espone anche `Avviso`, lo salva insieme a `fondo`/`ente_erogatore` e lo mostra sia nel riepilogo delivery sia nelle card lista progetti.
- Aggiornato `PianiFinanziariManager`: il caricamento dei template di ambito `piano_finanziario` ora filtra anche per `project.avviso`; se il progetto ha gia un avviso, quello diventa il default operativo del piano.
- Rafforzata la coerenza backend in `crud.py`: quando si seleziona esplicitamente un template piano finanziario, il sistema verifica che `ente_erogatore` e `avviso` del template coincidano con quelli del progetto, evitando agganci incoerenti.
- Verifiche eseguite:
  - `python3 -m py_compile backend/models.py backend/schemas.py backend/crud.py backend/main.py backend/alembic/versions/011_add_avviso_to_projects.py` passato
  - `npm run build` passato

### Collegamento diretto template piano sul progetto
- Esteso `Project` con `template_piano_finanziario_id` (FK a `contract_templates`) per memorizzare direttamente quale template piano finanziario governa il progetto.
- Aggiunta migration Alembic `012_add_project_template_piano_finanziario.py` + runtime schema update in `backend/main.py`.
- Backend `crud.py` aggiornato: in create/update progetto, se il template piano è valorizzato viene validato come `ambito_template = piano_finanziario` con `ente_erogatore` e `avviso` obbligatori, poi il progetto eredita automaticamente questi valori dal template.
- Frontend `ProjectManager` aggiornato: nuovo campo `Template Piano Finanziario`; selezionandolo vengono auto-compilati `fondo`, `ente_erogatore`, `avviso` e i campi restano bloccati per evitare mismatch manuali.
- Frontend `PianiFinanziariManager` aggiornato: in assenza di piano già selezionato, usa `project.template_piano_finanziario_id` come template preferito di default.
- Verifiche eseguite:
  - `python3 -m py_compile backend/models.py backend/schemas.py backend/crud.py backend/main.py backend/alembic/versions/012_add_project_template_piano_finanziario.py` passato
  - `npm run build` passato

### Applicazione migration + test E2E coerenza template-progetto
- Corretto `backend/alembic.ini`: `script_location` puntava a `migrations` (vuota), riallineato a `alembic`.
- Corretto chain Alembic e revision id:
  - `010_link_piani_templates_by_avviso.py` ora dipende da `009` (non `009_add_piani_fondimpresa`).
  - Revision ID accorciati a `010`, `011`, `012` per evitare overflow su `alembic_version.version_num` (`VARCHAR(32)` nel DB corrente).
- Migration applicate su DB Docker backend fino a head `012`; verificata presenza colonne `projects.avviso` e `projects.template_piano_finanziario_id`.
- Durante test E2E emerso un `AmbiguousForeignKeysError` SQLAlchemy tra `projects` e `contract_templates` dopo nuovo FK progetto->template:
  - fix in `backend/models.py` con `foreign_keys` espliciti su `ContractTemplate.progetto` e nuova relazione `Project.template_piano_finanziario`.
- Test E2E finale eseguito in container backend:
  - creato template `piano_finanziario` (ente `FORMAZIENDA`, avviso `9/2026`);
  - creato progetto con valori intenzionalmente incoerenti ma con `template_piano_finanziario_id`;
  - verificato override coerente e persistente su progetto (`fondo/ente_erogatore/avviso` allineati al template) anche dopo update manuale incongruente.
  - esito: `RESULT PASS`.

### Rifinitura logica Template documentali (contratti/timesheet/piani)
- Richiesta utente recepita: area Template non deve essere centrata solo sui contratti; deve governare famiglie documentali diverse (contratti, timesheet, piani finanziari, altri documenti).
- Pulizia dati test: rimossi dal DB `E2E Template Piano Sync` e il progetto `E2E Progetto Template Piano`.
- Backend `crud.py` rifattorizzato con normalizzazione/validazione per ambito:
  - per `contratto`: obbligatorio un `tipo_contratto` specifico (non `documento_generico`);
  - per ambiti non contrattuali: `tipo_contratto` forzato a `documento_generico` e `is_default` disabilitato;
  - per ambiti non contrattuali: `chiave_documento` obbligatoria;
  - per `piano_finanziario`: obbligatori `ente_erogatore` e `avviso`.
- Backend `get_contract_template_by_type` ristretto ai soli template di ambito `contratto`, evitando selezioni involontarie di template documentali generici.
- Frontend template aggiornato con nuovo ambito `timesheet`:
  - `ContractTemplateModal.js`: aggiunta opzione `Timesheet` negli ambiti;
  - `ContractTemplatesManager.js`: mappatura badge/lista aggiornata con `🕒 Timesheet`.
- Verifiche:
  - `python3 -m py_compile backend/models.py backend/schemas.py backend/crud.py` passato
  - `npm run build` passato

### Chiavi documento standard + selezione guidata
- Introdotta tassonomia operativa `chiave_documento` per ambito nel modal Template:
  - `contratto`: `contratto_professionale`, `contratto_occasionale`, `ordine_di_servizio`, `contratto_a_progetto`
  - `timesheet`: `timesheet_standard`, `timesheet_mensile`, `timesheet_docente`, `timesheet_tutor`
  - `piano_finanziario`: `piano_finanziario_formazienda`, `piano_finanziario_fapi`, `piano_finanziario_fondimpresa`
  - `preventivo`, `ordine`, `generico` con chiavi standard dedicate.
- UX aggiornata in `ContractTemplateModal`: `chiave_documento` non è più solo input libero; ora è select guidata con opzione `Personalizzata...` (input libero solo se necessario).
- Normalizzazione backend in `crud.py`: la `chiave_documento` viene convertita in `snake_case` (`lowercase + underscore`) al salvataggio, per evitare varianti incoerenti tra UI/DB.
- Verifiche:
  - `python3 -m py_compile backend/crud.py backend/schemas.py backend/models.py` passato
  - `npm run build` passato

### Aggancio automatico template ai flussi Timesheet + Piani
- Implementato in `backend/crud.py` il resolver unico `resolve_document_template(...)` basato su:
  - `ambito_template`
  - `chiave_documento` (con normalizzazione snake_case)
  - contesto (`progetto_id`, `ente_attuatore_id`, `ente_erogatore`, `avviso`)
  con ranking per specificità (progetto/ente/ente_erogatore/avviso/chiave).
- Integrato in `GET /api/v1/reporting/timesheet`:
  - nuovo parametro query opzionale `chiave_documento`
  - risoluzione automatica template ambito `timesheet` (default chiave `timesheet_standard`)
  - payload esteso con `template_documento` (metadata template selezionato o `null`).
- Integrato in `GET /api/v1/piani-finanziari/{id}`:
  - `PianoFinanziarioDettaglio` esteso con `template_documento`
  - se `template_id` piano non è valorizzato, fallback automatico a resolver su ambito `piano_finanziario` con chiave derivata dal fondo (`piano_finanziario_<fondo_normalizzato>`).
- Corretto bug preesistente in `routers/reporting.py`:
  - usava campi `Attendance.hours_worked` e `Attendance.note` non esistenti;
  - riallineato a `Attendance.hours` e `Attendance.notes`.
- Smoke test eseguiti:
  - `GET /api/v1/reporting/timesheet` -> `200`, campo `template_documento` presente
  - `GET /api/v1/piani-finanziari/1` -> `200`, campo `template_documento` presente
- in ambiente corrente il valore è `null` perché non risultano template matching attivi per quel contesto.

### Fix visibilità template non-contratto + seed iniziale
- Analisi diretta DB: la sezione Template mostrava solo contratti perché in tabella esistevano solo record con `ambito_template='contratto'`.
- Individuato e corretto bug strutturale sul vincolo DB `idx_unique_default_per_tipo`:
  - era univoco su `(tipo_contratto, is_default)` senza condizione, bloccando la creazione di più template `documento_generico` con `is_default=false`;
  - corretto con indice parziale (`WHERE is_default = true`) tramite migration `013_fix_unique_default_template_index.py`.
- Aggiornato `models.py` per coerenza ORM (`postgresql_where=text('is_default = true')`).
- Seed operativo template documentali:
  - `piano_finanziario_formazienda` (`Piano Formazienda Standard`)
  - `piano_finanziario_fapi` (`Piano FAPI Standard`)
  - `piano_finanziario_fondimpresa` (`Piano Fondimpresa Standard`)
  - `timesheet_standard` (`Timesheet Standard`)
- Stato finale DB template per ambito:
  - `contratto`: 5
  - `piano_finanziario`: 3
  - `timesheet`: 1

### UX dedicata template Piano Finanziario
- Requisito utente esplicito applicato: quando `ambito_template = piano_finanziario` il modal non deve mostrare campi da contrattualistica.
- `ContractTemplateModal.js` aggiornato in modalità dedicata piano:
  - nascosti `Tipo Contratto`, `Ente Applicabile`, `Progetto Applicabile`;
  - sezione contenuto rinominata in `Schema Piano Finanziario` (`Schema Piano (JSON/HTML)`);
  - nascosti upload DOCX, pannello variabili, intestazione/piè di pagina;
  - nascoste intere sezioni `Configurazione Logo` e `Clausole Standard`;
  - sezione finale ridotta a `Stato Template` (senza formati data/importo).
- Restano centrali solo i campi coerenti con la logica repository piani: `chiave_documento` (schema), `ente_erogatore`, `avviso`, stato/versione.
- Verifica: `npm run build` passato.

### Refresh runtime frontend
- Su feedback utente ("vedo ancora tutto uguale"), eseguito riavvio container frontend:
  - `docker compose restart frontend`
  - container `pythonpro_frontend` ripartito correttamente.
- Indicazione operativa data all'utente: refresh hard browser (`Ctrl+F5`) per invalidare cache asset e visualizzare il modal aggiornato.

## Sessione 2026-04-02 — Audit coerenza dati full-stack

### Problema rilevato: "russo" nel piano finanziario
Il nome "russo" appare come riga nel piano finanziario ma non corrisponde a nessun collaboratore attivo nel gestionale. Questo è un sintomo di un problema strutturale: i campi `nominativo` (stringa libera) in `RigaNominativoFondimpresa`, `BudgetConsulenteFondimpresa` e `edizione_label` in `VocePianoFinanziario` non hanno FK verso `collaborators`. Se un collaboratore viene cancellato (soft-delete o hard-delete), il suo nome rimane come orfano nel piano.

**Causa tecnica**: `VocePianoFinanziario.edizione_label` è un `String` libero. In `crud.py` (`build_effective_piano_rows`) il nome viene composto dal `collaborator.first_name + last_name` al momento della generazione e salvato come label, poi non viene più aggiornato se il collaboratore viene modificato o cancellato.

### Problemi critici emersi (5 totali)

| # | File:riga | Problema | Impatto |
|---|-----------|----------|---------|
| 1 | `models.py:113` | `Project.ente_attuatore_id` FK senza `ondelete` → FK orfana se ente cancellato | Integrità referenziale compromessa, contratti generati senza ente valido |
| 2 | `models.py:678,724` | `nominativo` nei piani Fondimpresa è String libero senza FK a `collaborators` | Nomi orfani (es. "russo") non riconducibili a nessun record reale |
| 3 | `crud.py:217` | Soft-delete collaboratore NON disattiva i suoi `Assignment` → assignments attivi di collaboratori inattivi | Timesheet/reporting includono ore di persone non più attive |
| 4 | `models.py:14` | Tabella M2M `collaborator_project` senza `ondelete="CASCADE"` | Hard-delete collaboratore fallisce su FK; record orfani nella M2M |
| 5 | `crud.py:335` | Soft-delete progetto NON disattiva `ProgettoMansioneEnte` → mansioni di progetti "cancellati" visibili nelle dropdown | Nuove assegnazioni possono essere create su mansioni orfane |

### Problemi medi (6 totali)

| # | File | Problema |
|---|------|----------|
| 6 | `routers/collaborators.py` | GET `/collaborators` non filtra per `is_active=True` → collaboratori inattivi selezionabili nei modal assegnazione |
| 7 | `crud.py:217` | Soft-delete collaboratore non propaga a `Attendance` → presenze storiche ambigue |
| 8 | `crud.py:2530` | `edizione_label` costruito al volo e non aggiornato → "russo" e altri nomi orfani nel piano |
| 9 | `crud.py:2533` | Righe dinamiche piano generate senza `collaborator_id` FK → nessun modo di risalire all'origine |
| 10 | `models.py:154` | `Attendance.assignment_id SET NULL` → se assignment cancellato, presenze orfane non contate nel reporting |
| 11 | `models.py:455` | `ProgettoMansioneEnte` CASCADE ma no soft-delete → conflitto con logica soft-delete del progetto padre |

### Flussi end-to-end con problemi

**Flusso A: Collaboratore → Assegnazione → Presenze → Reporting**
- ❌ Soft-delete collaboratore non propaga a Assignment.is_active
- ❌ Se Assignment cancellato, Attendance rimane orfana (assignment_id=NULL) → ore "spariscono" dal reporting

**Flusso B: Piano Finanziario → Riepilogo ore**
- ❌ edizione_label è String libero (no FK) → nomi orfani come "russo"
- ❌ Righe dinamiche non tracciate a un collaborator_id reale
- ✅ build_effective_piano_rows filtra Collaborator.is_active, ma il nome rimane storico

**Flusso C: Progetto → Mansioni → Assegnazioni**
- ❌ Soft-delete progetto NON disattiva ProgettoMansioneEnte
- ✅ AssignmentModal ora usa piani finanziari invece di ProgettoMansioneEnte (fix recente)

### Priorità di fix

**FASE 1 — Critica** (prima di usare il sistema in produzione):
1. `models.py:113`: aggiungere `ondelete="SET NULL"` a `Project.ente_attuatore_id`
2. `models.py:14`: aggiungere `ondelete="CASCADE"` alla M2M `collaborator_project`
3. `crud.py:217`: soft-delete collaboratore deve disattivare anche i suoi `Assignment`
4. `crud.py` delete_assignment: bloccare se ha `Attendance` collegate
5. Pulizia dati: trovare e rimuovere/ricollegare nomi orfani nel piano (es. "russo")

**FASE 2 — Media** (prossime sessioni):
6. Aggiungere `collaborator_id FK` (nullable) a `VocePianoFinanziario` e `RigaNominativoFondimpresa`
7. Endpoint `/api/v1/collaborators/active` per dropdown (filtra is_active=True)
8. Soft-delete progetto deve disattivare ProgettoMansioneEnte figlie
9. Migliorare build_effective_piano_rows per tracciare collaborator_id nelle righe generate

**FASE 3 — Minore**:
10. Completare migrazione `ente_erogatore` → `ente_attuatore_id` (campo marcato DEPRECATO da tempo)
11. Aggiungere `created_by_user` a VocePianoFinanziario per audit trail
12. Sync agenzia → disattivazione quando collaboratore soft-deleted
13. Messaggio user-friendly su errore RESTRICT per aziende con preventivi

## Sessione 2026-04-03

### Fix da fare in ordine (Fase 1 — Critica)

**Fix 1 — models.py:113**: `Project.ente_attuatore_id` aggiungere `ondelete="SET NULL"`
```python
# PRIMA:
ente_attuatore_id = Column(Integer, ForeignKey("implementing_entities.id"), nullable=True, index=True)
# DOPO:
ente_attuatore_id = Column(Integer, ForeignKey("implementing_entities.id", ondelete="SET NULL"), nullable=True, index=True)
```
Richiede migration Alembic (`014_fix_fk_ondelete.py`).

**Fix 2 — models.py:14**: M2M `collaborator_project` aggiungere `ondelete="CASCADE"` su entrambe le colonne
```python
Column('collaborator_id', Integer, ForeignKey('collaborators.id', ondelete="CASCADE"), primary_key=True),
Column('project_id', Integer, ForeignKey('projects.id', ondelete="CASCADE"), primary_key=True)
```
Stesso file migration 014.

**Fix 3 — crud.py:217**: `delete_collaborator` deve disattivare anche Assignment figli
Trovare la funzione `delete_collaborator` (circa riga 217) e aggiungere dopo il soft-delete del collaboratore:
```python
db.query(models.Assignment).filter(
    models.Assignment.collaborator_id == collaborator_id,
    models.Assignment.is_active == True
).update({"is_active": False})
```

**Fix 4 — crud.py (delete_assignment)**: bloccare delete se ha Attendance collegate
Trovare la funzione di delete assignment e aggiungere check preventivo:
```python
count = db.query(models.Attendance).filter(models.Attendance.assignment_id == assignment_id).count()
if count > 0:
    raise ValueError(f"Impossibile eliminare: {count} presenze collegate.")
```

**Fix 5 — crud.py:335**: `delete_project` deve disattivare ProgettoMansioneEnte figlie
Trovare `delete_project` e aggiungere soft-delete delle mansioni associate.

### Fix da fare in ordine (Fase 2 — Media)

**Fix 6 — routers/collaborators.py**: aggiungere parametro `?active_only=true` o endpoint `/active`
Il GET `/collaborators` deve poter filtrare `is_active=True` per le dropdown dei modal.

**Fix 7 — VocePianoFinanziario**: aggiungere FK nullable `collaborator_id`
In `models.py` aggiungere colonna e in `crud.py` valorizzarla quando si generano le righe dinamiche.
Migration Alembic `015_add_collaborator_fk_to_voci_piano.py`.

**Fix 8 — crud.py:335**: soft-delete progetto deve disattivare `ProgettoMansioneEnte` figlie.

### Stato attuale del sistema (2026-04-02 fine sessione)
- Backend Docker: `pythonpro_backend` — in esecuzione, migrations applicate fino a `012`
- Frontend Docker: `pythonpro_frontend` — in esecuzione su `http://localhost:3001` / `http://192.168.2.161:3001`
- DB: migrations head `012`, runtime schema updates presenti in `backend/main.py`
- Ultimo `npm run build`: passato
- Ultimo `py_compile` su moduli core: passato
- Nessuna modifica al codice applicata in questa sessione (solo audit + aggiornamento STATUS)

## Sessione 2026-04-03 — Fix coerenza dati full-stack (Fasi 1+2+3)

### Verifica DB "russo" / nomi orfani
- Eseguita query sul DB: nessun record con "russo" o "rossi" trovato in `collaborators`, `voci_piano_finanziario`, `righe_nominativo_fondimpresa`. Problema non riproducibile nell'ambiente attuale.

### Fase 1 — Fix critici (tutti applicati)
- **Fix 1** — `models.py`: `Project.ente_attuatore_id` aggiunto `ondelete="SET NULL"` sulla FK verso `implementing_entities`
- **Fix 2** — `models.py`: tabella M2M `collaborator_project` aggiunto `ondelete="CASCADE"` su entrambe le FK (`collaborator_id`, `project_id`)
- **Fix 3** — `crud.py`: `delete_collaborator` ora disattiva anche tutte le `Assignment` attive del collaboratore eliminato
- **Fix 4** — `crud.py`: `delete_assignment` ora blocca con `ValueError` se esistono presenze (`Attendance`) collegate
- **Fix 5** — `crud.py`: `delete_project` ora disattiva le `ProgettoMansioneEnte` figlie via soft-delete
- **Migration 014** — `014_fix_fk_ondelete.py`: applicata su DB, altera FK `ente_attuatore_id` e M2M

### Fase 2 — Fix medi (tutti applicati)
- **Fix 6** — `routers/collaborators.py`: endpoint `GET /collaborators` espone `?active_only=true` (passa `is_active=True` a `crud.get_collaborators` già predisposto)
- **Fix 7a** — `models.py`: `VocePianoFinanziario` aggiunta FK nullable `collaborator_id → collaborators.id` (`SET NULL`)
- **Fix 7b** — `models.py`: `RigaNominativoFondimpresa` aggiunta FK nullable `collaborator_id → collaborators.id`
- **Fix 7c** — `models.py`: `BudgetConsulenteFondimpresa` aggiunta FK nullable `collaborator_id → collaborators.id`
- **Fix 8** — `crud.py`: `build_effective_piano_rows` ora include `collaborator_id` nelle righe generate (sia statiche da `voce` che dinamiche da `assignment`)
- **Migration 015** — `015_add_collaborator_fk_to_voci_piano.py`: aggiunge colonna + FK + indice alle 3 tabelle

### Fase 3 — Fix minori (tutti applicati)
- **Fix 10** — `schemas.py`: campo `ente_erogatore` in `ProjectBase`/`ProjectUpdate` marcato `# DEPRECATO` con indicazione di usare `ente_attuatore`; colonna DB non droppata (retrocompatibilità)
- **Fix 11** — `models.py` + `schemas.py`: aggiunto `created_by_user: String(100)` nullable a `VocePianoFinanziario` per audit trail
- **Fix 12** — `crud.py`: aggiunta funzione `_sync_consultant_from_collaborator` — il soft-delete collaboratore ora disattiva anche il record `Consulente` collegato (la sync agenzia era già presente); aggiunto anche `collaborator_id` FK al modello `Consulente`
- **Fix 13** — `routers/aziende_clienti.py`: endpoint DELETE ora cattura `IntegrityError` e restituisce HTTP 400 con messaggio leggibile ("esistono preventivi o ordini collegati")
- **Migration 016** — `016_add_created_by_user_to_voci_piano.py`: aggiunge `created_by_user` a `voci_piano_finanziario` e `collaborator_id` a `consulenti`

### Schema fix (Phase 1+2 del piano make-plan)
- **Phase 1** — `schemas.py`: aggiunto `collaborator_id: Optional[int] = None` a `VocePianoFinanziarioBase` — il campo FK ora viene esposto correttamente nei payload API
- **Phase 2** — `models.py`: aggiunta `collaborator = relationship("Collaborator", foreign_keys=[collaborator_id], lazy="select")` a `VocePianoFinanziario`, `RigaNominativoFondimpresa`, `BudgetConsulenteFondimpresa`
- **Phase 3 e 4**: verificato che già implementate in sessioni precedenti (`active_only` endpoint e soft-delete progetto → ProgettoMansioneEnte)
- Verifiche: `py_compile` OK + `npm run build` OK

### Refactor `fondo` → `ente_erogatore` (unificazione campo)
- **Decisione**: eliminato il campo `fondo` da tutti i modelli — `ente_erogatore` è ora l'unico campo canonico per identificare il soggetto finanziatore
- **Migration 017** — `017_rename_fondo_to_ente_erogatore.py`: copia `projects.fondo → ente_erogatore` dove vuoto, DROP COLUMN `projects.fondo`, RENAME COLUMN `piani_finanziari.fondo → ente_erogatore`, RENAME `piani_finanziari_fondimpresa.fondo → ente_erogatore`, indice univoco ricreato come `idx_unique_piano_progetto_anno_ente_avviso`
- **Backend**: aggiornati `models.py`, `schemas.py` (ProjectBase, ProjectUpdate, PianoFinanziarioBase, PianoFondimpresaBase), `crud.py`, `routers/piani_finanziari.py`, `routers/piani_fondimpresa.py`, `routers/reporting.py`, `main.py`
- **Frontend**: rimosso `fondo` da `ProjectManager.js` (form, stato, submit, resetForm, startEdit) — `ente_erogatore` è ora il campo principale; aggiornati `PianiFinanziariManager.js` (stato `fondo` → `enteErogatore`, prop `forcedFondo` → `forcedEnte`), `PianiFondimpresaManager.js`
- **Nuovo flusso UX Piano Finanziario**: `PianiFinanziariHub.js` riscritto con cascata a 3 step: **Ente Erogatore → Avviso → Progetto** — i valori sono estratti dinamicamente dai progetti reali, non da una lista statica
- Migration applicata su DB: `alembic upgrade head` → 017 ✅
- Verifiche: `py_compile` OK + `npm run build` OK + Docker backend+frontend ricostruiti ✅

### Audit tecnico completo (Senior Technical Auditor)
- Prodotto schema ER Mermaid completo con 24 tabelle e tutte le relazioni
- Analisi vincoli: overlap orario (crud.py:459), limiti macrovoce piano (A:20%/B:50%/C:30%), C.6 forfait (10%)
- Gap tecnici identificati: nessuna firma digitale, nessuna task queue asincrona, nessun audit log, nessuna integrazione AI/agenti
- Stima maturità ERP: ~60-65% rispetto a un ERP verticale completo per formazione finanziata
- Roadmap AI agent-ready definita in 4 fasi (infrastruttura async → state machine → tool API → primo agente)

### Stato sistema fine sessione 2026-04-03 (seconda parte)
- Backend Docker: `pythonpro_backend` — in esecuzione, ricostruito
- Frontend Docker: `pythonpro_frontend` — in esecuzione su `http://localhost:3001` / `http://192.168.2.161:3001`
- DB: migrations head **017**
- Ultimo `py_compile`: passato su tutti i file modificati
- Ultimo `npm run build`: passato
- Ultimo `alembic upgrade head`: passato fino a 017

## Prossima sessione — punto di ripartenza

### Stato attuale post-refactor
- `fondo` eliminato ovunque — campo canonico: `ente_erogatore`
- Flusso Piani Finanziari: cascata ente → avviso → progetto funzionante
- DB a 017, tutti i fix di coerenza dati applicati

### Priorità suggerite
1. **Validare in UI** il nuovo flusso cascata ente/avviso/progetto su dati reali (verificare che i progetti esistenti abbiano `ente_erogatore` popolato correttamente dopo migration 017)
2. **Reportistica**: aggiungere report consolidato piano vs. consuntivo per avviso (gap critico per rendicontazione)
3. **Lifecycle contratto**: aggiungere stati espliciti (bozza → generato → inviato → firmato → archiviato) su `Assignment`
4. **Task queue**: integrare ARQ con Redis già presente — prerequisito per qualsiasi agente AI
5. **Audit log**: tabella `audit_log(entity, entity_id, action, old_value, new_value, actor, timestamp)` — prerequisito per conformità e agenti
- Sistemare `App.test.js` e il resto della suite frontend, oggi ancora disallineati al flusso login e alla shell applicativa reale.
- Completare la seconda fase con wizard progetto, per avere simmetria sui due principali flussi di inserimento dati.
- Avviare la terza fase: revisione tabelle e calendario in chiave operativa.
- Completare la quarta fase: UX differenziata per ruolo anche su dashboard/navigation/azioni secondarie.
- Decidere come trattare il route legacy `GET /api/v1/assignments/{id}/generate-contract`: mantenerlo per retrocompatibilita backend o farlo convergere internamente sul flusso template-based.
- Aggiungere test frontend mirati sul contract preflight e sulla generazione template-based.

## Implementazione 2026-03-30 — Blocco 1: Anagrafica Espansa

### File backend aggiunti/modificati
- `backend/alembic/versions/004_add_agenzie_consulenti_aziende_clienti.py` — migration nuove tabelle
- `backend/models.py` — aggiunti modelli `Agenzia`, `Consulente`, `AziendaCliente` con validazioni e indici
- `backend/schemas.py` — aggiunti schemi Base/Create/Update/Response per le 3 entità + `PaginatedResponse[T]` generico + validazione P.IVA italiana con checksum
- `backend/crud.py` — aggiunte funzioni CRUD + ricerca full-text paginata per le 3 entità
- `backend/routers/agenzie.py` — CRUD completo `/api/v1/agenzie/`
- `backend/routers/consulenti.py` — CRUD + lista paginata + sottoroute `/aziende` → `/api/v1/consulenti/`
- `backend/routers/aziende_clienti.py` — CRUD + lista paginata con filtri + ordinamento + search autocomplete → `/api/v1/aziende-clienti/`
- `backend/main.py` — registrati i 3 nuovi router
- `backend/seed_blocco1.py` — script seed (3 agenzie, 5 consulenti, 10 aziende clienti)

### File frontend aggiunti/modificati
- `frontend/src/services/apiService.js` — aggiunte funzioni API per agenzie, consulenti, aziende clienti
- `frontend/src/components/AgenzieManager.js` + `.css` — gestione agenzie (card grid, modal create/edit)
- `frontend/src/components/ConsulentiManager.js` + `.css` — gestione consulenti (tabella paginata, modal 2-col)
- `frontend/src/components/AziendeClientiManager.js` + `.css` — gestione aziende clienti (tabella paginata, filtri debounce, ordinamento colonne, modal a sezioni)
- `frontend/src/App.js` — aggiunte sezioni `agenzie`, `consulenti`, `aziende-clienti` (ruolo: admin)

### Verifiche eseguite
- `python3 -m py_compile` su tutti i file backend → OK
- `npm run build` → `Compiled successfully.` (zero warning nuovi)

### Note tecniche
- Relazioni bidirezionali: `Consulente` ↔ `Agenzia`, `AziendaCliente` ↔ `Consulente`
- Soft delete su tutte e 3 le entità (campo `attivo=False`)
- `PaginatedResponse[T]` è ora disponibile come schema generico riutilizzabile
- Per attivare le nuove tabelle: eseguire la migration 004 (`alembic upgrade head`)
- Per dati di test: `python3 seed_blocco1.py` dalla cartella backend

## Implementazione 2026-03-30 — Blocco 2: Smart Collaborators List

### File backend aggiunti/modificati
- `backend/alembic/versions/005_add_collaborators_search_indexes.py` — indici su `first_name`, `last_name`, `position`, `city`, `is_active`
- `backend/crud.py` — aggiunta `search_collaborators_paginated()` con filtri full-text, disponibilità (subquery progetti attivi), città, ordinamento multi-colonna
- `backend/routers/collaborators.py` — aggiunto `GET /api/v1/collaborators/search` → restituisce `PaginatedResponse` con `items, total, page, pages, has_next`; endpoint precedente `/` invariato (zero breaking change)

### File frontend aggiunti/modificati
- `frontend/src/services/apiService.js` — aggiunta `getCollaboratorsPaginated(params)`
- `frontend/src/components/collaborators/CollaboratorsTable.js` — riscrittura completa:
  - **Self-sufficient**: gestisce il proprio fetch server-side (non dipende più da prop `collaborators`)
  - **Sticky filter bar**: ricerca testuale (debounce 300ms), filtro competenza, filtro disponibilità, filtro città
  - **Toggle card/list view**: card con avatar colorati, badge stato, quick actions (mail, tel); list view con tabella densa e righe espandibili
  - **URL sync**: ogni cambio filtro aggiorna i query params per bookmarking/condivisione
  - **CSV export**: scarica i risultati correnti in CSV con BOM UTF-8
  - **Paginazione server-side**: 10/20/50/100 per pagina
  - **Shortcut tastiera**: Ctrl+F focalizza il campo ricerca
- `frontend/src/components/CollaboratorManager.js` — aggiunto `refreshTrigger` per sincronizzare la tabella dopo ogni operazione CRUD (create/update/delete/bulk-import)
- `frontend/src/components/CollaboratorManager.css` — aggiunti ~200 righe CSS per il nuovo design (summary chips, filter bar sticky, card grid, avatar, badge)

### Verifiche eseguite
- `python3 -m py_compile crud.py routers/collaborators.py` → OK
- `npm run build` → `Compiled successfully.` (zero warning nuovi)

### Note tecniche
- L'endpoint `/search` è prima di `/{collaborator_id}` nel router quindi FastAPI fa match correttamente
- Il filtro `disponibile` usa una subquery su `collaborator_project` JOIN `projects WHERE status='active'`
- La prop `collaborators` è stata rimossa dal `CollaboratorsTable` (breaking change interna — aggiornato il solo `CollaboratorManager`)

## Prossimi passi consigliati
1. Eseguire migration 004+005 sul DB live (`alembic upgrade head`)
2. Eseguire `seed_blocco1.py` per i dati di test
3. Verificare da browser il nuovo flusso collaboratori: checkbox `agenzia` / `consulente`, badge tabella/card e assenza delle schede dedicate `Agenzie` / `Consulenti`
4. Avviare Blocco 3: Catalogo + Listini
5. Avviare Blocco 4: Preventivi + Ordini

## Audit 2026-03-29 — Findings principali
- Critico: il frontend genera il PDF contratto da `GET /assignments/{id}/generate-contract`, ma il backend espone la generazione da `POST /api/v1/contracts/generate-contract`; la UI collaboratori può quindi fallire in produzione durante la generazione contratto.
- Critico: il frontend chiama endpoint che nel backend attuale non risultano presenti (`/auth/register`, `/analytics/*`, `/search`, `/upload`), quindi alcune parti del service layer sono incoerenti rispetto all'API reale.
- Critico: l'autenticazione seeda utenti con password di default (`admin123`, `operatore123`) allo startup e il modulo auth usa ancora un fallback `SECRET_KEY` hardcoded se la variabile ambiente manca.
- Alto: il backend applica mutazioni schema a runtime con `ALTER TABLE` in `main.py`; è una misura di emergenza utile per compatibilità, ma rende fragile la gestione migrazioni e riduce la prevedibilità del deploy.
- Alto: esistono due entrypoint backend (`backend/main.py` reale e `backend/app/main.py` scheletro/TODO). Questo aumenta il rischio di confusione, documentazione falsa e integrazione CI incompleta.
- Alto: i test frontend sono disallineati col codice corrente. `npm test -- --watch=false` fallisce subito su `src/App.test.js` per import a modulo inesistente e su `Dashboard.test.js` perché la dashboard reale è ancora placeholder.
- Medio: mobile e documentazione mobile non sono pienamente affidabili come fonte di stato reale; alcune aspettative contrattuali su payload/auth refresh risultano da ricontrollare contro backend attuale.

## Audit 2026-03-29 — Stato test
- Frontend: `npm test -- --watch=false` eseguito, fallito.
- Backend: `pytest` e `python3 -m pytest` non disponibili nell'ambiente locale corrente.

## Audit 2026-03-29 — Integrazioni agentiche consigliate
- Agente documentale: controllo scadenze documento identità, file mancanti, reminder operativi e preparazione pratiche.
- Agente contratti: verifica completezza dati collaboratore/progetto/ente prima della generazione contratto e segnalazione campi mancanti.
- Agente timesheet/compliance: validazione anomalie presenze, sovrapposizioni, ore residue, presenze fuori periodo assegnazione.
- Agente QA operativo: smoke test guidati su backend/frontend dopo deploy o prima di rilascio.
- Agente PM/ops: riepilogo giornaliero stato progetto, backlog reale, rischi aperti, drift tra documentazione, codice e test.

## Audit 2026-03-29 — UX/UI
- L'interfaccia è funzionale ma non ancora coerente come prodotto unico: header, manager, form e modali seguono pattern visivi diversi tra loro.
- La UX è ancora centrata su moduli CRUD separati, mentre il dominio richiede workflow guidati: collaboratore -> progetto -> assegnazione -> presenza -> contratto.
- La dashboard è ancora placeholder e non svolge il ruolo di cockpit operativo.
- I form risultano cognitivamente pesanti: molti campi, poca progressive disclosure, poca guida contestuale.
- Mancano viste forti di priorità e alert: documenti, anomalie presenze, ore residue, contratti bloccati, incompletezze enti.
- L'esperienza per ruolo (`admin` vs `operatore`) è solo parzialmente differenziata: accesso diverso, ma non ancora home/task/azioni davvero diverse.
- La mobile app va trattata come canale operativo rapido per operatori, non come semplice copia ridotta della web app.

## Audit 2026-03-29 — Backlog UX/UI da realizzare
1. Design system condiviso per tutto il frontend.
2. Dashboard operativa reale con KPI, alert e task prioritari.
3. Workflow guidato end-to-end tra collaboratori, progetti, assegnazioni, presenze e contratti.
4. Wizard multi-step per creazione/modifica collaboratore.
5. Wizard multi-step per creazione/modifica progetto.
6. Vista unica alert/compliance per documenti, presenze, ore e contratti.
7. Contract preflight panel prima della generazione PDF.
8. Tabella collaboratori più operativa con quick actions, badge e filtri persistenti.
9. Tabella progetti orientata allo stato e alle anomalie.
10. Calendario presenze con inserimento rapido e prevenzione errori.
11. Esperienze differenziate per ruolo utente.
12. Strategia mobile-first per operatore sul campo.
13. Sistema unificato di feedback, loading, empty state ed error state.
14. Piano accessibilità minimo serio per tastiera, contrasto e messaggi errore.

## Audit 2026-03-29 — Priorità implementativa consigliata
1. Design system + dashboard + alert/compliance.
2. Wizard collaboratore e progetto.
3. Revisione tabelle e calendario.
4. Preflight contratti e UX differenziata per ruolo.
5. Allineamento desktop/mobile.

## Implementazione 2026-03-30 — Fase 1 completata
- File frontend toccati: `frontend/src/index.css`, `frontend/src/App.css`, `frontend/src/App.js`, `frontend/src/components/Dashboard.js`, `frontend/src/components/Dashboard.css`, `frontend/src/components/Dashboard.test.js`.
- Inseriti token visuali globali minimi e resa più coerente di background, header, breadcrumb, section shell e navigation.
- Sostituito il vecchio placeholder dashboard con un cockpit operativo reale:
  - KPI principali
  - centro alert/compliance
  - ranking top progetti e collaboratori
  - distribuzione contratti
  - refresh manuale
- Le regole alert implementate oggi coprono:
  - documenti identità mancanti/scaduti/in scadenza
  - assegnazioni senza tipo contratto
  - assegnazioni con dati economici mancanti
  - assegnazioni con date incoerenti o prossime alla chiusura
  - progetti attivi oltre data fine
- Scelta tecnica importante: niente dipendenza da `analytics/*`; il cockpit usa solo endpoint effettivamente presenti nel backend.
- Test verificato: `npm test -- --watch=false --runInBand src/components/Dashboard.test.js` passato.
- Warning noto nei test: rumore `act(...)`/`ReactDOMTestUtils.act` proveniente dalla toolchain test React corrente; non blocca l'esecuzione del test mirato.

## Implementazione 2026-03-30 — Fase 2 in corso
- Primo blocco completato: wizard collaboratore in `frontend/src/components/collaborators/CollaboratorForm.js`.
- Il form ora e organizzato in 3 step:
  - identita
  - profilo
  - documenti
- Aggiunti:
  - stepper laterale cliccabile
  - card stato avanzamento
  - riepilogo checkpoint operativo
  - pannelli documentali con stato file
  - navigazione avanti/indietro senza cambiare il payload finale di submit
- CSS relativo aggiunto/esteso in `frontend/src/components/CollaboratorManager.css`.
- Verifica eseguita: `npm run build` passato.
- Warning residui build non introdotti in questa implementazione:
  - `frontend/src/App.js`
  - `frontend/src/components/Calendar.js`
  - `frontend/src/components/ProgettoMansioneEnteManager.js`

## Implementazione 2026-03-30 — Fase 2 completata
- Secondo blocco completato: wizard progetto in `frontend/src/components/ProjectManager.js`.
- Il form progetto ora e organizzato in 3 step:
  - base
  - governance
  - delivery
- Aggiunti:
  - stepper laterale cliccabile
  - card avanzamento
  - checkpoint progetto
  - riepilogo delivery per ente attuatore, sede ed ente erogatore
  - navigazione avanti/indietro mantenendo invariato il submit finale verso create/update
- CSS relativo aggiunto/esteso in `frontend/src/components/ProjectManager.css`.
- Verifica eseguita: `npm run build` passato anche dopo il wizard progetto.
- Warning residui build ancora preesistenti:
  - `frontend/src/App.js`
  - `frontend/src/components/Calendar.js`
  - `frontend/src/components/ProgettoMansioneEnteManager.js`

## Implementazione 2026-03-30 — Fase 3 completata
- Collaboratori:
  - `frontend/src/components/collaborators/CollaboratorsTable.js`
  - `frontend/src/components/CollaboratorManager.css`
- Progetti:
  - `frontend/src/components/ProjectManager.js`
  - `frontend/src/components/ProjectManager.css`
- Calendario:
  - `frontend/src/components/Calendar.js`
  - `frontend/src/components/Calendar.css`
- Migliorie introdotte:
  - summary cards operative nei collaboratori
  - quick filter per collaboratori `tutti / in attenzione / senza attivita / coperti`
  - righe tabella collaboratori con stato operativo evidenziato
  - summary cards operative nei progetti
  - filtro progetti `attenzione`
  - badge di rischio nelle project card
  - calendario con operations board: ore oggi, ore settimana, agenda del giorno, carico collaboratori
  - conteggi calendario riallineati a dati piu utili lato operativita
- Verifica eseguita: `npm run build` passato.
- Warning residui build ancora preesistenti:
  - `frontend/src/App.js`
  - `frontend/src/components/Calendar.js`
  - `frontend/src/components/ProgettoMansioneEnteManager.js`

## Implementazione 2026-03-30 — Fase 4 parziale
- File frontend toccati:
  - `frontend/src/App.js`
  - `frontend/src/components/CollaboratorManager.js`
  - `frontend/src/components/CollaboratorManager.css`
  - `frontend/src/components/collaborators/CollaboratorsTable.js`
  - `frontend/src/components/collaborators/CollaboratorProjectsRow.js`
- Introdotto pannello `contract preflight` nel flusso collaboratori:
  - click su `Contratto` non genera piu subito il PDF
  - prima mostra check su anagrafica, progetto, tipo contratto, mansione, dati economici, periodo, documento identita ed ente attuatore
  - i blocchi reali impediscono la generazione, i warning restano visibili ma non bloccanti
- Introdotta prima UX differenziata per ruolo su gestione collaboratori:
  - `admin`: pieno controllo operativo
  - `manager` / `user`: experience guidata con focus su assegnazioni e qualita dati
  - azioni distruttive o strutturali limitate in UI agli admin per delete collaboratore, rimozione link progetto e import massivo
- Nota tecnica importante:
  - backend reale confermato con doppio flusso contratti:
    - legacy `GET /api/v1/assignments/{id}/generate-contract`
    - template-based `POST /api/v1/contracts/generate-contract`
  - il nuovo preflight espone gia questa distinzione lato operatore, ma il service layer non e ancora stato riallineato a un singolo percorso di generazione
- Verifica eseguita:
  - `npm run build` passato
  - warning ESLint residui invariati e preesistenti in:
    - `frontend/src/App.js`
    - `frontend/src/components/Calendar.js`
    - `frontend/src/components/ProgettoMansioneEnteManager.js`

## Implementazione 2026-03-30 — Fase 4 riallineamento contratti
- File toccati:
  - `frontend/src/components/CollaboratorManager.js`
  - `frontend/src/services/apiService.js`
  - `backend/schemas.py`
  - `backend/routers/contract_templates.py`
- Decisione presa:
  - per la UI collaboratori il percorso unico e ora il flusso template-based `POST /api/v1/contracts/generate-contract`
  - l'assenza di `ente_attuatore_id` non e piu tollerata come fallback implicito al legacy nel preflight
- Modifiche introdotte:
  - il manager collaboratori costruisce il payload di generazione a partire dall'assegnazione e dal progetto corrente
  - il frontend passa `collaboratore_id`, `progetto_id`, `ente_attuatore_id`, `mansione`, ore, tariffa, date e `contract_signed_date`
  - il backend template-based valorizza ora anche i placeholder firma contratto quando la data firma e presente sull'assegnazione
  - rimosso l'uso frontend dell'export legacy `generateContractPdf`
- Verifiche eseguite:
  - `npm run build` passato
  - `python3 -m py_compile backend/schemas.py backend/routers/contract_templates.py` passato
- Warning residui build ancora preesistenti:
  - `frontend/src/App.js`
  - `frontend/src/components/Calendar.js`
  - `frontend/src/components/ProgettoMansioneEnteManager.js`

## Implementazione 2026-03-30 — Fix UX form collaboratore
- File toccati:
  - `frontend/src/components/CollaboratorManager.js`
  - `frontend/src/components/CollaboratorManager.css`
- Problema risolto:
  - il flusso modifica collaboratore risultava incoerente: il wizard compariva inline in alto pagina, mentre l'utente percepiva anche un'interazione separata tipo popup
  - documento identita e curriculum erano quindi raggiungibili solo nel form in alto e non in una finestra unica di editing
- Correzione introdotta:
  - il wizard collaboratore ora viene aperto dentro un modal overlay dedicato sia in creazione sia in modifica
  - chiusura possibile anche cliccando sull'overlay
  - documento identita e CV restano nello stesso wizard/modal, senza sdoppiamento dell'esperienza
- Verifica eseguita:
  - `npm run build` passato
  - warning ESLint residui invariati e preesistenti in `App.js`, `Calendar.js`, `ProgettoMansioneEnteManager.js`

## Implementazione 2026-03-30 — Fix stato wizard collaboratore
- File toccati:
  - `frontend/src/hooks/useForm.js`
  - `frontend/src/components/CollaboratorManager.js`
  - `frontend/src/components/CollaboratorManager.css`
- Problema risolto:
  - aprendo il form di modifica per un secondo collaboratore, il wizard continuava a mostrare i dati del primo record aperto
  - il modal risultava percepito come maschera alta/poco separata dal contenuto pagina
- Correzione introdotta:
  - `useForm` ora sincronizza davvero il proprio stato quando cambiano gli `initialValues`
  - `CollaboratorForm` viene montato con `key` legata all'id collaboratore per forzare reset pulito tra un record e l'altro
  - il modal collaboratore e ora centrato con `max-height` e scroll interno, invece di restare ancorato verso l'alto
- Verifica eseguita:
  - `npm run build` passato
  - warning ESLint residui invariati e preesistenti in `App.js`, `Calendar.js`, `ProgettoMansioneEnteManager.js`

## Implementazione 2026-03-30 — Fix dev API base URL
- File toccati:
  - `frontend/src/lib/http.js`
- Problema risolto:
  - avviando il frontend su una porta locale diversa da `3000` o `3001` il client HTTP non si riconosceva piu come dev locale
  - su `3002` le chiamate API cadevano quindi su path relativi `/api/v1` dello stesso dev server React, ricevendo HTML (`<!DOCTYPE html>`) invece di JSON
- Correzione introdotta:
  - la detection locale ora usa qualunque porta localhost diversa dalla backend API `8001`
  - in dev locale il frontend punta di nuovo a `http://localhost:8001`
- Verifica eseguita:
  - hot reload del dev server su `3002` completato
  - `npm run build` passato

## Implementazione 2026-03-30 — Fix API base per frontend LAN su 3001
- File toccati:
  - `frontend/src/lib/http.js`
- Problema risolto:
  - il frontend servito su `http://192.168.2.161:3001/` non veniva riconosciuto come runtime da collegare al backend remoto
  - senza `REACT_APP_API_URL`, il client cadeva su `/api/v1` relativo e riceveva HTML dal frontend nginx invece del JSON API
- Correzione introdotta:
  - aggiunto riconoscimento host IPv4 privati in LAN
  - quando il frontend gira su `192.168.x.x:3001`, `10.x.x.x:3001` o `172.16-31.x.x:3001`, il client usa automaticamente `http://<host>:8001/api/v1`
  - verificato che il backend reale risponde su `http://192.168.2.161:8001/health`
- Verifica eseguita:
  - `npm run build` passato

## Implementazione 2026-03-30 — UX per ruolo e cleanup frontend
- File toccati:
  - `frontend/src/App.js`
  - `frontend/src/App.css`
  - `frontend/src/components/Dashboard.js`
  - `frontend/src/components/Dashboard.css`
  - `frontend/src/components/Dashboard.test.js`
  - `frontend/src/components/Calendar.js`
  - `frontend/src/components/ProgettoMansioneEnteManager.js`
- Modifiche introdotte:
  - shell applicativa con home diversa per ruolo: `admin -> dashboard`, `user/manager -> collaboratori`
  - strip di navigazione con contesto operativo e quick actions diverse per ruolo
  - dashboard con focus separato tra vista di governo admin e vista operativa team
  - rimossi i warning hook frontend presenti in `App.js`, `Calendar.js`, `ProgettoMansioneEnteManager.js`
- Verifiche eseguite:
  - `npm test -- --watch=false --runInBand src/components/Dashboard.test.js` passato
  - `npm run build` passato con `Compiled successfully`
  - restano solo warning toolchain `baseline-browser-mapping` / `caniuse-lite`

## Implementazione 2026-03-30 — Verifica runtime backend/frontend
- Verifiche eseguite:
  - frontend confermato raggiungibile in LAN su `http://192.168.2.161:3001/`
  - smoke backend eseguito con `node scripts/smoke.js`
  - esito smoke: `6/6` test passati (`health`, root, `projects`, `collaborators`, `docs`, `backup_scheduler`)
- Nota:
  - il check POST login da terminale sandbox resta non conclusivo per limiti `EPERM` del contesto locale, quindi il login reale va confermato dal browser

## Implementazione 2026-03-30 — Convergenza route legacy contratti
- File toccati:
  - `backend/routers/contract_templates.py`
  - `backend/routers/assignments.py`
- Decisione presa:
  - il route legacy `GET /api/v1/assignments/{id}/generate-contract` resta disponibile per retrocompatibilita
  - quando l'assegnazione ha `ente_attuatore_id`, il legacy delega ora al motore template-based condiviso
  - se il motore template-based non puo essere usato, il legacy fa fallback controllato al vecchio `ContractGenerator`
- Impatto:
  - eliminata la duplicazione del renderer template dentro il route legacy
  - allineato il comportamento backend alla direzione gia scelta nel frontend
- Verifica eseguita:
  - `python3 -m py_compile backend/routers/contract_templates.py backend/routers/assignments.py` passato

## Implementazione 2026-03-30 — Sblocco template contratti e test end-to-end
- File toccati:
  - `backend/schemas.py`
  - `backend/contract_generator.py`
- Correzioni introdotte:
  - `GET /api/v1/contracts/` non va piu in `500` per record storici con `is_default = NULL`; lo schema backend ora tollera il dato legacy
  - il fallback legacy `ContractGenerator` non prova piu a creare output sotto `/app/contracts_output`, ma usa una directory sicura in `/tmp`
- Dati caricati nel backend:
  - template default `professionale` creato con ID `8`
  - template default `ordine_servizio` creato con ID `9`
  - template default `contratto_progetto` creato con ID `10`
  - template `occasionale` default attivo gia presente nel database
- Verifiche eseguite:
  - login reale backend confermato con `POST /api/v1/auth/login` -> `200`
  - `GET /api/v1/contracts/?limit=5` -> `200`
  - test reale su `GET /api/v1/assignments/1/generate-contract` -> `200 application/pdf`
  - test reale su `POST /api/v1/contracts/generate-contract` -> `200 application/pdf`
  - filename restituito: `contratto_Cacciapuoti_Next Group srl_20260330.pdf`
  - `python3 -m py_compile backend/schemas.py backend/contract_generator.py` passato

## Implementazione 2026-03-30 — UX ruolo su ProjectManager
- File toccati:
  - `frontend/src/App.js`
  - `frontend/src/components/ProjectManager.js`
  - `frontend/src/components/ProjectManager.css`
- Modifiche introdotte:
  - `ProjectManager` riceve ora `currentUser` dalla shell applicativa
  - aggiunto banner operativo coerente con il ruolo, allineato alla logica gia introdotta sui collaboratori
  - per `user/manager` le azioni strutturali di creazione/eliminazione progetto sono rese guidate o nascoste, lasciando il focus su aggiornamento stato, delivery e dati attuativi
  - per `admin` restano disponibili creazione, modifica ed eliminazione complete
- Verifica eseguita:
  - `npm run build` passato con `Compiled successfully`

## Implementazione 2026-03-30 — Riallineamento operativo manager enti
- File toccati:
  - `frontend/src/App.js`
  - `frontend/src/components/ImplementingEntitiesList.js`
  - `frontend/src/components/ImplementingEntitiesList.css`
- Modifiche introdotte:
  - `ImplementingEntitiesList` riceve ora `currentUser` dalla shell applicativa
  - aggiunto banner operativo coerente con il perimetro admin-only della sezione enti
  - introdotte summary cards operative su enti attivi, totale censito e anagrafiche in attenzione
  - aggiunta evidenza in card quando mancano PEC o legale rappresentante, per supportare il presidio contrattuale
- Verifica eseguita:
  - `npm run build` passato con `Compiled successfully`

## Implementazione 2026-03-30 — Dashboard monitor template contratti
- File toccati:
  - `frontend/src/components/Dashboard.js`
  - `frontend/src/components/Dashboard.test.js`
- Modifiche introdotte:
  - la dashboard carica anche i template contrattuali attivi/default dal backend
  - aggiunto alert critico quando esistono assegnazioni con `contract_type` privo di template default attivo
  - aggiunto focus esplicito sui default contrattuali nella vista admin e nel perimetro operativo
  - il cockpit rende quindi visibile subito un problema come l'assenza di `professionale`, senza aspettare il fallimento della generazione PDF
- Verifiche eseguite:
  - `npm test -- --watch=false --runInBand src/components/Dashboard.test.js` passato
  - `npm run build` passato con `Compiled successfully`

## Implementazione 2026-03-30 — Preparazione QA UI LAN
- Decisione operativa:
  - il backend contratti e il frontend sono considerati pronti per una verifica manuale UI su `http://192.168.2.161:3001/`
- Checklist QA preparata per il prossimo passaggio:
  - login admin (`admin / admin123`)
  - controllo dashboard/home per ruolo admin
  - verifica collaboratori -> preflight contratto -> generazione PDF
  - verifica progetti -> azioni admin disponibili
  - verifica enti attuatori -> summary cards e note di attenzione
- Obiettivo:
  - usare la UI reale come ultimo filtro per intercettare incoerenze residue di wiring, rendering o download file non visibili dai soli test locali

## Nota operativa
- In questa sessione non sono stati avviati container; lo stato sopra è basato su lettura dei file, struttura repository, `git status` e test frontend locali.
- Dopo il riallineamento contratti lato frontend, il prossimo passo piu sensato e:
  - verificare da browser login reale, dashboard e una generazione contratto end-to-end dalla UI collaboratori
  - completare la UX differenziata per ruolo nelle azioni secondarie ancora non riallineate nei manager residui
  - decidere in una fase successiva se dismettere definitivamente il fallback `ContractGenerator`

## Implementazione 2026-03-30 — Blocco 3: Catalogo + Listini

### File backend aggiunti/modificati
- `backend/alembic/versions/006_add_prodotti_listini.py` — migration tabelle `prodotti`, `listini`, `listino_voci`
- `backend/models.py` — aggiunti `Prodotto` (con `@validates tipo/prezzo_base`, indice su tipo+attivo), `Listino` (con `@validates tipo_cliente`), `ListinoVoce` (con `@hybrid_property prezzo_finale = override ?? base*(1-sconto/100)`)
- `backend/schemas.py` — aggiunti schemi per Prodotto, Listino, ListinoVoce + `ListinoWithVoci`, `PrezzoCalcolatoResponse`, `TIPI_PRODOTTO`/`TIPI_CLIENTE` Literal
- `backend/crud.py` — CRUD completo per le 3 entità + `calcola_prezzo_finale()` + `get_prezzo_prodotto_in_listino()`
- `backend/routers/catalogo.py` — `/api/v1/catalogo/` con `GET /tipi` prima di `/{id}`
- `backend/routers/listini.py` — `/api/v1/listini/` con `GET /tipi-cliente`, sub-routes `/voci` (CRUD), `/{id}/prezzo/{prodotto_id}`
- `backend/main.py` — registrati router `catalogo` e `listini`

### File frontend aggiunti/modificati
- `frontend/src/services/apiService.js` — aggiunte funzioni API per prodotti e listini/voci
- `frontend/src/components/CatalogoManager.js` + `.css` — prodotti raggruppati per tipo in sezioni grid, tipo-badge colorati, prezzo con Intl.NumberFormat
- `frontend/src/components/ListiniManager.js` + `.css` — split panel (sidebar listini + panel voci), inline voce form con price preview real-time, tabella voci con colonne prezzo_finale/override/sconto
- `frontend/src/App.js` — aggiunte sezioni `catalogo` e `listini` esposte ai ruoli `admin`, `user`, `manager`

### Verifiche
- `python3 -m py_compile` → OK
- `npm run build` → `Compiled successfully.`

### Note tecniche
- Prezzo finale su ListinoVoce: `prezzo_override ?? prezzo_base × (1 - sconto/100)`, ricalcolato ogni volta
- Route `/tipi` e `/tipi-cliente` definite PRIMA di `/{id}` per evitare conflitti FastAPI

---

## Implementazione 2026-03-30 — Blocco 4: Preventivi + Ordini

### File backend aggiunti/modificati
- `backend/alembic/versions/007_add_preventivi_ordini.py` — migration tabelle `preventivi`, `preventivo_righe`, `ordini`
- `backend/models.py` — aggiunti `Preventivo` (state machine `bozza|inviato|accettato|rifiutato`, `@hybrid_property totale`), `PreventivoRiga` (snapshot prezzo + calcolo importo), `Ordine` (stati `in_lavorazione|completato|annullato`, FK a preventivo + progetto)
- `backend/schemas.py` — schemi Create/Update/Read per le 3 entità + `PreventivoWithRighe`, `OrdineRead`, `STATI_PREVENTIVO`/`STATI_ORDINE` Literal
- `backend/crud.py` — CRUD completo + `transizione_stato()` con matrice transizioni valide + `converti_in_ordine()` + auto-numbering `PRV-YYYY-NNN`/`ORD-YYYY-NNN` via `MAX(numero_progressivo)+1`
- `backend/routers/preventivi.py` — `/api/v1/preventivi/` con endpoints stato (`/invia`, `/accetta`, `/rifiuta`, `/converti-ordine`), righe CRUD, `GET /{id}/pdf` via reportlab (tabella righe A4 con intestazione, metadati, totale)
- `backend/routers/ordini.py` — `/api/v1/ordini/` con lista paginata e update stato
- `backend/routers/__init__.py` + `backend/main.py` — registrati `preventivi` e `ordini`

### File frontend aggiunti/modificati
- `frontend/src/services/apiService.js` — aggiunte funzioni API per preventivi (incluso `downloadPreventivoPDF` con `responseType: 'blob'`) e ordini
- `frontend/src/components/PreventiviManager.js` + `.css` — tabella con badge stato colorati, azioni contestuali per stato (Invia/Accetta/Rifiuta/→Ordine/PDF/Elimina), modal dettaglio con gestione righe inline (calcolo importo real-time, auto-fill prezzo da prodotto), download PDF blob
- `frontend/src/components/OrdiniManager.js` + `.css` — lista ordini con filtri, transizioni Completa/Annulla, link al preventivo di origine
- `frontend/src/App.js` — aggiunte sezioni `preventivi` e `ordini` esposte ai ruoli `admin`, `user`, `manager`

### Verifiche
- `python3 -m py_compile` su tutti i file backend → OK
- `npm run build` → `Compiled successfully.` (zero warning)

### Note tecniche
- State machine lato backend: transizioni valide in dict `TRANSIZIONI_VALIDE = {'bozza': ['inviato'], 'inviato': ['accettato','rifiutato'], ...}`
- `converti_in_ordine()` controlla: stato=accettato, nessun ordine già esistente
- PDF generato con reportlab: tabella righe, metadati cliente/scadenza/stato, totale evidenziato — nessuna dipendenza aggiuntiva (già presente per contract_generator.py)
- Auto-numbering: `MAX(numero_progressivo) WHERE anno = year` → thread-safe a patto di non avere alta concorrenza; per produzione valutare SEQUENCE PostgreSQL nativa

## Prossimi passi consigliati (dopo Blocco 4)
1. Eseguire `alembic upgrade head` sul DB live (migration 004→007)
2. Verificare da browser: Catalogo, Listini, Preventivi, Ordini
3. Seed dati di test: prodotti/listini/preventivi di esempio
4. Collegare `Preventivo → Progetto`: alla conversione in ordine, offrire di creare/associare un progetto
5. Notifiche: alert dashboard per preventivi in scadenza o inviati senza risposta
6. Smoke test reale per ruoli `admin` e `operator` sul flusso commerciale, dato che le sezioni sono gia esposte anche a `user` e `manager`

## Deploy 2026-03-30 — Riavvio frontend

- Build copiato nel container `pythonpro_frontend` via `docker cp frontend/build/. pythonpro_frontend:/usr/share/nginx/html/`
- Nginx ricaricato con `nginx -s reload` → risposta HTTP 200 confermata
- Frontend disponibile su `http://localhost:3001` (porta pubblica `3001→80`)
- Blocchi 1–4 ora visibili nella navigazione admin

## Implementazione 2026-03-30 — Piano Finanziario Progetto centrato sul progetto

- Consolidata la decisione di dominio: la vecchia area `Associazioni Progetto-Ente` va trattata come `Piano Finanziario Progetto`, non come semplice collegamento tecnico tra entita'.
- La schermata e ora centrata sul progetto selezionato:
  - scelta progetto come punto di ingresso
  - riepilogo autoalimentato del progetto aperto
  - filtri secondari per mansione e stato dentro il progetto
  - tabella righe piano limitata al solo progetto selezionato
  - empty state guidato se nessun progetto e ancora scelto
- Il pulsante `Nuova Riga Piano` resta disabilitato finche non viene selezionato un progetto, per evitare inserimenti fuori contesto.
- Quando si apre una nuova riga piano da un progetto selezionato, il form eredita il progetto corrente e precompila l'ente dal progetto se `ente_attuatore_id` e gia presente.
- Il riepilogo economico del progetto mostra:
  - ore pianificate
  - ore assegnate
  - ore effettive
  - budget pianificato
  - costo assegnato
  - numero righe piano
- Verifica locale eseguita dopo il refactor: `npm run build` passato.
- Deploy finale eseguito nella stessa sessione: `docker compose up -d --build frontend` completato con container `pythonpro_frontend` ricreato e frontend disponibile su `http://localhost:3001`.

## Prossimo passo consigliato
1. Verificare da browser il flusso reale: selezione progetto -> lettura riepilogo -> inserimento nuova riga piano -> modifica/disattivazione riga.

## Sessione 2026-04-03 — FASE A Audit (Infrastruttura Agent-Ready)

### Task 1 — Vincoli e coerenza temporale (Gap 2.1/2.2)
- Potenziata `check_attendance_overlap()` in `backend/crud.py` con supporto cross-check su tabella `assignments`:
  - oltre alla sovrapposizione su `attendances`, ora verifica anche conflitti temporali su assegnazioni attive cross-progetto/cross-ente.
- Introdotte nuove validazioni backend su presenze:
  - `Attendance` con `assignment_id` ora valida obbligatoriamente che l'assegnazione sia attiva,
    appartenga a stesso collaboratore/progetto, e che la data presenza sia nel range `start_date/end_date`.
  - Blocco esplicito in caso di ore presenza fuori disponibilità assegnazione (coerenza con ore residue).
- Introdotto controllo cross-progetto su assegnazioni:
  - un collaboratore non può avere assegnazioni attive sovrapposte nel tempo su progetti di enti attuatori diversi.
  - applicato sia in `create_assignment` sia in `update_assignment`.

### Task 2 — Infrastruttura asincrona/event-driven con ARQ (Gap 1/2 AI Integration)
- Aggiunta dipendenza `arq` in `backend/requirements.txt`.
- Creato modulo `backend/async_events.py` con:
  - configurazione Redis settings,
  - enqueue ARQ da codice sincrono,
  - decorator `track_entity_event(...)` per emissione eventi su entità chiave,
  - helper webhook outbound `enqueue_webhook_notification(...)`.
- Creato worker ARQ `backend/arq_worker.py` con job:
  - `process_entity_change_event`
  - `send_outbound_webhook` (POST via `httpx` a URL esterno predefinito `PYTHONPRO_OUTBOUND_WEBHOOK_URL`).
- Integrato event emission su modifiche entità chiave:
  - `create_contract_template` / `update_contract_template`
  - `create_piano_finanziario`
- Integrato trigger webhook budget:
  - quando un piano supera il 90% (`totale_consuntivo / totale_preventivo >= 0.9`) viene accodata notifica outbound.
  - trigger attivo dopo creazione piano e dopo update voci piano.

### Task 3 — Audit log + endpoint aggregato per agenti (Gap 3/4 AI Integration)
- Aggiunto modello ORM `AuditLog` immutabile in `backend/models.py`:
  - campi: `entity`, `action`, `old_value`, `new_value`, `user_id`, `created_at`.
  - append-only enforcement via listener SQLAlchemy (`before_update`/`before_delete` -> errore).
- Introdotto helper audit in CRUD (`_create_audit_log`) e tracciamento operativo su:
  - create/update template contratti,
  - create piano finanziario,
  - update voci piano.
- Aggiunto endpoint super-contesto AI:
  - `GET /api/v1/projects/{id}/full-context` (`backend/routers/projects.py`).
  - ritorna in un’unica risposta: progetto, ente attuatore, piani finanziari attivi con stato budget, stato ore collaboratori aggregato.
  - implementazione con eager loading/subquery aggregate per evitare pattern N+1.
- Aggiunti schema Pydantic dedicati in `backend/schemas.py`:
  - `ProjectFullContext`, `PianoFinanziarioContextItem`, `ProjectCollaboratorHoursContext`, `AuditLog*`.

### Verifiche eseguite
- `python3 -m py_compile backend/crud.py backend/models.py backend/schemas.py backend/routers/projects.py backend/async_events.py backend/arq_worker.py` -> OK
- Test automatici non eseguiti: `pytest` non disponibile nell’ambiente (`No module named pytest`).

### Note operative / prossimi passi
- Configurare worker ARQ in runtime (processo separato) con Redis raggiungibile.
- Valutare deduplica webhook su soglia 90% per evitare notifiche ripetute su update ravvicinati.
- Estendere audit log ad altri aggregate critici (assignments/attendances) con identificazione `user_id` reale da auth context.
- Aggiungere migration Alembic esplicita per `audit_logs` se si vuole rollout controllato su ambienti dove `create_all` non è la strategia primaria.

## Sessione 2026-04-03 — FASE A Audit (Infrastruttura Agent-Ready)

### Task 1 — Potenziamento Vincoli Presenze/Assegnazioni
- Rifinita `check_attendance_overlap` in `backend/crud.py` con validazione estesa su tabella `assignments` nella stessa finestra temporale:
  - controllo assegnazioni attive sovrapposte (`start_date <= end_time` e `end_date >= start_time`),
  - blocco se `assignment_id` passato alla presenza non e attivo nel time window richiesto,
  - blocco cross-progetto/cross-ente quando esistono assegnazioni sovrapposte su enti attuatori diversi.
- Confermata e mantenuta la validazione backend su presenze fuori range assegnazione collegata (`_validate_attendance_assignment_date_range`) sia in `create_attendance` sia in `update_attendance`.
- Confermato il controllo cross-progetto sulle assegnazioni attive tra enti diversi in create/update assignment (`_validate_assignment_date_overlap_by_ente`).

### Task 2 — Infrastruttura Asincrona/Event-Driven (ARQ + Redis)
- Consolidato wiring ARQ:
  - `backend/arq_worker.py` ora usa `REDIS_HOST/REDIS_PORT/REDIS_DB/REDIS_PASSWORD` anche lato worker (`WorkerSettings.redis_settings`), evitando configurazione locale hardcoded.
- Estesa emissione eventi asincroni su entita chiave:
  - `bulk_upsert_voci_piano` decorata con `@track_entity_event("piano_finanziario", "updated")`.
  - `delete_contract_template` decorata con `@track_entity_event("contract_template", "deleted")`.
- Esteso outbound webhook base:
  - mantenuto trigger budget >=90% su piano (`_emit_piano_budget_threshold_event`),
  - aggiunte notifiche webhook anche su soft-delete/delete dei template contratto (`contract_template_soft_deleted`, `contract_template_deleted`).

### Task 3 — Audit Log + Super-Context
- Modello `AuditLog` immutabile gia presente e mantenuto (`backend/models.py`) con blocco update/delete via event listeners.
- Aggiunta migration Alembic `018_add_audit_logs_and_overlap_indexes.py`:
  - crea `audit_logs` se assente,
  - crea indici audit (`entity`, `action`, `user_id`, `created_at`),
  - aggiunge indici ottimizzati per overlap check su `assignments` e `attendances`.
- Endpoint agente `GET /api/v1/projects/{id}/full-context` gia operativo e documentato semanticamente (`summary` + `description`) in `backend/routers/projects.py`; aggregazione eseguita in `crud.get_project_full_context` evitando N+1 con eager loading + subquery aggregate.

### Fix infrastrutturale aggiuntivo
- Corretto `ensure_runtime_schema_updates()` in `backend/main.py`: rimossa collisione di chiavi duplicate `assignments` nel dict `table_updates` (ora include insieme `contract_signed_date` e `edizione_label`).

### Verifiche eseguite
- `python3 -m py_compile backend/crud.py backend/arq_worker.py backend/main.py backend/alembic/versions/018_add_audit_logs_and_overlap_indexes.py` -> OK

### Pendente residuo
- Eseguire `alembic upgrade head` sull'ambiente runtime target per applicare `018`.
- Validare end-to-end ARQ worker in ambiente Docker (enqueue + processing webhook) con `PYTHONPRO_OUTBOUND_WEBHOOK_URL` valorizzato.

### Sessione 2026-04-03 — Esecuzione operativa post-refactor
- Eseguito upgrade DB nel container backend: `python -m alembic upgrade head` -> applicata migration `017 -> 018` con successo.
- Verificata coda ARQ con smoke test reale:
  - enqueue job `process_entity_change_event`
  - enqueue job `send_outbound_webhook`
  - avvio worker `arq arq_worker.WorkerSettings --burst`
  - entrambi i job processati correttamente (`status: processed` e `status: sent`).
- Nota test webhook: URL usato per smoke `http://backend:8000/api/v1/system/health` ha risposto `404`, ma il worker ha completato regolarmente la POST, confermando catena enqueue->worker->HTTP outbound funzionante.
- Allineamento ambiente container: installato `arq` nel backend container (mancava nel runtime corrente).

### Sessione 2026-04-03 — Esecuzione guidata Step 1→4 (completata)

- **Step 1 (webhook URL predefinito)**
  - Aggiornato `docker-compose.yml` sul servizio `backend` con:
    - `PYTHONPRO_OUTBOUND_WEBHOOK_URL=http://webhook_sink:8080` (default)
    - `REDIS_DB=0`
  - Aggiunto servizio locale `webhook_sink` (`mendhak/http-https-echo:31`) per ricezione webhook outbound e verifica oggettiva.

- **Step 2 (persistenza dipendenze + rebuild)**
  - Confermato `arq` presente in `backend/requirements.txt`.
  - Eseguito rebuild backend con `docker compose up -d --build backend ...`.
  - Verifica runtime: `import arq` nel container backend -> `ARQ_OK 0.27.0`.

- **Step 3 (worker ARQ persistente)**
  - Aggiunto servizio `arq_worker` in `docker-compose.yml`.
  - Corretto avvio worker con override esplicito:
    - `entrypoint: ["arq"]`
    - `command: ["arq_worker.WorkerSettings"]`
  - Verifica: container `pythonpro_arq_worker` stabile e log worker attivo.

- **Step 4 (test funzionale trigger >=90 + audit)**
  - Eseguito test funzionale completo che porta il piano `id=1` oltre soglia budget (usage rilevato: `122.56%`).
  - Evidenza worker:
    - job `send_outbound_webhook` per evento `piano_finanziario_budget_threshold`
    - esito `status: sent`, `status_code: 200`.
  - Evidenza sink:
    - POST ricevuta con payload completo (`warning_code=budget_90_reached`, `usage_percentage=122.56`).
  - Audit log verificato:
    - record `entity=piano_finanziario`, `action=update_voci` presente.

#### Nota operativa importante
- Per forzare la verifica della soglia 90% sono stati inseriti **dati di test** su `piano_id=1` (presenze/valori economici). Prima di uso business reale va eseguito riallineamento del dataset con valori di produzione.

### Sessione 2026-04-03 — Fix 502 frontend `/health`
- Problema rilevato: il frontend Nginx faceva proxy verso un IP backend stale (`172.19.0.4`) dopo recreate container; risultato `502 Bad Gateway` su `http://100.100.49.54:3001/health`.
- Root cause: risoluzione DNS statica di `backend` in `frontend/nginx.conf` (upstream fissato all'avvio).
- Fix applicato:
  - aggiunto resolver Docker DNS dinamico in `frontend/nginx.conf`: `resolver 127.0.0.11 ipv6=off valid=10s;`
  - cambiato `proxy_pass` su `/api/` e `/health` usando variabile `backend_upstream` per risoluzione runtime.
- Deploy/fix runtime: `docker compose up -d --build frontend` eseguito con successo.
- Verifica finale:
  - `curl http://127.0.0.1:3001/health` -> `200`
  - body: `{"status":"ok"}`

## Sessione 2026-04-03 — Modulo Avvisi (implementazione operativa)

### Punto 1 — Refactor backend verso `avviso_id` (compatibile)
- Aggiunta entita `Avviso` nel dominio backend (`models.py`) con campi: `codice`, `ente_erogatore`, `descrizione`, `template_id`, `is_active`.
- Aggiunte FK `avviso_id` su:
  - `projects`
  - `piani_finanziari`
  - `piani_finanziari_fondimpresa`
- Aggiunte relazioni ORM (`avviso_rel`) e allineamento schemi Pydantic con `avviso_id` + oggetto annidato.
- Nuovo router API `backend/routers/avvisi.py` con CRUD + soft-delete.
- `crud.py` aggiornato con funzioni `get/create/update/delete avviso` e risoluzione avviso nei flussi project/piani con fallback compatibile.
- `piani_finanziari.py` aggiornato per usare codice avviso effettivo da relazione (`avviso_rel`) dove disponibile.
- Wiring completato in `backend/main.py` e `backend/routers/__init__.py`.

### Punto 2 — Migration e cleanup
- Aggiunta migration `019_add_avvisi_table_and_fk_columns.py`:
  - crea tabella `avvisi`
  - aggiunge colonne/FK/index `avviso_id` su tabelle target.
- Aggiunta migration `020_cleanup_legacy_avviso_columns.py`:
  - aggiorna indice univoco piani su `(..., avviso_id)`
  - prepara cleanup colonne legacy `avviso`.
- Runtime index aggiornato in `backend/main.py` su `idx_unique_piano_progetto_anno_ente_avviso_id`.

### Punto 3 — Frontend
- Nuova sezione UI admin `Avvisi`:
  - nuovo componente `frontend/src/components/AvvisiManager.js`
  - integrazione navigazione in `frontend/src/App.js`.
- API frontend aggiunte in `frontend/src/services/apiService.js`:
  - `getAvvisi`, `getAvviso`, `createAvviso`, `updateAvviso`, `deleteAvviso`.
- `ProjectManager` aggiornato:
  - carica catalogo avvisi da backend
  - invia `avviso_id` nel payload progetto
  - sostituito campo avviso libero con select da catalogo filtrata per ente erogatore.

### Verifiche eseguite
- Backend compile check:
  - `python3 -m py_compile backend/crud.py backend/models.py backend/schemas.py backend/routers/avvisi.py backend/routers/piani_finanziari.py backend/main.py backend/alembic/versions/019_add_avvisi_table_and_fk_columns.py backend/alembic/versions/020_cleanup_legacy_avviso_columns.py` -> OK
- Frontend build:
  - `npm run build` -> `Compiled successfully`.
  - warning non bloccanti su dataset browser (`baseline-browser-mapping`, `caniuse-lite`) invariati.

### Pendente residuo
- Completare refactor approfondito dei filtri template ancora basati su `contract_templates.avviso` per passare pienamente a join su `avvisi` (fase hard-cut post migrazione 020).
- Validare in ambiente Docker il flusso completo UI: Progetto -> Avviso -> Piano -> Template collegato.

## Sessione 2026-04-03 — Fix operativo avvisi multipli + piani (hotfix UI/DB)

### Problema segnalato utente
- In UI non era visibile/affidabile il flusso per collegare **piu avvisi allo stesso template piano finanziario**.
- In sezione `Piani Finanziari` il comportamento appariva bloccato su `Formazienda` invece di rispettare il contesto ente selezionato.

### Interventi eseguiti
- **Backend / DB**
  - Confermato e applicato modello 1→N template-avvisi (un template puo avere piu avvisi).
  - Rimosso vincolo one-to-one su `avvisi.template_id` nel modello ORM.
  - Aggiunta migration `021_allow_multiple_avvisi_per_template.py` (drop indice unique su `template_id`).
  - Eseguito `alembic upgrade head` nel container backend (`pythonpro_backend`).

- **Frontend Template**
  - `ContractTemplateModal` aggiornato:
    - aggiunta sezione `Avvisi Collegati (selezione multipla)` con **checkbox** (niente Ctrl/Cmd multi-select).
    - aggiunta creazione inline `+ Aggiungi Avviso` (incrementale) filtrata per ente erogatore.
    - il save passa `linked_avviso_ids` al manager.
  - `ContractTemplatesManager` aggiornato:
    - dopo create/update template sincronizza i link su `/avvisi`:
      - collega gli avvisi selezionati al template,
      - scollega quelli rimossi.

- **Frontend Piani**
  - `PianiFinanziariManager` aggiornato:
    - caricamento catalogo avvisi da API,
    - campo `Avviso` convertito da input libero a select filtrata per ente,
    - rimosso fallback che manteneva contesti sporchi (avviso/ente) e causava effetto percepito `solo Formazienda`.

- **Deploy/runtime**
  - Rebuild completo frontend con `docker compose up -d --build frontend`.
  - Backend ricreato nel medesimo ciclo compose.
  - Porta frontend confermata: `3001`.

### Verifiche eseguite
- `npm run build` frontend: `Compiled successfully`.
- `python3 -m py_compile` sui file backend toccati: OK.
- `docker compose up -d --build frontend`: completato.
- `docker exec pythonpro_backend python -m alembic upgrade head`: completato.

### Stato attuale
- Flusso richiesto disponibile: da `Template` (ambito `piano_finanziario`) e possibile collegare **piu avvisi** allo stesso template.
- In `Piani Finanziari` la selezione avviso e ora guidata da catalogo e allineata all'ente.

### Nota operativa
- Se lato browser non compaiono subito i nuovi blocchi, necessario hard refresh (`Ctrl+F5`) e verifica accesso con ruolo `admin` sulla UI aggiornata in porta `3001`.

## Sessione 2026-04-03 — Fix template piano finanziario multi-avviso (UI coerente)

### Problema affrontato
- I template `piano_finanziario` potevano gia avere piu avvisi collegati tramite `avvisi.template_id`, ma varie UI continuavano a leggere solo il campo legacy `template.avviso`.
- Effetto operativo: nella selezione template/piano/progetto sembrava valido solo un avviso, tipicamente l'ultimo salvato o quello scritto nel campo legacy.

### Interventi eseguiti
- `frontend/src/components/ContractTemplatesManager.js`
  - caricata la mappa reale `template_id -> [avvisi]` da `/api/v1/avvisi`;
  - estesa la ricerca testuale anche ai codici/descrizioni degli avvisi collegati;
  - aggiunta visibilita esplicita in card della lista `Avvisi collegati`, non solo del campo legacy `avviso`.
- `frontend/src/components/PianiFinanziariManager.js`
  - la selezione automatica del template ora confronta l'avviso scelto con tutti gli avvisi collegati al template, non solo con `template.avviso`;
  - la select `Template piano` mostra l'elenco reale degli avvisi collegati (`Avvisi X, Y, Z`);
  - quando si seleziona un template, il form valorizza il primo avviso realmente collegato come default coerente.
- `frontend/src/components/ProjectManager.js`
  - la select `Template Piano Finanziario` mostra tutti gli avvisi collegati al template;
  - il collegamento template -> avviso progetto ora usa il catalogo reale degli avvisi associati e non piu solo una lookup singola implicita.

### Verifiche eseguite
- `npm run build` in `frontend/` -> `Compiled successfully`.
- Restano solo warning non bloccanti gia noti su `baseline-browser-mapping` e `caniuse-lite`.

### Stato attuale
- In `Template Documenti` i template piano finanziario mostrano gli avvisi collegati come elenco reale.
- In `Piani Finanziari` e `Progetti` la UI non si comporta piu come se esistesse solo l'ultimo avviso salvato.
- La persistenza backend resta invariata: il legame ufficiale continua a vivere su `avvisi.template_id`, con compatibilita legacy su `contract_templates.avviso`.

### Pendente residuo
- Valutare hardening backend/API per esporre direttamente nel payload template un array `linked_avvisi`, evitando alla UI di dover ricostruire sempre la join lato client.
- Validare in ambiente utente finale che il default "primo avviso collegato" sia sufficiente oppure se serve una nozione esplicita di avviso primario per template.

## Sessione 2026-04-03 — Step aggiuntivo UI modal template piano: tabella avvisi

### Intervento aggiuntivo
- Su richiesta utente, il modal di `Template Piano Finanziario` ora mostra una **tabella avvisi** esplicita nella sezione `Avvisi Collegati`.
- File aggiornati:
  - `frontend/src/components/ContractTemplateModal.js`
  - `frontend/src/components/ContractTemplateModal.css`

### Dettagli UI
- Aggiunto riepilogo numerico `N avvisi collegati`.
- Sostituita la lista minimale con tabella avente colonne:
  - `Collega`
  - `Codice`
  - `Descrizione`
  - `Stato`
- Evidenza visiva delle righe gia collegate al template con badge `Collegato`.
- La selezione multipla resta invariata, ma ora e leggibile e verificabile a colpo d'occhio.

### Verifica
- `npm run build` frontend -> `Compiled successfully`.

## Sessione 2026-04-03 — Fix selezione avvisi in Piani e Delivery Progetti

### Problema affrontato
- In `Piani Finanziari` la select `Avviso` non esponeva in modo coerente tutti gli avvisi collegati al template selezionato.
- In `Progetti > Delivery`, selezionando un `Template Piano Finanziario`, i campi `Ente Erogatore` e `Avviso` risultavano bloccati e il sistema si fermava di fatto sul primo avviso disponibile (es. `2/2022`).

### Interventi eseguiti
- `frontend/src/components/PianiFinanziariManager.js`
  - la select `Avviso` ora usa come sorgente primaria gli avvisi realmente collegati al template selezionato;
  - se non c'e un template selezionato, continua a mostrare il catalogo filtrato per ente erogatore.
- `frontend/src/components/ProjectManager.js`
  - rimossa la disabilitazione forzata dei campi `Ente Erogatore` e `Avviso` quando e presente un template piano;
  - la select `Avviso` mostra gli avvisi collegati al template selezionato, non un solo default implicito;
  - se l'utente cambia manualmente ente erogatore verso un ente incompatibile con il template corrente, il template viene sganciato per evitare incoerenze.

### Verifica
- `npm run build` frontend -> `Compiled successfully`.

## Sessione 2026-04-03 — Verifica runtime e rebuild frontend

### Evidenza dati reali
- Verificato dentro il container backend che gli avvisi Formazienda sono entrambi collegati al template `id=12`:
  - `2/2022` -> `template_id=12`
  - `2/2025` -> `template_id=12`
- Quindi il problema residuo non era nel dato salvato ma nel frontend servito/runtime lato browser.

### Azione eseguita
- Eseguito rebuild e recreate del servizio frontend:
  - `docker compose -f /DATA/progetti/pythonpro/docker-compose.yml up -d --build frontend`
- Stato finale servizio frontend: `healthy`.

## Sessione 2026-04-03 — Consolidamento UI avvisi sotto Template

### Decisione presa
- Gli avvisi dei `piani_finanziari` non devono vivere in una sezione admin separata.
- La ownership UI viene consolidata nella sezione `Template`, che resta il punto unico di gestione per:
  - template piano finanziario
  - avvisi collegati al template
  - tabella degli avvisi collegati

### Interventi eseguiti
- Rimossa la voce di navigazione admin `Avvisi` dal frontend.
- Rimossa la route/render section `avvisi` da `frontend/src/App.js`.
- Aggiornata la copy in `ContractTemplatesManager` per esplicitare che la gestione avvisi avviene direttamente dentro `Template`.
- Rebuild e recreate del frontend Docker completati con successo.

### Stato attuale
- L'utente gestisce gli avvisi dei piani finanziari dal modal/template piano finanziario.
- Non esiste piu una sezione separata `Avvisi` nella navigazione admin.

## Sessione 2026-04-03 — Cleanup codice morto AvvisiManager

### Intervento eseguito
- Eliminato il file non piu usato `frontend/src/components/AvvisiManager.js`.
- La sezione `Avvisi` era gia stata rimossa dalla navigation e dal render path; questo step completa il cleanup del codice morto.

### Verifiche
- `npm run build` frontend -> `Compiled successfully`.
- Rebuild frontend Docker completato con successo.

## Sessione 2026-04-03 — Estensione anagrafiche Aziende e Collaboratori

### Decisioni operative fissate
- In `Aziende Clienti`, `ragione_sociale` e `partita_iva` sono da considerare obbligatori nel flusso applicativo.
- La `partita_iva` deve essere univoca globalmente tra `aziende_clienti` e `collaborators`, non solo all'interno della singola tabella.
- Le anagrafiche devono diventare profili progressivamente arricchibili: i campi di profiling restano opzionali e aggiornabili in seguito.

### Interventi backend eseguiti
- Esteso il dominio `AziendaCliente` con nuovi campi di profiling:
  - `attivita_erogate`
  - social/canali ufficiali azienda: `sito_web`, `linkedin_url`, `facebook_url`, `instagram_url`
  - legale rappresentante: nome, cognome, codice fiscale, email, telefono, linkedin, facebook, instagram, tiktok
  - referente operativo: nome, ruolo, email, telefono, luogo nascita, data nascita, linkedin, facebook, instagram, tiktok
- Esteso il dominio `Collaborator` con nuovi campi di profiling:
  - `profilo_professionale`, `competenze_principali`, `certificazioni`
  - canali personali/professionali: `sito_web`, `portfolio_url`, `linkedin_url`, `facebook_url`, `instagram_url`, `tiktok_url`
- Aggiunti helper backend in `crud.py` per ricerca conflitti incrociati di partita IVA tra aziende e collaboratori.
- Aggiornati i router `aziende_clienti` e `collaborators` per bloccare create/update/import quando una partita IVA e gia usata dall'altra entita.
- Corretto il router `admin/metrics` per serializzare in modo JSON-safe i risultati SQLAlchemy ed evitare `500` lato dashboard admin.

### Migration / runtime schema
- Aggiunta migration Alembic `022_add_azienda_cliente_profiling_fields.py`.
- Aggiunta migration Alembic `023_add_collaborator_profiling_fields.py`.
- Aggiunta migration Alembic `024_extend_azienda_contact_profiles.py`.
- Aggiornato `backend/main.py` con runtime schema update coerente per nuovi campi `aziende_clienti` e `collaborators`.

### Interventi frontend eseguiti
- `AziendeClientiManager` esteso con:
  - obbligatorieta frontend di `Partita IVA`
  - validazione checksum P.IVA prima del submit
  - sezioni aggiuntive per attivita/servizi erogati, social ufficiali azienda, legale rappresentante e referente operativo
  - distinzione esplicita tra social ufficiali azienda, social del referente e social del legale rappresentante
  - luogo/data nascita del referente operativo
  - fix post-create per far comparire subito la nuova azienda in elenco
  - fix query `consulenti`/`agenzie` portate a `limit=100` per allineamento ai vincoli API
- `CollaboratorForm` esteso con campi di profiling e social:
  - bio/profilo professionale
  - competenze principali
  - certificazioni
  - sito, portfolio, LinkedIn, Facebook, Instagram, TikTok

### Verifiche eseguite
- `python3 -m py_compile backend/models.py backend/schemas.py backend/main.py backend/routers/admin.py backend/routers/aziende_clienti.py backend/routers/collaborators.py backend/crud.py backend/alembic/versions/022_add_azienda_cliente_profiling_fields.py backend/alembic/versions/023_add_collaborator_profiling_fields.py backend/alembic/versions/024_extend_azienda_contact_profiles.py` passato
- `npm run build` frontend passato
- `docker compose up -d --build backend frontend` eseguito con successo

### Stato attuale
- Backend e frontend Docker riallineati e ripartiti con i nuovi campi.
- Le anagrafiche aziende e collaboratori ora supportano profiling piu ricco senza imporre da subito tutti i dettagli.
- Punto da osservare nelle prossime sessioni: verificare sul dato reale l'ergonomia del nuovo form aziende/collaboratori e valutare eventuali ulteriori campi verticali per commerciale/HR.

## Sessione 2026-04-03 — Programma sviluppo primi 5 agenti

### Obiettivo
- Avviare l'integrazione in piattaforma dei primi 5 agenti AI realmente utili a `pythonpro`, evitando chatbot generici e privilegiando agenti verticali che lavorano su anagrafiche, qualita dato, documenti e compliance.

### Ordine di implementazione approvato
1. `Data Quality Agent`
2. `Azienda Profiler Agent`
3. `Collaboratore Profiler Agent`
4. `Document Intake Agent`
5. `Compliance Agent`

### Principi architetturali fissati
- Gli agenti non devono scrivere dati in automatico senza tracciabilita.
- Ogni agente deve produrre:
  - output strutturato
  - `confidence_score`
  - motivazione sintetica
  - proposta di aggiornamento
  - stato revisione (`pending_review`, `accepted`, `rejected`, `applied`)
- Esecuzione asincrona via job queue/worker, non in request sincrona della UI.
- Distinzione netta tra:
  - dati sorgente
  - dati derivati
  - dati suggeriti da agente
- Audit log obbligatorio per ogni esecuzione e per ogni applicazione suggerimento.

### Fondazione tecnica comune da sviluppare prima degli agenti
- Creare modulo backend dedicato `ai_agents/` con:
  - registry agenti
  - orchestratore job
  - serializer input/output
  - policy di review
- Introdurre tabelle nuove:
  - `agent_runs`
  - `agent_suggestions`
  - `agent_review_actions`
  - `agent_profiles_cache` oppure equivalente per snapshot derivati
- Definire payload standard:
  - `entity_type`
  - `entity_id`
  - `agent_name`
  - `input_snapshot`
  - `result_payload`
  - `confidence_score`
  - `status`
  - `reviewed_by`
  - `reviewed_at`
- Aggiungere endpoint API:
  - `POST /api/v1/agents/run`
  - `GET /api/v1/agents/runs`
  - `GET /api/v1/agents/suggestions`
  - `POST /api/v1/agents/suggestions/{id}/accept`
  - `POST /api/v1/agents/suggestions/{id}/reject`
- Prevedere UI admin/operativa per:
  - lanciare agente
  - vedere risultati
  - applicare o scartare suggerimenti

### Roadmap per agente

#### 1. Data Quality Agent
- Scopo:
  - trovare incoerenze e buchi dati su aziende, collaboratori, referenti, documenti, P.IVA, CF, template, assegnazioni
- Input:
  - `aziende_clienti`
  - `collaborators`
  - `assignments`
  - `contract_templates`
  - document metadata
- Output:
  - issue list con severita (`critical`, `warning`, `info`)
  - score qualita anagrafica per entita
  - task suggerite
- Primo deliverable:
  - check P.IVA duplicate cross-entity
  - campi obbligatori mancanti
  - documenti scaduti/mancanti
  - referente/legale rappresentante incompleti
- UI:
  - badge score in scheda azienda/collaboratore
  - lista issue filtrabile
- Motivazione priorita:
  - e la base per tutti gli altri agenti; senza qualita dato gli agenti di profiling generano risultati sporchi

#### 2. Azienda Profiler Agent
- Scopo:
  - arricchire il profilo azienda con descrizione operativa, classificazioni, focus attivita, maturita commerciale e tag
- Input:
  - anagrafica azienda
  - attivita erogate
  - preventivi/ordini/progetti collegati
  - note operative
- Output:
  - `company_summary`
  - `industry_tags`
  - `service_tags`
  - `commercial_maturity`
  - `missing_profile_fields`
- Primo deliverable:
  - generazione riepilogo azienda
  - tagging automatico settore/servizi
  - suggerimenti campi da completare
- UI:
  - box “Profilo AI azienda”
  - accetta/rigetta suggerimenti di classificazione

#### 3. Collaboratore Profiler Agent
- Scopo:
  - costruire un profilo professionale leggibile e utilizzabile per matching e contratti
- Input:
  - anagrafica collaboratore
  - competenze
  - certificazioni
  - storico assegnazioni/presenze
  - documenti caricati
- Output:
  - `professional_summary`
  - `skills_tags`
  - `role_fit`
  - `profile_completeness`
  - `missing_documents`
- Primo deliverable:
  - riepilogo professionale
  - tag competenze
  - warning sui dati mancanti
- UI:
  - box “Profilo AI collaboratore”
  - sezione “Competenze suggerite”

#### 4. Document Intake Agent
- Scopo:
  - leggere documenti caricati e proporre compilazione strutturata dei campi piattaforma
- Input:
  - CV
  - documento identita
  - documenti aziendali
  - template/documenti vari
- Output:
  - campi estratti
  - campi riconosciuti con confidence
  - mismatch tra documento e anagrafica corrente
- Primo deliverable:
  - parsing CV collaboratore
  - parsing documento identita collaboratore
  - parsing documento aziendale base
- UI:
  - preview campi estratti
  - apply selettivo campo per campo
- Dipendenze:
  - richiede gia pronta la pipeline `agent_suggestions`

#### 5. Compliance Agent
- Scopo:
  - controllare se una pratica e pronta per contratto/assegnazione/flusso operativo
- Input:
  - collaboratore
  - azienda
  - progetto
  - assignment
  - template
  - documenti
- Output:
  - checklist compliance
  - blocchi operativi
  - warning risolvibili
  - suggerimenti completamento
- Primo deliverable:
  - preflight per generazione contratto
  - check coerenza template/ente/progetto
  - check documenti e anagrafiche minime
- UI:
  - pannello semaforico `ready / warning / blocked`

### Milestone sviluppo consigliate

#### Milestone 1 — Infrastruttura agenti
- creare tabelle e router base
- creare orchestratore job
- creare schermata review suggerimenti
- risultato atteso:
  - piattaforma pronta a ospitare agenti senza logica hardcoded nei router business

#### Milestone 2 — Data Quality Agent
- implementare controlli base
- mostrare score e issue list in UI
- risultato atteso:
  - prima funzionalita AI realmente usabile in produzione interna

#### Milestone 3 — Profiler azienda + collaboratore
- attivare suggerimenti testuali e tagging
- integrare review/apply nei dettagli entita
- risultato atteso:
  - anagrafiche vive e progressivamente arricchibili

#### Milestone 4 — Document Intake
- introdurre estrazione campi da file
- apply selettivo dei suggerimenti
- risultato atteso:
  - riduzione data-entry manuale

#### Milestone 5 — Compliance
- chiudere il giro con preflight prima di contratti/assegnazioni
- risultato atteso:
  - blocchi automatici sui casi non pronti

### Backlog operativo prossima sessione
- [ ] Disegnare schema DB per `agent_runs`, `agent_suggestions`, `agent_review_actions`
- [ ] Definire contratto JSON standard degli agenti
- [ ] Creare struttura backend `ai_agents/`
- [ ] Scegliere se usare worker esistente oppure coda dedicata per esecuzione agenti
- [ ] Implementare prima versione del `Data Quality Agent`

## Sessione 2026-04-04 — Milestone 1 agenti backend completata

### Obiettivo eseguito
- Ripresa la parte "agenti" del backlog senza riesplorare il repo da zero, con focus su infrastruttura backend minima realmente eseguibile.

### Interventi eseguiti
- Aggiunto scaffolding backend `backend/ai_agents/` con registry centrale e primo runner `data_quality`.
- Implementato `Data Quality Agent` iniziale:
  - analizza `projects`, `collaborators`, `aziende_clienti`
  - genera suggerimenti strutturati su campi mancanti, documenti incompleti, incoerenze date e mancanza template piano.
- Aggiunte nuove tabelle ORM:
  - `agent_runs`
  - `agent_suggestions`
  - `agent_review_actions`
- Aggiunta migration Alembic `027_add_ai_agent_core_tables.py`.
- Estesi gli schemi Pydantic con contratto standard agenti:
  - catalogo agenti
  - richiesta run
  - run con summary/suggestions
  - suggestion con review actions
- Aggiunto router backend `backend/routers/agents.py` con endpoint:
  - `GET /api/v1/agents/catalog`
  - `POST /api/v1/agents/run`
  - `GET /api/v1/agents/runs`
  - `GET /api/v1/agents/suggestions`
  - `POST /api/v1/agents/suggestions/{id}/accept`
  - `POST /api/v1/agents/suggestions/{id}/reject`
- Integrato il router in `backend/main.py` e `backend/routers/__init__.py`.
- Tracciamento audit aggiunto anche sul perimetro agenti:
  - creazione run
  - accettazione/rifiuto suggestion

### Verifiche eseguite
- `python3 -m py_compile backend/models.py backend/schemas.py backend/main.py backend/routers/__init__.py backend/routers/agents.py backend/ai_agents/__init__.py backend/ai_agents/registry.py backend/ai_agents/data_quality.py backend/alembic/versions/027_add_ai_agent_core_tables.py` -> OK

### Stato attuale parte agenti
- La piattaforma non e piu solo "agent-ready" a livello infrastrutturale: esiste ora un primo backend agentico eseguibile e reviewabile.
- Il primo agente disponibile e `data_quality`.
- Le suggestion non applicano ancora modifiche automatiche ai dati: restano in stato review umano (`pending/accepted/rejected`), coerentemente con la decisione di non permettere scritture automatiche senza tracciabilita.

### Pendente residuo parte agenti
- Eseguire `alembic upgrade head` sull'ambiente runtime target per applicare la migration `027`.
- Decidere se l'esecuzione agenti deve restare sync lato API o passare sul worker ARQ gia introdotto.
- Implementare UI dedicata per review `agent_suggestions`.
- Introdurre il primo apply controllato dei suggerimenti accettati.
- Estendere il catalogo con `Azienda Profiler Agent`, `Collaboratore Profiler Agent`, `Document Intake Agent`, `Compliance Agent`.

### Decisione per prossima ripartenza
- La prossima sessione deve partire dalla chiusura della parte agenti con focus su:
  - applicazione migration `027`
  - UI review suggerimenti
  - eventuale asincronizzazione run su ARQ

## Sessione 2026-04-04 — Mail Recovery Agent backend aggiunto

### Obiettivo eseguito
- Esteso il perimetro agenti con un agente focalizzato sulla comunicazione verso collaboratori per recupero dati mancanti e documenti in scadenza, coerente con il bisogno operativo espresso.

### Interventi eseguiti
- Aggiunto nuovo agente `mail_recovery` nel registry backend agenti.
- Implementato `backend/ai_agents/mail_recovery.py`:
  - supporto iniziale sul perimetro `collaborator`
  - genera suggestion email verso collaboratori con:
    - dati anagrafici/professionali mancanti
    - curriculum mancante
    - partita IVA mancante
    - documento identita mancante
    - documento identita senza scadenza
    - documento identita in scadenza entro 30 giorni
- Ogni suggestion contiene gia payload email strutturato:
  - destinatario
  - oggetto
  - corpo bozza
  - metadati campi mancanti / giorni alla scadenza
- Aggiunto nuovo modello ORM `AgentCommunicationDraft` per persistere le bozze email.
- Aggiunta migration Alembic `028_add_agent_communication_drafts.py`.
- Esteso `backend/routers/agents.py`:
  - quando gira `mail_recovery`, le suggestion vengono materializzate anche come bozze persistenti
  - nuovo endpoint `GET /api/v1/agents/communications`
  - nuovo endpoint `POST /api/v1/agents/communications/{draft_id}/status`
- Estesi schemi Pydantic con `AgentCommunicationDraft*`.

### Verifiche eseguite
- `python3 -m py_compile backend/models.py backend/schemas.py backend/routers/agents.py backend/ai_agents/registry.py backend/ai_agents/mail_recovery.py backend/alembic/versions/028_add_agent_communication_drafts.py` -> OK

### Stato attuale
- Il catalogo agenti include ora:
  - `data_quality`
  - `mail_recovery`
- `mail_recovery` non invia email reali: prepara e persiste bozze reviewabili, mantenendo controllo umano sul flusso.

### Pendente residuo parte agenti
- Applicare anche la migration `028` oltre alla `027` nell'ambiente runtime.
- Aggiungere template email configurabili per tipologia richiesta.
- Introdurre integrazione SMTP/IMAP o provider esterno solo dopo aver chiuso review UI e policy di invio.
- Estendere `mail_recovery` anche al perimetro `azienda_cliente` se serve recupero PEC/referente/documenti aziendali.

## Sessione 2026-04-04 — UI Agenti esposta nel frontend + fix errori runtime

### Problemi emersi
- In frontend gli agenti non erano visibili nonostante il backend fosse gia attivo: mancavano voce di navigazione, schermata dedicata e service layer.
- In parallelo sono emersi due errori runtime:
  - `GET /api/v1/catalogo/?attivo=true&limit=500` -> `422` per superamento limite massimo API (`200`)
  - `GET /api/v1/piani-finanziari/?...` -> `500` per colonna DB mancante `piani_finanziari.avviso`

### Interventi eseguiti
- Aggiunta UI admin `Agenti` nel frontend:
  - nuovo componente `frontend/src/components/AgentsManager.js`
  - nuovi stili `frontend/src/components/AgentsManager.css`
  - nuova voce navbar admin `Agenti` e route frontend `/agents`
  - integrazione in `frontend/src/App.js`
- Esteso `frontend/src/services/apiService.js` con supporto endpoint agenti:
  - `GET /agents/catalog`
  - `POST /agents/run`
  - `GET /agents/runs`
  - `GET /agents/suggestions`
  - `POST /agents/suggestions/{id}/accept`
  - `POST /agents/suggestions/{id}/reject`
  - `GET /agents/communications`
  - `POST /agents/communications/{id}/status`
- La UI Agenti ora permette:
  - selezione agente e tipo entita
  - scelta record progetto/collaboratore/azienda o run globale
  - esecuzione agente con `limit`
  - lettura run recenti con summary
  - review suggerimenti `accept/reject`
  - review bozze comunicazione `approved/sent`
- Fix frontend `ListiniManager`: ridotto `limit` catalogo da `500` a `200` per rispettare il vincolo backend.
- Fix backend `main.py`: l'auto-heal schema runtime ora ricrea anche `piani_finanziari.avviso` quando manca, riallineando installazioni che avevano gia migrato via la colonna legacy.

### Verifiche eseguite
- `python3 -m py_compile backend/main.py backend/routers/agents.py` -> OK
- `npm run build` -> OK
- `docker compose up -d --build backend frontend` -> OK
- `docker compose up -d --build frontend` -> OK dopo aggiunta UI agenti
- Verifica endpoint dal container backend:
  - `GET /api/v1/piani-finanziari/?limit=3` -> `200`
  - `GET /api/v1/catalogo/?attivo=true&limit=3` -> `200`
  - `GET /api/v1/agents/catalog` -> catalogo agenti disponibile

### Stato attuale parte agenti
- Gli agenti ora sono visibili e usabili dal gestionale lato admin.
- Il catalogo esposto in UI include al momento:
  - `data_quality`
  - `mail_recovery`
- Restano agenti "assistiti": producono analisi, suggerimenti e bozze, ma non applicano ancora scritture automatiche ai dati.

### Pendente residuo parte agenti
- Passare `requested_by_user_id` / `reviewed_by_user_id` reali dal frontend invece di `null`, se si vuole audit utente completo.
- Valutare filtri aggiuntivi e paginazione nella UI Agenti quando il numero di run/suggestions cresce.
- Decidere se portare i run agenti su ARQ per evitare esecuzioni sincrone in request/response.

## Sessione 2026-04-04 — Layer LLM pluggabile per agenti

### Obiettivo eseguito
- Rendere i primi agenti compatibili con un provider LLM reale senza legarli a un solo vendor, mantenendo fallback deterministico e nessuna dipendenza nuova oltre a `httpx` gia presente.

### Interventi eseguiti
- Aggiunto nuovo layer comune `backend/ai_agents/llm.py` per provider configurabili via environment.
- Provider supportati in questa prima versione:
  - `none`
  - `ollama`
  - `openclaw`
- Scelta architetturale esplicita:
  - i controlli business restano deterministici nei runner Python
  - l'LLM viene usato solo per migliorare la copy delle comunicazioni
  - se il provider non risponde o non e configurato, il flusso continua con le bozze deterministiche gia presenti
- Integrato il layer LLM nel runner `backend/ai_agents/mail_recovery.py`:
  - le email di recupero dati e documento identita possono ora essere riscritte da LLM
  - il payload suggestion salva anche `copy_provider` e `copy_model`
  - il summary del run espone `llm_provider`, `llm_enabled`, `llm_generated_count`
- Aggiunte variabili ambiente documentate su:
  - `.env.example`
  - `.env.sample`
  - `.env.production.template`
- Configurazione prevista:
  - `AI_AGENT_LLM_PROVIDER=ollama` + `OLLAMA_BASE_URL` + `AI_AGENT_LLM_MODEL`
  - oppure `AI_AGENT_LLM_PROVIDER=openclaw` + `OPENCLAW_BASE_URL` + `AI_AGENT_LLM_MODEL`
- Assunzione implementativa per `openclaw`:
  - trattato come endpoint chat compatibile OpenAI su path configurabile `OPENCLAW_CHAT_PATH`
  - se l'istanza reale usa un path o payload diverso, bastera adattare solo `backend/ai_agents/llm.py`

### Verifiche eseguite
- `python3 -m py_compile backend/ai_agents/llm.py backend/ai_agents/mail_recovery.py backend/ai_agents/registry.py backend/routers/agents.py` -> OK
- `npm run build` -> OK

### Stato attuale parte agenti
- Il backend agenti ha ora due livelli distinti:
  - analisi/regole deterministiche
  - arricchimento opzionale LLM per la sola generazione copy
- `mail_recovery` e il primo agente realmente predisposto per provider LLM locali/remoti.
- `data_quality` resta ancora deterministic-only, coerentemente con la scelta di introdurre l'LLM prima dove il ROI e piu alto.

### Pendente residuo parte agenti
- Verificare con test reale di connettivita quale endpoint `OpenClaw` sia esposto sul server e se sia davvero compatibile `chat/completions`.
- Portare in environment runtime le variabili:
  - `AI_AGENT_LLM_PROVIDER`
  - `AI_AGENT_LLM_MODEL`
  - `OLLAMA_BASE_URL` oppure `OPENCLAW_BASE_URL`
- Valutare un endpoint diagnostico semplice per mostrare in UI se il provider LLM e raggiungibile.
- Estendere anche `data_quality` con spiegazioni/prioritizzazione LLM, ma solo dopo aver validato il path `mail_recovery`.

## Sessione 2026-04-04 — Runtime LLM attivato su Ollama + health check

### Obiettivo eseguito
- Portare il layer LLM da "solo codice predisposto" a configurazione runtime realmente funzionante nel backend `pythonpro`.

### Interventi eseguiti
- Esteso `backend/routers/agents.py` con endpoint diagnostico `GET /api/v1/agents/llm/health`.
- Esteso `backend/schemas.py` con schema `AgentLlmHealth`.
- Esteso `backend/ai_agents/llm.py` con probe health provider-specifico:
  - `ollama`: check `GET /api/tags`
  - `openclaw`: check reachability gateway base URL + dettaglio configurazione
- Aggiornato `docker-compose.yml`:
  - pass-through env LLM su `backend` e `arq_worker`
  - `extra_hosts: host.docker.internal:host-gateway` per raggiungere provider locali sul server host
- Configurato `.env` runtime del progetto per usare `ollama` come primo provider attivo:
  - `AI_AGENT_LLM_PROVIDER=ollama`
  - `AI_AGENT_LLM_MODEL=qwen2.5:1.5b`
  - `AI_AGENT_LLM_TIMEOUT_SECONDS=60`
  - `OLLAMA_BASE_URL=http://host.docker.internal:11434`
- Lasciata anche configurazione `OpenClaw` pronta ma non attiva:
  - `OPENCLAW_BASE_URL=http://host.docker.internal:18789`
  - `OPENCLAW_CHAT_PATH=/v1/chat/completions`

### Verifiche eseguite
- Dal backend container:
  - `http://host.docker.internal:11434/api/tags` -> `200`
  - `http://host.docker.internal:18789/` -> `200` con UI OpenClaw raggiungibile
- `GET /api/v1/agents/llm/health` -> provider `ollama`, `reachable=true`
- Smoke test reale `generate_mail_recovery_copy(...)` -> OK con risposta generata da `ollama`
- `docker compose up -d backend arq_worker` -> backend/worker riallineati all'ambiente

### Stato attuale parte agenti
- `mail_recovery` e ora in grado di usare davvero un LLM locale in runtime, non solo in teoria.
- Il provider attivo al momento e `ollama`, scelto perche immediatamente utilizzabile senza risolvere auth gateway di `OpenClaw`.
- `OpenClaw` risulta raggiungibile come gateway/UI, ma non e ancora stato autenticato/verificato sul path `POST /v1/chat/completions`.

### Pendente residuo parte agenti
- Se si vuole usare `OpenClaw` come provider attivo, serve configurare anche il token gateway (`OPENCLAW_API_KEY`) e verificare che `chatCompletions` sia realmente abilitato.
- Valutare se esporre il check `llm/health` anche in frontend nella schermata `Agenti`.
- Migliorare il prompt/tono delle email generate da `mail_recovery`: il test reale funziona ma la copy va ancora raffinata per qualita italiana/business.

## Sessione 2026-04-04 — Quality gate sulle bozze LLM di Mail Recovery

### Obiettivo eseguito
- Evitare che `mail_recovery` usi copy LLM scadente solo perche il provider risponde tecnicamente.

### Interventi eseguiti
- Rafforzato il prompt in `backend/ai_agents/llm.py` con:
  - vincoli editoriali piu stretti
  - istruzioni specifiche per `missing_collaborator_data`
  - istruzioni specifiche per `identity_document_followup`
- Aggiunta normalizzazione minima del testo generato (`subject/body`).
- Aggiunto quality gate applicativo:
  - se la bozza contiene pattern indesiderati o non cita correttamente i campi richiesti, viene scartata
  - in quel caso il sistema ricade sul fallback deterministico gia presente

### Verifiche eseguite
- `python3 -m py_compile backend/ai_agents/llm.py` -> OK
- Smoke test reale con provider `ollama`:
  - richiesta LLM eseguita con successo
  - output valutato non conforme ai controlli minimi
  - fallback automatico attivato correttamente

### Decisione tecnica attuale
- Meglio usare fallback deterministic che una mail LLM mediocre o fuoripista.
- `Ollama` resta attivo e disponibile, ma il layer LLM non viene forzato: passa solo se la qualita minima e accettabile.

### Pendente residuo
- Se si vuole una qualita copy migliore mantenendo local LLM, conviene provare un modello piu forte (`qwen2.5-coder:7b/14b` non e ideale per email; meglio un modello instruction generalista piu adatto alla lingua naturale).
- In alternativa, tenere LLM solo per health/esperimenti e lasciare `mail_recovery` deterministic fino alla validazione di un modello migliore.

## Sessione 2026-04-04 — Cleanup UX schermata Agenti

### Obiettivo eseguito
- Rendere la schermata `Agenti` piu coerente col backend reale, riducendo errori utente e mostrando lo stato LLM in modo esplicito.

### Interventi eseguiti
- Frontend `AgentsManager` aggiornato:
  - i tipi entita non supportati non vengono piu mostrati nel select corrente dell'agente scelto
  - aggiunto badge/stato LLM nella hero con reachability provider
  - collegato `GET /agents/llm/health` via service layer
  - se `currentUser.id` e disponibile, le azioni agente passano ora `requested_by_user_id` e `reviewed_by_user_id` reali
- Frontend `App.js` aggiornato:
  - dopo login viene chiamato `/auth/me`
  - `currentUser` include cosi anche `id`, non solo `username/full_name/role`
- Frontend deployato con nuovo bundle:
  - `main.14b4a1ae.js`

### Verifiche eseguite
- `npm run build` -> OK
- `docker compose up -d --build frontend` -> OK

### Stato attuale parte agenti
- La UI non dovrebbe piu proporre all'utente combinazioni invalide come `mail_recovery + globale`.
- Lo stato provider LLM e visibile direttamente nella schermata `Agenti`.
- L'audit frontend/backend puo ora usare `user_id` reale dopo nuovo login, grazie al refresh di sessione via `/auth/me`.

## Sessione 2026-04-04 — Fix modifica collaboratore: agenzia e scadenza documento

### Obiettivo eseguito
- Correggere il flusso di modifica collaboratore quando viene allegato un nuovo documento e quando si marca il collaboratore come agenzia.

### Interventi eseguiti
- Frontend `CollaboratorForm` aggiornato:
  - eliminato l'ultimo accesso non sicuro a `partita_iva.trim()` nel controllo `is_agency`
  - il check usa ora normalizzazione sicura anche con valori `undefined/null`
- Frontend `CollaboratorManager` aggiornato:
  - il form in edit ora riceve tutti i campi profilo/social/documentali, non solo un sottoinsieme
  - il payload di `documento_identita_scadenza` viene inviato in formato ISO coerente `YYYY-MM-DDT00:00:00Z`
- Frontend ridistribuito con nuovo bundle:
  - `main.110b6d4c.js`

### Verifiche eseguite
- `npm run build` -> OK
- `docker compose up -d --build frontend` -> OK

### Stato attuale
- In modifica collaboratore il toggle `Agenzia` non dovrebbe piu saltare o rompersi per campi opzionali mancanti.
- La scadenza del documento dovrebbe persistere correttamente anche quando si carica un nuovo file nello stesso salvataggio.

### Pendente residuo
- Se l'utente segnala ancora mancata persistenza su record specifici, verificare direttamente il payload `PUT /api/v1/collaborators/{id}` e l'eventuale `POST /upload-documento` di quel collaboratore nei log runtime.

### Root cause identificata dopo verifica runtime
- Il backend riceveva e salvava correttamente `documento_identita_scadenza`, ma il form frontend si resettava durante i rerender.
- Causa specifica: `CollaboratorForm` passava a `useForm(...)` un nuovo oggetto `initialValues` ad ogni render; quando l'utente allegava un file (`setDocumentoIdentitaFile`) il rerender rimontava i valori iniziali e perdeva le modifiche non ancora salvate (`is_agency`, `partita_iva`, data scadenza appena cambiata).
- Correzione finale applicata:
  - memoizzazione di `initialFormValues` con `useMemo`
  - deploy frontend con bundle `main.67c9eab1.js`

## Sessione 2026-04-04 — Workflow automatico Data Quality su collaboratori

### Obiettivo eseguito
- Spostare `data_quality` da agente solo manuale a workflow automatico orientato all'operatore:
  - controllo automatico quando un collaboratore viene creato/aggiornato
  - apertura pratica interna
  - decisione operatore
  - bozza/invio email
  - follow-up dopo 7 giorni senza risposta

### Interventi backend
- Aggiunto service condiviso [`agent_workflows.py`](/DATA/progetti/pythonpro/backend/agent_workflows.py):
  - `run_agent_workflow(...)` per esecuzioni agente riusabili
  - `sync_collaborator_data_quality(...)` per trigger automatico su collaboratore
  - `apply_workflow_action(...)` per azioni operatore (`approve`, `wait`, `close`, `remind`)
  - `promote_due_followups(...)` per promuovere a `followup_due` le pratiche inviate da oltre 7 giorni
  - creazione/aggiornamento bozza comunicazione collegata al suggerimento
  - invio email SMTP se configurato (`ENABLE_EMAIL=true` + credenziali SMTP)
- Router agenti aggiornato [`routers/agents.py`](/DATA/progetti/pythonpro/backend/routers/agents.py):
  - `POST /api/v1/agents/run` usa ora il service condiviso
  - nuovo endpoint `POST /api/v1/agents/suggestions/{id}/workflow`
  - letture `suggestions` e `communications` applicano housekeeping follow-up
- Router collaboratori aggiornato [`routers/collaborators.py`](/DATA/progetti/pythonpro/backend/routers/collaborators.py):
  - trigger automatico `data_quality` su create
  - trigger automatico `data_quality` su update
  - trigger automatico anche su upload documento e curriculum

### Interventi frontend
- Service agenti aggiornato [`apiService.js`](/DATA/progetti/pythonpro/frontend/src/services/apiService.js):
  - aggiunta `workflowAgentSuggestion(...)`
- UI agenti aggiornata [`AgentsManager.js`](/DATA/progetti/pythonpro/frontend/src/components/AgentsManager.js):
  - nuova sezione `Inbox operatore`
  - visualizzazione pratiche automatiche `data_quality` sui collaboratori
  - azioni operatore: `Invia richiesta`, `Metti in attesa`, `Invia sollecito`, `Chiudi`
  - mantenuti anche run/suggerimenti/bozze manuali per debug e controllo

### Stati workflow introdotti
- Suggerimenti:
  - `pending` = pratica nuova da valutare
  - `waiting` = l'operatore decide di attendere
  - `approved` = richiesta approvata ma non inviata (es. email non configurata)
  - `sent` = comunicazione inviata
  - `followup_due` = da sollecitare dopo 7 giorni
  - `completed` = pratica chiusa/risolta
- Comunicazioni:
  - `draft`, `approved`, `waiting`, `sent`, `followup_due`, `completed`

### Verifiche eseguite
- `python3 -m py_compile` sui file backend toccati -> OK
- `npm run build` frontend -> OK
- `docker compose up -d --build backend frontend` -> OK
- verifica DB:
  - nuovo `agent_run` automatico `data_quality` su collaboratore
  - nuovo `agent_suggestion` automatico su collaboratore ID 18
  - bozza comunicazione generabile/associabile al suggerimento

### Stato attuale
- Il controllo qualità collaboratore non dipende più solo dal click su `Esegui agente`.
- La schermata `Agenti` funge ora da inbox operativa per l'operatore.
- Il reminder a 7 giorni è gestito automaticamente quando la inbox/letture agenti vengono interrogate.

### Pendente residuo
- Se vuoi vera automazione anche senza accesso UI, il passo successivo è schedulare `promote_due_followups(...)` in ARQ worker/cron invece di eseguirlo sulle letture API.
- WhatsApp non è ancora integrato: il canale attuale è email/draft email.
- Da collegare eventualmente una card sintetica anche in dashboard o collaboratori per far vedere subito le pratiche aperte senza entrare in `Agenti`.

## Sessione 2026-04-04 — Chiusura step successivi workflow agenti

### Step 1 completato — Visibilità pratiche in Dashboard e Collaboratori
- `Dashboard` aggiornato:
  - carica anche `agent_suggestions` e `agent_communications`
  - mostra le pratiche automatiche `data_quality` dentro il centro alert/compliance
  - KPI e task operatore/admin includono ora il numero di pratiche agenti aperte
- `CollaboratorsTable` aggiornato:
  - carica la coda agenti sui collaboratori
  - mostra badge `task agente` o `sollecito agente` direttamente su card/tabella

### Step 2 completato — Scheduler vero per follow-up 7 giorni
- `arq_worker.py` aggiornato:
  - aggiunta funzione `promote_agent_followups`
  - aggiunto cron ARQ `cron(promote_agent_followups, minute={5,35})`
- Verifica runtime:
  - log worker conferma bootstrap: `process_entity_change_event, send_outbound_webhook, promote_agent_followups, cron:promote_agent_followups`

### Step 3 completato — Canale WhatsApp come draft operatore
- `agent_workflows.py` esteso per supportare piu draft sulla stessa pratica:
  - `email`
  - `whatsapp`
- La pratica operatore puo ora avere canali multipli.
- `AgentsManager` aggiornato:
  - inbox operatore mostra email e WhatsApp separatamente
  - azioni disponibili per canale:
    - `Invia email`
    - `Prepara WhatsApp`
    - `Sollecito email`
    - `Sollecito WhatsApp`
- Implementazione attuale:
  - email: invio reale via SMTP se configurato
  - WhatsApp: draft operativo e stato workflow pronti, ma invio provider non ancora collegato

### Verifiche eseguite
- `python3 -m py_compile` backend -> OK
- `npm run build` frontend -> OK
- `docker compose up -d --build backend frontend arq_worker` -> OK
- verifica DB:
  - draft email creato per suggerimento collaboratore ID 18
  - draft email + whatsapp creati per suggerimento collaboratore con telefono valorizzato (es. suggestion ID 5)

### Stato finale attuale
- Workflow automatico `data_quality` collaboratori attivo
- Inbox operatore attiva
- Follow-up schedulato su worker ARQ
- Supporto multi-canale email/WhatsApp a livello di pratica/draft attivo

### Pendente residuo reale
- Collegare provider esterno WhatsApp per invio reale automatico
- Se desiderato, portare le stesse pratiche anche in una sezione dashboard dedicata o dentro il dettaglio collaboratore con azioni inline piu ricche

## Sessione 2026-04-04 — Workflow documentale collaboratori

### Backend completato
- Aggiunti i modelli ORM:
  - `DocumentoRichiesto` con migration dedicata applicata e tabella verificata
  - `Notifica` con indici su destinatario/letta
- Esteso `crud.py` con CRUD piani/voci piano e CRUD `DocumentoRichiesto`, inclusi:
  - documenti mancanti
  - documenti in scadenza
  - validazione/rifiuto
  - marcatura automatica scaduti
- Creato router [`backend/routers/documenti_richiesti.py`](/DATA/progetti/pythonpro/backend/routers/documenti_richiesti.py) e registrato in [`backend/main.py`](/DATA/progetti/pythonpro/backend/main.py)
- Creato servizio SMTP [`backend/services/email_sender.py`](/DATA/progetti/pythonpro/backend/services/email_sender.py):
  - supporto env `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`
  - `send_email(...)`
  - `send_template_email(...)`
  - test mode e rendering template Jinja2
- Aggiornato [`backend/app/core/settings.py`](/DATA/progetti/pythonpro/backend/app/core/settings.py) con configurazione SMTP esplicita
- Creati template email:
  - [`backend/templates/email/default.html`](/DATA/progetti/pythonpro/backend/templates/email/default.html)
  - [`backend/templates/email/default.txt`](/DATA/progetti/pythonpro/backend/templates/email/default.txt)
  - [`backend/templates/email/sollecito_documento.html`](/DATA/progetti/pythonpro/backend/templates/email/sollecito_documento.html)
  - [`backend/templates/email/sollecito_documento.txt`](/DATA/progetti/pythonpro/backend/templates/email/sollecito_documento.txt)
- Creato job standalone/schedulabile [`backend/jobs/check_scadenze.py`](/DATA/progetti/pythonpro/backend/jobs/check_scadenze.py):
  - esecuzione singola `python jobs/check_scadenze.py run`
  - scheduler giornaliero `python jobs/check_scadenze.py schedule`
  - marca scaduti, crea notifiche per documenti in scadenza, invio email opzionale
  - bootstrap difensivo tabella `notifiche`
- Aggiornato [`docker-compose.yml`](/DATA/progetti/pythonpro/docker-compose.yml) con servizio `check_scadenze_scheduler`

### Frontend completato
- Creato manager documentale collaboratore [`frontend/src/components/DocumentiCollaboratore.js`](/DATA/progetti/pythonpro/frontend/src/components/DocumentiCollaboratore.js):
  - tabella documenti
  - badge stato
  - upload file
  - warning scadenze
  - valida/rifiuta per operatore
  - filtro per stato
- Integrato in [`frontend/src/components/CollaboratorManager.js`](/DATA/progetti/pythonpro/frontend/src/components/CollaboratorManager.js) come sezione espandibile richiamata dalla tabella collaboratori
- Estesa [`frontend/src/components/collaborators/CollaboratorsTable.js`](/DATA/progetti/pythonpro/frontend/src/components/collaborators/CollaboratorsTable.js) con azione `📄` per aprire i documenti del collaboratore
- Creato dashboard globale [`frontend/src/components/DocumentiMancanti.js`](/DATA/progetti/pythonpro/frontend/src/components/DocumentiMancanti.js):
  - conteggio totale documenti mancanti/scaduti
  - lista collaboratori ordinata per urgenza
  - filtri per tipo documento e scadenza
  - sollecito singolo e bulk via `mailto:`
  - export CSV
- Aggiornato [`frontend/src/App.js`](/DATA/progetti/pythonpro/frontend/src/App.js):
  - nuova voce menu `Documenti` sotto gruppo `Reportistica`
  - nuova sezione `documenti-mancanti`
- Esteso [`frontend/src/services/apiService.js`](/DATA/progetti/pythonpro/frontend/src/services/apiService.js) con endpoint frontend per:
  - documenti richiesti
  - documenti collaboratore
  - documenti mancanti
  - upload/valida/rifiuta documento richiesto

### Verifiche eseguite
- `python3 -m py_compile backend/models.py` -> OK
- `python3 -m py_compile backend/crud.py backend/routers/documenti_richiesti.py backend/main.py` -> OK
- `python3 -m py_compile backend/services/email_sender.py backend/jobs/check_scadenze.py` -> OK
- `docker compose exec backend alembic upgrade head` -> OK per `documenti_richiesti`
- verifica DB nel container backend:
  - `documenti_richiesti` presente
  - `notifiche` bootstrap/creazione riuscita
- `docker compose exec backend python jobs/check_scadenze.py --help` -> OK
- `docker compose exec backend python jobs/check_scadenze.py run` -> OK
- `npm run build` frontend -> OK

### Stato attuale
- Il gestionale ha ora un primo workflow documentale end-to-end su collaboratori:
  - richieste documenti
  - upload/validazione/rifiuto
  - dashboard documenti mancanti
  - template email sollecito
  - job schedulabile per scadenze/notifiche

### Pendente residuo reale
- Aggiungere migration Alembic esplicita per `Notifica` invece del bootstrap runtime nel job
- Esporre endpoint backend dedicato per `invia sollecito` reale, evitando il fallback frontend via `mailto:`
- Collegare la dashboard `Documenti Mancanti` anche a una card sintetica in `Dashboard`

## Sessione 2026-04-05 — Sistema Agenti AI

### Backend completato
- Riallineati i modelli ORM agentici in [`backend/models.py`](/DATA/progetti/pythonpro/backend/models.py):
  - `AgentRun`
  - `AgentSuggestion`
  - `AgentReviewAction`
- Creata e applicata migration Alembic dedicata [`backend/alembic/versions/a10d08b5e238_add_agent_tables.py`](/DATA/progetti/pythonpro/backend/alembic/versions/a10d08b5e238_add_agent_tables.py) per riallineare le tre tabelle agenti legacy al nuovo schema richiesto.
- Aggiunti gli schema Pydantic agentici in fondo a [`backend/schemas.py`](/DATA/progetti/pythonpro/backend/schemas.py).
- Esteso [`backend/crud.py`](/DATA/progetti/pythonpro/backend/crud.py) con CRUD completo per:
  - `AgentRun`
  - `AgentSuggestion`
  - `AgentReviewAction`
- Ricostruita la struttura `backend/ai_agents/`:
  - [`backend/ai_agents/__init__.py`](/DATA/progetti/pythonpro/backend/ai_agents/__init__.py) vuoto
  - [`backend/ai_agents/registry.py`](/DATA/progetti/pythonpro/backend/ai_agents/registry.py) con `BaseAgent`, `AgentRunResult`, `AgentRegistry`, singleton `agent_registry`
  - [`backend/ai_agents/data_quality.py`](/DATA/progetti/pythonpro/backend/ai_agents/data_quality.py) con primo agente concreto `DataQualityAgent`
- Sostituito [`backend/routers/agents.py`](/DATA/progetti/pythonpro/backend/routers/agents.py) con endpoint coerenti al nuovo registry:
  - lista agenti registrati
  - info agente
  - run manuale
  - lista/dettaglio run
  - lista/dettaglio suggerimenti
  - pending
  - review singola
  - apply fix
  - bulk review
- Aggiornato [`backend/main.py`](/DATA/progetti/pythonpro/backend/main.py) per importare `ai_agents.data_quality` al bootstrap e registrare il router agenti.
- Creato script schedulabile [`backend/jobs/run_agents.py`](/DATA/progetti/pythonpro/backend/jobs/run_agents.py):
  - `--all`
  - `--agent <type>`
  - `--show-schedule`
  - esecuzione robusta con logging e isolamento errori tra agenti
- Aggiunto file operativo [`docs/CRONTAB_EXAMPLE.md`](/DATA/progetti/pythonpro/docs/CRONTAB_EXAMPLE.md) con esempi crontab per:
  - `data_quality`
  - `document_reminder`
  - `budget_alert`

### Frontend completato
- Creato [`frontend/src/components/AgentSuggestionsReview.js`](/DATA/progetti/pythonpro/frontend/src/components/AgentSuggestionsReview.js):
  - contatori pending per priority
  - filtri status/priority/entity/agent
  - bulk review
  - dettaglio suggerimento con review log
  - fix automatico
- Esteso [`frontend/src/services/apiService.js`](/DATA/progetti/pythonpro/frontend/src/services/apiService.js) per i nuovi endpoint agenti (`info`, `run by type`, dettaglio run, pending, detail suggestion, review, apply fix, bulk review).
- Avviato routing frontend agenti in [`frontend/src/App.js`](/DATA/progetti/pythonpro/frontend/src/App.js):
  - route `agents-dashboard`
  - route `agents-review`
- Installata dipendenza frontend `recharts` per il dashboard panoramico agenti richiesto nella sessione corrente.

### Verifiche eseguite
- `python3 -m py_compile backend/models.py` -> OK
- `python3 -m py_compile backend/schemas.py` -> OK
- `python3 -m py_compile backend/crud.py` -> OK
- `python3 -m py_compile backend/ai_agents/registry.py backend/ai_agents/data_quality.py` -> OK
- `python3 -m py_compile backend/routers/agents.py backend/main.py` -> OK
- `python3 -m py_compile backend/alembic/versions/a10d08b5e238_add_agent_tables.py` -> OK
- `docker compose exec backend alembic upgrade head` -> OK
- `docker compose exec backend python -c "from models import AgentRun, AgentSuggestion, AgentReviewAction; print('OK')"` -> OK
- `npm install recharts` -> OK
- `npm run build` frontend -> OK dopo introduzione review suggerimenti agenti

### Stato attuale
- Il backend dispone ora di un primo framework agentico persistente con:
  - registry singleton
  - tracking run
  - suggerimenti persistiti
  - review actions
  - primo agente `data_quality`
  - esecuzione manuale via API
  - esecuzione schedulabile da CLI/cron
- Il frontend dispone di una prima UI operativa per review suggerimenti agentici.

### Pendente residuo reale
- Chiudere [`frontend/src/components/AgentsDashboard.js`](/DATA/progetti/pythonpro/frontend/src/components/AgentsDashboard.js) con grafico Recharts, quick actions e route `/agents/dashboard`
- Riallineare o rimuovere il vecchio [`frontend/src/components/AgentsManager.js`](/DATA/progetti/pythonpro/frontend/src/components/AgentsManager.js), oggi ancora parzialmente basato sul vecchio contratto agenti
- Creare gli agenti successivi:
  - `document_reminder`
  - `budget_alert`
- Aggiungere apply-fix reale lato backend per suggerimenti che supportano correzione automatica, oggi ancora simulato
