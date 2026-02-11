# Prevenzione Nomi File "null"

## Problema

File o cartelle con nome "null", "None" o "undefined" causano problemi di sincronizzazione con OneDrive e altri servizi cloud storage.

**Sintomi:**
- Errori di sincronizzazione OneDrive
- File che non si sincronizzano correttamente
- Messaggi di errore dal cloud storage

## Causa

Quando variabili JavaScript `null` o `undefined` (o Python `None`) vengono convertite in stringhe per creare nomi di file, producono letteralmente "null", "None" o "undefined".

Esempio problematico:
```javascript
// JavaScript - ERRATO
const filename = data.filename;  // Se è null
link.download = filename;  // Crea un file chiamato "null"
```

```python
# Python - ERRATO
filename = data.get('filename')  # Se è None
path = f"uploads/{filename}"  # Crea path "uploads/None"
```

## Soluzioni Implementate

### Frontend (JavaScript/React)

**1. Utility Functions Centralizzate (fileNameValidator.js)**

È disponibile un modulo completo per la validazione e sanitizzazione dei nomi file:

```javascript
import {
  isValidFileName,
  sanitizeFileName,
  createDownloadFileName,
  extractSafeName
} from './utils/fileNameValidator';

// Verifica validità nome
if (isValidFileName(filename)) {
  // OK, usa il filename
}

// Sanitizza nome con fallback
const safeName = sanitizeFileName(filename, 'documento.pdf');

// Crea nome per download
const downloadName = createDownloadFileName({
  filename: data.filename,
  fallbackName: 'documento',
  extension: 'pdf',
  id: collaboratorId
});

// Estrai nome da oggetto
const name = extractSafeName(
  collaborator,
  ['first_name', 'last_name'],
  'collaboratore'
);
```

**2. Validazione nei download (CollaboratorManager.js)**

```javascript
// Sanitizza filename prima del download
const safeFilename = (filename && filename !== 'null' && filename !== 'undefined')
  ? filename
  : `documento_${id}_${Date.now()}.pdf`;
```

**Best Practice Frontend:**
- **SEMPRE usare le utility functions** invece di validazioni manuali
- Verificare che il valore non sia `null`, `undefined` o stringa "null"
- Fornire un nome di fallback significativo
- Usare template literals con valori garantiti
- Testare con i casi edge (vedi fileNameValidator.test.js)

### Backend (Python)

**1. Sanitizzazione filename (file_upload.py)**

```python
def sanitize_filename(filename: str) -> str:
    """Previene nomi file problematici"""
    # Gestisci casi None/null/undefined
    if not filename or filename in ('null', 'None', 'undefined', 'NULL', 'NONE', 'UNDEFINED'):
        return "file_unnamed"
    # ... resto della sanitizzazione
```

**2. Validazione ID (file_upload.py)**

```python
# Valida collaborator_id prima di usarlo nei path
if not collaborator_id or str(collaborator_id) in ('null', 'None', 'undefined'):
    raise HTTPException(status_code=400, detail="ID collaboratore non valido")
```

**3. Utility function generale**

```python
from backend.file_upload import validate_name_not_null

# Usa ovunque serva validare un nome
safe_name = validate_name_not_null(user_input, default="unnamed")
```

**4. Contract Generator (contract_generator.py)**

```python
# Valida nomi prima di creare filename contratti
invalid_values = {None, 'null', 'None', 'undefined', 'NULL', 'NONE', 'UNDEFINED', ''}
collaborator_name = name if name not in invalid_values else 'collaboratore'
```

## Regole da Seguire

### ✅ DO (Fare)

1. **Sempre validare variabili prima di usarle in nomi file/cartelle**
   ```javascript
   const filename = data?.filename || `default_${Date.now()}.pdf`;
   ```

2. **Usare optional chaining in JavaScript**
   ```javascript
   const name = user?.lastName || 'unnamed';
   ```

3. **Controllare valori None in Python**
   ```python
   name = data.get('name') or 'default'
   ```

4. **Usare funzioni di validazione**
   ```python
   from backend.file_upload import validate_name_not_null
   safe_name = validate_name_not_null(user_input)
   ```

5. **Logging per debugging**
   ```python
   logger.warning(f"Nome invalido rilevato: '{name}', uso default")
   ```

### ❌ DON'T (Non fare)

1. **Non usare direttamente variabili che potrebbero essere null**
   ```javascript
   // ERRATO
   link.download = data.filename;
   ```

2. **Non concatenare senza controlli**
   ```python
   # ERRATO
   path = f"uploads/{user_id}/{filename}"
   ```

3. **Non assumere che i dati siano sempre validi**
   ```javascript
   // ERRATO
   const name = `${user.lastName}_${user.firstName}`;
   ```

## Checklist Pre-Commit

Prima di committare codice che gestisce file/cartelle, verificare:

- [ ] Tutte le variabili usate in nomi file sono validate?
- [ ] Esiste un fallback se il valore è null/undefined?
- [ ] Usate funzioni di sanitizzazione (`sanitize_filename`, `validate_name_not_null`)?
- [ ] Testato con dati mancanti/null?
- [ ] Aggiunto logging per valori invalidi?

## Testing

Testare sempre con questi casi:
```javascript
// Frontend
const testCases = [null, undefined, '', 'null', 'undefined', 'None'];
testCases.forEach(value => {
  const result = sanitizeFilename(value);
  console.assert(!result.includes('null'), `Failed for ${value}`);
});
```

```python
# Backend
test_cases = [None, '', 'null', 'None', 'undefined']
for value in test_cases:
    result = validate_name_not_null(value)
    assert result != 'null' and result != 'None'
```

## Risorse

### Backend
- **backend/file_upload.py**: Funzioni di validazione e sanitizzazione
- **backend/contract_generator.py**: Validazione nomi contratti
- **scripts/check_null_filenames.py**: Script per scansionare e rinominare file problematici

### Frontend
- **frontend/src/utils/fileNameValidator.js**: Utility functions per validazione nomi file
- **frontend/src/utils/fileNameValidator.test.js**: Test completi per la validazione
- **frontend/src/components/CollaboratorManager.js**: Esempi di validazione nei download

### Strumenti
- **Script di verifica**: `python scripts/check_null_filenames.py`
- **Script di fix automatico**: `python scripts/check_null_filenames.py --fix`
- **Configurazione ESLint**: `.eslintrc-null-filenames.json`

## Contatti

Per domande o problemi relativi a questa best practice, contattare il team di sviluppo.

---

**Data ultima modifica:** 2025-10-06
**Versione:** 1.1
**Modifiche:** Aggiunte utility functions centralizzate nel frontend (fileNameValidator.js) e test completi
