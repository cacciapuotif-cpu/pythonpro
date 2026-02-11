# MODIFICHE IMPLEMENTATE - MANSIONI E ORE RIMANENTI

## Data: 2025-10-04
## Team: Programmatori Fullstack

---

## PROBLEMA RISCONTRATO

Nel sistema precedente:
1. **Calendario Presenze**: NON richiedeva la selezione della mansione → le ore non venivano associate a una specifica assegnazione
2. **Assegnazione Progetto**: NON mostrava le ore rimanenti → impossibile sapere quanto lavoro manca
3. **Calcolo ore completate**: Basato su collaboratore+progetto invece che su assignment_id specifico → se un collaboratore aveva più mansioni sullo stesso progetto, TUTTE le ore venivano sommate in TUTTE le mansioni

---

## MODIFICHE IMPLEMENTATE

### 1. FRONTEND - AttendanceModal.js (Calendario Presenze)

**File**: `frontend/src/components/AttendanceModal.js`

**Righe modificate**: 468-502

**Cosa è stato fatto**:
- ✅ Campo "Mansione" ora è **OBBLIGATORIO** (asterisco rosso)
- ✅ Dropdown mansione mostra: `{ruolo} - {ore_assegnate}h (Rimanenti: {ore_rimanenti}h)`
- ✅ Validazione che impedisce salvataggio senza mansione selezionata
- ✅ Messaggio di aiuto dinamico:
  - Se non hai selezionato collaboratore/progetto: "Seleziona prima collaboratore e progetto..."
  - Se non ci sono mansioni: "⚠️ Nessuna mansione assegnata..."
  - Altrimenti: "Seleziona la mansione a cui associare queste ore"

**Codice chiave**:
```javascript
<label htmlFor="assignment_id">
  Mansione <span className="required">*</span>
</label>
<select
  id="assignment_id"
  name="assignment_id"
  value={formData.assignment_id}
  disabled={!formData.collaborator_id || !formData.project_id}
>
  {filteredAssignments.map(assignment => (
    <option key={assignment.id} value={assignment.id}>
      {assignment.role} - {assignment.assigned_hours}h
      (Rimanenti: {Math.max(0, assignment.assigned_hours - (assignment.completed_hours || 0))}h)
    </option>
  ))}
</select>
```

---

### 2. FRONTEND - AssignmentModal.js (Assegnazione Progetto)

**File**: `frontend/src/components/AssignmentModal.js`

**Righe**: 349-382

**Cosa è già presente** (verificato):
- ✅ Sezione "Riepilogo Ore" che mostra:
  - Ore Assegnate
  - Ore Completate
  - **Ore Rimanenti** (calcolate dinamicamente)
  - Progresso %
  - Barra di progresso visiva

**Nota**: Questa sezione appare SOLO quando **modifichi** un'assegnazione esistente, NON durante la creazione.

---

### 3. BACKEND - crud.py (Logica calcolo ore)

**File**: `backend/crud.py`

**Funzione modificata**: `update_assignment_progress()` (righe 360-379)

**PRIMA** (ERRATO):
```python
def update_assignment_progress(db: Session, collaborator_id: int, project_id: int):
    # Somma TUTTE le ore di un collaboratore su un progetto
    total_hours = db.query(func.sum(models.Attendance.hours)).filter(
        models.Attendance.collaborator_id == collaborator_id,
        models.Attendance.project_id == project_id
    ).scalar() or 0
```

**DOPO** (CORRETTO):
```python
def update_assignment_progress(db: Session, assignment_id: int):
    # Somma SOLO le ore collegate a questa specifica assegnazione
    total_hours = db.query(func.sum(models.Attendance.hours)).filter(
        models.Attendance.assignment_id == assignment_id
    ).scalar() or 0
```

**Modifiche alle funzioni CRUD**:
- ✅ `create_attendance()`: Chiama `update_assignment_progress(assignment_id)` dopo inserimento
- ✅ `update_attendance()`: Aggiorna sia la vecchia che la nuova assegnazione se cambiata
- ✅ `delete_attendance()`: Aggiorna l'assegnazione dopo eliminazione

---

### 4. BACKEND - schemas.py (Schema API)

**File**: `backend/schemas.py`

**Righe modificate**: 138-147

**Campi aggiunti al response model**:
```python
class Assignment(AssignmentBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_hours: float  # Ore completate (calcolate)
    progress_percentage: float  # Percentuale completamento
    is_active: bool  # Assegnazione attiva
```

---

### 5. BACKEND - models.py (Modello Database)

**File**: `backend/models.py`

**Verifica**: Il modello aveva già i campi necessari:
- ✅ `Attendance.assignment_id` (FK nullable verso Assignment)
- ✅ `Assignment.completed_hours` (Float, default 0.0)
- ✅ `Assignment.progress_percentage` (Float, default 0.0)
- ✅ `Assignment.is_active` (Boolean, default True)

---

## COME TESTARE LE MODIFICHE

### Test 1: Verificare campo Mansione obbligatorio

1. Apri browser su `http://localhost:3000`
2. Vai su **Calendario**
3. Clicca su uno slot per creare una presenza
4. Seleziona un collaboratore (es. Francesco Cacciapuoti)
5. Seleziona un progetto (es. Test)
6. **VERIFICA**: Dovresti vedere il campo "Mansione *" (con asterisco rosso)
7. **VERIFICA**: La dropdown mansione dovrebbe mostrare le mansioni disponibili con formato:
   - "Docente - 20h (Rimanenti: 20h)"
8. Prova a salvare SENZA selezionare la mansione
9. **VERIFICA**: Dovrebbe apparire errore "Seleziona una mansione"

### Test 2: Verificare ore rimanenti in Assegnazione Progetto

1. Vai su **Collaboratori**
2. Clicca su "Francesco Cacciapuoti"
3. Nella sezione "Progetti Assegnati", clicca su un'assegnazione esistente
4. **VERIFICA**: Dovresti vedere la sezione "📊 Riepilogo Ore" con:
   - Ore Assegnate: XXh
   - Ore Completate: XXh
   - **Ore Rimanenti: XXh**
   - Progresso: XX%
   - Barra di progresso

### Test 3: Verificare calcolo corretto ore

1. Crea un'assegnazione: Francesco → Progetto Test → Docente → 20 ore
2. Inserisci presenza: Francesco → Progetto Test → Mansione Docente → 5 ore
3. **VERIFICA API**:
   ```bash
   curl http://localhost:8000/assignments/{assignment_id}
   ```
   Dovrebbe mostrare `completed_hours: 5.0`
4. Riapri l'assegnazione dal frontend
5. **VERIFICA**: Ore Rimanenti dovrebbero essere 15h (20 - 5)

---

## PROBLEMI NOTI E SOLUZIONI

### Problema 1: "Non vedo il campo Mansione"

**Causa possibile**:
- Cache del browser
- Frontend non ricompilato

**Soluzione**:
1. Fai hard refresh del browser: `Ctrl + Shift + R` (Windows) o `Cmd + Shift + R` (Mac)
2. Oppure apri in modalità incognito
3. Verifica che il frontend sia compilato correttamente (vedi console)

### Problema 2: "Non vedo le ore rimanenti"

**Verifica**:
1. Le ore rimanenti appaiono SOLO quando **modifichi** un'assegnazione esistente
2. NON appaiono quando crei una nuova assegnazione
3. Devi prima selezionare collaboratore e progetto per vedere le mansioni

### Problema 3: "completed_hours è null"

**Causa**: Record creati prima delle modifiche

**Soluzione**:
```bash
cd backend
venv/Scripts/python.exe -c "from database import SessionLocal; from models import Assignment; db = SessionLocal(); db.query(Assignment).filter(Assignment.completed_hours == None).update({Assignment.completed_hours: 0.0}); db.query(Assignment).filter(Assignment.progress_percentage == None).update({Assignment.progress_percentage: 0.0}); db.commit(); print('Aggiornato')"
```

---

## FILE MODIFICATI - RIEPILOGO

| File | Righe | Cosa è stato modificato |
|------|-------|------------------------|
| `frontend/src/components/AttendanceModal.js` | 468-502, 226-240 | Campo mansione obbligatorio + validazione |
| `backend/crud.py` | 360-379, 345-355, 382-400, 402-413 | Calcolo ore per assignment_id specifico |
| `backend/schemas.py` | 138-147 | Aggiunto completed_hours, progress_percentage, is_active |
| `backend/crud.py` | 526-539 | Inizializzazione esplicita valori default |

---

## SERVIZI IN ESECUZIONE

Dopo le modifiche, assicurati che entrambi i servizi siano attivi:

1. **Backend**: `http://localhost:8000`
   ```bash
   cd backend
   venv/Scripts/python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

2. **Frontend**: `http://localhost:3000`
   ```bash
   cd frontend
   npm start
   ```

---

## CONTATTI E SUPPORTO

Per problemi o domande:
- Verifica i log del backend in `backend/backend.log`
- Verifica la console del browser (F12) per errori frontend
- Riavvia entrambi i servizi se necessario

---

**Data modifica**: 2025-10-04
**Versione**: 3.1
**Team**: Programmatori Fullstack
