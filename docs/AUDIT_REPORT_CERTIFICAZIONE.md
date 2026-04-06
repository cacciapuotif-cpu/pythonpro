# Audit Report Certificazione
Data audit: 2026-04-05
Repository: `/DATA/progetti/pythonpro`
Perimetro: backend FastAPI/SQLAlchemy/Alembic, frontend React, runtime Docker, piani finanziari

## 1. Riepilogo Esecutivo
- Stato generale: `CRITICAL`
- Problemi critici rilevati: `7`
- Warning rilevati: `10`
- Suggerimenti principali: `8`
- Esito sintetico:
  - il backend non e' raggiungibile su `localhost:8000`
  - il frontend non compila
  - il database e' accessibile ma almeno un modello (`AgentReviewAction`) non e' allineato allo schema reale
  - il dominio piani finanziari nuovo e' presente nel DB ma non e' ancora operativo end-to-end sui dati esistenti

## 2. Inventario Completo
### 2.1 Modelli SQLAlchemy
| Modello | Stato | Note |
|---|---|---|
| `Collaborator` | OK | usato in router, crud, frontend |
| `DocumentoRichiesto` | WARNING | router dedicato senza `prefix`, payload custom |
| `Notifica` | WARNING | usata in job, non esposta via API dedicata |
| `Project` | WARNING | ancora accoppiato a template/avvisi legacy |
| `Avviso` | WARNING | dominio legacy convivente col nuovo dominio `AvvisoPianoFinanziario` |
| `TemplatePianoFinanziario` | OK | presente e popolato con 3 record |
| `AvvisoPianoFinanziario` | WARNING | tabella presente ma 0 record |
| `Attendance` | OK | usata e validata |
| `Assignment` | WARNING | logica auto-link presente ma dati esistenti non riallineati |
| `ImplementingEntity` | OK | router e CRUD presenti |
| `ProgettoMansioneEnte` | OK | router e CRUD presenti |
| `PianoFinanziario` | WARNING | forte stratificazione legacy + nuovo dominio |
| `VocePianoFinanziario` | WARNING | struttura nuova presente ma nessuna voce con `assignment_id` |
| `PianoFinanziarioFondimpresa` | OK | router dedicato presente |
| `VoceFondimpresa` | OK | usata dal router fondimpresa |
| `RigaNominativoFondimpresa` | OK | usata dal dominio fondimpresa |
| `DocumentoFondimpresa` | OK | usata dal dominio fondimpresa |
| `DettaglioBudgetFondimpresa` | OK | usata dal dominio fondimpresa |
| `BudgetConsulenteFondimpresa` | OK | usata dal dominio fondimpresa |
| `BudgetCostoFissoFondimpresa` | OK | usata dal dominio fondimpresa |
| `BudgetMargineFondimpresa` | OK | usata dal dominio fondimpresa |
| `Prodotto` | OK | modulo catalogo presente |
| `Listino` | OK | modulo listini presente |
| `ListinoVoce` | OK | modulo listini presente |
| `Agenzia` | OK | modulo presente |
| `Consulente` | OK | modulo presente |
| `AziendaCliente` | OK | modulo presente |
| `Preventivo` | OK | modulo presente |
| `PreventivoRiga` | OK | modulo presente |
| `Ordine` | OK | modulo presente |
| `ContractTemplate` | WARNING | nome router `/api/v1/contracts`, naming non allineato al file |
| `AuditLog` | WARNING | usato poco rispetto alla superficie del sistema |
| `AgentRun` | WARNING | dominio agenti presente ma app non boota |
| `AgentSuggestion` | WARNING | dominio agenti presente ma app non boota |
| `AgentReviewAction` | CRITICAL | modello non allineato al DB |
| `AgentCommunicationDraft` | WARNING | dominio presente ma runtime bloccato |

### 2.2 Schemas Pydantic
- Totale classi in `backend/schemas.py`: molto elevato e multi-dominio.
- Problema strutturale:
  - duplicati reali con shadowing: `AgentRunBase`, `AgentSuggestionBase`, `AgentReviewActionBase`, `AgentReviewActionCreate`, `AgentReviewAction`, `AgentSuggestion`, `AgentRun`, `PianoFinanziarioBase`, `PianoFinanziarioCreate`, `PianoFinanziario`, `VocePianoFinanziarioBase`, `VocePianoFinanziarioCreate`, `VocePianoFinanziario`.
- Evidenza:
  - primo blocco piani finanziari legacy in [schemas.py](/DATA/progetti/pythonpro/backend/schemas.py#L669)
  - secondo blocco piani finanziari attuale in [schemas.py](/DATA/progetti/pythonpro/backend/schemas.py#L1801)
- Effetto:
  - le definizioni finali sovrascrivono le precedenti
  - documentazione e manutenzione diventano ambigue

### 2.3 CRUD
- `backend/crud.py` contiene oltre 150 funzioni.
- Copertura CRUD base buona per collaboratori, progetti, presenze, assegnazioni, enti, contratti, listini, preventivi, ordini, piani, agenti.
- Gap e warning:
  - molte funzioni helper non sono chiamate dai router direttamente; alcune sono helper interni leciti, altre sembrano residue
  - esempi di funzioni senza uso diretto dai router: `get_collaborator_cached`, `get_documenti_in_scadenza`, `marca_scaduti`, `get_template_by_tipo_fondo`, `get_avvisi_by_template`, `get_piani_finanziari_count`

### 2.4 Router
- Router trovati e registrati in `main.py`: `auth`, `system`, `collaborators`, `projects`, `attendances`, `assignments`, `implementing_entities`, `progetto_mansione_ente`, `contract_templates`, `reporting`, `admin`, `agenzie`, `consulenti`, `aziende_clienti`, `catalogo`, `listini`, `preventivi`, `ordini`, `piani_finanziari`, `piani_fondimpresa`, `documenti_richiesti`, `avvisi`, `agents`.
- Problemi:
  - `documenti_richiesti.py` non usa `prefix=` e hardcoda i path completi sugli endpoint, vedi [documenti_richiesti.py](/DATA/progetti/pythonpro/backend/routers/documenti_richiesti.py#L14) e [documenti_richiesti.py](/DATA/progetti/pythonpro/backend/routers/documenti_richiesti.py#L51)
  - molti endpoint del router documenti non definiscono `response_model`
  - naming API incoerente: file `contract_templates.py` espone `/api/v1/contracts`, file `implementing_entities.py` espone `/api/v1/entities`

### 2.5 Validators
- Classi trovate in `backend/validators.py`:
  - `InputSanitizer`
  - `BusinessValidator`
  - `EnhancedCollaboratorCreate`
  - `EnhancedProjectCreate`
  - `EnhancedAttendanceCreate`
  - `EnhancedAssignmentCreate`
  - `BatchOperationValidator`
- Uso effettivo nei router:
  - `EnhancedCollaboratorCreate` usato
  - `EnhancedAttendanceCreate` usato
  - `EnhancedAssignmentCreate` usato
- Non usati nei router:
  - `EnhancedProjectCreate`
  - `InputSanitizer`
  - `BusinessValidator`
  - `BatchOperationValidator`

## 3. Verifica Database
### 3.1 Connessione e tabelle
- `SELECT 1`: `(1,)`
- Tabelle rilevate: `users`, `login_attempts`, `collaborator_project`, `alembic_version`, `assignments`, `attendances`, `contract_templates`, `documenti_richiesti`, `aziende_clienti`, `agent_review_actions`, `agent_communication_drafts`, `progetto_mansione_ente`, `projects`, `collaborators`, `listini`, `implementing_entities`, `audit_logs`, `listino_voci`, `prodotti`, `consulenti`, `agenzie`, `preventivi`, `preventivo_righe`, `ordini`, `righe_nominativo_fondimpresa`, `budget_consulenti_fondimpresa`, `voci_fondimpresa`, `dettaglio_budget_fondimpresa`, `documenti_fondimpresa`, `avvisi`, `piani_finanziari_fondimpresa`, `budget_costi_fissi_fondimpresa`, `budget_margine_fondimpresa`, `notifiche`, `agent_runs`, `piani_finanziari`, `agent_suggestions`, `template_piani_finanziari`, `avvisi_piani_finanziari`, `voci_piano_finanziario`

### 3.2 Conteggi principali
- `collaborators`: 21
- `projects`: 2
- `assignments`: 4
- `attendances`: 7
- `implementing_entities`: 2
- `progetto_mansione_ente`: 1
- `contract_templates`: 9
- `piani_finanziari`: 2
- `voci_piano_finanziario`: 54
- `documenti_richiesti`: 0
- `notifiche`: 0
- `agent_runs`: 11
- `agent_suggestions`: 12
- `agent_review_actions`: errore query per colonna mancante `reviewed_by`

### 3.3 Integrita' relazioni
- Presenze orfane senza collaboratore: `0`
- Presenze orfane senza progetto: `0`
- Assegnazioni orfane: `0`
- Progetti con ente invalido: `0`

## 4. Verifica Migrazioni Alembic
- Catena revisioni legacy lineare da `001` a `028`.
- Seconda catena presente:
  - `528d59380940` -> `d3de21183882` -> `a10d08b5e238` -> `029_piani_fin_complete`
- Stato:
  - la catena e' valida ma non semplice; richiede disciplina per evitare fork/confusione
  - non e' stata verificata la reversibilita' di ogni migration con `downgrade`
- Problema concreto:
  - il modello `AgentReviewAction` non coincide con il DB reale, quindi le migration non coprono lo stato corrente del modello

## 5. Verifica API
- Tutti i `curl` verso `http://localhost:8000/...` falliscono con `curl: (7) Failed to connect`
- Causa root:
  - il backend non completa il boot per `ImportError: cannot import name 'get_agent_definition' from 'ai_agents'`
- Evidenza:
  - import fallisce in [agent_workflows.py](/DATA/progetti/pythonpro/backend/agent_workflows.py#L14)
  - [ai_agents/__init__.py](/DATA/progetti/pythonpro/backend/ai_agents/__init__.py) e' vuoto

## 6. Verifica Test
- Test presenti:
  - [test_api_in_memory.py](/DATA/progetti/pythonpro/backend/tests/test_api_in_memory.py)
  - [test_assignment_overlap.py](/DATA/progetti/pythonpro/backend/tests/test_assignment_overlap.py)
  - [test_routers_api_v1.py](/DATA/progetti/pythonpro/backend/tests/test_routers_api_v1.py)
- Esito esecuzione:
  - `pytest` non parte correttamente perche' `pytest.ini` richiede `--cov` ma il plugin coverage non e' disponibile
  - evidenza in [pytest.ini](/DATA/progetti/pythonpro/backend/pytest.ini)
- Copertura funzionale osservata:
  - overlap assegnazioni: presente
  - validazione date assegnazione/presenza: presente
  - validazione fiscal code: presente in `test_improvements.py`, fuori dalla suite `tests/`
  - CRUD piani finanziari: assente
  - CRUD documenti richiesti: assente
  - sistema agenti: assente
- Warning forte:
  - [test_api_in_memory.py](/DATA/progetti/pythonpro/backend/tests/test_api_in_memory.py#L1) testa `app.main` in-memory, non l'app reale `backend/main.py`
  - [test_routers_api_v1.py](/DATA/progetti/pythonpro/backend/tests/test_routers_api_v1.py#L1) usa path e aspettative obsolete (`/api/v1/entities`, `/api/v1/contracts`, status code spesso 200 invece di 201/204)

## 7. Stato Piani Finanziari
- [x] Template Formazienda presente e configurato
- [x] Template FAPI presente e configurato
- [x] Template Fondimpresa presente e configurato
- [ ] Avvisi associati a ogni template
- [ ] Mansioni -> Voci piano: collegamento funzionante sui dati correnti
- [ ] Calcolo automatico importi da presenze verificato sui dati correnti

### Evidenze
- Template trovati: `3`
- Tipi presenti: `formazienda`, `fapi`, `fondimpresa`
- Avvisi associati: `0`
- Progetti con piano: `2`
- Progetto `Progetto Test`: `4` assegnazioni attive, ma nessuna ha trovato una voce piano corrispondente
- Voci con `assignment_id` valorizzato: `0`

### Diagnosi
- la nuova logica `collega_assegnazione_a_piano` e' presente in `crud.create_assignment`
- i dati gia' esistenti non sono stati backfillati
- il requisito "mansione assegnata -> voce piano popolata automaticamente" non e' dimostrato sui record correnti

## 8. Problemi Critici
1. [backend/agent_workflows.py](/DATA/progetti/pythonpro/backend/agent_workflows.py#L14)
   Descrizione: import di `get_agent_definition` e `run_registered_agent` da package `ai_agents`, ma [backend/ai_agents/__init__.py](/DATA/progetti/pythonpro/backend/ai_agents/__init__.py) e' vuoto.
   Impatto: backend non avviabile, API completamente giu'.
   Fix: esportare i simboli richiesti da `ai_agents/__init__.py` oppure importare dal modulo corretto (`ai_agents.registry` o equivalente).
2. [backend/models.py](/DATA/progetti/pythonpro/backend/models.py#L1844)
   Descrizione: `AgentReviewAction` usa campi `reviewed_by`, `reviewed_at`, ma il DB reale non li ha.
   Impatto: query su `agent_review_actions` fallisce.
   Fix: creare/applicare migration coerente o riallineare il modello ai campi reali.
3. [backend/schemas.py](/DATA/progetti/pythonpro/backend/schemas.py#L669) e [backend/schemas.py](/DATA/progetti/pythonpro/backend/schemas.py#L1801)
   Descrizione: definizioni duplicate per schemi piano e agenti.
   Impatto: shadowing silenzioso, manutenzione ad alto rischio.
   Fix: eliminare i duplicati e mantenere una sola definizione canonica per classe.
4. [frontend/src/App.js](/DATA/progetti/pythonpro/frontend/src/App.js#L27)
   Descrizione: import di `./components/AgentsDashboard`, file non presente.
   Impatto: `npm run build` fallisce.
   Fix: creare il componente o rimuovere import e branch `agents-dashboard`.
5. [backend/pytest.ini](/DATA/progetti/pythonpro/backend/pytest.ini)
   Descrizione: `pytest` richiede `--cov`, ma il plugin non e' installato nel container.
   Impatto: la suite test non e' eseguibile.
   Fix: installare `pytest-cov` o rimuovere temporaneamente le opzioni coverage da `addopts`.
6. [backend/routers/documenti_richiesti.py](/DATA/progetti/pythonpro/backend/routers/documenti_richiesti.py#L14)
   Descrizione: router senza `prefix`, path hardcoded e payload locali senza `response_model`.
   Impatto: inconsistenza API e OpenAPI meno affidabile.
   Fix: introdurre `prefix="/api/v1/documenti-richiesti"` e schemi Pydantic condivisi.
7. [backend/crud.py](/DATA/progetti/pythonpro/backend/crud.py#L1596) + dati correnti
   Descrizione: logica auto-link piano presente, ma nessun record esistente e' allineato.
   Impatto: requisito piani finanziari non verificato sui dati reali.
   Fix: script di backfill `Assignment -> VocePianoFinanziario` e ricalcolo consuntivi da `Attendance`.

## 9. Warning
- [backend/models.py](/DATA/progetti/pythonpro/backend/models.py#L235) relazione legacy `Avviso.piani_finanziari` resa `viewonly`, sintomo di dominio legacy/non-legacy sovrapposto.
- [backend/tests/test_api_in_memory.py](/DATA/progetti/pythonpro/backend/tests/test_api_in_memory.py#L1) punta a una app secondaria e non rappresenta il backend reale.
- [backend/tests/test_routers_api_v1.py](/DATA/progetti/pythonpro/backend/tests/test_routers_api_v1.py#L1) usa path/expectation obsolete.
- [frontend/src/components/PianiFinanziariHub.js](/DATA/progetti/pythonpro/frontend/src/components/PianiFinanziariHub.js) risulta non referenziato.
- [frontend/src/components/ContractTemplateModal.js](/DATA/progetti/pythonpro/frontend/src/components/ContractTemplateModal.js) usa `fetch` diretto e path legacy, riducendo coerenza col layer `apiService`.
- naming API non uniforme: `entities`, `contracts`, `project-assignments`, `piani-finanziari`.
- vari `TODO` operativi in `backend/app/main.py` indicano perimetro app alternativo incompleto.
- nel DB i template piano sono presenti ma non esistono avvisi associati.
- `documenti_richiesti` e `notifiche` hanno record `0`; il flusso documentale non e' dimostrato in ambiente.
- i report da shell su funzioni "inutilizzate" includono helper interni, ma confermano superficie di codice molto ampia e poco governata.

## 10. Codice Morto o Ridondante
- Duplicati/ridondanze reali:
  - schemi duplicati in `schemas.py`
  - test che puntano a una app parallela (`backend/app/`)
- File/componenti sospetti:
  - `frontend/src/components/PianiFinanziariHub.js` non risulta importato
  - `backend/app/` sembra essere un secondo perimetro applicativo non allineato al backend reale
- Ricerca backup:
  - nessun `.bak` applicativo significativo nel backend
  - presenza legittima di `backup_manager.py`, `run_backup.py`, cartella `backups/`

## 11. Incoerenze Da Allineare
- Modello vs DB:
  - `AgentReviewAction`
- Schemi vs modelli:
  - doppio set di schemi piano/agenti
- Router vs naming:
  - `contract_templates.py` -> `/api/v1/contracts`
  - `implementing_entities.py` -> `/api/v1/entities`
  - `documenti_richiesti.py` senza prefix
- Frontend vs filesystem:
  - import `AgentsDashboard` senza file
- Test vs app reale:
  - suite orientata a perimetri legacy/in-memory

## 12. Test Mancanti
- CRUD completi piani finanziari nuovi (`TemplatePianoFinanziario`, `AvvisoPianoFinanziario`)
- backfill/auto-link `Assignment -> VocePianoFinanziario`
- ricalcolo `Attendance -> importo_rendicontato`
- regressione `AgentReviewAction` dopo migration
- router `documenti_richiesti`
- router `agents`
- build frontend e smoke UI su sezione agenti

## 13. Suggerimenti Miglioramento
- Consolidare il dominio applicativo: una sola app backend, un solo set di schemi.
- Introdurre una migration dedicata di riallineamento per `agent_review_actions`.
- Aggiungere uno script ufficiale di backfill piani finanziari.
- Spostare `documenti_richiesti` su schemi condivisi in `schemas.py`.
- Uniformare i prefix API.
- Aggiungere smoke test runtime post-boot.
- Ripristinare `pytest-cov` nel container backend.
- Aggiungere CI minima per `python -m py_compile`, `pytest`, `npm run build`.

## 14. Checklist Pre-Produzione
- [ ] Tutti i test passano
- [ ] Nessun codice morto rilevante
- [ ] Tutte le migrazioni applicate e allineate ai modelli
- [ ] Validazioni attive e coperte da test
- [ ] API documentata in modo coerente
- [ ] Frontend collegato e compilabile
- [ ] Logging configurato
- [ ] Error handling completo
- [x] 3 Template piani finanziari presenti
- [ ] Avvisi configurati per ogni template
- [ ] Flusso Mansione -> Voce Piano funzionante sui dati reali
