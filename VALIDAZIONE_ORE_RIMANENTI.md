# VALIDAZIONE ORE RIMANENTI - IMPEDIRE ORE COMPLETATE > ORE ASSEGNATE

## Data: 2025-10-04
## Implementato da: Team Programmatori Fullstack

---

## PROBLEMA

Il sistema permetteva di inserire ore di presenza che superavano le ore rimanenti dell'assegnazione, causando:
- Ore completate > Ore assegnate
- Impossibilità di tracciare correttamente il progresso
- Dati inconsistenti nel riepilogo ore

---

## SOLUZIONE IMPLEMENTATA

### 1. FRONTEND - Validazione Preventiva (`AttendanceModal.js`)

**File**: `frontend/src/components/AttendanceModal.js`

#### A) Visualizzazione chiara ore nella dropdown mansione (Righe 505-516)

**PRIMA**:
```javascript
{assignment.role} - {assignment.assigned_hours}h (Rimanenti: {ore_rimanenti}h)
```

**DOPO**:
```javascript
{assignment.role} - Assegnate: {oreAssegnate}h | Rimanenti: {oreRimanenti}h
```

Esempio visivo:
```
Docente - Assegnate: 20h | Rimanenti: 15h
Tutor - Assegnate: 10h | Rimanenti: 10h
Coordinatore - Assegnate: 5h | Rimanenti: 2h
```

#### B) Validazione ore inserite (Righe 272-290)

```javascript
// Validazione ore rimanenti dell'assegnazione
if (formData.assignment_id && formData.hours) {
  const selectedAssignment = filteredAssignments.find(
    a => a.id === parseInt(formData.assignment_id)
  );

  if (selectedAssignment) {
    const oreCompletate = selectedAssignment.completed_hours || 0;
    const oreAssegnate = selectedAssignment.assigned_hours;

    // Se stiamo modificando, sottrai le ore già registrate
    const oreGiaRegistrate = attendance ? attendance.hours : 0;
    const oreRimanenti = oreAssegnate - oreCompletate + oreGiaRegistrate;

    if (formData.hours > oreRimanenti) {
      newErrors.hours = `Le ore inserite (${formData.hours}h) superano le ore rimanenti (${oreRimanenti}h) per questa mansione`;
    }
  }
}
```

**Logica**:
1. Trova l'assegnazione selezionata
2. Calcola ore rimanenti = ore assegnate - ore completate
3. Se è una modifica, aggiungi le ore già registrate (così puoi modificare senza errori)
4. Se le ore inserite superano le rimanenti → ERRORE

**Messaggio di errore**:
```
⚠️ Le ore inserite (8h) superano le ore rimanenti (5h) per questa mansione
```

---

### 2. BACKEND - Validazione Server-Side (`crud.py`)

#### A) Validazione in `create_attendance()` (Righe 345-360)

```python
# Validazione ore rimanenti dell'assegnazione
if attendance_data.get('assignment_id'):
    assignment = db.query(models.Assignment).filter(
        models.Assignment.id == attendance_data['assignment_id']
    ).first()

    if assignment:
        ore_completate = assignment.completed_hours or 0
        ore_assegnate = assignment.assigned_hours
        ore_rimanenti = ore_assegnate - ore_completate

        if attendance_data['hours'] > ore_rimanenti:
            raise ValueError(
                f"Le ore inserite ({attendance_data['hours']}h) superano le ore rimanenti "
                f"({ore_rimanenti}h) per questa mansione"
            )
```

#### B) Validazione in `update_attendance()` (Righe 406-429)

```python
# Validazione ore rimanenti se cambiano le ore o l'assegnazione
new_assignment_id = update_data.get('assignment_id', db_attendance.assignment_id)
new_hours = update_data.get('hours', db_attendance.hours)

if new_assignment_id:
    assignment = db.query(models.Assignment).filter(
        models.Assignment.id == new_assignment_id
    ).first()

    if assignment:
        ore_completate = assignment.completed_hours or 0
        ore_assegnate = assignment.assigned_hours

        # Se stiamo modificando la stessa assegnazione, sottrai le ore vecchie
        if new_assignment_id == old_assignment_id:
            ore_disponibili = ore_assegnate - ore_completate + old_hours
        else:
            ore_disponibili = ore_assegnate - ore_completate

        if new_hours > ore_disponibili:
            raise ValueError(
                f"Le ore inserite ({new_hours}h) superano le ore disponibili "
                f"({ore_disponibili}h) per questa mansione"
            )
```

**Logica per modifica**:
1. Se modifichi la stessa assegnazione → aggiungi le ore vecchie (per permettere modifiche)
2. Se cambi assegnazione → calcola ore disponibili nella nuova assegnazione
3. Valida che le nuove ore non superino le disponibili

---

## SCENARI DI VALIDAZIONE

### Scenario 1: Nuova presenza - OK ✅

```
Assegnazione: Docente - 20h assegnate, 10h completate → 10h rimanenti
Inserimento: 5 ore
Risultato: ✅ OK (5h <= 10h)
Nuovo stato: 20h assegnate, 15h completate, 5h rimanenti
```

### Scenario 2: Nuova presenza - ERRORE ❌

```
Assegnazione: Docente - 20h assegnate, 18h completate → 2h rimanenti
Inserimento: 5 ore
Risultato: ❌ ERRORE "Le ore inserite (5h) superano le ore rimanenti (2h)"
```

### Scenario 3: Modifica presenza stessa assegnazione - OK ✅

```
Presenza esistente: 5 ore su Docente (20h assegnate, 15h completate)
Modifica a: 7 ore
Calcolo: 20 - 15 + 5 (vecchie) = 10h disponibili
Risultato: ✅ OK (7h <= 10h)
Nuovo stato: 20h assegnate, 17h completate, 3h rimanenti
```

### Scenario 4: Modifica presenza cambiando assegnazione - VALIDAZIONE ✅

```
Presenza esistente: 5 ore su Docente
Cambio a: Tutor (10h assegnate, 8h completate → 2h rimanenti)
Ore nuove: 5 ore
Risultato: ❌ ERRORE "Le ore inserite (5h) superano le ore disponibili (2h)"
```

---

## COME TESTARE

### Test 1: Verifica visualizzazione ore

1. Apri browser su `http://localhost:3000`
2. Vai su **Calendario** → Clicca uno slot
3. Seleziona **Collaboratore** e **Progetto**
4. **VERIFICA** dropdown mansione mostra:
   ```
   Docente - Assegnate: 20h | Rimanenti: 15h
   ```

### Test 2: Test validazione ore eccessive

1. Seleziona una mansione con poche ore rimanenti (es. 2h)
2. Inserisci 9:00 - 18:00 (9 ore)
3. **VERIFICA**: Appare errore rosso:
   ```
   ⚠️ Le ore inserite (9h) superano le ore rimanenti (2h) per questa mansione
   ```
4. Tentativo salvataggio → BLOCCATO

### Test 3: Test modifica presenza

1. Apri presenza esistente da 5h
2. Modifica ore da 5h a 7h
3. Se ci sono almeno 7h disponibili (considerando le 5h già registrate) → ✅ OK
4. Altrimenti → ❌ ERRORE

### Test 4: Test validazione backend (API diretta)

```bash
# Crea presenza con ore eccessive (deve fallire)
curl -X POST http://localhost:8000/attendances/ \
  -H "Content-Type: application/json" \
  -d '{
    "collaborator_id": 2,
    "project_id": 1,
    "assignment_id": 1,
    "date": "2025-10-05T00:00:00",
    "start_time": "2025-10-05T09:00:00",
    "end_time": "2025-10-05T20:00:00",
    "hours": 100
  }'

# Risposta attesa (se ore rimanenti < 100):
{
  "error": "Le ore inserite (100.0h) superano le ore rimanenti (XXh) per questa mansione"
}
```

---

## FILE MODIFICATI

| File | Righe | Modifiche |
|------|-------|-----------|
| `frontend/src/components/AttendanceModal.js` | 272-290 | Validazione frontend ore rimanenti |
| `frontend/src/components/AttendanceModal.js` | 505-516 | Visualizzazione chiara ore in dropdown |
| `backend/crud.py` | 345-360 | Validazione create_attendance |
| `backend/crud.py` | 406-429 | Validazione update_attendance |

---

## MESSAGGI DI ERRORE

### Frontend
```
Le ore inserite (Xh) superano le ore rimanenti (Yh) per questa mansione
```

### Backend
```python
ValueError: "Le ore inserite (Xh) superano le ore rimanenti (Yh) per questa mansione"
ValueError: "Le ore inserite (Xh) superano le ore disponibili (Yh) per questa mansione"
```

---

## BENEFICI

✅ **Impossibile** inserire ore che superano quelle assegnate
✅ **Validazione doppia**: frontend (UX immediata) + backend (sicurezza)
✅ **Messaggi chiari** che indicano esattamente il problema
✅ **Calcolo corretto** durante le modifiche (considera ore già registrate)
✅ **Dati consistenti** nel database
✅ **Tracciamento preciso** del progresso

---

## STATO SERVIZI

- **Backend**: http://localhost:8000 ✅ ONLINE
- **Frontend**: http://localhost:3000 ✅ COMPILATO

Per verificare:
```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

---

**Data implementazione**: 2025-10-04
**Versione**: 3.2
**Team**: Programmatori Fullstack
