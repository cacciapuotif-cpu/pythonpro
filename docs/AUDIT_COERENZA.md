# AUDIT COERENZA — PythonPro ERP

> Generato: 2026-04-06

---

## 1. FUNZIONI CRUD NON USATE NEI ROUTER

Le seguenti funzioni sono definite in `crud.py` ma non vengono chiamate da nessun router:

| Funzione | Riga approx. | Categoria | Note |
|---|---|---|---|
| `get_collaborator_cached` | 69 | Cache inutile | Cache in-process, inutile con multi-worker |
| `invalidate_collaborator_cache` | 87 | Cache inutile | Idem |
| `get_collaborators_count` | 379 | Non esposta | Nessun endpoint `/count` |
| `sync_consultants_from_collaborators` | 573 | Non usata | Nessun trigger o endpoint |
| `get_attendances_summary` | 980 | Non esposta | Potenzialmente utile per dashboard |
| `get_monthly_stats` | 995 | Non esposta | Potenzialmente utile per dashboard |
| `check_assignment_overlap` | 1208 | Interna | Chiamata solo da `create_assignment` |
| `bulk_update_assignments` | 1718 | Non esposta | Nessun endpoint bulk |
| `get_active_assignments` | 1704 | Non esposta | Filtro non accessibile via API |
| `get_implementing_entity_by_piva` | 1876 | Non esposta | Ricerca per P.IVA non accessibile |
| `get_implementing_entities_count` | 1921 | Non esposta | Nessun endpoint `/count` |
| `soft_delete_implementing_entity` | 2019 | Non usata | Il router usa `delete_implementing_entity` |
| `get_progetto_mansione_ente_active_by_date` | 2180 | Non esposta | Filtro per data non accessibile |
| `get_progetto_mansione_ente_count` | 2144 | Non esposta | Nessun endpoint `/count` |
| `soft_delete_progetto_mansione_ente` | 2313 | Non verificata | Da verificare se usata |
| `get_template_with_variables` | 2886 | Parziale | Sostituita da `/{id}/variables` |
| `get_contract_templates_count` | 2600 | Non esposta | Nessun endpoint `/count` |
| `get_aziende_by_consulente` | 3017 | Non esposta | Join non accessibile via API |
| `get_prezzo_prodotto_in_listino` | 4887 | Non esposta | Calcolo prezzo non esposto |
| `get_voce_by_mansione` | 3826 | Non esposta | Lookup non accessibile |
| `get_voce_by_assignment` | 3833 | Non esposta | Lookup non accessibile |
| `calcola_budget_utilizzato` | 3558 | Wrapper | Non usata nei router |
| `get_piano_by_progetto` | 3540 | Duplicata | Esiste `get_piani_by_progetto` (plurale) |

**Totale funzioni non esposte**: ~23 su 220 (~10%)

---

## 2. CAMPI DUPLICATI / RIDONDANTI NEI MODELLI

### 2.1 Modello Project — 5 campi sovrapposti per ente/avviso

```
Project
├── ente_erogatore     (String)  ← LEGACY: testo libero "Formazienda"
├── avviso             (String)  ← LEGACY: testo libero "Avviso 1/2024"
├── avviso_id          (FK → avvisi)              ← Sistema strutturato A
├── avviso_pf_id       (FK → avvisi_piani_finanziari) ← Sistema strutturato B
└── template_piano_finanziario_id (FK → contract_templates) ← FK ERRATA (vedi Bug #1)
```

**I tre sistemi non sono sincronizzati**: se si aggiorna `avviso_id`, `ente_erogatore` non viene aggiornato automaticamente.

**Soluzione proposta**:
1. Deprecare `ente_erogatore` e `avviso` (String) — renderli nullable
2. Usare solo `avviso_pf_id` come riferimento strutturato
3. Derivare `ente_erogatore` e `avviso` dalla relazione `avviso_pf_id.ente_erogatore`
4. Correggere FK `template_piano_finanziario_id` (vedi Bug #1)

### 2.2 Modello AgentRun — campi duplicati legacy

```
AgentRun
├── agent_name    (String)  ← vecchio campo testuale
└── agent_type    (String)  ← nuovo campo enum/tipo

AgentSuggestion
├── confidence       (Float)  ← campo legacy
└── confidence_score (Float)  ← campo nuovo
```

### 2.3 Modello AgentReviewAction — `reviewed_by` duplicato

```
AgentReviewAction
├── reviewed_by         (String)  ← nome utente testuale
└── reviewed_by_user_id (Integer) ← FK utente
```

### 2.4 Modello PianoFinanziario — dati denormalizzati

```
Project
├── budget_totale
├── budget_utilizzato   ← ricalcolato, rischio incoerenza
└── budget_rimanente    ← ricalcolato, rischio incoerenza

PianoFinanziario
├── budget_approvato
├── budget_rendicontato  ← ricalcolato, rischio incoerenza
└── budget_richiesto     ← ricalcolato, rischio incoerenza
```

---

## 3. ENDPOINT FRONTEND vs BACKEND

Dall'analisi dei componenti frontend, tutti gli endpoint principali chiamati con `/api/v1/` hanno corrispondenza nei router backend. Nessun mismatch critico identificato per i moduli principali.

**Pattern URL coerenti**:
- `/api/v1/collaborators/` ↔ `routers/collaborators.py`
- `/api/v1/projects/` ↔ `routers/projects.py`
- `/api/v1/assignments/` ↔ `routers/assignments.py`
- `/api/v1/attendances/` ↔ `routers/attendances.py`
- `/api/v1/piani-finanziari/` ↔ `routers/piani_finanziari.py`
- `/api/v1/implementing-entities/` ↔ `routers/implementing_entities.py`
- `/api/v1/project-assignments/` ↔ `routers/progetto_mansione_ente.py`
- `/api/v1/contracts/` ↔ `routers/contract_templates.py`

---

## 4. CATENA MIGRAZIONI ALEMBIC

**34 file di migrazione totali**:
- File numerati: `001_...` → `029_...` (catena chiara e sequenziale)
- File hash-named (5):
  - `528d59380940_add_piani_finanziari.py`
  - `a10d08b5e238_...`
  - `b1c2d3e4f5a6_...`
  - `c2d3e4f5a6b7_...`
  - `d3de21183882_...`

**Problema**: i file hash-named sono stati generati con `alembic revision --autogenerate` in momenti diversi. Se il loro `down_revision` non punta correttamente ai file numerati, esistono **rami orfani** che non vengono applicati in un deploy fresh.

**Verifica manuale richiesta**:
```bash
docker compose exec backend alembic history --verbose
docker compose exec backend alembic heads  # deve mostrare UN solo head
docker compose exec backend alembic current
```

Se `alembic heads` mostra più di un head, la catena è spezzata.

---

## 5. SCHEMA DB vs MODELLI

### 5.1 ensure_runtime_schema_updates() — bypass Alembic

`backend/main.py` righe 94–251 contiene ~250 righe di `ALTER TABLE` raw SQL eseguiti a ogni avvio. Queste colonne **non sono nelle migrazioni Alembic**.

**Rischio**: in un deploy su DB vuoto:
1. Alembic applica le 34 migrazioni → schema parziale
2. `ensure_runtime_schema_updates()` aggiunge le colonne mancanti
3. Ma se alcune migrazioni hash-named già includono quelle colonne → `ALTER TABLE ADD COLUMN` fallisce con "column already exists"

**Lista colonne aggiunte a runtime** (da verificare):
- Aggiornamenti a `collaborators`, `projects`, `assignments`
- Nuovi indici e constraint

---

## 6. CONSTRAINT E INDICI

### 6.1 UNIQUE constraint duplicato su PianoFinanziario

**In models.py**:
```python
UniqueConstraint('progetto_id', 'anno', 'ente_erogatore', 'avviso')
```

**In main.py** (runtime):
```python
CREATE UNIQUE INDEX idx_unique_piano_progetto_anno_ente_avviso_id
ON piani_finanziari(progetto_id, anno, ente_erogatore, avviso_id)
```

Due constraint distinti su concetti sovrapposti (uno su `avviso` testo, l'altro su `avviso_id` FK).

### 6.2 Assenza constraint UNIQUE su Attendance

Nessun UNIQUE index `(collaborator_id, project_id, data, ora_inizio)` a livello DB. La validazione overlap è solo applicativa (Python), aggirabile con accesso diretto al DB o race condition.

---

## 7. RIEPILOGO PROBLEMI DI COERENZA

| Categoria | Numero problemi | Gravità |
|---|---|---|
| Funzioni CRUD non esposte | 23 | Bassa (codice morto) |
| Campi duplicati/ridondanti | 4 gruppi | Media-Alta |
| FK errata | 1 (critica) | Critica |
| Catena Alembic da verificare | 5 file | Alta |
| Runtime ALTER TABLE | ~15 colonne | Alta |
| UNIQUE constraint duplicato | 1 | Media |
| Mancanza constraint Attendance | 1 | Media |
