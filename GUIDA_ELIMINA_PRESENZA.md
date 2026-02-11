# GUIDA: COME ELIMINARE UNA PRESENZA DAL CALENDARIO

## ✅ LA FUNZIONALITÀ ESISTE GIÀ!

Il pulsante per **eliminare** le presenze è **già implementato** nel sistema.

---

## 📍 DOVE SI TROVA IL PULSANTE ELIMINA

Il pulsante "Elimina" appare **SOLO quando modifichi una presenza esistente**, non quando ne crei una nuova.

### Posizione nel modal:
- **In basso a sinistra** nel footer del modal
- **Colore rosso** (#dc3545)
- Testo: **"Elimina"**

---

## 🔧 COME ELIMINARE UNA PRESENZA - PASSO PASSO

### STEP 1: Apri il Calendario
1. Vai su http://localhost:3000
2. Clicca su **"📅 Calendario"** nel menu

### STEP 2: Clicca sulla Presenza da Eliminare
1. **IMPORTANTE**: Non cliccare su uno slot vuoto!
2. Clicca **direttamente sulla presenza esistente** (il blocco colorato nel calendario)
3. Si aprirà il modal con i dati della presenza

### STEP 3: Clicca sul Pulsante Elimina
1. Nel modal aperto, guarda **in basso a sinistra**
2. Vedrai il pulsante rosso **"Elimina"**
3. Clicca su "Elimina"

### STEP 4: Conferma Eliminazione
1. Appare una **conferma gialla** con il messaggio:
   ```
   Sei sicuro di voler eliminare questa presenza?
   ```
2. Due opzioni:
   - **"Sì, Elimina"** → Conferma ed elimina
   - **"Annulla"** → Annulla l'operazione

### STEP 5: Presenza Eliminata
- La presenza viene eliminata dal database
- Il calendario si aggiorna automaticamente
- Le **ore completate** dell'assegnazione vengono ricalcolate automaticamente

---

## 🎨 ASPETTO VISIVO

### Pulsante Elimina (normale):
```
[ Elimina ]  [ Annulla ]  [ Salva/Aggiorna ]
   ↑ rosso      grigio      blu/verde
```

### Conferma Eliminazione (appare al posto dei pulsanti):
```
┌─────────────────────────────────────────────────────────┐
│ ⚠️ Sei sicuro di voler eliminare questa presenza?      │
│                                                         │
│         [ Sì, Elimina ]  [ Annulla ]                   │
│           rosso scuro      grigio                      │
└─────────────────────────────────────────────────────────┘
```

---

## ⚙️ CODICE IMPLEMENTATO

### Frontend (`AttendanceModal.js`)

**Pulsante Elimina** (righe 628-637):
```javascript
{attendance && !showDeleteConfirm && (
  <button
    className="delete-button"
    onClick={() => setShowDeleteConfirm(true)}
    disabled={loading}
  >
    Elimina
  </button>
)}
```

**Conferma Eliminazione** (righe 640-657):
```javascript
{showDeleteConfirm && (
  <div className="delete-confirm">
    <span>Sei sicuro di voler eliminare questa presenza?</span>
    <button
      className="confirm-delete-button"
      onClick={handleDelete}
      disabled={loading}
    >
      Sì, Elimina
    </button>
    <button
      className="cancel-delete-button"
      onClick={() => setShowDeleteConfirm(false)}
      disabled={loading}
    >
      Annulla
    </button>
  </div>
)}
```

**Funzione handleDelete** (righe 368-383):
```javascript
const handleDelete = async () => {
  if (!attendance) return;

  setLoading(true);

  try {
    await deleteAttendance(attendance.id);
    onDelete();  // Ricarica i dati
  } catch (error) {
    console.error('Errore nell\'eliminazione:', error);
    setErrors({ general: 'Errore nell\'eliminazione. Riprova.' });
  } finally {
    setLoading(false);
    setShowDeleteConfirm(false);
  }
};
```

### Backend (`crud.py`)

**Funzione delete_attendance** (righe 419-430):
```python
def delete_attendance(db: Session, attendance_id: int):
    db_attendance = db.query(models.Attendance).filter(
        models.Attendance.id == attendance_id
    ).first()

    if db_attendance:
        assignment_id = db_attendance.assignment_id
        db.delete(db_attendance)
        db.commit()

        # Aggiorna statistiche dell'assegnazione dopo la cancellazione
        if assignment_id:
            update_assignment_progress(db, assignment_id)

    return db_attendance
```

**Cosa fa**:
1. Trova la presenza da eliminare
2. Salva l'ID dell'assegnazione collegata
3. Elimina la presenza dal database
4. **Aggiorna automaticamente** le ore completate dell'assegnazione

---

## 🧪 TEST DI VERIFICA

### Test 1: Visualizzare il Pulsante Elimina

1. Apri http://localhost:3000
2. Vai su **Calendario**
3. Clicca su una **presenza esistente** (blocco colorato)
4. **VERIFICA**: In basso a sinistra vedi il pulsante rosso "Elimina"

### Test 2: Eliminare una Presenza

1. Clicca su una presenza con 5 ore (es. Docente con 20h assegnate, 15h completate)
2. Clicca su **"Elimina"**
3. **VERIFICA**: Appare conferma gialla
4. Clicca su **"Sì, Elimina"**
5. **VERIFICA**: Presenza eliminata, calendario aggiornato
6. Riapri l'assegnazione Docente
7. **VERIFICA**: Ora mostra 10h completate (15 - 5 = 10) e 10h rimanenti

### Test 3: Annullare Eliminazione

1. Clicca su una presenza
2. Clicca su **"Elimina"**
3. Clicca su **"Annulla"**
4. **VERIFICA**: Conferma scompare, pulsanti normali tornano visibili

---

## ❓ DOMANDE FREQUENTI

### Q: "Non vedo il pulsante Elimina!"

**A**: Il pulsante appare SOLO quando:
- Apri una **presenza esistente** (cliccando sul blocco colorato nel calendario)
- NON quando crei una nuova presenza (cliccando su uno slot vuoto)

### Q: "Come faccio a sapere se una presenza è esistente?"

**A**: Le presenze esistenti sono i **blocchi colorati** nel calendario con:
- Nome del collaboratore
- Nome del progetto
- Orario

### Q: "Cosa succede alle ore completate quando elimino?"

**A**: Le ore vengono **automaticamente ricalcolate**:
- Se elimini una presenza di 5h da un'assegnazione con 15h completate
- Le ore completate diventano 10h
- Le ore rimanenti aumentano di 5h

### Q: "Posso annullare dopo aver cliccato Elimina?"

**A**: **SÌ!** Hai due chance:
1. Prima conferma: Clicca "Annulla" invece di "Sì, Elimina"
2. Il modal non si chiude finché non confermi

### Q: "Il pulsante è disabilitato (grigio)"

**A**: Il pulsante si disabilita durante il caricamento:
- Mentre elimina la presenza
- Durante l'aggiornamento del calendario
- Aspetta qualche secondo

---

## 🎯 RIASSUNTO VELOCE

```
1. Vai su CALENDARIO
2. CLICCA sulla presenza (blocco colorato)
3. Clicca ELIMINA (rosso, in basso a sinistra)
4. Conferma SÌ, ELIMINA
5. ✅ Presenza eliminata!
```

---

## 🔗 FILE COINVOLTI

| File | Cosa fa |
|------|---------|
| `AttendanceModal.js` | Mostra pulsante Elimina e gestisce conferma |
| `AttendanceModal.css` | Stili del pulsante rosso e conferma gialla |
| `crud.py` (delete_attendance) | Elimina presenza e aggiorna ore |
| `api.js` (deleteAttendance) | Chiama API DELETE /attendances/{id} |

---

## 📊 FLUSSO ELIMINAZIONE

```
┌─────────────────────────────────────────────────────────────┐
│ 1. USER: Clicca su presenza esistente nel calendario       │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. FRONTEND: Apre modal con dati presenza                  │
│    - Mostra pulsante "Elimina" (rosso, in basso a sx)      │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. USER: Clicca su "Elimina"                               │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. FRONTEND: Mostra conferma gialla                        │
│    "Sei sicuro di voler eliminare questa presenza?"        │
│    [Sì, Elimina] [Annulla]                                 │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. USER: Clicca "Sì, Elimina"                              │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. FRONTEND: Chiama deleteAttendance(attendance.id)        │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 7. BACKEND: DELETE /attendances/{id}                       │
│    - Elimina presenza dal DB                               │
│    - Aggiorna ore completate dell'assegnazione             │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ 8. FRONTEND: Chiude modal e ricarica calendario            │
│    ✅ Presenza eliminata!                                   │
└─────────────────────────────────────────────────────────────┘
```

---

**Data**: 2025-10-04
**Versione**: 3.2
**Sistema**: Gestionale Collaboratori - Calendario Presenze
