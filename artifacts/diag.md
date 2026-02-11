# 🔍 RICOGNIZIONE DIAGNOSTICA - Gestionale

## Struttura Progetto

```
pythonpro/
├── backend/          # FastAPI Python backend
│   ├── main.py       # Entry point
│   ├── routers/      # Router modulari
│   ├── .env          # Config backend (PORT=8000)
│   └── ...
├── frontend/         # React (Create React App)
│   ├── src/
│   │   ├── services/
│   │   │   └── apiService.js  # ❌ Client API (ISSUE QUI!)
│   │   └── ...
│   ├── package.json  # react-scripts 5.0.1
│   ├── .env.local    # ❌ REACT_APP_API_URL=http://localhost:8001 (WRONG!)
│   └── .env.sample   # Template config
└── artifacts/        # Deliverables diagnostica
```

## Configurazione Attuale

### Frontend (Create React App)

**File**: `frontend/package.json`
- **Toolchain**: Create React App (react-scripts 5.0.1)
- **Porta**: 3001 (da `.env.local`)
- **Script start**: `react-scripts start`
- **Nessun proxy configurato** (no setupProxy.js, no proxy in package.json)

**File**: `frontend/.env.local`
```bash
REACT_APP_API_URL=http://localhost:8001  # ❌ PORTA ERRATA!
PORT=3001
WDS_SOCKET_PORT=3001
```

**File**: `frontend/src/services/apiService.js:7`
```javascript
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8001';
// ❌ Default fallback ANCHE SBAGLIATO!

// Axios instance
const apiClient = axios.create({
  baseURL: API_BASE_URL,  // http://localhost:8001 ❌
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' }
});
```

**Chiamate API** (esempio progetti):
```javascript
// Line 208 in apiService.js
apiClient.get(`/api/v1/projects/?${params.toString()}`)
// URL completo: http://localhost:8001/api/v1/projects/ ❌ 404!
```

### Backend (FastAPI Python)

**File**: `backend/.env`
```bash
PORT=8000          # ✅ Backend ascolta su porta 8000
HOST=0.0.0.0
DATABASE_URL=sqlite:///./gestionale.db
DEBUG=True
```

**File**: `backend/main.py`
- FastAPI app
- CORS configurato per: `localhost:3000`, `localhost:3001`, `127.0.0.1:3001`
- Routers modulari registrati con prefissi

**File**: `backend/routers/projects.py:16`
```python
router = APIRouter(prefix="/api/v1/projects", tags=["Projects"])

@router.get("/", response_model=List[schemas.Project])
def read_projects(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """OTTIENI LISTA DI TUTTI I PROGETTI"""
    projects = crud.get_projects(db, skip=skip, limit=limit)
    return projects
```

**Endpoint esposto**: `GET http://localhost:8000/api/v1/projects/` ✅

**Altri routers** (tutti con prefix `/api/v1/`):
- `/api/v1/collaborators` (collaborators.py)
- `/api/v1/attendances` (attendances.py)
- `/api/v1/assignments` (assignments.py)
- `/api/v1/entities` (implementing_entities.py)
- `/api/v1/contracts/templates` (contract_templates.py)
- `/api/v1/reporting` (reporting.py)
- `/health` (system.py - no prefix)

## 🚨 PROBLEMI IDENTIFICATI

### ❌ PROBLEMA #1: MISMATCH DI PORTA (404)

**Frontend chiama**:
```
http://localhost:8001/api/v1/projects/
```

**Backend ascolta su**:
```
http://localhost:8000/api/v1/projects/  ✅ Corretto
```

**Risultato**: `404 Not Found` perché sulla porta 8001 non c'è niente in ascolto!

**File coinvolti**:
- `frontend/.env.local:5` → `REACT_APP_API_URL=http://localhost:8001`
- `frontend/src/services/apiService.js:7` → Default fallback sbagliato

### ❌ PROBLEMA #2: React Error #31 (Render Oggetto)

React Error #31 = "Objects are not valid as a React child"

**Causa probabile**:
Quando la chiamata API fallisce (404), l'errore viene catturato ma renderizzato direttamente in JSX come oggetto:

```jsx
// ❌ ERRATO
{error}  // Se error è un oggetto → React error #31!

// ✅ CORRETTO
{error.message}  // Stringa
// Oppure
<ErrorBanner error={error} />  // Component che gestisce stringify
```

**Grep necessario**: Cercare tutti i punti dove viene renderizzato `{error}` o simili.

### ⚠️ PROBLEMA #3: Nessun Proxy Dev Configurato

Create React App supporta proxy in `package.json` o `setupProxy.js`, ma **nessuno è configurato**.

**Opzioni**:
1. **Opzione A (preferita)**: Fix `.env.local` con porta corretta → più semplice
2. **Opzione B**: Aggiungere proxy in `package.json`:
   ```json
   "proxy": "http://localhost:8000"
   ```
   E cambiare tutte le chiamate da `/api/v1/...` a path relativi

## Path API Mappati

### Frontend → Backend

| Frontend Call | URL Completo (attuale) | Backend Endpoint | Status |
|--------------|------------------------|------------------|--------|
| `apiClient.get('/api/v1/projects/')` | `http://localhost:8001/api/v1/projects/` ❌ | `http://localhost:8000/api/v1/projects/` ✅ | 404 |
| `apiClient.get('/api/v1/collaborators/')` | `http://localhost:8001/api/v1/collaborators/` ❌ | `http://localhost:8000/api/v1/collaborators/` ✅ | 404 |
| `apiClient.get('/health')` | `http://localhost:8001/health` ❌ | `http://localhost:8000/health` ✅ | 404 |

**Tutte le chiamate API falliscono con 404** perché puntano alla porta sbagliata!

## File da Modificare (Preview)

1. **frontend/.env.local** → Cambiare porta da 8001 a 8000
2. **frontend/src/services/apiService.js** → Fix default fallback
3. Cercare e fixare rendering errori (`{error}` → `<ErrorBanner>`)
4. Aggiungere `ErrorBanner.jsx` component
5. Aggiungere healthcheck script
6. Aggiornare README.md

## Comando Avvio Attuale

**Backend**:
```bash
cd backend
venv/Scripts/python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000
```

**Frontend**:
```bash
cd frontend
PORT=3001 npm start
# oppure: npm start (legge PORT da .env.local)
```

## Prossimi Step

1. ✅ Ricognizione completata
2. ⏭️ Riproduzione bug (avviare stack e catturare 404 + React error)
3. ⏭️ Diagnosi tecnica (grep rendering errori)
4. ⏭️ Fix implementativi
5. ⏭️ Verifica con smoke test
6. ⏭️ Documentazione finale
