# Calendario con Filtri (barra filtri, multi-selezione, URL sync) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Il calendario (`frontend/src/components/Calendar.js`) oggi non ha alcun filtro: carica tutte le presenze dalla cache globale `AppContext` e le mostra tutte insieme, illeggibile con più progetti/collaboratori. Questo piano aggiunge una barra filtri persistente (progetto singolo/multiplo, collaboratore multi-selezione, periodo, filtri secondari), sincronizzata con l'URL e con `localStorage`, con filtraggio **lato server** (mai tutto-e-poi-filtra-nel-browser), e un avviso quando il risultato è troppo ampio per essere reso leggibilmente.

**Architecture:** Il calendario smette di appoggiarsi alla cache condivisa `AppContext.state.attendances` (usata *solo* da `Calendar.js` oggi — nessun altro componente la legge, verificato) e passa a un fetch diretto e locale, sul modello già in uso in `frontend/src/components/collaborators/CollaboratorsTable.js` (stato locale + sync manuale su `window.location.search` via `URLSearchParams`, nessun hook custom). Il backend riceve un **nuovo endpoint dedicato** `GET /api/v1/attendances/calendar` (non tocchiamo l'endpoint esistente `GET /api/v1/attendances/` per non rischiare di rompere `AppContext`/`CalendarSimple.js`, che restano tal quali e diventano semplicemente non più esercitati da `Calendar.js`). Il nuovo endpoint eredita automaticamente le stesse regole RBAC di `/api/v1/attendances` (stesso prefisso `OPERATIONAL_PREFIXES`), quindi consultazione ha già accesso in sola lettura senza modifiche a `auth.py`/`permissions.js`.

**Tech Stack:** FastAPI + SQLAlchemy (backend), React + `react-big-calendar`/`moment` (frontend, invariati), nessuna nuova dipendenza.

## Global Constraints

- Mai scaricare tutte le presenze e filtrare nel browser: ogni filtro deve tradursi in una clausola SQL lato server.
- Non modificare l'endpoint esistente `GET /api/v1/attendances/` né `AppContext.js` né `CalendarSimple.js` (fuori scope, nessun consumatore attivo li richiede dopo questo piano).
- Non serve nessuna nuova migrazione Alembic: `Attendance.date` ha già `index=True` (colonna singola, `backend/models.py:769`), esiste già l'indice composito `ix_attendances_collaborator_project_date (collaborator_id, project_id, date)` (`backend/models.py:810`, replicato in `backend/alembic/versions/036_add_production_readiness_indexes.py:30-36`). Verificare solo, non aggiungere.
- RBAC: `/api/v1/attendances/calendar` eredita automaticamente da `OPERATIONAL_PREFIXES` (`backend/auth.py:141`, `frontend/src/auth/permissions.js:72`) — GET per tutti e 3 i ruoli, scritture solo admin/operatore. Nessuna modifica a `auth.py`/`permissions.js` richiesta per questo piano.
- Persistenza filtri: nessun meccanismo di preferenze utente lato backend esiste oggi; usare `localStorage`, chiave che include lo username (`pythonpro:calendarFilters:<username>`) per non mescolare le preferenze di utenti diversi sullo stesso browser.
- Repo con sessioni concorrenti in corso su altri file (`admin.py`, `apiService.js`, `App.js`, ecc.): ogni task che tocca un file condiviso deve **rileggerlo appena prima di modificarlo**, non fidarsi di una copia in memoria vecchia.

---

### Task 1: `crud.get_attendances_calendar` — query filtrata multi-selezione con conteggio totale

**Files:**
- Modify: `backend/crud.py` (aggiungere nuova funzione dopo `get_attendances_total_hours`, circa riga 1120)
- Test: `backend/tests/test_crud_attendances_calendar.py` (nuovo)

**Interfaces:**
- Produces: `get_attendances_calendar(db, *, collaborator_ids=None, project_ids=None, start_date, end_date, include_closed_projects=False, skip=0, limit=500) -> tuple[list[models.Attendance], int]` — usata da Task 2.

- [x] **Step 1: Scrivi il test che deve fallire**

```python
# backend/tests/test_crud_attendances_calendar.py
"""crud.get_attendances_calendar: multi-selezione collaboratori/progetti,
esclusione progetti chiusi di default, conteggio totale server-side."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import crud
import models
from database import Base


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _make_collaborator(db, **overrides):
    defaults = dict(first_name="Mario", last_name="Rossi", email=f"m{overrides.get('_n', 1)}@x.it")
    defaults.update({k: v for k, v in overrides.items() if k != "_n"})
    c = models.Collaborator(**defaults)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _make_project(db, *, is_active=True, **overrides):
    defaults = dict(name="Progetto Test", status="active" if is_active else "completed", is_active=is_active)
    defaults.update(overrides)
    p = models.Project(**defaults)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _make_attendance(db, *, collaborator_id, project_id, when):
    a = models.Attendance(
        collaborator_id=collaborator_id,
        project_id=project_id,
        date=when,
        start_time=when,
        end_time=when + timedelta(hours=1),
        hours=1,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def test_filtra_per_piu_collaboratori_e_piu_progetti(db_session):
    c1 = _make_collaborator(db_session, _n=1)
    c2 = _make_collaborator(db_session, _n=2)
    c3 = _make_collaborator(db_session, _n=3)
    p1 = _make_project(db_session)
    p2 = _make_project(db_session)
    now = datetime(2026, 7, 1, 9, 0)
    _make_attendance(db_session, collaborator_id=c1.id, project_id=p1.id, when=now)
    _make_attendance(db_session, collaborator_id=c2.id, project_id=p2.id, when=now)
    _make_attendance(db_session, collaborator_id=c3.id, project_id=p1.id, when=now)

    items, total = crud.get_attendances_calendar(
        db_session,
        collaborator_ids=[c1.id, c2.id],
        project_ids=[p1.id, p2.id],
        start_date=now - timedelta(days=1),
        end_date=now + timedelta(days=1),
    )

    assert total == 2
    assert {a.collaborator_id for a in items} == {c1.id, c2.id}


def test_esclude_progetti_chiusi_di_default(db_session):
    c1 = _make_collaborator(db_session, _n=1)
    p_aperto = _make_project(db_session, is_active=True)
    p_chiuso = _make_project(db_session, is_active=False)
    now = datetime(2026, 7, 1, 9, 0)
    _make_attendance(db_session, collaborator_id=c1.id, project_id=p_aperto.id, when=now)
    _make_attendance(db_session, collaborator_id=c1.id, project_id=p_chiuso.id, when=now)

    items, total = crud.get_attendances_calendar(
        db_session, start_date=now - timedelta(days=1), end_date=now + timedelta(days=1),
    )
    assert total == 1
    assert items[0].project_id == p_aperto.id

    items_incl, total_incl = crud.get_attendances_calendar(
        db_session,
        start_date=now - timedelta(days=1),
        end_date=now + timedelta(days=1),
        include_closed_projects=True,
    )
    assert total_incl == 2


def test_total_conta_tutte_le_righe_anche_oltre_il_limit(db_session):
    c1 = _make_collaborator(db_session, _n=1)
    p1 = _make_project(db_session)
    now = datetime(2026, 7, 1, 9, 0)
    for i in range(5):
        _make_attendance(db_session, collaborator_id=c1.id, project_id=p1.id, when=now + timedelta(hours=i))

    items, total = crud.get_attendances_calendar(
        db_session, start_date=now - timedelta(days=1), end_date=now + timedelta(days=1), limit=2,
    )
    assert total == 5
    assert len(items) == 2
```

- [x] **Step 2: Esegui e verifica che fallisca**

```bash
docker cp backend/tests/test_crud_attendances_calendar.py pythonpro_backend:/app/tests/test_crud_attendances_calendar.py
docker exec pythonpro_backend pytest tests/test_crud_attendances_calendar.py -q --no-cov
```

Atteso: `AttributeError: module 'crud' has no attribute 'get_attendances_calendar'` (o `ImportError`/`ModuleNotFoundError` equivalente) — la funzione non esiste ancora.

- [x] **Step 3: Implementa la funzione minima**

Aggiungi in `backend/crud.py` subito dopo `get_attendances_total_hours` (circa riga 1120):

```python
def get_attendances_calendar(
    db: Session,
    *,
    collaborator_ids: Optional[list[int]] = None,
    project_ids: Optional[list[int]] = None,
    start_date: datetime,
    end_date: datetime,
    include_closed_projects: bool = False,
    skip: int = 0,
    limit: int = 500,
) -> tuple[list["models.Attendance"], int]:
    """Query calendario: multi-selezione, esclude progetti chiusi di default,
    ritorna (righe pagina corrente, conteggio totale non paginato)."""
    base_query = db.query(models.Attendance).filter(
        models.Attendance.date.between(start_date, end_date)
    )

    if collaborator_ids:
        base_query = base_query.filter(models.Attendance.collaborator_id.in_(collaborator_ids))
    if project_ids:
        base_query = base_query.filter(models.Attendance.project_id.in_(project_ids))
    if not include_closed_projects:
        base_query = base_query.join(
            models.Project, models.Attendance.project_id == models.Project.id
        ).filter(models.Project.is_active.is_(True))

    total = base_query.with_entities(func.count(models.Attendance.id)).scalar() or 0

    items = (
        base_query
        .order_by(desc(models.Attendance.date), desc(models.Attendance.start_time))
        .offset(skip)
        .limit(limit)
        .all()
    )
    return items, int(total)
```

Verifica che in cima al file `backend/crud.py` siano già importati `Optional` (da `typing`) e `desc`/`func` (da `sqlalchemy`) — lo sono già, usati dalle funzioni esistenti nello stesso file (`get_attendances`, `get_attendances_count`).

- [x] **Step 4: Esegui e verifica che passi**

```bash
docker cp backend/crud.py pythonpro_backend:/app/crud.py
docker exec pythonpro_backend pytest tests/test_crud_attendances_calendar.py -q --no-cov
```

Atteso: `3 passed`.

- [x] **Step 5: Commit**

```bash
git add backend/crud.py backend/tests/test_crud_attendances_calendar.py
git commit -m "feat(calendar): query filtrata multi-selezione con conteggio totale"
```

---

### Task 2: Endpoint `GET /api/v1/attendances/calendar`

**Files:**
- Modify: `backend/routers/attendances.py` (aggiungere endpoint dopo `read_attendances`, circa riga 143)
- Test: `backend/tests/test_attendances_calendar_endpoint.py` (nuovo)

**Interfaces:**
- Consumes: `crud.get_attendances_calendar(...)` da Task 1; `auth.get_current_user`, `auth.User` (per `only_mine`).
- Produces: risposta JSON `{"items": [...], "total": int}` dove ogni item ha gli stessi campi di `schemas.Attendance` (`id, collaborator_id, project_id, assignment_id, date, start_time, end_time, hours, notes, created_at, updated_at`) — usata da Task 8 (`apiService.getCalendarAttendances`).

- [x] **Step 1: Scrivi il test che deve fallire**

```python
# backend/tests/test_attendances_calendar_endpoint.py
"""GET /api/v1/attendances/calendar: filtri multi-selezione, only_mine, RBAC."""
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from database import Base, get_db
import auth
from auth import User, UserRole, SecurityUtils, get_current_user
import models  # noqa: F401


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(db_session, monkeypatch):
    monkeypatch.setattr(auth, "RBAC_ENFORCE", True)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    original_startup = list(app.router.on_startup)
    app.router.on_startup.clear()
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.router.on_startup[:] = original_startup
        app.dependency_overrides.clear()


def _user(db, role, collaborator_id=None):
    u = User(
        username=f"u_{role}_{collaborator_id}",
        email=f"u_{role}_{collaborator_id}@example.com",
        hashed_password=SecurityUtils.hash_password("Password123!Test"),
        role=role,
        is_active=True,
        collaborator_id=collaborator_id,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _collaborator(db):
    c = models.Collaborator(first_name="Mario", last_name="Rossi", email=f"m{id(object())}@x.it")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _project(db, is_active=True):
    p = models.Project(name="P", status="active" if is_active else "completed", is_active=is_active)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _attendance(db, collaborator_id, project_id, when):
    a = models.Attendance(
        collaborator_id=collaborator_id, project_id=project_id,
        date=when, start_time=when, end_time=when + timedelta(hours=1), hours=1,
    )
    db.add(a)
    db.commit()
    return a


def test_filtro_multi_collaboratore_e_progetto_via_query_string(client, db_session):
    import models
    admin = _user(db_session, UserRole.ADMIN.value)
    c1, c2 = _collaborator(db_session), _collaborator(db_session)
    p1 = _project(db_session)
    now = datetime(2026, 7, 1, 9, 0)
    _attendance(db_session, c1.id, p1.id, now)
    _attendance(db_session, c2.id, p1.id, now)
    app.dependency_overrides[get_current_user] = lambda: admin

    resp = client.get(
        "/api/v1/attendances/calendar",
        params={
            "collaborator_ids": f"{c1.id}",
            "start_date": "2026-06-01T00:00:00",
            "end_date": "2026-08-01T00:00:00",
        },
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["collaborator_id"] == c1.id


def test_only_mine_ignora_collaborator_ids_esplicito(client, db_session):
    c_mio, c_altro = _collaborator(db_session), _collaborator(db_session)
    p1 = _project(db_session)
    now = datetime(2026, 7, 1, 9, 0)
    _attendance(db_session, c_mio.id, p1.id, now)
    _attendance(db_session, c_altro.id, p1.id, now)
    consultazione = _user(db_session, UserRole.CONSULTAZIONE.value, collaborator_id=c_mio.id)
    app.dependency_overrides[get_current_user] = lambda: consultazione

    resp = client.get(
        "/api/v1/attendances/calendar",
        params={
            "collaborator_ids": f"{c_altro.id}",
            "only_mine": "true",
            "start_date": "2026-06-01T00:00:00",
            "end_date": "2026-08-01T00:00:00",
        },
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["collaborator_id"] == c_mio.id


def test_consultazione_non_puo_scrivere_ma_legge(client, db_session):
    consultazione = _user(db_session, UserRole.CONSULTAZIONE.value)
    app.dependency_overrides[get_current_user] = lambda: consultazione

    resp = client.get(
        "/api/v1/attendances/calendar",
        params={"start_date": "2026-06-01T00:00:00", "end_date": "2026-08-01T00:00:00"},
    )
    assert resp.status_code == 200

    resp_post = client.post(
        "/api/v1/attendances/",
        json={
            "collaborator_id": 1, "project_id": 1,
            "date": "2026-07-01T09:00:00", "start_time": "2026-07-01T09:00:00",
            "end_time": "2026-07-01T10:00:00", "hours": 1,
        },
    )
    assert resp_post.status_code == 403
```

- [x] **Step 2: Esegui e verifica che fallisca**

```bash
docker cp backend/tests/test_attendances_calendar_endpoint.py pythonpro_backend:/app/tests/test_attendances_calendar_endpoint.py
docker exec -e JWT_SECRET_KEY=test_secret_key_per_ci_non_usare_in_prod pythonpro_backend pytest tests/test_attendances_calendar_endpoint.py -q --no-cov
```

Atteso: `404 Not Found` sul primo test (endpoint non esiste).

- [x] **Step 3: Implementa l'endpoint minimo**

In `backend/routers/attendances.py`, aggiungi in cima ai import: `from auth import User, get_current_user` e aggiungi dopo `read_attendances` (circa riga 143):

```python
@router.get("/calendar")
def read_attendances_calendar(
    start_date: datetime,
    end_date: datetime,
    collaborator_ids: Optional[str] = Query(None, description="CSV di id collaboratore"),
    project_ids: Optional[str] = Query(None, description="CSV di id progetto"),
    include_closed_projects: bool = False,
    only_mine: bool = False,
    skip: int = 0,
    limit: int = 500,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Endpoint dedicato calendario: multi-selezione + conteggio totale
    server-side. Non sostituisce GET /attendances/ (usato da AppContext/
    CalendarSimple, invariati)."""
    parsed_collaborator_ids = (
        [int(v) for v in collaborator_ids.split(",") if v.strip()] if collaborator_ids else None
    )
    parsed_project_ids = (
        [int(v) for v in project_ids.split(",") if v.strip()] if project_ids else None
    )

    if only_mine:
        parsed_collaborator_ids = [current_user.collaborator_id] if current_user.collaborator_id else []

    items, total = crud.get_attendances_calendar(
        db,
        collaborator_ids=parsed_collaborator_ids,
        project_ids=parsed_project_ids,
        start_date=start_date,
        end_date=end_date,
        include_closed_projects=include_closed_projects,
        skip=skip,
        limit=limit,
    )

    return {
        "items": [schemas.Attendance.model_validate(a).model_dump(mode="json") for a in items],
        "total": total,
    }
```

Aggiungi `Query` all'import esistente da `fastapi` in cima al file (già importa `APIRouter, Depends, HTTPException, Query, Response, status` — `Query` è già presente, nessuna modifica import necessaria).

- [x] **Step 4: Esegui e verifica che passi**

```bash
docker cp backend/routers/attendances.py pythonpro_backend:/app/routers/attendances.py
docker exec -e JWT_SECRET_KEY=test_secret_key_per_ci_non_usare_in_prod pythonpro_backend pytest tests/test_attendances_calendar_endpoint.py -q --no-cov
```

Atteso: `3 passed`.

- [x] **Step 5: Regressione mirata**

```bash
docker exec -e JWT_SECRET_KEY=test_secret_key_per_ci_non_usare_in_prod -e ADMIN_DEFAULT_PASSWORD=Admin123!Test -e OPERATOR_DEFAULT_PASSWORD=Oper123!Test pythonpro_backend pytest tests/test_attendance_overlap.py tests/test_dom21_attendance_exclusion_pg.py tests/test_rbac_download_endpoints.py -q --no-cov
```

Atteso: nessuna regressione (tutti verdi).

- [x] **Step 6: Commit**

```bash
git add backend/routers/attendances.py backend/tests/test_attendances_calendar_endpoint.py
git commit -m "feat(calendar): endpoint GET /attendances/calendar con multi-selezione e only_mine"
```

---

### Task 3: `apiService.getCalendarAttendances` + lista leggera progetti/collaboratori

**Files:**
- Modify: `frontend/src/services/apiService.js`
- Test: nessuno dedicato (funzione banale, coperta indirettamente dai test del componente in Task 6)

**Interfaces:**
- Consumes: nessuno (chiama `http.get` direttamente).
- Produces: `apiService.getCalendarAttendances({ startDate, endDate, collaboratorIds, projectIds, includeClosedProjects, onlyMine })` → `Promise<{items, total}>`. Usata da Task 6.

- [x] **Step 1: Rileggi il file prima di editare**

```bash
sed -n '1,20p' frontend/src/services/apiService.js
```

(Il file è condiviso con altre modifiche in corso in questa sessione di lavoro: verifica sempre lo stato reale prima di un `Edit`, non fidarti di una copia vecchia.)

- [x] **Step 2: Aggiungi il metodo**

Aggiungi vicino a `getAttendances` esistente (dopo la sua chiusura):

```js
  async getCalendarAttendances(filters = {}) {
    const params = {
      start_date: filters.startDate,
      end_date: filters.endDate,
    };
    if (filters.collaboratorIds && filters.collaboratorIds.length) {
      params.collaborator_ids = filters.collaboratorIds.join(',');
    }
    if (filters.projectIds && filters.projectIds.length) {
      params.project_ids = filters.projectIds.join(',');
    }
    if (filters.includeClosedProjects) params.include_closed_projects = true;
    if (filters.onlyMine) params.only_mine = true;

    const response = await http.get('/attendances/calendar', { params });
    return response.data;
  }
```

- [x] **Step 3: Verifica manuale rapida**

```bash
cd frontend && node -e "console.log(require('fs').readFileSync('src/services/apiService.js','utf8').includes('getCalendarAttendances'))"
```

Atteso: `true`.

- [x] **Step 4: Commit**

```bash
git add frontend/src/services/apiService.js
git commit -m "feat(calendar): apiService.getCalendarAttendances"
```

---

### Task 4: `frontend/src/components/calendar/calendarFilters.js` — stato URL/localStorage (funzioni pure)

**Files:**
- Create: `frontend/src/components/calendar/calendarFilters.js`
- Test: `frontend/src/components/calendar/calendarFilters.test.js`

**Interfaces:**
- Produces:
  - `DEFAULT_CALENDAR_FILTERS` (oggetto: `{ projectIds: [], collaboratorIds: [], includeClosedProjects: false, onlyMine: false, view: 'month', date: <ISO string oggi> }`)
  - `filtersToParams(filters) -> URLSearchParams`
  - `filtersFromURL() -> filters` (legge `window.location.search`)
  - `loadPersistedFilters(username) -> filters | null` (legge `localStorage`, chiave `` `pythonpro:calendarFilters:${username}` ``)
  - `savePersistedFilters(username, filters) -> void`
  - `MAX_RENDERABLE_EVENTS = 400` (costante soglia)

Usate da Task 6 (`Calendar.js`).

- [x] **Step 1: Scrivi il test che deve fallire**

```js
// frontend/src/components/calendar/calendarFilters.test.js
import {
  DEFAULT_CALENDAR_FILTERS,
  filtersToParams,
  filtersFromURL,
  loadPersistedFilters,
  savePersistedFilters,
  MAX_RENDERABLE_EVENTS,
} from './calendarFilters';

beforeEach(() => {
  window.history.replaceState({}, '', '/');
  localStorage.clear();
});

test('filtersToParams serializza multi-selezione come CSV', () => {
  const params = filtersToParams({
    ...DEFAULT_CALENDAR_FILTERS,
    projectIds: [3, 7],
    collaboratorIds: [1],
    includeClosedProjects: true,
  });
  expect(params.get('project_ids')).toBe('3,7');
  expect(params.get('collaborator_ids')).toBe('1');
  expect(params.get('include_closed_projects')).toBe('true');
});

test('filtersFromURL ricostruisce array numerici dalla query string', () => {
  window.history.replaceState({}, '', '/?project_ids=3,7&collaborator_ids=1,2&only_mine=true');
  const filters = filtersFromURL();
  expect(filters.projectIds).toEqual([3, 7]);
  expect(filters.collaboratorIds).toEqual([1, 2]);
  expect(filters.onlyMine).toBe(true);
});

test('savePersistedFilters e loadPersistedFilters sono simmetrici per utente', () => {
  const filters = { ...DEFAULT_CALENDAR_FILTERS, projectIds: [5] };
  savePersistedFilters('mario.rossi', filters);
  expect(loadPersistedFilters('mario.rossi')).toEqual(filters);
  expect(loadPersistedFilters('altro.utente')).toBeNull();
});

test('MAX_RENDERABLE_EVENTS è una soglia numerica positiva', () => {
  expect(MAX_RENDERABLE_EVENTS).toBeGreaterThan(0);
});
```

- [x] **Step 2: Esegui e verifica che fallisca**

```bash
cd frontend && CI=true npx react-scripts test src/components/calendar/calendarFilters.test.js --watchAll=false
```

Atteso: `Cannot find module './calendarFilters'`.

- [x] **Step 3: Implementa il modulo minimo**

```js
// frontend/src/components/calendar/calendarFilters.js
export const MAX_RENDERABLE_EVENTS = 400;

export const DEFAULT_CALENDAR_FILTERS = {
  projectIds: [],
  collaboratorIds: [],
  includeClosedProjects: false,
  onlyMine: false,
  view: 'month',
  date: new Date().toISOString(),
};

const CSV_FIELDS = ['projectIds', 'collaboratorIds'];
const BOOL_FIELDS = ['includeClosedProjects', 'onlyMine'];
const FIELD_TO_PARAM = {
  projectIds: 'project_ids',
  collaboratorIds: 'collaborator_ids',
  includeClosedProjects: 'include_closed_projects',
  onlyMine: 'only_mine',
  view: 'view',
  date: 'date',
};

export const filtersToParams = (filters) => {
  const params = new URLSearchParams();
  Object.entries(FIELD_TO_PARAM).forEach(([field, param]) => {
    const value = filters[field];
    if (CSV_FIELDS.includes(field)) {
      if (value && value.length) params.set(param, value.join(','));
      return;
    }
    if (BOOL_FIELDS.includes(field)) {
      if (value) params.set(param, 'true');
      return;
    }
    if (value !== undefined && value !== null && value !== '') {
      params.set(param, String(value));
    }
  });
  return params;
};

export const filtersFromURL = () => {
  const params = new URLSearchParams(window.location.search);
  const filters = { ...DEFAULT_CALENDAR_FILTERS };
  if (params.has('project_ids')) {
    filters.projectIds = params.get('project_ids').split(',').filter(Boolean).map(Number);
  }
  if (params.has('collaborator_ids')) {
    filters.collaboratorIds = params.get('collaborator_ids').split(',').filter(Boolean).map(Number);
  }
  if (params.has('include_closed_projects')) {
    filters.includeClosedProjects = params.get('include_closed_projects') === 'true';
  }
  if (params.has('only_mine')) {
    filters.onlyMine = params.get('only_mine') === 'true';
  }
  if (params.has('view')) filters.view = params.get('view');
  if (params.has('date')) filters.date = params.get('date');
  return filters;
};

const storageKey = (username) => `pythonpro:calendarFilters:${username}`;

export const loadPersistedFilters = (username) => {
  if (!username) return null;
  try {
    const raw = localStorage.getItem(storageKey(username));
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
};

export const savePersistedFilters = (username, filters) => {
  if (!username) return;
  try {
    localStorage.setItem(storageKey(username), JSON.stringify(filters));
  } catch {
    // storage non disponibile (quota, modalità privata): non bloccare l'utente
  }
};
```

- [x] **Step 4: Esegui e verifica che passi**

```bash
cd frontend && CI=true npx react-scripts test src/components/calendar/calendarFilters.test.js --watchAll=false
```

Atteso: `4 passed`.

- [x] **Step 5: Commit**

```bash
git add frontend/src/components/calendar/calendarFilters.js frontend/src/components/calendar/calendarFilters.test.js
git commit -m "feat(calendar): stato filtri puro con sync URL e localStorage"
```

---

### Task 5: `frontend/src/components/calendar/CalendarFilterBar.js` — componente presentazionale

**Files:**
- Create: `frontend/src/components/calendar/CalendarFilterBar.js`
- Create: `frontend/src/components/calendar/CalendarFilterBar.css`
- Test: `frontend/src/components/calendar/CalendarFilterBar.test.js`

**Interfaces:**
- Consumes: `DEFAULT_CALENDAR_FILTERS` da Task 4 (solo per i default nei test).
- Produces: `<CalendarFilterBar filters projects collaborators eventCount onChange onReset />` dove:
  - `projects: Array<{id, name, is_active}>`, `collaborators: Array<{id, first_name, last_name}>`
  - `onChange(partialFilters)` — chiamato ad ogni interazione con un oggetto parziale da mergiare nello stato del genitore (pattern identico a `updateField` visto in `UserManagement.js`/`AreaPersonale.js`: il genitore possiede lo stato, questo componente è controllato).
  - `onReset()` — bottone "Azzera filtri".
  - `eventCount: number` — mostrato come "N eventi mostrati".
  Usato da Task 6.

- [x] **Step 1: Scrivi il test che deve fallire**

```js
// frontend/src/components/calendar/CalendarFilterBar.test.js
import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';

import CalendarFilterBar from './CalendarFilterBar';
import { DEFAULT_CALENDAR_FILTERS } from './calendarFilters';

const PROJECTS = [
  { id: 1, name: 'Progetto Alfa', is_active: true },
  { id: 2, name: 'Progetto Beta (chiuso)', is_active: false },
];
const COLLABORATORS = [
  { id: 10, first_name: 'Mario', last_name: 'Rossi' },
  { id: 11, first_name: 'Giulia', last_name: 'Bianchi' },
];

test('mostra il contatore eventi', () => {
  render(
    <CalendarFilterBar
      filters={DEFAULT_CALENDAR_FILTERS}
      projects={PROJECTS}
      collaborators={COLLABORATORS}
      eventCount={7}
      onChange={jest.fn()}
      onReset={jest.fn()}
    />,
  );
  expect(screen.getByText(/7 eventi mostrati/i)).toBeInTheDocument();
});

test('selezionare un collaboratore aggiunge il suo id (multi-selezione)', () => {
  const onChange = jest.fn();
  render(
    <CalendarFilterBar
      filters={DEFAULT_CALENDAR_FILTERS}
      projects={PROJECTS}
      collaborators={COLLABORATORS}
      eventCount={0}
      onChange={onChange}
      onReset={jest.fn()}
    />,
  );

  fireEvent.click(screen.getByLabelText(/mario rossi/i));

  expect(onChange).toHaveBeenCalledWith({ collaboratorIds: [10] });
});

test('deselezionare un collaboratore già scelto lo rimuove', () => {
  const onChange = jest.fn();
  render(
    <CalendarFilterBar
      filters={{ ...DEFAULT_CALENDAR_FILTERS, collaboratorIds: [10, 11] }}
      projects={PROJECTS}
      collaborators={COLLABORATORS}
      eventCount={0}
      onChange={onChange}
      onReset={jest.fn()}
    />,
  );

  fireEvent.click(screen.getByLabelText(/mario rossi/i));

  expect(onChange).toHaveBeenCalledWith({ collaboratorIds: [11] });
});

test('la ricerca collaboratore filtra la lista visibile', () => {
  render(
    <CalendarFilterBar
      filters={DEFAULT_CALENDAR_FILTERS}
      projects={PROJECTS}
      collaborators={COLLABORATORS}
      eventCount={0}
      onChange={jest.fn()}
      onReset={jest.fn()}
    />,
  );

  fireEvent.change(screen.getByPlaceholderText(/cerca collaboratore/i), { target: { value: 'giulia' } });

  expect(screen.queryByLabelText(/mario rossi/i)).not.toBeInTheDocument();
  expect(screen.getByLabelText(/giulia bianchi/i)).toBeInTheDocument();
});

test('il toggle "includi chiusi" mostra anche il progetto chiuso nel select', () => {
  render(
    <CalendarFilterBar
      filters={{ ...DEFAULT_CALENDAR_FILTERS, includeClosedProjects: true }}
      projects={PROJECTS}
      collaborators={COLLABORATORS}
      eventCount={0}
      onChange={jest.fn()}
      onReset={jest.fn()}
    />,
  );
  expect(screen.getByText('Progetto Beta (chiuso)')).toBeInTheDocument();
});

test('azzera filtri chiama onReset', () => {
  const onReset = jest.fn();
  render(
    <CalendarFilterBar
      filters={DEFAULT_CALENDAR_FILTERS}
      projects={PROJECTS}
      collaborators={COLLABORATORS}
      eventCount={0}
      onChange={jest.fn()}
      onReset={onReset}
    />,
  );
  fireEvent.click(screen.getByRole('button', { name: /azzera filtri/i }));
  expect(onReset).toHaveBeenCalled();
});
```

- [x] **Step 2: Esegui e verifica che fallisca**

```bash
cd frontend && CI=true npx react-scripts test src/components/calendar/CalendarFilterBar.test.js --watchAll=false
```

Atteso: `Cannot find module './CalendarFilterBar'`.

- [x] **Step 3: Implementa il componente minimo**

```js
// frontend/src/components/calendar/CalendarFilterBar.js
import React, { useMemo, useState } from 'react';
import './CalendarFilterBar.css';

const CalendarFilterBar = ({ filters, projects, collaborators, eventCount, onChange, onReset }) => {
  const [collaboratorSearch, setCollaboratorSearch] = useState('');

  const visibleProjects = useMemo(
    () => projects.filter((p) => filters.includeClosedProjects || p.is_active),
    [projects, filters.includeClosedProjects],
  );

  const visibleCollaborators = useMemo(() => {
    const term = collaboratorSearch.trim().toLowerCase();
    if (!term) return collaborators;
    return collaborators.filter((c) => (
      `${c.first_name} ${c.last_name}`.toLowerCase().includes(term)
    ));
  }, [collaborators, collaboratorSearch]);

  const toggleCollaborator = (id) => {
    const current = filters.collaboratorIds;
    const next = current.includes(id)
      ? current.filter((existing) => existing !== id)
      : [...current, id];
    onChange({ collaboratorIds: next });
  };

  const toggleProject = (id) => {
    const current = filters.projectIds;
    const next = current.includes(id)
      ? current.filter((existing) => existing !== id)
      : [...current, id];
    onChange({ projectIds: next });
  };

  return (
    <div className="calendar-filter-bar">
      <div className="calendar-filter-group">
        <span className="calendar-filter-label">Progetto</span>
        <div className="calendar-filter-checklist">
          {visibleProjects.map((project) => (
            <label key={project.id}>
              <input
                type="checkbox"
                checked={filters.projectIds.includes(project.id)}
                onChange={() => toggleProject(project.id)}
              />
              {project.name}
            </label>
          ))}
        </div>
        <label className="calendar-filter-inline-toggle">
          <input
            type="checkbox"
            checked={filters.includeClosedProjects}
            onChange={(event) => onChange({ includeClosedProjects: event.target.checked })}
          />
          Includi progetti chiusi
        </label>
      </div>

      <div className="calendar-filter-group">
        <span className="calendar-filter-label">Collaboratore</span>
        <input
          type="search"
          placeholder="Cerca collaboratore..."
          value={collaboratorSearch}
          onChange={(event) => setCollaboratorSearch(event.target.value)}
        />
        <div className="calendar-filter-checklist">
          {visibleCollaborators.map((collaborator) => (
            <label key={collaborator.id}>
              <input
                type="checkbox"
                checked={filters.collaboratorIds.includes(collaborator.id)}
                onChange={() => toggleCollaborator(collaborator.id)}
              />
              {collaborator.first_name} {collaborator.last_name}
            </label>
          ))}
        </div>
      </div>

      <div className="calendar-filter-group">
        <label>
          <input
            type="checkbox"
            checked={filters.onlyMine}
            onChange={(event) => onChange({ onlyMine: event.target.checked })}
          />
          Solo i miei impegni
        </label>
      </div>

      <div className="calendar-filter-actions">
        <button type="button" className="cancel-button" onClick={onReset}>
          Azzera filtri
        </button>
        <span className="calendar-filter-count">{eventCount} eventi mostrati</span>
      </div>
    </div>
  );
};

export default CalendarFilterBar;
```

```css
/* frontend/src/components/calendar/CalendarFilterBar.css */
.calendar-filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
  padding: 16px;
  margin-bottom: 16px;
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 12px;
  position: sticky;
  top: 0;
  z-index: 5;
}

.calendar-filter-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 180px;
}

.calendar-filter-label {
  font-weight: 600;
  font-size: 0.85em;
  color: #555;
}

.calendar-filter-checklist {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 140px;
  overflow-y: auto;
}

.calendar-filter-inline-toggle {
  font-size: 0.85em;
  color: #666;
}

.calendar-filter-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-left: auto;
}

.calendar-filter-count {
  font-size: 0.85em;
  color: #666;
  white-space: nowrap;
}
```

- [x] **Step 4: Esegui e verifica che passi**

```bash
cd frontend && CI=true npx react-scripts test src/components/calendar/CalendarFilterBar.test.js --watchAll=false
```

Atteso: `6 passed`.

- [x] **Step 5: Commit**

```bash
git add frontend/src/components/calendar/CalendarFilterBar.js frontend/src/components/calendar/CalendarFilterBar.css frontend/src/components/calendar/CalendarFilterBar.test.js
git commit -m "feat(calendar): barra filtri presentazionale (multi-selezione, ricerca, toggle)"
```

---

### Task 6: Riscrivi `Calendar.js` — fetch diretto server-side, no più cache condivisa

**Files:**
- Modify: `frontend/src/components/Calendar.js` (righe 67-144 circa: sostituire lettura da `useAppContext` per `attendances` con fetch diretto; **non toccare** `AppContext.js`)
- Modify: `frontend/src/components/Calendar.js` (righe 147-149, 464-480: colori/legenda — vedi Task 7)
- Test: `frontend/src/components/Calendar.test.js` (nuovo — il file non esiste oggi)

**Interfaces:**
- Consumes: `apiService.getCalendarAttendances` (Task 3), `apiService.getProjects`/`apiService.getCollaborators` (già esistenti, invariati), `DEFAULT_CALENDAR_FILTERS`/`filtersToParams`/`filtersFromURL`/`loadPersistedFilters`/`savePersistedFilters`/`MAX_RENDERABLE_EVENTS` (Task 4), `<CalendarFilterBar>` (Task 5).
- Produces: nessuna nuova interfaccia esterna (componente foglia, montato da `App.js` come oggi — `App.js` non richiede modifiche perché la prop `currentUser` è già passata).

- [x] **Step 1: Scrivi il test che deve fallire**

```js
// frontend/src/components/Calendar.test.js
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';

import Calendar from './Calendar';
import apiService from '../services/apiService';

jest.mock('../services/apiService', () => ({
  __esModule: true,
  default: {
    getCalendarAttendances: jest.fn(),
    getProjects: jest.fn(),
    getCollaborators: jest.fn(),
    createAttendance: jest.fn(),
    updateAttendance: jest.fn(),
    deleteAttendance: jest.fn(),
  },
}));

const CURRENT_USER = { id: 1, username: 'mario.rossi', role: 'admin', collaborator_id: 10 };

const PROJECTS_RESPONSE = { items: [{ id: 1, name: 'Progetto Alfa', is_active: true }], total: 1 };
const COLLABORATORS_RESPONSE = {
  items: [{ id: 10, first_name: 'Mario', last_name: 'Rossi' }, { id: 11, first_name: 'Giulia', last_name: 'Bianchi' }],
  total: 2,
};

beforeEach(() => {
  jest.clearAllMocks();
  window.history.replaceState({}, '', '/');
  localStorage.clear();
  apiService.getProjects.mockResolvedValue(PROJECTS_RESPONSE);
  apiService.getCollaborators.mockResolvedValue(COLLABORATORS_RESPONSE);
  apiService.getCalendarAttendances.mockResolvedValue({ items: [], total: 0 });
});

test('al primo caricamento chiama getCalendarAttendances con i filtri di default', async () => {
  render(<Calendar currentUser={CURRENT_USER} />);

  await waitFor(() => expect(apiService.getCalendarAttendances).toHaveBeenCalled());
  const callArgs = apiService.getCalendarAttendances.mock.calls[0][0];
  expect(callArgs.collaboratorIds).toEqual([]);
  expect(callArgs.projectIds).toEqual([]);
  expect(callArgs.includeClosedProjects).toBe(false);
});

test('selezionare un collaboratore rifà la fetch con il filtro e aggiorna la URL', async () => {
  render(<Calendar currentUser={CURRENT_USER} />);
  await screen.findByLabelText(/mario rossi/i);

  fireEvent.click(screen.getByLabelText(/mario rossi/i));

  await waitFor(() => {
    const lastCall = apiService.getCalendarAttendances.mock.calls.at(-1)[0];
    expect(lastCall.collaboratorIds).toEqual([10]);
  });
  expect(window.location.search).toContain('collaborator_ids=10');
});

test('i filtri vengono letti dalla URL al montaggio', async () => {
  window.history.replaceState({}, '', '/?project_ids=1');
  render(<Calendar currentUser={CURRENT_USER} />);

  await waitFor(() => {
    const callArgs = apiService.getCalendarAttendances.mock.calls[0][0];
    expect(callArgs.projectIds).toEqual([1]);
  });
});

test('senza parametri URL, ripristina i filtri salvati in localStorage per l\'utente corrente', async () => {
  localStorage.setItem(
    'pythonpro:calendarFilters:mario.rossi',
    JSON.stringify({
      projectIds: [1], collaboratorIds: [], includeClosedProjects: false, onlyMine: false,
      view: 'month', date: new Date().toISOString(),
    }),
  );
  render(<Calendar currentUser={CURRENT_USER} />);

  await waitFor(() => {
    const callArgs = apiService.getCalendarAttendances.mock.calls[0][0];
    expect(callArgs.projectIds).toEqual([1]);
  });
});

test('oltre la soglia mostra l\'avviso invece del calendario', async () => {
  apiService.getCalendarAttendances.mockResolvedValue({ items: [], total: 500 });
  render(<Calendar currentUser={CURRENT_USER} />);

  expect(await screen.findByText(/restringi i filtri/i)).toBeInTheDocument();
});

test('azzera filtri riporta ai valori di default e pulisce la URL', async () => {
  window.history.replaceState({}, '', '/?project_ids=1');
  render(<Calendar currentUser={CURRENT_USER} />);
  await screen.findByLabelText(/mario rossi/i);

  fireEvent.click(screen.getByRole('button', { name: /azzera filtri/i }));

  await waitFor(() => expect(window.location.search).toBe(''));
});
```

- [x] **Step 2: Esegui e verifica che fallisca**

```bash
cd frontend && CI=true npx react-scripts test src/components/Calendar.test.js --watchAll=false
```

Atteso: fallimenti multipli — `getCalendarAttendances` non ancora chiamato/non ancora esistente nel componente, checkbox collaboratore non trovate (la barra filtri non è ancora montata in `Calendar.js`).

- [x] **Step 3: Modifica `Calendar.js`**

Nella sezione stato/fetch di `frontend/src/components/Calendar.js` (circa righe 67-144), **rimuovi** la dipendenza da `useAppContext()` per `attendances`/`collaborators`/`projects` (lascia `useAppContext` solo se altre parti del file lo richiedono per altro — verifica con `grep -n "useAppContext" frontend/src/components/Calendar.js` prima di editare, dato che il file è stato appena letto da un agente di ricerca e potrebbe già avere altri usi) e sostituiscila con:

```js
import { DEFAULT_CALENDAR_FILTERS, MAX_RENDERABLE_EVENTS, filtersFromURL, filtersToParams, loadPersistedFilters, savePersistedFilters } from './calendar/calendarFilters';
import CalendarFilterBar from './calendar/CalendarFilterBar';

// ...dentro il componente, al posto dello stato letto da AppContext:
const [filters, setFilters] = useState(() => {
  const fromUrl = filtersFromURL();
  const hasUrlFilters = window.location.search.length > 0;
  if (hasUrlFilters) return fromUrl;
  return loadPersistedFilters(currentUser?.username) || DEFAULT_CALENDAR_FILTERS;
});
const [attendances, setAttendances] = useState({ items: [], total: 0 });
const [projects, setProjects] = useState([]);
const [collaborators, setCollaborators] = useState([]);
const [loadingAttendances, setLoadingAttendances] = useState(true);

useEffect(() => {
  apiService.getProjects({}, { skip: 0, limit: 1000 }).then((res) => setProjects(res.items || res));
  apiService.getCollaborators({}, { skip: 0, limit: 1000 }).then((res) => setCollaborators(res.items || res));
}, []);

useEffect(() => {
  let cancelled = false;
  setLoadingAttendances(true);
  const currentDate = new Date(filters.date);
  const rangeStart = moment(currentDate).startOf(filters.view === 'day' ? 'day' : filters.view === 'week' ? 'week' : 'month').toISOString();
  const rangeEnd = moment(currentDate).endOf(filters.view === 'day' ? 'day' : filters.view === 'week' ? 'week' : 'month').toISOString();

  apiService.getCalendarAttendances({
    startDate: rangeStart,
    endDate: rangeEnd,
    collaboratorIds: filters.collaboratorIds,
    projectIds: filters.projectIds,
    includeClosedProjects: filters.includeClosedProjects,
    onlyMine: filters.onlyMine,
  }).then((res) => {
    if (cancelled) return;
    setAttendances(res);
    setLoadingAttendances(false);
    window.history.replaceState({}, '', `?${filtersToParams(filters).toString()}`);
    savePersistedFilters(currentUser?.username, filters);
  });

  return () => { cancelled = true; };
}, [filters, currentUser?.username]);

const updateFilters = (partial) => setFilters((previous) => ({ ...previous, ...partial }));
const resetFilters = () => {
  setFilters(DEFAULT_CALENDAR_FILTERS);
  window.history.replaceState({}, '', window.location.pathname);
};
```

Nel JSX di rendering (prima del `<BigCalendar ...>` esistente, circa riga 500), inserisci:

```jsx
<CalendarFilterBar
  filters={filters}
  projects={projects}
  collaborators={collaborators}
  eventCount={attendances.total}
  onChange={updateFilters}
  onReset={resetFilters}
/>

{attendances.total > MAX_RENDERABLE_EVENTS ? (
  <div className="calendar-too-many-events">
    <p>Troppi eventi da mostrare ({attendances.total}): restringi i filtri per continuare.</p>
  </div>
) : (
  <BigCalendar
    /* ...props esistenti... */
    events={attendances.items.map(/* mapping esistente verso il formato BigCalendar, invariato */)}
    onNavigate={(date, view) => updateFilters({ date: date.toISOString(), view })}
    onView={(view) => updateFilters({ view })}
  />
)}
```

Nota: il mapping `attendances.items.map(...)` deve riusare esattamente la stessa logica di trasformazione presenza→evento BigCalendar già esistente nel file (oggi applicata su `attendances.data` letto da `useAppContext`) — sostituisci solo la sorgente dei dati (`attendances.items` invece di `state.attendances.data`), non la logica di mapping stessa.

- [x] **Step 4: Esegui e verifica che passi**

```bash
cd frontend && CI=true npx react-scripts test src/components/Calendar.test.js --watchAll=false
```

Atteso: `6 passed`.

- [x] **Step 5: Regressione frontend completa**

```bash
cd frontend && CI=true npx react-scripts test --watchAll=false
```

Atteso: nessuna regressione. Presta attenzione a `App.test.js` (mocka `./components/Calendar` come `() => <div>Calendario test</div>` — verificato, non risente delle modifiche interne) e a qualunque altro test che referenzi `state.attendances` in `AppContext` (nessuno trovato oltre a `Calendar.js` stesso).

- [x] **Step 6: Build produzione + redeploy per verifica manuale**

```bash
cd frontend && CI=true npm run build
cd .. && export DOCKER_CONFIG=/tmp/dockercfg && docker compose build frontend && docker compose up -d --force-recreate --no-deps frontend
```

- [x] **Step 7: Commit**

```bash
git add frontend/src/components/Calendar.js frontend/src/components/Calendar.test.js
git commit -m "feat(calendar): fetch server-side diretto con barra filtri, URL sync e localStorage"
```

---

### Task 7: Legenda colori — progetto o collaboratore a seconda della selezione multipla

**Files:**
- Modify: `frontend/src/components/Calendar.js` (righe 37-41 `PROJECT_COLORS`, 147-149 `getProjectColor`, 464-480 blocco legenda)

**Interfaces:**
- Consumes: `filters.projectIds`, `filters.collaboratorIds` (stato da Task 6).
- Produces: funzione locale `getColorDimension(filters) -> 'project' | 'collaborator'` e `getEntityColor(dimension, entityId) -> string` (sostituisce `getProjectColor`).

- [x] **Step 1: Scrivi il test che deve fallire**

Aggiungi a `frontend/src/components/Calendar.test.js` (Task 6):

```js
test('con più collaboratori selezionati e un solo progetto, la legenda mostra i collaboratori', async () => {
  window.history.replaceState({}, '', '/?collaborator_ids=10,11');
  apiService.getCalendarAttendances.mockResolvedValue({
    items: [
      { id: 1, collaborator_id: 10, project_id: 1, date: '2026-07-01T09:00:00', start_time: '2026-07-01T09:00:00', end_time: '2026-07-01T10:00:00', hours: 1 },
    ],
    total: 1,
  });
  render(<Calendar currentUser={CURRENT_USER} />);

  expect(await screen.findByText(/legenda: collaboratori/i)).toBeInTheDocument();
});

test('con più progetti selezionati la legenda mostra i progetti (default)', async () => {
  window.history.replaceState({}, '', '/?project_ids=1,2');
  render(<Calendar currentUser={CURRENT_USER} />);

  expect(await screen.findByText(/legenda: progetti/i)).toBeInTheDocument();
});
```

- [x] **Step 2: Esegui e verifica che fallisca**

```bash
cd frontend && CI=true npx react-scripts test src/components/Calendar.test.js --watchAll=false -t "legenda"
```

Atteso: 2 fallimenti (testo "Legenda: ..." non ancora presente/dinamico).

- [x] **Step 3: Implementa**

Sostituisci il blocco legenda esistente (righe 464-480) con logica che sceglie la dimensione:

```js
const colorDimension = filters.collaboratorIds.length > 1 && filters.projectIds.length <= 1
  ? 'collaborator'
  : 'project';

const legendEntities = colorDimension === 'collaborator'
  ? collaborators.filter((c) => filters.collaboratorIds.length === 0 || filters.collaboratorIds.includes(c.id))
  : projects.filter((p) => filters.projectIds.length === 0 || filters.projectIds.includes(p.id));

const getEntityColor = (dimension, entityId) => PROJECT_COLORS[entityId % PROJECT_COLORS.length];
```

```jsx
<div className="calendar-legend">
  <h4>Legenda: {colorDimension === 'collaborator' ? 'Collaboratori' : 'Progetti'}</h4>
  {legendEntities.map((entity) => (
    <div key={entity.id} className="legend-item">
      <span className="legend-swatch" style={{ background: getEntityColor(colorDimension, entity.id) }} />
      {colorDimension === 'collaborator' ? `${entity.first_name} ${entity.last_name}` : entity.name}
    </div>
  ))}
</div>
```

Il mapping eventi→BigCalendar (Task 6) deve usare `getEntityColor(colorDimension, colorDimension === 'collaborator' ? attendance.collaborator_id : attendance.project_id)` invece del vecchio `getProjectColor(attendance.project_id)` fisso, cosí i colori nel calendario corrispondono alla legenda corrente.

- [x] **Step 4: Esegui e verifica che passi**

```bash
cd frontend && CI=true npx react-scripts test src/components/Calendar.test.js --watchAll=false
```

Atteso: tutti i test del file verdi (8 totali con Task 6).

- [x] **Step 5: Commit**

```bash
git add frontend/src/components/Calendar.js frontend/src/components/Calendar.test.js
git commit -m "feat(calendar): legenda dinamica progetto/collaboratore in base alla selezione multipla"
```

---

### Task 8: Test di performance/correttezza su volume dati generato

**Files:**
- Test: `backend/tests/test_attendances_calendar_performance.py` (nuovo)

**Interfaces:**
- Consumes: `crud.get_attendances_calendar` (Task 1), endpoint `/api/v1/attendances/calendar` (Task 2).

- [x] **Step 1: Scrivi il test (nessun codice di produzione da toccare — è un test puro, non serve fase RED/GREEN separata perché non introduce comportamento nuovo, solo lo verifica sotto volume)**

```python
# backend/tests/test_attendances_calendar_performance.py
"""Correttezza e tempo di risposta di get_attendances_calendar con dataset
generato (migliaia di righe), non dati di produzione reali."""
import time
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import crud
import models
from database import Base

N_COLLABORATORS = 30
N_PROJECTS = 10
N_ATTENDANCES = 3000


@pytest.fixture(scope="module")
def seeded_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    collaborators = []
    for i in range(N_COLLABORATORS):
        c = models.Collaborator(first_name=f"Nome{i}", last_name=f"Cognome{i}", email=f"c{i}@test.it")
        db.add(c)
        collaborators.append(c)
    db.commit()

    projects = []
    for i in range(N_PROJECTS):
        p = models.Project(name=f"Progetto {i}", status="active", is_active=True)
        db.add(p)
        projects.append(p)
    db.commit()

    base_date = datetime(2026, 1, 1, 9, 0)
    for i in range(N_ATTENDANCES):
        collaborator = collaborators[i % N_COLLABORATORS]
        project = projects[i % N_PROJECTS]
        when = base_date + timedelta(hours=i)
        db.add(models.Attendance(
            collaborator_id=collaborator.id, project_id=project.id,
            date=when, start_time=when, end_time=when + timedelta(hours=1), hours=1,
        ))
    db.commit()

    yield db, collaborators, projects
    db.close()
    engine.dispose()


def test_conteggio_corretto_su_dataset_ampio_con_filtro_multi(seeded_db):
    db, collaborators, projects = seeded_db
    target_collaborators = [collaborators[0].id, collaborators[1].id]

    items, total = crud.get_attendances_calendar(
        db,
        collaborator_ids=target_collaborators,
        start_date=datetime(2026, 1, 1),
        end_date=datetime(2027, 1, 1),
        limit=50,
    )

    expected_total = sum(
        1 for i in range(N_ATTENDANCES)
        if collaborators[i % N_COLLABORATORS].id in target_collaborators
    )
    assert total == expected_total
    assert len(items) == 50


def test_tempo_risposta_ragionevole_su_dataset_ampio(seeded_db):
    db, _, _ = seeded_db
    start = time.monotonic()
    items, total = crud.get_attendances_calendar(
        db, start_date=datetime(2026, 1, 1), end_date=datetime(2027, 1, 1), limit=100,
    )
    elapsed = time.monotonic() - start

    assert total == N_ATTENDANCES
    assert elapsed < 2.0, f"Query troppo lenta su {N_ATTENDANCES} righe: {elapsed:.2f}s"
```

- [x] **Step 2: Esegui e verifica che passi (non c'è fase RED: la funzione esiste già da Task 1)**

```bash
docker cp backend/tests/test_attendances_calendar_performance.py pythonpro_backend:/app/tests/test_attendances_calendar_performance.py
docker exec pythonpro_backend pytest tests/test_attendances_calendar_performance.py -q --no-cov
```

Atteso: `2 passed`. Se il test di tempo fallisse per lentezza reale, tornare a Task 1 e verificare che gli indici esistenti vengano davvero usati (controllare `EXPLAIN QUERY PLAN` se serve) prima di aggiungere nuovi indici.

- [x] **Step 3: Commit**

```bash
git add backend/tests/test_attendances_calendar_performance.py
git commit -m "test(calendar): correttezza e tempo di risposta su dataset generato"
```

---

## Self-Review (copertura spec)

- **a) Barra filtri persistente**: Task 5/6 (progetto multi-selezione + toggle chiusi, collaboratore multi-selezione con ricerca, periodo via `onNavigate`/`onView` di BigCalendar già esistente, "azzera filtri" + contatore).
- **b) Comportamento**: URL sync (Task 4/6), localStorage per utente (Task 4/6), legenda dinamica (Task 7), soglia "troppi eventi" (Task 4 costante + Task 6 rendering condizionale).
- **c) Backend server-side**: Task 1/2 (mai fetch-tutto-e-filtra-in-browser), indici verificati esistenti (nessuna migrazione necessaria, documentato nei Global Constraints), paginazione (`skip`/`limit` + `total`).
- **d) RBAC**: ereditata automaticamente da `OPERATIONAL_PREFIXES` (nessun task dedicato necessario, verificato con test in Task 2); "solo i miei impegni" in Task 2/5/6.
- **e) Test**: filtri singoli/combinati (Task 1/2), multi-selezione collaboratori (Task 1/2/5/6), URL param (Task 4/6), performance con dataset generato (Task 8).

Nessun gap residuo individuato rispetto ai punti a-e della richiesta.
