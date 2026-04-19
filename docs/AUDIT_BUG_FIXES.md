# AUDIT BUG FIXES — PythonPro ERP

> Generato: 2026-04-06  
> Totale bug identificati: 10 (4 critici, 4 importanti, 2 minori)

---

## Bug #1 — FK errata: Project.template_piano_finanziario_id

**Gravità**: 🔴 CRITICA  
**File**: `backend/models.py` ~riga 185  
**Problema**:
```python
# SBAGLIATO: punta a contract_templates (template HTML per contratti)
template_piano_finanziario_id = Column(
    Integer,
    ForeignKey("contract_templates.id", ondelete="SET NULL"),
    nullable=True
)
template_piano_finanziario = relationship("ContractTemplate", ...)
```
Il campo è semanticamente un riferimento a `TemplatePianoFinanziario` (template economico per piani finanziari), ma punta alla tabella sbagliata `contract_templates`.

**Impatto**: 
- La logica `_apply_project_financial_template()` in crud.py carica un oggetto `ContractTemplate` (template HTML) invece di `TemplatePianoFinanziario` (struttura economica)
- La struttura del piano finanziario non viene derivata correttamente dal template

**Fix**:
```python
# models.py — cambiare FK e relationship
template_piano_finanziario_id = Column(
    Integer,
    ForeignKey("template_piani_finanziari.id", ondelete="SET NULL"),
    nullable=True
)
template_piano_finanziario = relationship(
    "TemplatePianoFinanziario",
    foreign_keys=[template_piano_finanziario_id]
)
```
```bash
# Migrazione Alembic necessaria:
alembic revision --autogenerate -m "fix_project_template_pf_fk"
# Poi editare il file generato per gestire i dati esistenti
```

---

## Bug #2 — Doppio UNIQUE constraint su PianoFinanziario

**Gravità**: 🔴 CRITICA  
**File**: `backend/models.py` ~riga 837 + `backend/main.py` ~riga 264  
**Problema**:
```python
# models.py — usa campo testo "avviso"
UniqueConstraint('progetto_id', 'anno', 'ente_erogatore', 'avviso')

# main.py — usa FK "avviso_id" (viene applicato a runtime via ALTER)
CREATE UNIQUE INDEX idx_unique_piano_progetto_anno_ente_avviso_id
ON piani_finanziari(progetto_id, anno, ente_erogatore, avviso_id)
```
Due constraint distinti su colonne diverse (testo vs FK). Un piano può soddisfare uno ma non l'altro, creando incoerenza.

**Impatto**: possibile inserimento di piani finanziari duplicati; comportamento imprevedibile nella deduplication.

**Fix**:
1. Deprecare campo `avviso` (String) — renderlo nullable
2. Rimuovere `UniqueConstraint` su `avviso` (testo) da models.py
3. Mantenere solo l'indice su `avviso_id` (FK)
4. Migrare dati legacy: `UPDATE piani_finanziari SET avviso_id = ... WHERE avviso IS NOT NULL`

---

## Bug #3 — Credenziali hardcoded in startup

**Gravità**: 🔴 CRITICA  
**File**: `backend/main.py` righe ~544–565  
**Problema**:
```python
# main.py — HARDCODED
admin_password = "admin123"  # o simile
operatore_password = "operatore123"
```
I commenti nel codice stesso avvertono "CAMBIARE IN PRODUZIONE!" ma le password sono nel codice, non in variabili d'ambiente.

**Impatto**: in qualsiasi deploy dove le env var non vengono configurate, il sistema è accessibile con credenziali note.

**Fix**:
```python
import secrets
import os

admin_password = os.getenv(
    "ADMIN_DEFAULT_PASSWORD",
    secrets.token_urlsafe(16)  # random se non configurato
)
if not os.getenv("ADMIN_DEFAULT_PASSWORD"):
    logger.warning(
        f"ADMIN_DEFAULT_PASSWORD non configurato. "
        f"Password generata automaticamente — vedere log."
    )
    logger.info(f"Admin password temporanea: {admin_password}")
```

---

## Bug #4 — ensure_runtime_schema_updates() bypassa Alembic

**Gravità**: 🔴 CRITICA  
**File**: `backend/main.py` righe 94–251  
**Problema**: 250+ righe di `ALTER TABLE` raw SQL vengono eseguiti a ogni avvio dell'applicazione:
```python
async def ensure_runtime_schema_updates():
    """Aggiorna schema DB a runtime bypassando Alembic"""
    async with engine.begin() as conn:
        await conn.execute(text("ALTER TABLE collaborators ADD COLUMN IF NOT EXISTS ..."))
        # ... ~15 ALTER TABLE simili
```
Queste colonne non sono nelle migrazioni Alembic. Se qualcuno esegue `alembic upgrade head` su un DB vuoto, alcune colonne potrebbero essere mancanti o essere aggiunte due volte.

**Impatto**: schema DB non riproducibile; impossibile fare rollback; stato Alembic incoerente; deploy su nuovo ambiente può fallire.

**Fix** (effort L):
1. Per ogni `ALTER TABLE` in `ensure_runtime_schema_updates()`, creare la migrazione Alembic corrispondente
2. Testare la catena completa su un DB vuoto
3. Rimuovere la funzione `ensure_runtime_schema_updates()`
4. Aggiungere `alembic upgrade head` come step obbligatorio nello startup script

---

## Bug #5 — Cache in-process inutile con multi-worker

**Gravità**: 🟡 IMPORTANTE  
**File**: `backend/crud.py` righe 37–84  
**Problema**:
```python
class QueryCache:
    def __init__(self):
        self._cache = {}  # dict Python in-memory
    
    def get(self, key): ...
    def set(self, key, value): ...
    def invalidate(self, key): ...
```
Con uvicorn/gunicorn multi-worker ogni processo ha la propria `QueryCache` in-memory. Quando un worker modifica un collaboratore e chiama `invalidate_collaborator_cache()`, gli altri worker hanno ancora il dato stale.

**Impatto**: dati obsoleti visibili agli utenti in ambiente multi-worker; difficile da diagnosticare.

**Fix opzione A** (rimuovere cache):
```python
# Rimuovere QueryCache e le funzioni get_collaborator_cached/invalidate_collaborator_cache
# SQLAlchemy connection pool è già efficiente
```

**Fix opzione B** (usare Redis già presente):
```python
# redis_cache.py è già nel progetto — usarlo invece della dict in-memory
from redis_cache import cache_client
```

---

## Bug #6 — limit=10000 hardcoded nel report timesheet

**Gravità**: 🟡 IMPORTANTE  
**File**: `backend/routers/reporting.py` ~riga 63  
**Problema**:
```python
attendances = crud.get_attendances(db, skip=0, limit=10000, ...)
```
Con dataset grandi (azienda con molti collaboratori su più anni) questo carica decine di migliaia di righe in memoria.

**Impatto**: timeout, OOM (Out of Memory), lentezza del backend.

**Fix**:
```python
# Opzione A: streaming con generator
# Opzione B: paginazione nel report
# Opzione C: export asincrono con task background e download

# Soluzione rapida (parziale):
attendances = crud.get_attendances(db, skip=skip, limit=min(limit, 1000), ...)
```

---

## Bug #7 — Nessun endpoint DELETE per Ordine

**Gravità**: 🟡 IMPORTANTE  
**File**: `backend/routers/ordini.py`  
**Problema**: il router Ordini espone CRUD ma manca `DELETE /{id}`. Un ordine creato per errore non può essere annullato/eliminato via API.

**Impatto**: impossibile pulire ordini errati senza accesso diretto al DB.

**Fix**:
```python
# Da aggiungere in routers/ordini.py
@router.delete("/{ordine_id}", status_code=204)
async def delete_ordine(
    ordine_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    ordine = await crud.get_ordine(db, ordine_id)
    if not ordine:
        raise HTTPException(404, "Ordine non trovato")
    # Soft delete: cambia stato invece di eliminare fisicamente
    await crud.update_ordine(db, ordine_id, {"stato": "annullato"})
    return None
```

---

## Bug #8 — CORS allow_origins=["*"] in produzione

**Gravità**: 🟡 IMPORTANTE  
**File**: `backend/main.py` righe ~336–342  
**Problema**:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # qualsiasi origine
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Impatto**: in produzione qualsiasi sito web può fare richieste all'API. Con `allow_credentials=False` le cookie non vengono inviate, ma se in futuro si passa ad auth via cookie, questo diventa una falla di sicurezza.

**Fix**:
```python
allowed_origins = os.getenv(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)
```

---

## Bug #9 — Catena migrazioni Alembic potenzialmente spezzata

**Gravità**: 🔴 CRITICA (da verificare)  
**File**: `backend/alembic/versions/` — 5 file con nome hash  
**Problema**: i file hash-named (`528d59380940_...`, `a10d08b5e238_...`, ecc.) potrebbero avere `down_revision` non collegato alla catena sequenziale numerata. Se il loro `down_revision` è `None` o punta a un hash non riconosciuto, sono rami orfani.

**Verifica**:
```bash
docker compose exec backend alembic history --verbose
docker compose exec backend alembic heads  
# Se output > 1 riga → catena spezzata
```

**Fix** (se catena è spezzata):
```python
# Editare ogni file hash-named per collegarlo correttamente:
# Es. 528d59380940_add_piani_finanziari.py
down_revision = '029_ultimo_file_numerato'  # correggere questo
branch_labels = None
depends_on = None
```

---

## Bug #10 — progress_percentage non aggiornato automaticamente

**Gravità**: 🟡 IMPORTANTE  
**File**: `backend/crud.py` + `backend/models.py`  
**Problema**: il campo `Project.progress_percentage` e `Assignment.ore_completate` sono denormalizzati ma non vengono aggiornati automaticamente quando si crea/elimina una presenza.

**Impatto**: il dashboard mostra percentuali di avanzamento obsolete.

**Fix**:
```python
# In crud.create_attendance(), dopo il commit, aggiornare:
async def update_project_progress(db, project_id):
    total = await db.scalar(
        select(func.sum(Attendance.ore_lavorate))
        .where(Attendance.project_id == project_id)
        .where(Attendance.stato != 'rifiutata')
    )
    await db.execute(
        update(Project)
        .where(Project.id == project_id)
        .values(
            ore_completate=total or 0,
            progress_percentage=min(100, (total or 0) / Project.ore_totali * 100)
        )
    )
```

---

## RIEPILOGO

| Bug | Gravità | Effort | File principale |
|---|---|---|---|
| #1 FK errata template_piano_finanziario_id | 🔴 Critico | M | models.py |
| #2 Doppio UNIQUE constraint PianoFinanziario | 🔴 Critico | M | models.py + main.py |
| #3 Credenziali hardcoded | 🔴 Critico | S | main.py |
| #4 ensure_runtime_schema_updates() | 🔴 Critico | L | main.py |
| #5 Cache in-process multi-worker | 🟡 Importante | M | crud.py |
| #6 limit=10000 report timesheet | 🟡 Importante | S | routers/reporting.py |
| #7 Nessun DELETE per Ordine | 🟡 Importante | S | routers/ordini.py |
| #8 CORS allow_origins=["*"] | 🟡 Importante | S | main.py |
| #9 Catena Alembic potenzialmente spezzata | 🔴 Critico | M | alembic/versions/ |
| #10 progress_percentage non aggiornato | 🟡 Importante | M | crud.py |
