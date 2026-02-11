# 🔥 ROOT CAUSE ANALYSIS - Bug 404 + React Error #31

## Executive Summary

Il gestionale presenta **2 bug correlati**:

1. **404 su tutte le chiamate API** → Causa: mismatch di porta (frontend chiama 8001, backend ascolta su 8000)
2. **React minified error #31** → Causa: rendering diretto di oggetti errore in JSX (`{error}` invece di `{error.message}`)

---

## Bug #1: 404 Not Found su API Calls

### Evidenza

Tutte le chiamate API dal frontend falliscono con **404 Not Found**:
- `/api/v1/projects/` → 404
- `/api/v1/collaborators/` → 404
- `/api/v1/attendances/` → 404
- Etc.

### Root Cause

**MISMATCH DI PORTA** tra frontend e backend:

**Frontend** (`frontend/.env.local:5`):
```bash
REACT_APP_API_URL=http://localhost:8001  # ❌ PORTA SBAGLIATA!
```

**Frontend** (`frontend/src/services/apiService.js:7`):
```javascript
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8001';
//                                                       ^^^^^^^^^^^^^^^^^^^
//                                                       Anche il fallback è sbagliato!
```

**Backend** (`backend/.env:15`):
```bash
PORT=8000  # ✅ Backend gira correttamente qui
```

### Flusso dell'Errore

```
1. Frontend carica, legge .env.local
   → API_BASE_URL = 'http://localhost:8001'

2. User apre app, React tenta di caricare progetti
   → apiClient.get('/api/v1/projects/')
   → URL completo: http://localhost:8001/api/v1/projects/

3. Browser fa richiesta HTTP GET
   → Connection refused (niente ascolta su porta 8001)
   → 404 Not Found

4. apiService.getProjects() riceve errore
   → Promise rejected con AxiosError
```

### Verifica Backend Routes

**Backend espone correttamente** (verificato in `backend/routers/projects.py:16`):
```python
router = APIRouter(prefix="/api/v1/projects", tags=["Projects"])

@router.get("/", response_model=List[schemas.Project])
def read_projects(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """OTTIENI LISTA DI TUTTI I PROGETTI"""
    return crud.get_projects(db, skip=skip, limit=limit)
```

Endpoint corretto: `GET http://localhost:8000/api/v1/projects/` ✅

### Fix Required

**Opzione 1 (SCELTA)**: Fix .env.local
```bash
# frontend/.env.local
REACT_APP_API_URL=http://localhost:8000  # ✅ Porta corretta
```

**Opzione 2**: Aggiungere proxy in Create React App (più complesso, non necessario per dev)

---

## Bug #2: React Minified Error #31

### Evidenza

Console browser mostra:
```
Error: Minified React error #31
Objects are not valid as a React child (found: object with keys {...}).
If you meant to render a collection of children, use an array instead.
```

### Root Cause

**RENDERING DIRETTO DI OGGETTI IN JSX**

Quando una chiamata API fallisce, l'errore viene salvato in state come oggetto (es. AxiosError), ma poi renderizzato **direttamente in JSX**:

```jsx
{error}  // ❌ Se error è un oggetto → React error #31!
```

React **non può renderizzare oggetti JavaScript direttamente**. Può solo renderizzare:
- Stringhe
- Numeri
- Elementi React
- Array di elementi validi

### File Coinvolti (3 casi critici)

#### 1. `frontend/src/components/AssignmentModal.js:427`

```jsx
{error && (
  <div className="error-message">
    ⚠️ {error}  // ❌ ERRATO - oggetto renderizzato direttamente
  </div>
)}
```

#### 2. `frontend/src/components/CalendarSimple.js:156`

```jsx
<div style={{ color: 'red', marginBottom: '20px' }}>
  ⚠️ {error}  // ❌ ERRATO - oggetto renderizzato direttamente
</div>
```

#### 3. `frontend/src/components/ProgettoMansioneEnteManager.js:318`

```jsx
<div className="alert alert-error">
  <span className="alert-icon">⚠️</span>
  {error}  // ❌ ERRATO - oggetto renderizzato direttamente
</div>
```

### Struttura Oggetto Errore (AxiosError)

Quando una chiamata axios fallisce, l'oggetto error contiene:

```javascript
{
  name: "AxiosError",
  message: "Request failed with status code 404",
  code: "ERR_BAD_REQUEST",
  config: { /* ... */ },
  request: { /* ... */ },
  response: {
    status: 404,
    statusText: "Not Found",
    data: { /* ... */ }
  },
  stack: "..."
}
```

Renderizzare questo oggetto → React error #31!

### Fix Required

**Soluzione 1**: Stringify inline
```jsx
{error && (
  <div className="error-message">
    ⚠️ {error.message || JSON.stringify(error)}
  </div>
)}
```

**Soluzione 2 (SCELTA)**: Component ErrorBanner
```jsx
// Nuovo component: frontend/src/components/ErrorBanner.jsx
import { isAxiosError } from 'axios';

export default function ErrorBanner({ error }) {
  let message = 'Errore sconosciuto';

  if (isAxiosError(error)) {
    message = error.response?.data?.message
           || error.response?.data?.detail
           || error.message;
  } else if (error instanceof Error) {
    message = error.message;
  } else if (typeof error === 'string') {
    message = error;
  } else {
    try {
      message = JSON.stringify(error);
    } catch {
      message = String(error);
    }
  }

  return <>{message}</>;
}

// Uso:
import ErrorBanner from './ErrorBanner';

{error && (
  <div className="error-message">
    ⚠️ <ErrorBanner error={error} />
  </div>
)}
```

---

## Correlazione tra i Due Bug

```
┌─────────────────────────────────────────────────┐
│  1. Frontend chiama porta sbagliata (8001)     │
│     → Chiamata fallisce con 404                 │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│  2. axios.get() rigetta con AxiosError object   │
│     → catch(error) salva oggetto in state       │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│  3. JSX tenta di renderizzare {error}           │
│     → React vede oggetto invece di stringa      │
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────┐
│  4. React lancia Error #31                      │
│     "Objects are not valid as a React child"    │
└─────────────────────────────────────────────────┘
```

**Il Bug #1 causa il Bug #2**:
- Senza il 404, non ci sarebbe errore da renderizzare
- Ma anche fixando il 404, il Bug #2 potrebbe ripresentarsi con altri errori (es. 500, network error, ecc.)

**Quindi dobbiamo fixare ENTRAMBI**!

---

## Impact Assessment

**Severity**: 🔴 CRITICAL

**Affected Flows**:
- ✅ App startup (caricamento progetti)
- ✅ Caricamento collaboratori
- ✅ Calendario presenze
- ✅ Assegnazioni
- ✅ Tutte le operazioni CRUD

**User Experience**:
- App completamente non funzionante
- Nessun dato caricato
- Console piena di errori

---

## Remediation Plan

### Immediate Fixes (Ordine di esecuzione)

1. **Fix porta frontend** (`frontend/.env.local`)
   - Cambiare `REACT_APP_API_URL=http://localhost:8000`

2. **Fix default fallback** (`frontend/src/services/apiService.js`)
   - Cambiare fallback da 8001 a 8000

3. **Creare ErrorBanner component** (`frontend/src/components/ErrorBanner.jsx`)
   - Gestisce stringify di qualsiasi tipo di errore

4. **Fix rendering errori** (3 file):
   - `AssignmentModal.js:427` → `<ErrorBanner error={error} />`
   - `CalendarSimple.js:156` → `<ErrorBanner error={error} />`
   - `ProgettoMansioneEnteManager.js:318` → `<ErrorBanner error={error} />`

5. **Aggiungere logging** (opzionale ma raccomandato)
   - Loggare l'oggetto completo in console.error() nei catch
   - Aiuta debugging futuro

### Long-term Improvements

1. **Setup proxy CRA** (opzionale)
   - Proxy in package.json o setupProxy.js
   - Permette chiamate relative `/api/v1/...`

2. **Global ErrorBoundary**
   - Catch errori di rendering non gestiti

3. **Healthcheck script**
   - Smoke test per verificare connettività FE↔BE

4. **Monitoring**
   - Sentry o simili per produzione

---

## Files to Modify

| File | Line | Change | Priority |
|------|------|--------|----------|
| `frontend/.env.local` | 5 | `8001` → `8000` | P0 🔴 |
| `frontend/src/services/apiService.js` | 7 | Default fallback `8001` → `8000` | P0 🔴 |
| `frontend/src/components/ErrorBanner.jsx` | NEW | Creare component | P0 🔴 |
| `frontend/src/components/AssignmentModal.js` | 427 | `{error}` → `<ErrorBanner error={error} />` | P0 🔴 |
| `frontend/src/components/CalendarSimple.js` | 156 | `{error}` → `<ErrorBanner error={error} />` | P0 🔴 |
| `frontend/src/components/ProgettoMansioneEnteManager.js` | 318 | `{error}` → `<ErrorBanner error={error} />` | P0 🔴 |

---

## Verification Plan

1. **Fix porta** → Riavviare frontend
2. **cURL test**: `curl http://localhost:8000/api/v1/projects/` → 200 OK
3. **Browser test**: Aprire app, verificare lista progetti caricata
4. **Console check**: No React error #31
5. **Smoke test**: Script automatico healthcheck + API calls

---

## Lessons Learned

1. **Sempre verificare baseURL** in config env
2. **Mai renderizzare oggetti in JSX** → Usare component helper
3. **Aggiungere healthcheck** per verificare connettività FE↔BE
4. **Logging strutturato** aiuta diagnosi (console.error con context)
