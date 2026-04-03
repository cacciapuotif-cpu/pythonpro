# Design — Modulo Avvisi

_Data: 2026-04-03_

## Problema

Il campo `avviso` è attualmente una stringa libera su `Project`, `PianoFinanziario` e `ContractTemplate`. Non esiste un catalogo centralizzato di avvisi, quindi:
- La cascata ente→avviso→progetto nell'hub Piani non funziona (nessun avviso valorizzato nei progetti)
- Non è possibile collegare un avviso a un template piano finanziario in modo strutturato
- Duplicati e varianti (es. `9/2026` vs `9 / 2026`) non sono prevenibili

## Soluzione

Introdurre `Avviso` come entità autonoma di primo livello con collegamento one-to-one opzionale a un `ContractTemplate` di ambito `piano_finanziario`. Tutte le entità che usano `avviso` come stringa libera migrano a FK verso la nuova tabella.

---

## Modello dati

### Nuova tabella `avvisi`

| Campo | Tipo | Vincoli |
|---|---|---|
| `id` | Integer | PK |
| `codice` | String(50) | NOT NULL |
| `ente_erogatore` | String(100) | NOT NULL |
| `descrizione` | String(200) | nullable |
| `template_id` | FK → `contract_templates.id` | nullable, SET NULL on delete |
| `is_active` | Boolean | default True |

Indice univoco: `(codice, ente_erogatore)`.

### Tabelle modificate

| Tabella | Vecchio campo | Nuovo campo | Note |
|---|---|---|---|
| `projects` | `avviso String(100)` | `avviso_id FK → avvisi` | nullable, SET NULL |
| `piani_finanziari` | `avviso String(100)` | `avviso_id FK → avvisi` | nullable |
| `piani_finanziari_fondimpresa` | `avviso String(100)` | `avviso_id FK → avvisi` | nullable |
| `contract_templates` | `avviso String(100)` | — rimosso | collegamento inverso tramite `avvisi.template_id` |

Indice univoco `piani_finanziari` aggiornato: `(progetto_id, anno, ente_erogatore, avviso_id)`.

---

## Backend API

Nuovo router `backend/routers/avvisi.py` registrato in `main.py`:

| Metodo | Endpoint | Descrizione |
|---|---|---|
| `GET` | `/api/v1/avvisi/` | Lista avvisi. Filtri: `?ente_erogatore=`, `?active_only=true` |
| `POST` | `/api/v1/avvisi/` | Crea avviso |
| `GET` | `/api/v1/avvisi/{id}` | Dettaglio avviso |
| `PUT` | `/api/v1/avvisi/{id}` | Aggiorna avviso |
| `DELETE` | `/api/v1/avvisi/{id}` | Soft-delete (`is_active=False`) |

Response progetto e piano includono oggetto `avviso` annidato per evitare chiamate extra dal frontend:

```json
{
  "id": 1,
  "name": "Progetto Alpha",
  "avviso": {
    "id": 1,
    "codice": "9/2026",
    "ente_erogatore": "FORMAZIENDA",
    "descrizione": "Avviso formazione 2026",
    "template_id": 3
  }
}
```

### Modifiche a router esistenti

- `routers/projects.py`: `avviso` (stringa) → `avviso_id` (intero) in create/update; response include oggetto `avviso` annidato
- `routers/piani_finanziari.py`: stesso cambio
- `routers/piani_fondimpresa.py`: stesso cambio
- `crud.py`: aggiornare `build_effective_piano_rows` e `build_piano_finanziario_riepilogo` per usare `avviso_id` FK

---

## Frontend

### A — Hub Piani Finanziari

Il dropdown "Avviso" in `PianiFinanziariHub.js` cambia da stringhe estratte dai progetti a `GET /api/v1/avvisi/?ente_erogatore=<ente>&active_only=true`. Pulsante `+ Nuovo avviso` apre un mini-modal inline per creare un avviso al volo senza uscire dalla sezione.

### B — Wizard Progetto (Step Governance)

In `ProjectManager.js`, il campo `avviso` diventa un `<select>` alimentato da `GET /api/v1/avvisi/?ente_erogatore=<ente>` con bottone `+` per creare un nuovo avviso. Selezionando un avviso che ha `template_id`, il campo Template Piano si autocompila e si blocca.

### C — Modal Template Documenti

In `ContractTemplateModal.js`, per i template di ambito `piano_finanziario` si aggiunge il campo "Collega ad avviso" (`<select>` da `/api/v1/avvisi/`). Salvando il template con un avviso selezionato, il backend esegue un **pointer swap**: cerca se esiste un avviso con `template_id = questo template`, lo azzera, poi imposta `avviso.template_id = template.id` sul nuovo avviso selezionato. Questo garantisce che il vincolo one-to-one sia sempre rispettato senza lasciare puntatori orfani.

### D — Sezione Config "Avvisi"

Nuovo componente `AvvisiManager.js` + `.css` registrato in `App.js` sotto il gruppo Config. Tabella con colonne: Codice, Ente, Descrizione, Template collegato, Stato. Modal create/edit con i campi della tabella `avvisi`.

---

## Migrazione

Migration Alembic `018_add_avvisi.py`:

1. Crea tabella `avvisi` con indice univoco `(codice, ente_erogatore)`
2. Aggiunge colonna `avviso_id` (FK nullable) a `projects`, `piani_finanziari`, `piani_finanziari_fondimpresa`
3. Nessuna conversione dati: i record esistenti hanno `avviso=NULL`, niente da trasferire
4. Droppa colonna `avviso` (stringa) da `projects`, `piani_finanziari`, `piani_finanziari_fondimpresa`
5. Droppa colonna `avviso` (stringa) da `contract_templates`
6. Ricrea indice univoco `piani_finanziari` con `avviso_id` al posto di `avviso`

Runtime schema update aggiunto in `main.py` come fallback per ambienti non migrati.

---

## File da creare/modificare

| File | Azione |
|---|---|
| `backend/models.py` | Nuova classe `Avviso`, modifica `Project`, `PianoFinanziario`, `PianoFinanziarioFondimpresa`, `ContractTemplate` |
| `backend/schemas.py` | Nuovi schemi `AvvisoBase/Create/Update/Response`, aggiornamento schemi `Project*`, `PianoFinanziario*` |
| `backend/crud.py` | Funzioni CRUD avvisi, aggiornamento funzioni piano/progetto |
| `backend/routers/avvisi.py` | Nuovo router |
| `backend/routers/projects.py` | Aggiornamento per `avviso_id` |
| `backend/routers/piani_finanziari.py` | Aggiornamento per `avviso_id` |
| `backend/routers/piani_fondimpresa.py` | Aggiornamento per `avviso_id` |
| `backend/main.py` | Registrazione router avvisi, runtime schema update |
| `backend/alembic/versions/018_add_avvisi.py` | Migration |
| `frontend/src/components/AvvisiManager.js` | Nuovo componente |
| `frontend/src/components/AvvisiManager.css` | Stili |
| `frontend/src/components/PianiFinanziariHub.js` | Dropdown avvisi da DB |
| `frontend/src/components/ProjectManager.js` | Campo avviso → select dal DB |
| `frontend/src/components/ContractTemplateModal.js` | Campo "Collega ad avviso" |
| `frontend/src/components/ContractTemplatesManager.js` | Rimozione colonna avviso stringa |
| `frontend/src/App.js` | Aggiunta sezione AvvisiManager in Config |
| `frontend/src/services/apiService.js` | Funzioni API avvisi |
