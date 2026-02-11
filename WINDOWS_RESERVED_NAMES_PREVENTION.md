# Prevenzione Nomi Riservati Windows

## Problema

File o cartelle con nomi riservati Windows (come "nul", "con", "prn", "aux", "com1-9", "lpt1-9") causano **seri problemi** di sincronizzazione con OneDrive e altri servizi cloud storage.

### Sintomi
- ❌ Errori di sincronizzazione OneDrive
- ❌ File che non si sincronizzano correttamente
- ❌ Impossibilità di creare/modificare file
- ❌ Messaggi di errore dal cloud storage
- ❌ Cartelle che appaiono vuote

### Causa

Windows riserva alcuni nomi per dispositivi del sistema operativo. Questi nomi non possono essere usati come nomi di file o cartelle in Windows:

- **con** (console)
- **prn** (printer)
- **aux** (auxiliary)
- **nul** (null device)
- **com1** - **com9** (porte seriali)
- **lpt1** - **lpt9** (porte parallele)

Inoltre, anche "null", "None", "undefined" (da JavaScript/Python) causano problemi simili.

## Soluzioni Implementate

### 1. Script di Scansione e Rimozione

**Scansiona il progetto per trovare file problematici:**
```bash
python scripts/remove_windows_reserved_names.py
```

**Visualizza cosa verrebbe fatto (dry-run):**
```bash
python scripts/remove_windows_reserved_names.py --fix --dry-run
```

**Rimuove file con nomi riservati (PERMANENTE!):**
```bash
python scripts/remove_windows_reserved_names.py --fix
```

**Rinomina invece di rimuovere (più sicuro):**
```bash
python scripts/remove_windows_reserved_names.py --rename
```

### 2. Modulo di Validazione Python

**File:** `backend/windows_filename_validator.py`

Questo modulo fornisce funzioni complete per:
- Validare nomi file/cartelle
- Sanitizzare automaticamente nomi invalidi
- Generare nomi sicuri e univoci
- Gestire path completi

**Funzioni principali:**

```python
from backend.windows_filename_validator import (
    is_valid_filename,          # Verifica se un nome è valido
    sanitize_filename,          # Sanitizza un nome
    is_windows_reserved_name,   # Controlla nomi riservati
    generate_safe_filename,     # Genera nome sicuro univoco
    validate_and_fix_filename   # Valida e corregge
)

# Esempio 1: Validazione
if is_valid_filename("documento.pdf"):
    print("Nome valido!")

# Esempio 2: Sanitizzazione
safe_name = sanitize_filename("nul.txt", default="file_unnamed")
# Risultato: "file_unnamed.txt"

# Esempio 3: Generazione nome sicuro
safe_name = generate_safe_filename("report", "pdf", add_uuid=True)
# Risultato: "report_20250106_143022_a1b2c3d4.pdf"

# Esempio 4: Validazione e correzione automatica
try:
    filename = validate_and_fix_filename(
        user_input,
        default="documento.pdf",
        raise_on_invalid=True  # Solleva eccezione se invalido
    )
except ValueError as e:
    print(f"Nome invalido: {e}")
```

### 3. Protezione Integrata nei Moduli

**File Upload (`backend/file_upload.py`):**
- Tutti i file uploadati vengono automaticamente sanitizzati
- Protezione contro path traversal
- Validazione contro nomi riservati Windows

**Generazione Contratti (`backend/contract_generator.py`):**
- Nomi collaboratori e progetti sanitizzati
- Filename contratti validati automaticamente
- Fallback automatici se nomi invalidi

```python
# In file_upload.py
def sanitize_filename(filename: str) -> str:
    """
    Sanitizza nome file per sicurezza.

    Include:
    - Protezione contro "null", "None", "undefined"
    - Protezione contro nomi riservati Windows (nul, con, prn, aux, etc.)
    - Rimozione caratteri invalidi
    - Prevenzione path traversal
    """
    # Usa il validatore Windows completo
    sanitized = windows_sanitize_filename(
        filename,
        default="file_unnamed",
        add_timestamp=False
    )

    # Verifica finale
    if not is_valid_windows_filename(sanitized):
        return "file_unnamed"

    return sanitized
```

## Nomi Riservati Completi

### Nomi Dispositivi Windows
```python
WINDOWS_RESERVED_NAMES = {
    'con', 'prn', 'aux', 'nul',
    'com1', 'com2', 'com3', 'com4', 'com5', 'com6', 'com7', 'com8', 'com9',
    'lpt1', 'lpt2', 'lpt3', 'lpt4', 'lpt5', 'lpt6', 'lpt7', 'lpt8', 'lpt9'
}
```

### Nomi Problematici OneDrive
```python
ONEDRIVE_PROBLEMATIC_NAMES = {
    'null', 'none', 'undefined',
    'NULL', 'NONE', 'UNDEFINED',
    'None', 'Null'
}
```

### Caratteri Non Permessi
```python
# Windows non permette questi caratteri nei nomi file:
WINDOWS_INVALID_CHARS = '<>:"|?*/'
```

## Regole da Seguire

### ✅ FARE

1. **Usare sempre le funzioni di validazione:**
   ```python
   from backend.windows_filename_validator import sanitize_filename

   # Prima di creare qualsiasi file
   safe_filename = sanitize_filename(user_input)
   with open(safe_filename, 'w') as f:
       f.write(content)
   ```

2. **Validare input utente:**
   ```python
   if not is_valid_filename(user_filename):
       raise ValueError("Nome file invalido")
   ```

3. **Generare nomi sicuri per file temporanei:**
   ```python
   temp_file = generate_safe_filename("temp_upload", "pdf", add_uuid=True)
   ```

4. **Aggiungere logging:**
   ```python
   logger.warning(f"Nome file invalido '{filename}', uso default")
   ```

### ❌ NON FARE

1. **Non usare direttamente input utente per nomi file:**
   ```python
   # ERRATO - Non fare mai questo!
   with open(user_input, 'w') as f:
       f.write(content)

   # CORRETTO - Sanitizza prima
   safe_name = sanitize_filename(user_input)
   with open(safe_name, 'w') as f:
       f.write(content)
   ```

2. **Non concatenare senza controlli:**
   ```python
   # ERRATO
   filepath = f"uploads/{user_id}/{filename}"

   # CORRETTO
   filepath = sanitize_path(f"uploads/{user_id}/{filename}")
   ```

3. **Non assumere che i dati siano sempre validi:**
   ```python
   # ERRATO
   filename = f"{project_name}_{timestamp}.pdf"

   # CORRETTO
   safe_project = sanitize_filename(project_name, default="project")
   filename = f"{safe_project}_{timestamp}.pdf"
   ```

## Checklist Pre-Deploy

Prima di deployare codice che gestisce file/cartelle:

- [ ] Tutte le variabili usate in nomi file sono validate?
- [ ] Usate funzioni di sanitizzazione (`sanitize_filename`)?
- [ ] Esiste fallback se il valore è invalido?
- [ ] Testato con input invalidi (nul, con, prn, null)?
- [ ] Aggiunto logging per valori problematici?
- [ ] File temporanei usano generazione sicura?
- [ ] Path completi vengono sanitizzati?

## Testing

### Test Automatici

```python
# In windows_filename_validator.py
def run_self_tests():
    """Esegue test di auto-verifica"""
    # Test nomi riservati
    assert is_windows_reserved_name("nul") == True
    assert is_windows_reserved_name("con") == True
    assert is_windows_reserved_name("documento.pdf") == False

    # Test sanitizzazione
    assert sanitize_filename("nul.txt") == "file_unnamed.txt"
    assert sanitize_filename("null.txt") == "file_unnamed.txt"

    # Test validazione
    assert is_valid_filename("documento.pdf") == True
    assert is_valid_filename("nul") == False
```

**Esegui test:**
```bash
cd backend && python windows_filename_validator.py
```

### Test Manuali

Testa sempre con questi valori problematici:

```python
test_cases = [
    # Nomi riservati Windows
    'nul', 'con', 'prn', 'aux',
    'com1', 'com2', 'lpt1', 'lpt2',

    # Con estensioni
    'nul.txt', 'con.pdf', 'prn.docx',

    # Varianti maiuscole/minuscole
    'NUL', 'NULL', 'Null',

    # Nomi problematici JavaScript/Python
    'null', 'none', 'undefined',

    # Caratteri invalidi
    'file<test>.txt', 'file:test.pdf',

    # Casi edge
    '', None, '   ', '.'
]

for test in test_cases:
    result = sanitize_filename(test)
    print(f"{test} -> {result}")
    assert is_valid_filename(result), f"Failed for {test}"
```

## Verifica Progetto

**Script di verifica automatica:**
```bash
# Controlla se ci sono file problematici
python scripts/remove_windows_reserved_names.py

# Output:
# [OK] SUCCESSO: Nessun file o directory con nome riservato Windows!
# Il progetto e' conforme ai requisiti di OneDrive.
```

**Verifica manuale:**
```bash
# Cerca file con "nul" nel nome (case-insensitive)
find . -iname "*nul*" -not -path "*/node_modules/*" -not -path "*/venv/*"

# Non dovrebbe restituire nessun risultato!
```

## Troubleshooting

### "OneDrive non sincronizza alcuni file"

1. **Scansiona il progetto:**
   ```bash
   python scripts/remove_windows_reserved_names.py
   ```

2. **Se trova file problematici, rinominali:**
   ```bash
   python scripts/remove_windows_reserved_names.py --rename
   ```

3. **Riavvia OneDrive:**
   - Chiudi OneDrive
   - Apri Task Manager e termina tutti i processi OneDrive
   - Riapri OneDrive
   - La sincronizzazione dovrebbe riprendere

### "File creati con nome 'nul' o 'con'"

**Causa:** Codice che non usa le funzioni di validazione.

**Soluzione:**
1. Trova dove viene creato il file nel codice
2. Aggiungi validazione:
   ```python
   from backend.windows_filename_validator import sanitize_filename

   # Prima della creazione file
   safe_filename = sanitize_filename(filename)
   ```

### "Errori durante la creazione di contratti"

Se i contratti hanno nomi problematici:

```python
# contract_generator.py già include la protezione
# Ma se hai override, assicurati di usare:
from backend.windows_filename_validator import sanitize_filename

filename = sanitize_filename(proposed_name, default="contratto.pdf")
```

## Risorse

### Documentazione
- **PREVENT_NULL_FILENAMES.md** - Prevenzione nomi "null"
- **scripts/remove_windows_reserved_names.py** - Script rimozione file problematici
- **scripts/check_null_filenames.py** - Script controllo nomi "null"

### Moduli Python
- **backend/windows_filename_validator.py** - Validatore completo
- **backend/file_upload.py** - Upload file con protezione
- **backend/contract_generator.py** - Generazione contratti protetta

### Frontend
- **frontend/src/utils/fileNameValidator.js** - Validazione JavaScript
- **frontend/src/utils/fileNameValidator.test.js** - Test frontend

### Link Utili
- [Microsoft - Naming Files, Paths, and Namespaces](https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file)
- [OneDrive - Invalid File Names and File Types](https://support.microsoft.com/en-us/office/invalid-file-names-and-file-types-in-onedrive-and-sharepoint-64883a5d-228e-48f5-b3d2-eb39e07630fa)

## Supporto

Per problemi o domande:
1. Controlla questa documentazione
2. Verifica il progetto con lo script automatico
3. Controlla i log dell'applicazione
4. Contatta il team di sviluppo

---

**Ultima modifica:** 2025-10-06
**Versione:** 1.0
**Autore:** Sistema di Prevenzione Automatica
