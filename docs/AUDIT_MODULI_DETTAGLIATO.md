# AUDIT MODULI DETTAGLIATO — PythonPro ERP Formazione Finanziata

> Generato: 2026-04-06  
> Analisi di: 21 moduli, 25 classi SQLAlchemy, 220 funzioni CRUD, ~130 endpoint REST, 35+ componenti React

---

## STRUTTURA DEL PROGETTO

**Backend**: FastAPI + SQLAlchemy + PostgreSQL
- `models.py`: 1909 righe, 25+ classi ORM
- `crud.py`: 5399 righe, 220 funzioni
- `schemas.py`: 1891 righe, ~60 schemi Pydantic
- `main.py`: 612 righe
- Router: 21 file in `routers/`
- Migrazioni Alembic: 34 file (001–029 + 5 hash-named)

**Frontend**: React
- 35+ componenti JS in `frontend/src/components/`

---

## MAPPA CLASSI SQLALCHEMY

| Classe | Tabella | Scopo |
|---|---|---|
| `Collaborator` | collaborators | Anagrafica docenti/tutor/coordinatori |
| `Project` | projects | Progetti formativi finanziati |
| `Assignment` | assignments | Assegnazione collaboratore → progetto (con contratto) |
| `Attendance` | attendances | Presenze / ore lavorate |
| `ImplementingEntity` | implementing_entities | Enti attuatori (es. piemmei scarl) |
| `ProgettoMansioneEnte` | progetto_mansione_ente | Associazione progetto ↔ ente ↔ mansione |
| `ContractTemplate` | contract_templates | Template HTML contratti PDF |
| `Avviso` | avvisi | Bandi semplificati (codice + ente_erogatore) |
| `TemplatePianoFinanziario` | template_piani_finanziari | Template strutturati per PF |
| `AvvisoPianoFinanziario` | avvisi_piani_finanziari | Bandi completi con budget/date/costi |
| `PianoFinanziario` | piani_finanziari | Piano finanziario Formazienda/FAPI/FSE |
| `VocePianoFinanziario` | voci_piano_finanziario | Singola voce di spesa nel piano |
| `PianoFinanziarioFondimpresa` | piani_finanziari_fondimpresa | Piano Fondimpresa |
| `VoceFondimpresa` | voci_fondimpresa | Voce Fondimpresa |
| `Prodotto` | prodotti | Catalogo prodotti/servizi |
| `Listino` | listini | Listini prezzi per tipo cliente |
| `ListinoVoce` | listino_voci | Voce listino (prodotto → prezzo) |
| `Preventivo` | preventivi | Preventivo commerciale |
| `Ordine` | ordini | Ordine da preventivo accettato |
| `Agenzia` | agenzie | Agenzie commerciali |
| `Consulente` | consulenti | Agenti/consulenti commerciali |
| `AziendaCliente` | aziende_clienti | Clienti |
| `AgentRun` | agent_runs | Esecuzione agente AI |
| `AgentSuggestion` | agent_suggestions | Suggerimento agente |
| `DocumentoRichiesto` | documenti_richiesti | Documenti richiesti a collaboratore |

---

## MODULO 1: COLLABORATORI

**Descrizione**: Gestione dell'anagrafica di tutte le persone che lavorano su progetti formativi (docenti, tutor, coordinatori, esperti).

**Campi principali** (`Collaborator`):
- `nome`, `cognome`, `codice_fiscale` (UNIQUE, con validazione)
- `email`, `telefono`, `data_nascita`, `luogo_nascita`
- `indirizzo`, `citta`, `cap`, `provincia`
- `partita_iva` (opzionale per liberi professionisti)
- `iban`, `bic` (per pagamenti)
- `is_agency` (bool), `is_consultant` (bool) — flag per tipo collaboratore
- `stato` (attivo/inattivo/sospeso)

**Endpoint REST**:
- `GET /api/v1/collaborators/` — lista paginata con filtri
- `POST /api/v1/collaborators/` — crea collaboratore
- `GET /api/v1/collaborators/{id}` — dettaglio
- `PUT /api/v1/collaborators/{id}` — aggiorna
- `DELETE /api/v1/collaborators/{id}` — elimina
- `GET /api/v1/collaborators/{id}/assignments` — assegnazioni del collaboratore
- `GET /api/v1/collaborators/{id}/attendances` — presenze
- `GET /api/v1/collaborators/{id}/documents` — documenti richiesti

**Componenti Frontend**: `CollaboratorManager.js`, `DocumentiCollaboratore.js`

**Relazioni**:
- `Collaborator` ←→ `Project` (many-to-many via tabella `collaborator_project`)
- `Collaborator` → `Assignment` (one-to-many)
- `Collaborator` → `Attendance` (one-to-many)
- `Collaborator` → `DocumentoRichiesto` (one-to-many)

**Problemi identificati**:
- Flag `is_agency`/`is_consultant` senza FK verso `Agenzia`/`Consulente` (solo boolean non collegato)
- Funzione `get_collaborator_cached` usa cache in-process inutile con multi-worker

---

## MODULO 2: PROGETTI

**Descrizione**: Progetti formativi finanziati da fondi interprofessionali (Formazienda, FAPI, Fondimpresa, FSE). È il nodo centrale del sistema attorno cui ruotano presenze, assegnazioni e piani finanziari.

**Campi principali** (`Project`):
- `codice`, `titolo`, `descrizione`
- `data_inizio`, `data_fine`
- `stato` (bozza/attivo/completato/annullato)
- `ore_totali`, `ore_completate`, `progress_percentage`
- `budget_totale`, `budget_utilizzato`, `budget_rimanente`
- **DUPLICAZIONE (vedi AUDIT_COERENZA.md)**:
  - `ente_erogatore` (String legacy)
  - `avviso` (String legacy)
  - `avviso_id` (FK → `avvisi`)
  - `avviso_pf_id` (FK → `avvisi_piani_finanziari`)
  - `ente_attuatore_id` (FK → `implementing_entities`)
  - `template_piano_finanziario_id` (FK errata → `contract_templates` invece di `template_piani_finanziari`)

**Endpoint REST**:
- CRUD standard + `GET /api/v1/projects/{id}/full-context`

**Componenti Frontend**: `ProjectManager.js`

**Relazioni**:
- `Project` ←→ `Collaborator` (many-to-many)
- `Project` → `Assignment` (one-to-many)
- `Project` → `Attendance` (one-to-many)
- `Project` → `PianoFinanziario` (one-to-many)
- `Project` → `ProgettoMansioneEnte` (one-to-many)

---

## MODULO 3: ASSEGNAZIONI

**Descrizione**: Contratto di assegnazione che lega un collaboratore a un progetto per una mansione specifica, definendo ore previste e compenso.

**Campi principali** (`Assignment`):
- `collaborator_id` (FK), `project_id` (FK)
- `role` / `mansione` — ruolo nel progetto
- `ore_previste`, `ore_completate`, `ore_rimanenti`
- `tariffa_oraria`, `importo_totale`
- `data_inizio`, `data_fine`
- `stato` (attiva/completata/sospesa/annullata)

**Endpoint REST**: CRUD standard + bulk update

**Componenti Frontend**: `AssignmentModal.js`

**Relazioni**:
- `Assignment` → `Collaborator` (many-to-one)
- `Assignment` → `Project` (many-to-one)
- `Assignment` → `Attendance` (one-to-many)
- `Assignment` ↔ `VocePianoFinanziario` (possibile one-to-one, da verificare)

**Problemi identificati**:
- `check_assignment_overlap` esiste in crud ma non è esposta via endpoint
- La creazione di un'assegnazione NON crea automaticamente una voce nel piano (flusso manuale)

---

## MODULO 4: PRESENZE (TIMESHEET)

**Descrizione**: Registrazione delle ore lavorate da un collaboratore su un progetto in una data specifica.

**Campi principali** (`Attendance`):
- `collaborator_id` (FK), `project_id` (FK), `assignment_id` (FK, nullable)
- `data`, `ora_inizio`, `ora_fine`
- `ore_lavorate` (calcolato)
- `descrizione_attivita`
- `stato` (registrata/approvata/rifiutata)
- `importo` (tariffa_oraria × ore_lavorate)

**Endpoint REST**: CRUD standard
**Componenti Frontend**: `AttendanceModal.js`, `TimesheetReport.js`

**Problemi identificati**:
- Validazione overlap eseguita solo in Python (no constraint DB UNIQUE)
- `limit=10000` hardcoded nel report timesheet

---

## MODULO 5: CALENDARIO

**Descrizione**: Visualizzazione calendariale delle presenze e assegnazioni.

**Componenti Frontend**: `Calendar.js`, `CalendarSimple.js`
- Mostra eventi da presenze e/o assegnazioni
- Permette navigazione per mese/settimana
- Non ha backend dedicato (usa endpoint `/attendances` e `/assignments`)

---

## MODULO 6: ENTI ATTUATORI

**Descrizione**: Organizzazioni che attuano i progetti formativi (es. ente di formazione, cooperativa).

**Campi principali** (`ImplementingEntity`):
- `ragione_sociale`, `partita_iva`, `codice_fiscale`
- `indirizzo`, `citta`, `cap`, `provincia`
- `iban`, `bic`
- `logo_url`
- `rappresentante_legale`, `ruolo_rappresentante`
- `email_pec`, `telefono`

**Endpoint REST**: CRUD standard
**Componenti Frontend**: `ImplementingEntitiesList.js`, `ImplementingEntityModal.js`

**Relazioni**:
- `ImplementingEntity` → `Project` (one-to-many via `ente_attuatore_id`)

---

## MODULO 7: TEMPLATE PIANI FINANZIARI

**Descrizione**: Template strutturato che definisce le categorie di spesa per un tipo di fondo (Formazienda, FAPI, FSE).

**Campi principali** (`TemplatePianoFinanziario`):
- `nome`, `descrizione`
- `tipo_fondo` (formazienda/fapi/fse/fondimpresa/altro)
- `struttura_json` — definizione JSON delle voci tipo
- `is_active`

**Relazioni**:
- `TemplatePianoFinanziario` → `AvvisoPianoFinanziario` (one-to-many)

---

## MODULO 8: AVVISI PIANI FINANZIARI

**Descrizione**: Bando specifico con budget, date e limiti definiti, collegato a un template.

**Campi principali** (`AvvisoPianoFinanziario`):
- `codice`, `titolo`
- `template_id` (FK → `TemplatePianoFinanziario`)
- `ente_erogatore`, `tipo_fondo`
- `data_apertura`, `data_chiusura`
- `budget_massimo_progetto`, `budget_massimo_totale`
- `percentuale_cofinanziamento`
- `costo_orario_massimo_docenza`

**Relazioni**:
- `AvvisoPianoFinanziario` → `PianoFinanziario` (one-to-many)
- `AvvisoPianoFinanziario` ← `Project` (via `avviso_pf_id`)

---

## MODULO 9: PIANI FINANZIARI

**Descrizione**: Piano economico di un progetto che traccia budget, voci di spesa e stato di rendicontazione.

**Campi principali** (`PianoFinanziario`):
- `progetto_id` (FK), `avviso_pf_id` (FK, nullable)
- `anno`, `ente_erogatore`, `avviso` (legacy)
- `stato` (bozza/inviato/approvato/rendicontato)
- `budget_approvato`, `budget_rendicontato`, `budget_richiesto`
- UNIQUE constraint su `(progetto_id, anno, ente_erogatore, avviso)`

**Componenti Frontend**: `PianiFinanziariManager.js`, `PianiFinanziariHub.js`, `PianoFinanziarioManager.js`

**Problemi identificati**:
- Doppio constraint UNIQUE (vedi Bug #2 in AUDIT_BUG_FIXES.md)

---

## MODULO 10: VOCI PIANO FINANZIARIO

**Descrizione**: Singola voce di spesa nel piano (es. "Docenza senior", "Materiali didattici").

**Campi principali** (`VocePianoFinanziario`):
- `piano_id` (FK), `assignment_id` (FK, nullable)
- `categoria`, `sottocategoria`, `mansione_riferimento`
- `ore_previste`, `importo_previsto`
- `ore_rendicontate`, `importo_rendicontato`
- `note`

---

## MODULO 11: PIANI FONDIMPRESA

**Descrizione**: Modulo separato per la gestione dei piani Fondimpresa, con struttura diversa dai piani standard (righe nominative obbligatorie).

**Classi**: `PianoFinanziarioFondimpresa`, `VoceFondimpresa`, `RigaNominativoFondimpresa`

**Componenti Frontend**: `PianiFondimpresaManager.js`

**Logica differente**:
- Fondimpresa richiede la lista nominativa dei partecipanti per voce
- Budget diviso in costi diretti e indiretti con percentuali fisse

---

## MODULO 12: MANSIONI PER ENTE (ProgettoMansioneEnte)

**Descrizione**: Definisce quale mansione un ente attuatore può erogare su un progetto specifico, con tariffe negoziate.

**Campi principali** (`ProgettoMansioneEnte`):
- `progetto_id` (FK), `ente_id` (FK → `ImplementingEntity`)
- `mansione`, `descrizione`
- `tariffa_oraria`, `ore_previste`
- `data_inizio`, `data_fine`

**Componenti Frontend**: `ProgettoMansioneEnteManager.js`

---

## MODULO 13: TEMPLATE CONTRATTI

**Descrizione**: Template HTML con variabili placeholder per generare contratti PDF personalizzati.

**Campi principali** (`ContractTemplate`):
- `nome`, `descrizione`
- `content_html` — template con `{{variabile}}`
- `tipo` (docenza/coordinamento/tutoraggio/altro)
- `variables_list` — JSON con lista variabili supportate

**Endpoint REST**: CRUD + `POST /convert-docx-to-html`, `GET /{id}/variables`
**Componenti Frontend**: `ContractTemplatesManager.js`
**File backend**: `contract_generator.py`

---

## MODULO 14: AGENTI AI

**Descrizione**: Sistema di agenti AI per data quality, suggerimenti automatici e workflow intelligenti.

**Classi**:
- `AgentRun` — singola esecuzione agente (stato, log, metriche)
- `AgentSuggestion` — suggerimento prodotto dall'agente
- `AgentReviewAction` — azione umana su un suggerimento (accetta/rifiuta)

**File backend**: `ai_agents/`, `agent_workflows.py`, `routers/agents.py`
**Componenti Frontend**: `AgentsManager.js`, `AgentsDashboard.js`, `AgentSuggestionsReview.js`

**Problemi identificati**:
- Campi duplicati legacy: `agent_name` vs `agent_type`, `confidence` vs `confidence_score`
- `reviewed_by` (String) vs `reviewed_by_user_id` (Integer) in `AgentReviewAction`

---

## MODULO 15: AZIENDE CLIENTI

**Descrizione**: Anagrafica clienti aziendali per il modulo commerciale.

**Campi principali** (`AziendaCliente`):
- `ragione_sociale`, `partita_iva`, `codice_fiscale`
- `settore`, `dimensione`
- `referente_nome`, `referente_email`, `referente_telefono`
- `consulente_id` (FK → `Consulente`)

---

## MODULI 16-19: PREVENTIVI, ORDINI, CATALOGO, LISTINI

**Flusso commerciale**:
```
Prodotto (catalogo) → Listino (prezzi per tipo cliente)
                         ↓
AziendaCliente → Preventivo → (accettato) → Ordine
```

- `Preventivo`: intestazione + righe prodotto con prezzi
- `Ordine`: creato da preventivo accettato, con stato avanzamento
- `Prodotto`: catalogo con codice, descrizione, unità misura
- `Listino`: prezzi per categoria cliente (standard/premium/partner)

**Problema**: Nessun endpoint DELETE per `Ordine` — ordini errati non eliminabili.

---

## MODULO 20: DOCUMENTI COLLABORATORE

**Descrizione**: Tracciamento documenti richiesti e ricevuti per ogni collaboratore.

**Campi principali** (`DocumentoRichiesto`):
- `collaborator_id` (FK)
- `tipo_documento`, `descrizione`
- `data_richiesta`, `data_ricezione`
- `stato` (richiesto/ricevuto/scaduto)
- `file_path` (opzionale, path del file caricato)

---

## MATRICE RELAZIONI

```
                 Collab  Project  Assign  Attend  PianoFin  Voce  Ordine
Collaborator       -      M:M      1:M     1:M      -         -      -
Project           M:M      -       1:M     1:M      1:M       -      ?
Assignment        M:1     M:1       -      1:M      -        0:1     -
Attendance        M:1     M:1      M:1      -        -         -      -
PianoFinanziario  -       M:1       -       -        -        1:M     -
VocePiano         -        -       M:1      -       M:1        -      -
```
