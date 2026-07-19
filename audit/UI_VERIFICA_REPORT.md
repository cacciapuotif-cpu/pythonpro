# Ondata UI — GATE verifica pagine e collegamenti

**Data:** 2026-07-19

**Esito GATE:** **NON SUPERATO**

**Dichiarazione:** **TUTTE LE PAGINE COLLEGATE E FUNZIONANTI: NO**
**Manuale:** non iniziato, come richiesto dal gate.

La UI amministratore e gran parte delle funzioni legacy sono utilizzabili, ma i
due ruoli canonici `operatore` e `consultazione` non possono entrare nel frontend.
Inoltre sono rotti il caricamento dei piani finanziari, alcuni PDF timesheet, le
azioni del Cockpit e il portale allievi senza sessione ERP. Non è quindi corretto
scrivere ora un manuale dichiarando la piattaforma interamente operativa.

## Metodo ed evidenze

- Censimento statico di `frontend/src/App.js`, dei componenti pagina, degli hook e
  di `frontend/src/services/apiService.js`.
- Confronto delle chiamate con OpenAPI runtime (259 operazioni) e con la policy
  RBAC di `backend/auth.py`.
- Browser headless Playwright sulla UI reale: login, click di ogni voce menu,
  raccolta errori console/rete e screenshot. Chromium è stato eseguito con
  `--single-process --no-zygote`, necessari su questo host.
- Smoke API sui tre ruoli canonici. Poiché il frontend blocca `operatore` e
  `consultazione`, il crawl operativo supplementare è stato eseguito anche con
  il ruolo legacy `user`; questa prova **non** sostituisce il test fallito del
  ruolo canonico.
- Flussi con scrittura eseguiti esclusivamente sul clone PostgreSQL
  `gestionale_ui_verifica`, backend `pythonpro_backend_uiverifica` su porta 8003.
  Nessuna scrittura funzionale sul database reale.

Risultati crawl già acquisiti prima della chiusura UI-3:

- Admin: 18/18 sezioni visibili caricate senza errori console/rete.
- `user` legacy: 13/13 sezioni visibili caricate; trovati i 403 UI-05/UI-06.
- `operatore` canonico: login rifiutato dal frontend.
- `consultazione`: nessun profilo di login e nessuna sezione assegnata.

## Modello di navigazione e route

Il progetto non usa React Router: quasi tutte le pagine sono stati interni di
`App.js` e condividono `/`. Solo cinque sezioni hanno un path dedicato. Questo
rende impossibili bookmark e link profondi per la maggior parte delle pagine.

| Route browser | Componente/pagina | Come si raggiunge | Ruoli dichiarati nel frontend |
|---|---|---|---|
| `/` + stato `home` | `HomeCockpit` | menu Home | admin, user, manager |
| `/` + stato `dashboard` | `Dashboard` | menu Dashboard | admin, user, manager |
| `/` + stato `calendar` | `Calendar` | menu Calendario | admin, user, manager |
| `/` + stato `timesheet` | `TimesheetReport` + `TimesheetPDF` | menu Timesheet | admin, user, manager |
| `/documenti-mancanti` | `DocumentiMancanti` | menu Documenti | admin, user, manager |
| `/` + stato `collaborators` | `CollaboratorManager` | menu Collaboratori | admin, user, manager |
| `/` + stato `allievi` | `AllieviManager` | menu Allievi | admin, user, manager |
| `/` + stato `projects` | `ProjectManager` | menu Progetti | admin, user, manager |
| `/` + stato `aziende-clienti` | `AziendeClientiManager` | menu Aziende | admin, user, manager |
| `/` + stato `catalogo` | `CatalogoManager` | menu Catalogo | admin, user, manager |
| `/` + stato `listini` | `ListiniManager` | menu Listini | admin, user, manager |
| `/` + stato `preventivi` | `PreventiviManager` | menu Preventivi | admin, user, manager |
| `/` + stato `ordini` | `OrdiniManager` | menu Ordini | admin, user, manager |
| `/resources` | `ResourceArchive` | menu Archivio Risorse | admin, manager |
| `/` + stato `entities` | `ImplementingEntitiesList` | menu Enti Attuatori | admin |
| `/agents/dashboard` | `AgentsDashboard` | menu Agents Dashboard | admin |
| `/agents` | `AgentsManager` | menu Agenti | admin |
| `/agents/review` | `AgentSuggestionsReview` | link dall'Archivio; voce nascosta | admin, user, manager |
| `/` + stato `templates` | `ContractTemplatesManager` | menu Template | admin |
| `/portale-allievi?token=...` | `PortaleAllievi` | link esterno, nessuna voce menu | previsto pubblico, ma bloccato da UI-16 |

Componenti pagina orfani: `AgenzieManager`, `ConsulentiManager`,
`ProgettoMansioneEnteManager`, `CalendarSimple`. Non sono importati da `App.js` e
nessun menu/link li raggiunge. Non sono stati trattati come sezioni operative.

## Matrice pagina × ruolo × esito

Legenda: `OK` = provata; `BLOCCO UI-01` = backend raggiungibile ma il ruolo non
entra nella UI; `N/V` = non visibile per scelta dichiarata.

| Pagina | Admin | Operatore canonico | Consultazione | Nota runtime/RBAC |
|---|---|---|---|---|
| Home | OK | BLOCCO UI-01 | BLOCCO UI-01 | azioni rotte, UI-15 |
| Dashboard | OK | BLOCCO UI-01 | BLOCCO UI-01 | metriche admin nascoste al legacy user |
| Calendario | OK | BLOCCO UI-01 | BLOCCO UI-01 | CRUD presenze carica |
| Timesheet | OK | BLOCCO UI-01 | BLOCCO UI-01 | legacy user vede Export ma riceve 403; UI-04/UI-05 |
| Documenti | OK | BLOCCO UI-01 | BLOCCO UI-01 | lista, filtri ed export locale OK |
| Collaboratori | OK | BLOCCO UI-01 | BLOCCO UI-01 | download legacy user → 403; UI-06 |
| Allievi | OK | BLOCCO UI-01 | BLOCCO UI-01 | CRUD e stati vuoti OK |
| Progetti | OK | BLOCCO UI-01 | BLOCCO UI-01 | assegnazione corretta da UI-03; piani UI-02 |
| Aziende | OK | BLOCCO UI-01 | BLOCCO UI-01 | CRUD e filtri OK |
| Catalogo | OK | BLOCCO UI-01 | BLOCCO UI-01 | vuoto gestito |
| Listini | OK | BLOCCO UI-01 | BLOCCO UI-01 | lista/voci caricano |
| Preventivi | OK | BLOCCO UI-01 | BLOCCO UI-01 | vuoto gestito |
| Ordini | OK | BLOCCO UI-01 | BLOCCO UI-01 | lista/paginazione caricano |
| Archivio Risorse | OK | BLOCCO UI-01 | BLOCCO UI-01 | solo `manager` legacy è previsto; UI-07 |
| Enti Attuatori | OK | N/V | N/V | admin-only coerente |
| Agents Dashboard | OK | N/V | N/V | admin-only coerente |
| Agenti | OK | N/V | N/V | admin-only coerente |
| Revisione Agenti | OK | BLOCCO UI-01 | BLOCCO UI-01 | nascosta; per `user` legacy è orfana, UI-08 |
| Template | OK | N/V | N/V | admin-only coerente |
| Portale Allievi | ROTTO | ROTTO | ROTTO | senza sessione ERP mostra il login, UI-16 |

## Chiamate API per pagina e coerenza RBAC

La tabella riporta le famiglie effettivamente importate dalla pagina e dai suoi
modali/hook. Tutte le route elencate esistono nel backend; le eccezioni sono di
contratto/runtime, non route inesistenti.

| Pagina | API usate (metodi e path principali) | Esito/RBAC |
|---|---|---|
| Home | `GET /cockpit/decisioni`; URL azione restituiti dal backend | GET OK; azioni aperte col metodo sbagliato, UI-15 |
| Dashboard | `GET /reporting/summary`, `/reporting/timesheet`, `/collaborators/`, `/projects/`, `/assignments/`, `/contracts`, `/agents/suggestions/`, `/agents/communications`; admin anche `/admin/metrics` | letture OK; metriche correttamente nascoste |
| Calendario | CRUD `/attendances`, lettura `/assignments/` | OK per admin e legacy user |
| Timesheet | `GET /reporting/timesheet`, `POST /reporting/timesheet/export`, `GET /reporting/timesheet/export/{id}`, `GET /projects/{id}/timesheets`, `GET /assignments/{id}/timesheet`, `POST .../unlock` | export admin-only ma bottone visibile; alcuni PDF 500 |
| Documenti | `GET /documenti-richiesti/` | OK |
| Collaboratori | CRUD `/collaborators`, bulk import, upload/download documenti, `/collaborators/{id}/documenti*`, CRUD `/assignments`, `GET /piani-finanziari/`, POST/DELETE collaboratore↔progetto | UI-03 corretto; UI-02, UI-06 e UI-09 aperti |
| Allievi | CRUD `/allievi`, bulk import, letture `/aziende-clienti/`, `/projects/` | OK |
| Progetti | CRUD `/projects`, `/entities`, `/collaborators`, `/assignments`, beneficiari/moduli, upload/confirm FAPI/Fondimpresa e piani | catena principale OK; lettura piani rotta UI-02 |
| Aziende | CRUD `/aziende-clienti`, bulk import, letture `/consulenti`, `/agenzie`, `/projects` | OK |
| Catalogo | CRUD `/catalogo` | OK |
| Listini | CRUD `/listini`, CRUD `/listini/{id}/voci`, lettura `/catalogo` | OK |
| Preventivi | CRUD `/preventivi`, azioni stato, conversione ordine, PDF, CRUD righe; letture catalogo/aziende/listini/consulenti | OK sui dati presenti |
| Ordini | GET/PUT/DELETE `/ordini` | OK |
| Archivio | CRUD `/avvisi`, revisioni/ingest, deletion-impact e permanent delete | scrittura manager/admin; hard-delete nascosto correttamente ai non-admin |
| Enti Attuatori | CRUD `/entities` | admin-only coerente |
| Agents Dashboard | catalogo/run `/agents` | admin-only coerente |
| Agenti | health/suggestion/comunicazioni/email inbox e aggiornamento manuale collaboratore | admin-only per pagina; azioni agentiche proposal-only |
| Revisione Agenti | run/suggestion detail, review, bulk-review, apply-fix; letture collaboratori/progetti | backend consente operatore; percorso UI non raggiungibile per ruolo canonico |
| Template | CRUD `/contracts`, lettura/aggancio `/avvisi`, conversione DOCX, letture enti/progetti | admin-only coerente |
| Portale Allievi | `GET /portale-allievi/profilo?token=...` via `fetch` | API prevista, componente non montato senza login ERP |

## UI-3 — flussi trasversali

| # | Flusso | Esito | Evidenza e attrito |
|---:|---|---|---|
| 1 | MD → estrazione → regole | **PARZIALE** | Upload/ingest 201. Il primo run aveva 5/5 gruppi falliti perché il container clone non risolveva `host.docker.internal`. Ripetuto con URL Ollama raggiungibile: run 625 completed, 6 proposte, 1/5 gruppi in timeout; una data `30/09/2026` è stata scartata perché non ISO. Lo stato resta `estratto`: UI-17. |
| 2 | Piano da template → massimali → avviso | **PARZIALE** | B4/template non esiste. Creazione manuale e aggancio all'avviso OK. Su clone: docenza 101 € contro limite 100 € → 422 con messaggio chiaro; 100 € → 201. |
| 3 | Progetto → collaboratori → checklist → approvo | **OK** | Assegnazione 200 dopo UI-03; documento richiesto, upload e validazione operatore 200; `validato_da` obbligatorio e tracciato. |
| 4 | Collaboratore incompleto → agenti → contratto | **PARZIALE** | `fiscal_code` è obbligatorio anche nel caso “incompleto”; data_quality e contract_agent restano proposal-only. Contratto dipende da assignment/documenti completi. |
| 5 | Presenze → timesheet → esito | **PARZIALE** | Guardie periodo progetto/assegnazione rispondono 400 chiaro; PDF sano OK e unlock motivato OK. Assignment 1 resta 500 per float/Decimal, UI-04. |
| 6 | Dashboard agenti → review → approvo → effetto | **OK** | Suggestion strutturata 633 applicata via `POST .../apply-fix` → 200, stato `implemented`; nuovo telefono visibile via `GET /collaborators/13` → 200. Tutto sul clone. |
| 7 | HomeCockpit → pagina filtrata | **ROTTO** | I quattro contatori non hanno handler click. “Gestisci” usa `window.open(API + azione_url)`: una route POST viene aperta come GET. Prova: documento 3 → 405. |
| 8 | Chiedi all'archivio → citazioni → avviso | **NON ESISTE** | Ondata L non eseguita. Il capitolo 9 del manuale non è scrivibile. |

Anche il CRM richiesto dal capitolo 8 del manuale non esiste: Ondata C2 non è
stata eseguita e resta subordinata al prerequisito legale esterno.

## Finding UI

### 🔴 Rotti

- **UI-01 — Ruoli canonici fuori dalla UI.** `ACCESS_PROFILES`,
  `ROLE_EXPERIENCE` e `SECTION_CONFIG` riconoscono solo `admin`, `user`,
  `manager`. `operatore` e `consultazione` non possono entrare né navigare.
- **UI-02 — Contratto piani finanziari non compatibile con i dati reali.**
  `GET /api/v1/piani-finanziari/` restituisce 500: `tipo_fondo` non ammette
  `fapi`/`formazienda` e `budget_rimanente >= 0` non tollera un piano in
  sforamento. Rompe anche `AssignmentModal`.
- **UI-04 — PDF timesheet 500 su dati Decimal.** Assignment 1 fallisce in
  `timesheet_generator.py` (`float / Decimal`); assignment 52 è OK.
- **UI-15 — HomeCockpit non naviga.** Contatori non cliccabili; “Gestisci” apre
  endpoint di mutazione come GET in una nuova scheda (405/401), senza portare
  alla pagina filtrata richiesta.
- **UI-16 — Portale Allievi bloccato dal login ERP.** Il controllo
  `/portale-allievi` avviene dopo `if (!currentUser)`: un allievo con token ma
  senza sessione ERP vede la pagina di login gestionale.

### 🟠 Incoerenti / sicurezza e contratto

- **UI-05 — Export CSV timesheet visibile all'operatore legacy ma admin-only:**
  click → 403 grezzo.
- **UI-06 — Download/anteprima documento e CV visibili all'operatore legacy ma
  endpoint admin-only:** click → 403.
- **UI-09 — Endpoint cross-resource senza RBAC di ruolo.** I path storici e gli
  alias UI-03 dipendono solo da `get_current_user`; anche `consultazione` può
  assegnare/rimuovere via API.
- **UI-17 — Estrazione parziale marcata `estratto`.** Gruppi in timeout e date
  non parsabili vengono conteggiati/scartati, ma il run `completed` porta la
  revisione allo stato ottimistico `estratto` senza avviso operativo sufficiente.

### 🟡 Attriti UX

- **UI-07 — Archivio Risorse visibile a `manager` ma non a `user`**, sebbene il
  backend normalizzi entrambi come operatore.
- **UI-08 — Revisione Agenti nascosta.** Per `user` legacy è raggiungibile solo
  da Archivio, che quel ruolo non vede, oppure digitando l'URL.
- **UI-11 — Link “Documentazione API” hardcoded a `localhost:8001`.** Rotto da
  host client/remoto ed esposto a utenti non tecnici.
- **UI-12 — Errori grezzi.** I 403 mostrano “Request failed with status code
  403” invece di una spiegazione operativa.
- **UI-18 — Quasi tutte le sezioni condividono `/`.** Nessun bookmark/deep-link
  stabile per collaboratori, progetti, timesheet, ecc.

### 🟢 Igiene

- **UI-13 — Componenti orfani:** `AgenzieManager`, `ConsulentiManager`,
  `ProgettoMansioneEnteManager`, `CalendarSimple`.
- **UI-14 — Wrapper API morti**, inclusi `getCollaboratorsWithProjects` e
  `getAssignmentsByCollaborator`, senza consumer attivi.

### Finding chiusi durante l'ondata

- **UI-03 — CORRETTO** con commit `4b226d6`: alias `/api/v1` per
  assegna/rimuovi collaboratore↔progetto e test regressione.
- **UI-10 — NON CONFERMATO:** il comando hard-delete e la chiamata
  `deletion-impact` sono effettivamente renderizzati solo per `admin`; il manager
  vede la disattivazione sicura ma non il percorso definitivo.
- **UI-19 — CORRETTO** con commit `c9b9059`: test frontend riallineati ai moduli,
  mock e profili correnti; nessun comportamento applicativo modificato.

## Fix applicati e fix rinviati

Applicati i soli fix piccoli e certi UI-03 (`4b226d6`) e UI-19 (`c9b9059`).
UI-19 riguarda esclusivamente contratti/mock di test e l'export di una costante
già esistente; non modifica i flussi applicativi.

Da decidere prima del manuale:

1. UI-01: mappa/normalizzazione definitiva dei ruoli canonici.
2. UI-02: contratto di risposta dei piani, inclusa la semantica di sforamento.
3. UI-04: normalizzazione numerica nel generatore timesheet.
4. UI-05/UI-06: RBAC coerente oppure azioni nascoste/disabilitate con messaggio.
5. UI-09: `require_role` sugli endpoint cross-resource.
6. UI-15: destinazioni frontend e filtri del Cockpit.
7. UI-16: montaggio del portale tokenizzato prima del login gestionale.
8. UI-17: stato “parziale/da verificare” e dettaglio errori estrazione.

## Gate tecnici eseguiti

- Backend completo sul codice corrente: **569 passed, 3 skipped, 0 failed** su
  572 test (8m36s). Include il test regressione UI-03.
- Frontend completo: **6 suite passate, 54 test passati, 0 falliti**.
- Build frontend production: completata. Warning residui non bloccanti:
  `CATEGORIA_COLORE` inutilizzata in `HomeCockpit.js` e bundle sopra la soglia
  consigliata.
- `git diff --check`: pulito prima dei commit documentali.
- Teardown completato: rimossi container/volumi anonimi di
  `pythonpro_backend_uiverifica` e database `gestionale_ui_verifica`; backend,
  frontend, worker, PostgreSQL e Redis reali restano healthy, `/health` → 200.

## Verdetto del GATE

**GATE UI: NON SUPERATO.**

**TUTTE LE PAGINE COLLEGATE E FUNZIONANTI: NO.**

**MANUALE VERIFICATO SU PIATTAFORMA REALE: non dichiarabile perché il manuale non
è stato avviato e diverse procedure richieste non esistono o sono rotte.**

L'Ondata M deve restare ferma finché l'utente non decide quali correzioni
bloccanti includere e finché le relative prove runtime non sono verdi.
