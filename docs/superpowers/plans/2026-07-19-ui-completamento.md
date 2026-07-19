# Ondata UI-COMPLETAMENTO — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Chiudere le 3 eccezioni del GATE UI v2 (E2 test E2E catena contratto, E1 creazione piano da template, E3 "Chiedi all'archivio") e rieseguire il GATE UI v3.

**Architecture:** Backend FastAPI + SQLAlchemy (SQLite nei test, PostgreSQL runtime), frontend React CRA a sezioni (`App.js` switch su `activeSection`, matrice RBAC in `frontend/src/auth/permissions.js`). Flusso agenti canonico: collector puro → `run_agent_workflow` → `AgentSuggestion` → review umana. LLM via `ai_agents/llm.py` (`call_ollama_json`, timeout/retry esistenti).

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, pdfminer.six (runtime, per estrazione testo PDF nei test), React 18 CRA + jest, PostgreSQL FTS `italian` (con fallback ILIKE portabile).

## Global Constraints

- Commit atomici locali `feat/fix(ID): ...`; **mai push**.
- Suite completa sempre verde a fine task/ondata (baseline: backend 578 passed 3 skipped; frontend 96 passed).
- Migration **solo Alembic**, provata prima su copia DB (upgrade/downgrade/re-upgrade, dati invariati). Head attuale: `059`.
- Flusso canonico agenti: proposte, mai auto-apply.
- Nuovi problemi → `audit/FINDINGS_NUOVI.md`.
- Codice nuovo nei servizi di dominio; vietato aggiungere funzioni a `backend/crud.py` root.
- Stop al GATE UI v3 con dichiarazione onesta.
- Backup pre-ondata verificato: `/app/backups/gestionale_backup_ui_completamento_pre_20260719_143401.sql.zip.gpg` (INTEGRITY=True).
- Ondata M congelata fino a GATE UI v3 superato.
- Ordine: **E2 → E1 → E3 → GATE v3**.

## Ricognizione (fatta 2026-07-19 — NON ripetere)

**E2 — catena contratto, cosa esiste già:**
- Collector puro: `backend/ai_agents/contract_agent.py::collect_contract_suggestions` — suggestion `contract_ready` su `entity_type=assignment` quando tutti i `DocumentoRichiesto` obbligatori del collaboratore sono `validato`; payload include `generate_url: /api/v1/assignments/{id}/contract`.
- **Trigger reale già esistente:** `backend/routers/documenti_richiesti.py::_trigger_contract_agent_for_document` — chiamato da `POST /api/v1/documenti-richiesti/{doc_id}/valida` (e dall'update a stato validato, riga 129) via `run_agent_workflow(..., auto_mode=True)`.
- Endpoint documenti: `POST /api/v1/documenti-richiesti/` (crea richiesta), `POST .../{doc_id}/upload` (multipart, `data_scadenza` opzionale), `POST .../{doc_id}/valida` (payload `{validato_da}`), `POST .../{doc_id}/rifiuta`.
- Review umana: `POST /api/v1/agents/suggestions/{id}/accept` / `/review` / `/reject` (`backend/routers/agents.py:354-433`), RBAC `require_agents_write`.
- Generazione: `GET /api/v1/assignments/{assignment_id}/contract` in `backend/routers/sprint7.py:120` (`genera_contratto`) — StreamingResponse PDF, template `ContractTemplate` HTML se presente altrimenti fallback `ContractGenerator`. **Nessuna dipendenza auth visibile sull'endpoint** → verificare nel test; se non protetto è un finding.
- `_generate_contract_pdf_response` in `contract_templates.py:420` risulta **senza chiamanti** (relitto UI-14, non toccare in quest'ondata).
- Test pattern: SQLite + `app.dependency_overrides[get_db/get_current_user]` (vedi `backend/tests/test_upload.py`, `test_dom10_massimali_budget.py`); PDF reale minimo in `test_upload.py::create_test_pdf_bytes`. pdfminer.six 20260107 disponibile nel runtime (già in requirements) per `extract_text`.

**E1 — B4, cosa esiste già: NIENTE.**
- Zero occorrenze di `PianoFinanziarioTemplate` nel backend. Nessun seed, nessun endpoint. `PianoFinanziario.legacy_template_id` (models.py:1090) è un relitto intoccato.
- `Avviso.template_id` (models.py:350) punta a `ContractTemplate` (template contratti, NON piani) — relitto B4 da NON bonificare in quest'ondata (fuori scope E1 essenziale; censire).
- Creazione piano libera esistente: `POST /api/v1/piani-finanziari/` (+ `POST /{piano_id}/voci`).
- Massimali attuali: `_validate_massimale_voce` (`routers/piani_finanziari.py:24`) usa **solo** `MassimaleFondo` (fondo/anno, docenza|tutoraggio) → 422. **La precedenza regola-avviso-validata > MassimaleFondo (B2) NON esiste** — E1.c la introduce.
- `AvvisoRegola` (models.py:442): categoria in {'massimali','parametri_costo',...}, `stato='validata'`, `testo_originale`, `riferimento_articolo`, `valore` JSON, FK `avviso_revisione_id`. `PianoFinanziario` ha `avviso_pf_id` + `avviso_revisione_id`.

**E3 — L1, cosa esiste già: NIENTE di FTS.**
- Zero tsvector/to_tsquery nel backend (i match "fts" erano falsi positivi, es. "drafts"). Nessun endpoint di ricerca archivio.
- Fonti dati disponibili: `AvvisoRegola` (validate: chiave, valore, testo_originale, riferimenti), `AvvisoConoscenza` (contenuto, tags), `AvvisoEsitoProgetto` (note, esito, importi). **Non esiste una tabella chunk avvisi**: i markdown puliti stanno su file (`AvvisoRevisione.cleaned_md_path`). Versione essenziale e onesta: FTS sulle 3 fonti DB; i chunk file restano fuori (dichiararlo nel report).
- LLM: `ai_agents/llm.py::call_ollama_json` con retry/timeout/validazione; health probe `probe_agent_llm_health`. Riusare, non duplicare.
- UI archivio esistente: `frontend/src/components/ResourceArchive.js` (sezione `resources`).

**GATE v2 residui non bloccanti censiti:** UI-12, UI-13/14, UI-18, NEW-020 — non in scope.

---

# FASE E2 — TEST E2E CATENA CONTRATTO

### Task E2.1: Test E2E happy path — dalla creazione anagrafica al PDF

**Files:**
- Test (create): `backend/tests/test_e2e_catena_contratto.py`

**Interfaces:**
- Consumes: endpoint reali censiti in ricognizione. Nessun mock del collector; LLM non coinvolto (contract_agent non usa LLM).
- Produces: fixture riusabili nel file (`client`, `admin_user`, `catena_base`) per Task E2.2.

- [ ] **Step 1: Scrivere il test (RED atteso solo se la catena reale è rotta)**

Struttura del file (setup identico al pattern `test_dom10_massimali_budget.py`: engine SQLite `StaticPool`, `Base.metadata.create_all`, override `get_db` + `get_current_user` con utente admin ORM):

```python
"""
E2E catena contratto: anagrafica → progetto/assegnazione → documenti
obbligatori → upload+valida via API → trigger reale contract_agent →
accept umano → GET generate_url → PDF valido con dati del collaboratore.
"""
import io
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pdfminer.high_level import extract_text

# ... setup engine sqlite + overrides come test_dom10 ...

def _crea_catena_base(client):
    ente = client.post("/api/v1/implementing-entities/", json={...}).json()
    collab = client.post("/api/v1/collaborators/", json={
        "first_name": "Mario", "last_name": "Rossi",
        "fiscal_code": "RSSMRA80A01H501U", ...}).json()
    project = client.post("/api/v1/projects/", json={..., "ente_attuatore_id": ente["id"]}).json()
    assignment = client.post("/api/v1/assignments/", json={
        "collaborator_id": collab["id"], "project_id": project["id"],
        "role": "docenza", "assigned_hours": 40, "hourly_rate": 60.0, ...}).json()
    return ente, collab, project, assignment

def test_catena_contratto_completa(client, db_session):
    ente, collab, project, assignment = _crea_catena_base(client)

    # 3. documenti obbligatori
    doc_ids = []
    for tipo in ["documento_identita", "codice_fiscale"]:
        r = client.post("/api/v1/documenti-richiesti/", json={
            "collaboratore_id": collab["id"], "tipo_documento": tipo,
            "obbligatorio": True})
        assert r.status_code == 201
        doc_ids.append(r.json()["id"])

    # 4. upload + valida come farebbe l'operatore
    for doc_id in doc_ids:
        up = client.post(f"/api/v1/documenti-richiesti/{doc_id}/upload",
            files={"file": ("doc.pdf", io.BytesIO(PDF_BYTES), "application/pdf")})
        assert up.status_code == 200
        ok = client.post(f"/api/v1/documenti-richiesti/{doc_id}/valida",
            json={"validato_da": "admin_test"})
        assert ok.status_code == 200

    # 5. trigger REALE: la valida dell'ultimo doc ha lanciato contract_agent
    pend = client.get("/api/v1/agents/suggestions/pending").json()
    contract = [s for s in pend if s["suggestion_type"] == "contract_ready"
                and s["entity_id"] == assignment["id"]]
    assert len(contract) == 1
    sugg = contract[0]
    assert sugg["payload"]["generate_url"] == f"/api/v1/assignments/{assignment['id']}/contract"

    # run tracciato (non chiamata diretta al collector)
    runs = client.get("/api/v1/agents/runs/", params={"agent_type": "contract_agent"}).json()
    assert any(r["id"] == sugg["agent_run_id"] for r in runs)

    # 6. apply umano
    acc = client.post(f"/api/v1/agents/suggestions/{sugg['id']}/accept",
        json={"action": "accepted", "reviewed_by_user_id": admin_id})
    assert acc.status_code == 200
    assert acc.json()["status"] in ("accepted", "approved")

    # 7. generazione dall'endpoint reale
    pdf = client.get(sugg["payload"]["generate_url"])
    assert pdf.status_code == 200
    assert pdf.headers["content-type"].startswith("application/pdf")
    assert pdf.content.startswith(b"%PDF")
    assert len(pdf.content) > 1000

    # 8. asserzioni finali sul contenuto
    testo = extract_text(io.BytesIO(pdf.content))
    assert "Rossi" in testo and "Mario" in testo
    assert "docenza" in testo.lower()
    assert "40" in testo            # ore
    assert "60" in testo            # tariffa
    # stato pratica coerente
    sugg_after = client.get(f"/api/v1/agents/suggestions/{sugg['id']}").json()
    assert sugg_after["status"] != "pending"
    # audit trail: run + review action registrati
    assert sugg_after["review_actions"], "review action assente"
```

Nota: i nomi esatti dei campi obbligatori di collaborator/project/assignment vanno letti da `backend/schemas.py` al momento della scrittura (il worker li verifica, non li inventa). Se `ContractTemplate` di default serve per contenuto deterministico, crearne uno nel test con `contenuto_html` che usa i placeholder `«NOME»`, `«ORE»`, `«COSTO_UNITARIO»` ecc. (vedi sprint7.py:214-240) — così l'estrazione testo è garantita anche senza fallback generator.

- [ ] **Step 2: Eseguire il test**

Run: `docker exec pythonpro_backend python -m pytest tests/test_e2e_catena_contratto.py -x -v`

Esiti possibili: PASS (catena sana) oppure FAIL su un passaggio reale rotto → quello è il valore del test: aprire finding, correggere RED→GREEN con fix minimo nel punto giusto (mai nel test), ricommittare separatamente il fix con proprio ID.

- [ ] **Step 3: Se l'endpoint contratto risulta non autenticato** (sospetto da ricognizione: `genera_contratto` non ha dipendenza utente): censire in `FINDINGS_NUOVI.md` come NEW-021 e correggere aggiungendo la dipendenza RBAC coerente con gli altri endpoint sprint7 (`require_agents_execute` NON è quella giusta per un download operatore: usare la dipendenza auth standard usata da timesheet/documenti, verificare pattern in `routers/timesheet.py`). Test RBAC: consultazione → 403.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_e2e_catena_contratto.py
git commit -m "feat(E2): test E2E catena contratto completa fino al PDF"
```

### Task E2.2: Test negativi della catena

**Files:**
- Modify: `backend/tests/test_e2e_catena_contratto.py` (append)

- [ ] **Step 1: Tre test negativi**

```python
def test_documento_mancante_nessuna_suggestion(client):
    """Doc obbligatorio mai caricato → valida degli altri non produce contract_ready."""
    # catena base + 2 doc richiesti, upload+valida SOLO del primo
    # assert: nessuna suggestion contract_ready pending per l'assignment

def test_documento_non_validato_nessuna_suggestion(client):
    """Doc caricato ma stato 'caricato' (non validato) → nessuna suggestion."""
    # upload di tutti, valida di nessuno; trigger manuale via
    # POST /api/v1/agents/contract_agent/run (endpoint reale)
    # assert: 0 suggestion contract_ready

def test_accept_due_volte_nessun_doppio_effetto(client):
    """Secondo accept sulla stessa suggestion → nessun doppio effetto."""
    # catena completa fino ad accept OK
    # secondo POST accept → atteso 400 (workflow action non valida da stato
    # accepted) OPPURE no-op; in entrambi i casi:
    # assert: una sola transizione di stato; le review_actions non raddoppiano
    # l'effetto; status invariato dopo la seconda chiamata
```

Per il caso "documento scaduto": `upload` accetta `data_scadenza`; caricare con `data_scadenza` passata e verificare che la pratica non risulti completa (se invece il collector la considera completa → finding + fix in `_pratica_completa`, RED→GREEN).

- [ ] **Step 2: Run + eventuale fix disciplinato**

Run: `docker exec pythonpro_backend python -m pytest tests/test_e2e_catena_contratto.py -v`
Expected: PASS tutti. Ogni comportamento reale scoperto rotto → finding + fix separato.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_e2e_catena_contratto.py
git commit -m "feat(E2): test negativi catena contratto (doc mancante/scaduto, doppio accept)"
```

### Task E2.3: Gate di fase E2

- [ ] **Step 1:** Suite backend completa: `docker exec pythonpro_backend python -m pytest tests/ -q` — Expected: ≥578 passed + nuovi, 0 failed (3 skipped noti).
- [ ] **Step 2:** Aggiornare `audit/FINDINGS_NUOVI.md` con eventuali finding emersi; commit `docs(E2): ...` se toccato.

---

# FASE E1 — CREAZIONE PIANO DA TEMPLATE (B4 essenziale)

### Task E1.1: Modello `PianoFinanziarioTemplate` + migration 060 + seed

**Files:**
- Modify: `backend/models.py` (dopo `MassimaleFondo`, ~riga 1212+)
- Create: `backend/alembic/versions/060_add_piano_finanziario_templates.py`
- Create: `backend/services/piano_templates.py` (costanti seed + logica dominio)
- Test: `backend/tests/test_piano_templates_model.py`

**Interfaces:**
- Produces: `models.PianoFinanziarioTemplate` (campi sotto); `services/piano_templates.py::TEMPLATE_SEED` (list[dict]), `seed_templates(db) -> int` idempotente, `crea_piano_da_template(db, template_id, progetto_id, testata: dict, user) -> PianoFinanziario`.

- [ ] **Step 1: Test modello/vincoli (RED)**

```python
def test_template_versionato_unico():
    # stessa (nome, versione) → IntegrityError
def test_template_struttura_voci_json():
    # struttura_voci = [{"categoria": "docenza", "descrizione": ..., "macrovoce": ...}, ...]
def test_seed_idempotente(db_session):
    from services.piano_templates import seed_templates
    n1 = seed_templates(db_session); n2 = seed_templates(db_session)
    assert n1 > 0 and n2 == 0
```

- [ ] **Step 2: Modello**

```python
class PianoFinanziarioTemplate(Base):
    __tablename__ = "piano_finanziario_templates"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(200), nullable=False)
    descrizione = Column(Text, nullable=True)
    tipo_fondo = Column(String(30), nullable=False, index=True)   # stessi valori di PianoFinanziario.tipo_fondo
    ente_erogatore = Column(String(100), nullable=True)
    avviso_id = Column(Integer, ForeignKey("avvisi.id", ondelete="SET NULL"), nullable=True, index=True)
    versione = Column(Integer, nullable=False, default=1, server_default="1")
    is_active = Column(Boolean, nullable=False, default=True, server_default=text("true"))
    struttura_voci = Column(AVVISO_JSON_TYPE, nullable=False)     # lista voci: categoria, descrizione, macrovoce
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    __table_args__ = (
        UniqueConstraint("nome", "versione", name="uq_pf_template_nome_versione"),
        CheckConstraint("versione > 0", name="ck_pf_template_versione_positiva"),
    )
```

- [ ] **Step 3: Seed da costanti** in `services/piano_templates.py`: `TEMPLATE_SEED` con almeno un template generico per fondo presente nel DB reale (`formazienda`, `fapi`, `fondimpresa`) con voci standard docenza/tutoraggio/coordinamento/materiali; `seed_templates` inserisce solo i (nome, versione) assenti. **Nessun seed dentro la migration** (i dati seed sono ricreabili e la funzione è idempotente; la migration crea solo schema — coerente con catena greenfield NEW-003).

- [ ] **Step 4: Migration 060** — solo `op.create_table`/indici + downgrade `drop_table`. Prova su clone (procedura standard di progetto):

```bash
# clone dal backup fresco, upgrade 059→060, downgrade→059, re-upgrade, verifica dati invariati
docker exec pythonpro_db psql -U <user> -c "CREATE DATABASE pythonpro_e1_test TEMPLATE <db>;"
docker exec -e DATABASE_URL=<url clone> pythonpro_backend alembic upgrade head
docker exec -e DATABASE_URL=<url clone> pythonpro_backend alembic downgrade 059
docker exec -e DATABASE_URL=<url clone> pythonpro_backend alembic upgrade head
# poi conteggi tabelle chiave invariati; drop del clone
```

Solo dopo la prova su clone: `alembic upgrade head` sul DB reale (backup già fatto) + `seed_templates` via shell one-off documentata.

- [ ] **Step 5: Run test (GREEN) + commit**

```bash
git add backend/models.py backend/alembic/versions/060_*.py backend/services/piano_templates.py backend/tests/test_piano_templates_model.py
git commit -m "feat(E1): entità PianoFinanziarioTemplate versionata, migration 060 e seed idempotente"
```

### Task E1.2: Endpoint listing/anteprima/creazione da template

**Files:**
- Create: `backend/routers/piano_templates.py` (router `prefix="/api/v1/piano-templates"`)
- Modify: `backend/main.py` (include_router)
- Modify: `backend/schemas.py` (PianoTemplateRead, PianoTemplateAnteprima, PianoDaTemplateCreate)
- Modify: `backend/services/piano_templates.py` (anteprima + creazione)
- Test: `backend/tests/test_piano_templates_api.py`

**Interfaces:**
- Consumes: `models.PianoFinanziarioTemplate`, `crud.create_piano_finanziario`/`create_voce_piano` esistenti, `services/massimali.py` (Task E1.3 — l'anteprima usa `get_massimale_effettivo`; nell'ordine di esecuzione E1.3 può precedere o essere sviluppata insieme: il worker di E1.2 pu`ò` stub-are la fonte come solo MassimaleFondo e E1.3 la completa).
- Produces:
  - `GET /api/v1/piano-templates/?tipo_fondo=&avviso_id=` → lista template attivi pertinenti; se `avviso_id` ha template collegato, campo `preselezionato: true` su quello.
  - `GET /api/v1/piano-templates/{id}/anteprima?avviso_id=` → `{template, voci, massimali: [{categoria, limite, fonte: "regola_avviso"|"massimale_fondo", riferimento_articolo?}]}`.
  - `POST /api/v1/piani-finanziari/from-template` body `{template_id, progetto_id, avviso_id?, anno, nome, budget_totale?, ...testata}` → 201 `PianoFinanziarioWithVoci` con voci strutturate dal template. (Route montata nel router piani esistente per coerenza URL.)
- RBAC: listing/anteprima tutti e tre i ruoli; `from-template` admin+operatore, consultazione → 403. Usare le stesse dipendenze RBAC di `POST /api/v1/piani-finanziari/`.

- [ ] **Step 1: Test API (RED)** — casi: lista filtrata per fondo; preselezione da avviso; anteprima con fonti massimale; creazione → piano con voci giuste e `avviso_pf_id`/`avviso_revisione_id` (revisione corrente) valorizzati quando `avviso_id` è passato; consultazione 403 su from-template; **percorso libero `POST /api/v1/piani-finanziari/` resta invariato** (test di regressione esplicito).
- [ ] **Step 2: Implementazione minima** (service fa il lavoro, router sottile).
- [ ] **Step 3: Run GREEN.**
- [ ] **Step 4: Commit** `feat(E1): endpoint listing/anteprima/creazione piano da template`.

### Task E1.3: Massimali con precedenza regola avviso validata

**Files:**
- Create: `backend/services/massimali.py`
- Modify: `backend/routers/piani_finanziari.py` (`_validate_massimale_voce` delega al servizio)
- Test: `backend/tests/test_massimali_avviso.py`

**Interfaces:**
- Produces: `get_massimale_effettivo(db, piano, categoria: str) -> MassimaleEffettivo | None` con `dataclass MassimaleEffettivo(limite: Decimal, fonte: str, riferimento_articolo: str | None, testo_originale: str | None)`. Ricerca: `AvvisoRegola` con `stato='validata'`, `avviso_revisione_id == piano.avviso_revisione_id`, `categoria IN ('massimali','parametri_costo')`, chiave che matcha la categoria voce (`docenza`/`tutoraggio` — match su `chiave` normalizzata, valore numerico estratto da `valore` JSON: gestire sia scalare sia `{"importo": X}` sia `{"valore": X}`; se il formato non è interpretabile → log warning e fallback, MAI inventare limiti). Fallback: `MassimaleFondo` come oggi.

- [ ] **Step 1: Test (RED)**

```python
def test_precedenza_regola_avviso_su_massimale_fondo():
    # MassimaleFondo docenza=100; regola validata massimale docenza=80 su revisione del piano
    # voce tariffa 90 → 422 con riferimento_articolo della regola nel detail
def test_fallback_massimale_fondo_senza_regola(): ...
def test_regola_non_validata_ignorata(): ...   # stato='proposta' → vale il fondo
def test_422_cita_articolo():
    # detail contiene riferimento_articolo e "regola avviso"
def test_piano_da_template_eredita_enforcement():
    # piano creato via from-template con avviso: voce oltre soglia regola → 422
```

- [ ] **Step 2: Implementazione + delega da `_validate_massimale_voce`** (mantiene 422, arricchisce il detail con fonte e articolo).
- [ ] **Step 3: Run GREEN; regressione `test_dom10_massimali_budget.py` intatta.**
- [ ] **Step 4: Commit** `feat(E1): massimali con precedenza regola avviso validata e citazione articolo`.

### Task E1.4: Wizard UI 3 passi

**Files:**
- Create: `frontend/src/components/PianoTemplateWizard.js` (+ `.css`)
- Modify: `frontend/src/services/apiService.js` (pianoTemplates: list, anteprima, createFromTemplate)
- Modify: componente che ospita i piani finanziari (individuato a runtime: il punto dove oggi si crea un piano libero — seguire `apiService` per `piani-finanziari` POST; probabilmente `ProjectManager.js`/FapiUpload) — aggiungere bottone "Nuovo piano da template" accanto al percorso libero esistente.
- Modify: `frontend/src/auth/permissions.js` solo se serve azione dedicata (creazione = stessa permission dei piani).
- Test: `frontend/src/components/PianoTemplateWizard.test.js`

Wizard:
1. **SELEZIONE** — select fondo (obbligatorio) + select avviso (opzionale, filtrato per fondo); lista template pertinenti; template collegato all'avviso preselezionato ed evidenziato (badge "Consigliato dall'avviso").
2. **ANTEPRIMA** — tabella voci (categoria, descrizione, macrovoce) + massimali applicati con badge fonte: "Regola avviso (art. X)" vs "Massimale fondo generico".
3. **CONFERMA** — form testata (nome, anno, budget totale, date) → POST from-template → redirect/selezione del piano creato con voci visibili.

- [ ] **Step 1: Test jest (RED):** render 3 passi, preselezione template da avviso, badge fonte massimale, submit chiama `createFromTemplate` con payload giusto, ruolo consultazione non vede il bottone.
- [ ] **Step 2: Implementazione** (stile e pattern dei modali esistenti, es. `AssignmentModal`).
- [ ] **Step 3: `npm test` GREEN + build.**
- [ ] **Step 4: Commit** `feat(E1): wizard creazione piano da template in 3 passi`.

### Task E1.5: Gate di fase E1

- [ ] Suite backend completa verde; suite frontend completa verde; build production ok.
- [ ] Migration 060 applicata al DB reale (dopo prova clone in E1.1) + seed eseguito; runtime healthy.
- [ ] Findings aggiornati (incluso censimento relitti `Avviso.template_id`/`legacy_template_id` se non già presenti).
- [ ] Commit di eventuali doc: `docs(E1): ...`.

---

# FASE E3 — "CHIEDI ALL'ARCHIVIO" (essenziale e onesto)

### Task E3.1: Servizio di ricerca FTS + migration 061

**Files:**
- Create: `backend/services/archivio_search.py`
- Create: `backend/alembic/versions/061_add_archivio_fts_indexes.py`
- Test: `backend/tests/test_archivio_search.py`

**Interfaces:**
- Produces: `search_archivio(db, q: str, *, avviso_id=None, tipo_fondo=None, limit=20) -> list[RisultatoArchivio]` con `dataclass RisultatoArchivio(fonte: str, avviso_id, avviso_titolo, revisione_id, regola_id|None, conoscenza_id|None, esito_id|None, riferimento_articolo, estratto: str, rank: float)`.
- Fonti: `AvvisoRegola` (solo `stato='validata'`; testo = chiave + valore serializzato + testo_originale), `AvvisoConoscenza.contenuto`, `AvvisoEsitoProgetto.note`.
- Dialect-aware: su PostgreSQL usa `func.to_tsvector('italian', ...)` + `func.websearch_to_tsquery('italian', q)` + `ts_rank`; su SQLite (suite) fallback `ILIKE %term%` per termine con rank = numero di termini matchati. Stesso contratto di ritorno — il fallback E' anche il degrado runtime se mai servisse.
- Migration 061: indici GIN expression `to_tsvector('italian', ...)` sulle colonne testo delle 3 fonti (parziale `WHERE stato = 'validata'` per le regole). Solo schema; downgrade droppa gli indici. Prova su clone come 060, poi DB reale.

- [ ] **Step 1: Test (RED):** retrieval con risultati noti (regola validata trovata, proposta NON trovata), filtro avviso/fondo, estratto contiene il testo, ordinamento per rank, query vuota/corta → `[]`.
- [ ] **Step 2: Implementazione + migration; prova clone; run GREEN.** Test PG-only del percorso tsvector marcato come DOM-21 (skip se non PostgreSQL).
- [ ] **Step 3: Commit** `feat(E3): ricerca FTS archivio (regole validate, conoscenze, esiti) con migration 061`.

### Task E3.2: Endpoint search + "chiedi" con onestà non negoziabile

**Files:**
- Create: `backend/routers/archivio.py` (`prefix="/api/v1/archivio"`)
- Modify: `backend/main.py` (include_router)
- Modify: `backend/schemas.py` (ArchivioSearchResult, ArchivioChiediRequest/Response)
- Create: `backend/services/archivio_chiedi.py`
- Test: `backend/tests/test_archivio_chiedi.py`

**Interfaces:**
- `GET /api/v1/archivio/search?q=&avviso_id=&tipo_fondo=` → risultati con citazioni. RBAC: **tutti e tre i ruoli** (consultazione inclusa — è lettura).
- `POST /api/v1/archivio/chiedi` body `{domanda, avviso_id?, tipo_fondo?}` → `{stato: "ok"|"non_presente"|"degradato", risposta: str|None, citazioni: [{avviso_id, avviso_titolo, revisione_id, regola_id?, riferimento_articolo?, estratto}], risultati: [...]}`.
- Regole di onestà (test espliciti ciascuna):
  1. retrieval vuoto → `stato="non_presente"`, `risposta=None`, **LLM MAI chiamato** (assert su mock non invocato);
  2. prompt LLM impone risposta SOLO dai passaggi forniti; le citazioni in risposta sono un sottoinsieme dei chunk recuperati (validazione server-side: ogni citazione della risposta deve referenziare un id presente nel retrieval, altrimenti la risposta viene scartata → stato degradato);
  3. LLM giù/timeout (riusare `call_ollama_json` + `probe_agent_llm_health`) → `stato="degradato"` con i soli risultati di ricerca. La ricerca funziona sempre.

- [ ] **Step 1: Test (RED):** i 5 casi (risposta citata con mock LLM; non_presente senza chiamata LLM; degradato per LLM error; citazione fuori retrieval scartata; RBAC 3 ruoli 200 su search e chiedi).
- [ ] **Step 2: Implementazione** (service orchestrazione, router sottile; prompt in `services/archivio_chiedi.py` con istruzione citazioni obbligatorie e formato JSON validato).
- [ ] **Step 3: Run GREEN + commit** `feat(E3): endpoint search e chiedi-all-archivio con citazioni obbligatorie e degrado onesto`.

### Task E3.3: UI "Archivio / Chiedi all'archivio"

**Files:**
- Create: `frontend/src/components/ArchivioChiedi.js` (+ `.css`)
- Modify: `frontend/src/App.js` (sezione `archivio-chiedi`, case nel switch)
- Modify: `frontend/src/auth/permissions.js` (sezione visibile a admin/operatore/consultazione)
- Modify: `frontend/src/services/apiService.js` (archivio.search, archivio.chiedi)
- Modify: `frontend/src/components/ResourceArchive.js` solo se serve l'aggancio "apri alla regola citata" (deep-link interno: selezione avviso + evidenza regola)
- Test: `frontend/src/components/ArchivioChiedi.test.js`

UI: barra ricerca + filtri fondo/avviso; risposta con citazioni in evidenza cliccabili → vista avviso alla regola/sezione; disclaimer fisso "Risposta assistita: fa fede il testo dell'avviso"; stato degradato visibile ("AI non disponibile — risultati di sola ricerca"); stato non_presente esplicito ("Non presente in archivio").

- [ ] **Step 1: Test jest (RED):** ricerca renderizza risultati; risposta con citazioni; click citazione naviga alla vista avviso giusta; stato degradato renderizzato; stato non_presente renderizzato; sezione visibile ai 3 ruoli (snapshot menu aggiornato).
- [ ] **Step 2: Implementazione.**
- [ ] **Step 3: `npm test` GREEN + build + commit** `feat(E3): pagina Chiedi all'archivio con citazioni, degrado e disclaimer`.

### Task E3.4: Gate di fase E3

- [ ] Suite backend + frontend complete verdi; build ok; migration 061 su DB reale dopo clone; runtime healthy (`/health` 200).
- [ ] Verifica manuale via curl sui 3 ruoli reali (utenti `ui_test_*` esistenti) di search e chiedi (con Ollama on e off per il degrado).
- [ ] Findings aggiornati; commit doc.

---

# GATE UI v3 — RIESECUZIONE INTEGRALE

### Task G3.1: Protocollo completo Ondata UI

- [ ] Riesecuzione matrice pagina × ruolo (stesso harness Playwright/crawl del v2 — script e utenze `ui_test_*` già nel progetto; ripristinare l'ambiente di verifica come da report v2) su tutte le pagine incluse le due nuove.
- [ ] Flussi trasversali 1–8 TUTTI percorribili: il 2 ora passa da wizard template (E1), il 4 è coperto dall'E2E (E2), l'8 da Chiedi all'archivio (E3).
- [ ] Suite completa: backend (con i nuovi E2E), frontend, build production.

### Task G3.2: Report e dichiarazione

- [ ] `audit/UI_VERIFICA_REPORT.md` v3: sezione nuova con confronto v1→v2→v3, esiti matrice e flussi, gate tecnici (backup, alembic head 061, numeri suite), **dichiarazione finale: "TUTTE LE PAGINE COLLEGATE E FUNZIONANTI: SÌ/NO + eccezioni residue oneste"**.
- [ ] `REMEDIATION_LOG.md` aggiornato; `STATUS.md` aggiornato (entro 200 righe).
- [ ] Commit `docs(GATE): report GATE UI v3 e remediation log`.

### Task G3.3: Esito

- [ ] **Se v3 SUPERATO:** sbloccare e avviare l'Ondata M (manuale) come da prompt precedente — il manuale copre anche i capitoli 3 (piani da template) e 9 (chiedi all'archivio) su funzionalità reali verificate.
- [ ] **Se v3 NON superato:** fermarsi con elenco onesto delle eccezioni residue e attendere decisione utente.
