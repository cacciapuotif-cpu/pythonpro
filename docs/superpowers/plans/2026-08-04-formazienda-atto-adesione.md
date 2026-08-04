# Formazienda — Atto di adesione (Allegato E) + Formulario (Allegato A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the "Nuovo progetto" wizard recognize Formazienda's grant documents (Allegato E = atto concessorio, Allegato A = formulario) as first-class alongside FAPI's convenzione, unblocking project creation and Delivery for Formazienda without breaking the FAPI perimeter-restricted flow.

**Architecture:** A small fund-declaration registry says what each fund's atto concessorio provides (ente sì/no, aziende sì/no). That declaration drives: (1) whether a project's Delivery step is unlocked, (2) whether the aziende picker is perimeter-restricted (FAPI, aziende come dalla convenzione) or free-catalog (Formazienda, nessuna azienda nell'atto). Two new parsers (pdfplumber-based, same style as `convenzione_parser.py`) feed a new `formazienda_upload.py` router that reuses the existing `documento_progetto` reconciliation layer and a document-archival helper extracted out of `convenzione_upload.py` so both routers share it.

**Tech Stack:** FastAPI, SQLAlchemy, pdfplumber, React (existing FapiUpload.js patterns), pytest, SQLite-in-memory tests (existing convention).

## Global Constraints

- Never invent data the document doesn't contain (`documento_progetto` docstring rule: "nessuna sovrascrittura silenziosa"). Empty field ⇒ `None`, not a guess.
- The two verified date traps must be handled by context, not by label alone:
  - Allegato E / Allegato A footer `Data approvazione: DD/MM/YYYY` (every page) = approval of the FORM/module by the fund's CDA, not of the plan. Never map this to `Project.delibera_data` / `data_approvazione`.
  - The plan's real approval date is the `delibera del DD/MM/YYYY` sentence in the Allegato E premises.
  - The signature/subscription date is the `Data DD/MM/YYYY` immediately followed by `Il dichiarante` / `Firma digitale in formato Pades` on the last page.
- Existing FAPI test suites (`test_project_delivery_scope.py`, `test_ux6b_*`, `test_ux6_documento_progetto_esistente.py`) must stay green — the perimeter/blocking behavior for FAPI (and any fund not explicitly declared "aziende non fornite") is unchanged.
- Real sample files live in the repo at `/DATA/progetti/pythonpro/imports/formazienda/ALLEGATO E.pdf` (4 pages) and `/DATA/progetti/pythonpro/imports/formazienda/ALLEGATO A.pdf` (42 pages, 14 imprese). Tests parse these files directly — no synthetic fixtures for the parsers.
- Fields with no extraction confidence or no DB column (RSA/RSU, welfare, dipendenti maschi/femmine/disabili, descrizione impresa, fabbisogno formativo) are surfaced in the preview payload only, never persisted — same "shown but not saved" convention already used for `_confronto_aziende`'s `dati_progetto_azienda_rappresentabili: False` in `convenzione_upload.py`.

---

## Task 1 — Fund declaration registry

**Files:**
- Create: `backend/services/atto_concessorio_registry.py`
- Test: `backend/tests/test_atto_concessorio_registry.py`

**Interfaces:**
- Produces: `FondoAttoConcessorio` dataclass (`fondo`, `tipo_documento`, `etichetta`, `fornisce_ente_attuatore`, `fornisce_aziende_beneficiarie`), `REGISTRY: dict[str, FondoAttoConcessorio]`, `for_ente_erogatore(ente_erogatore: str | None) -> FondoAttoConcessorio`, `fornisce_aziende_beneficiarie(ente_erogatore: str | None) -> bool`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_atto_concessorio_registry.py
from services.atto_concessorio_registry import for_ente_erogatore, fornisce_aziende_beneficiarie


def test_fapi_fornisce_aziende():
    voce = for_ente_erogatore("FAPI")
    assert voce.tipo_documento == "convenzione"
    assert voce.fornisce_aziende_beneficiarie is True
    assert fornisce_aziende_beneficiarie("FAPI") is True


def test_formazienda_non_fornisce_aziende():
    voce = for_ente_erogatore("Formazienda")
    assert voce.tipo_documento == "atto_concessione"
    assert voce.etichetta == "Atto di adesione (Allegato E)"
    assert voce.fornisce_ente_attuatore is True
    assert voce.fornisce_aziende_beneficiarie is False
    assert fornisce_aziende_beneficiarie("Formazienda") is False


def test_fondo_sconosciuto_o_assente_resta_prudente():
    # Nessuna dichiarazione = comportamento FAPI-like (perimetro), mai il contrario:
    # allargare l'accesso di default sarebbe la regressione pericolosa.
    assert fornisce_aziende_beneficiarie(None) is True
    assert fornisce_aziende_beneficiarie("Ente Mai Visto") is True


def test_fondimpresa_struttura_predisposta_non_attivata():
    voce = for_ente_erogatore("Fondimpresa")
    assert voce.tipo_documento == "atto_concessione"
    assert voce.fornisce_aziende_beneficiarie is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_atto_concessorio_registry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.atto_concessorio_registry'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/services/atto_concessorio_registry.py
"""Cosa fornisce l'atto concessorio di ciascun fondo.

Il flusso di Delivery presumeva che l'atto concessorio contenesse sempre
ente + aziende beneficiarie: vero per la convenzione FAPI, falso per
l'Atto di adesione Formazienda (Allegato E), che porta l'ente ma nessuna
azienda. Questa dichiarazione per fondo e' quello che guida lo sblocco
selettivo della Delivery, non un'assunzione fissa nel codice del router.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FondoAttoConcessorio:
    fondo: str
    tipo_documento: str
    etichetta: str
    fornisce_ente_attuatore: bool
    fornisce_aziende_beneficiarie: bool


REGISTRY: dict[str, FondoAttoConcessorio] = {
    "fapi": FondoAttoConcessorio(
        fondo="fapi",
        tipo_documento="convenzione",
        etichetta="Convenzione",
        fornisce_ente_attuatore=True,
        fornisce_aziende_beneficiarie=True,
    ),
    "formazienda": FondoAttoConcessorio(
        fondo="formazienda",
        tipo_documento="atto_concessione",
        etichetta="Atto di adesione (Allegato E)",
        fornisce_ente_attuatore=True,
        fornisce_aziende_beneficiarie=False,
    ),
    # Struttura predisposta su richiesta esplicita, senza campione del
    # documento e senza toccare il router fondimpresa_upload.py esistente
    # (che oggi non versiona documenti): nessun comportamento cambia per
    # Fondimpresa finche' non arriva un parser dedicato.
    "fondimpresa": FondoAttoConcessorio(
        fondo="fondimpresa",
        tipo_documento="atto_concessione",
        etichetta="Lettera di ammissione",
        fornisce_ente_attuatore=True,
        fornisce_aziende_beneficiarie=False,
    ),
}

_DEFAULT = FondoAttoConcessorio(
    fondo="altro",
    tipo_documento="convenzione",
    etichetta="Convenzione",
    fornisce_ente_attuatore=True,
    fornisce_aziende_beneficiarie=True,
)


def for_ente_erogatore(ente_erogatore: str | None) -> FondoAttoConcessorio:
    chiave = (ente_erogatore or "").strip().lower()
    return REGISTRY.get(chiave, _DEFAULT)


def fornisce_aziende_beneficiarie(ente_erogatore: str | None) -> bool:
    return for_ente_erogatore(ente_erogatore).fornisce_aziende_beneficiarie
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_atto_concessorio_registry.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/services/atto_concessorio_registry.py backend/tests/test_atto_concessorio_registry.py
git commit -m "feat(formazienda): declare per-fondo atto concessorio data availability"
```

---

## Task 2 — Generalize the "has grant document" gate to include `atto_concessione`

**Files:**
- Modify: `backend/crud.py:712-719` (`project_has_current_convenzione`)
- Test: `backend/tests/test_project_delivery_scope.py` (add one test), keep all existing ones green

**Interfaces:**
- Consumes: nothing new.
- Produces: `crud.project_has_current_convenzione(db, project_id) -> bool` now also true when the current document's `tipo_documento == "atto_concessione"`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_project_delivery_scope.py`:

```python
def test_atto_concessione_soddisfa_il_gate_al_pari_della_convenzione(client, db_session):
    ente = models.ImplementingEntity(ragione_sociale="Ente Formazienda", partita_iva="80000000009")
    db_session.add(ente)
    db_session.flush()
    project = models.Project(
        name="Piano Formazienda",
        ente_erogatore="Formazienda",
        ente_attuatore_id=ente.id,
        status="active",
        data_approvazione=date(2026, 1, 10),
        data_avvio_piano=date(2026, 2, 1),
    )
    db_session.add(project)
    db_session.flush()
    db_session.add(models.ProjectDocumento(
        project_id=project.id,
        tipo_documento="atto_concessione",
        versione=1,
        file_path="/tmp/atto-concessione.pdf",
        file_name="atto.pdf",
        stato="corrente",
        source_removed=False,
    ))
    db_session.commit()

    response = client.get(f"/api/v1/projects/{project.id}/delivery-context")
    assert response.status_code == 200, response.text
    assert response.json()["has_convenzione"] is True
    assert response.json()["blocked_reason"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_project_delivery_scope.py::test_atto_concessione_soddisfa_il_gate_al_pari_della_convenzione -v`
Expected: FAIL — `blocked_reason` is `"La convenzione collegata non identifica un ente attuatore"` or the has_convenzione is False, because the query only matches `tipo_documento == "convenzione"`.

- [ ] **Step 3: Write minimal implementation**

In `backend/crud.py`, replace:

```python
def project_has_current_convenzione(db: Session, project_id: int) -> bool:
    """La convenzione collegata e' il documento corrente, non il vecchio path libero."""
    return db.query(models.ProjectDocumento.id).filter(
        models.ProjectDocumento.project_id == project_id,
        models.ProjectDocumento.tipo_documento == "convenzione",
        models.ProjectDocumento.stato == "corrente",
        models.ProjectDocumento.source_removed.is_(False),
    ).first() is not None
```

with:

```python
def project_has_current_convenzione(db: Session, project_id: int) -> bool:
    """Il gate e' soddisfatto da un atto concessorio corrente, di qualunque fondo.

    FAPI usa ``convenzione``; Formazienda (e la struttura predisposta per
    Fondimpresa) usano ``atto_concessione``. Sono la stessa cosa vista da qui:
    l'atto che rende il progetto attuabile.
    """
    return db.query(models.ProjectDocumento.id).filter(
        models.ProjectDocumento.project_id == project_id,
        models.ProjectDocumento.tipo_documento.in_(["convenzione", "atto_concessione"]),
        models.ProjectDocumento.stato == "corrente",
        models.ProjectDocumento.source_removed.is_(False),
    ).first() is not None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_project_delivery_scope.py -v`
Expected: PASS, all tests in the file including the new one and the pre-existing ones.

- [ ] **Step 5: Commit**

```bash
git add backend/crud.py backend/tests/test_project_delivery_scope.py
git commit -m "fix(delivery): accept atto_concessione as a valid grant document gate"
```

---

## Task 3 — Selective Delivery unlock: free azienda selection when the fund declares no aziende

**Files:**
- Modify: `backend/crud.py:722-770` (`_validate_delivery_update`, azienda_ids branch)
- Modify: `backend/routers/projects.py:130-211` (`read_project_delivery_companies`, `read_project_delivery_company_students`)
- Test: `backend/tests/test_project_delivery_scope.py` (add tests)

**Interfaces:**
- Consumes: `services.atto_concessorio_registry.fornisce_aziende_beneficiarie(ente_erogatore)` from Task 1.
- Produces: same endpoint contracts (`ProjectDeliveryCompanyPage`, `ProjectDeliveryStudentPage`), branch on fund only.

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_project_delivery_scope.py`:

```python
def test_formazienda_aziende_selezionabili_dal_catalogo_globale(client, db_session):
    ente = models.ImplementingEntity(ragione_sociale="Ente Formazienda 2", partita_iva="80000000010")
    db_session.add(ente)
    db_session.flush()
    project = models.Project(
        name="Piano Formazienda 2",
        ente_erogatore="Formazienda",
        ente_attuatore_id=ente.id,
        status="active",
        data_approvazione=date(2026, 1, 10),
        data_avvio_piano=date(2026, 2, 1),
    )
    db_session.add(project)
    db_session.flush()
    db_session.add(models.ProjectDocumento(
        project_id=project.id, tipo_documento="atto_concessione", versione=1,
        file_path="/tmp/x.pdf", file_name="x.pdf", stato="corrente", source_removed=False,
    ))
    azienda = models.AziendaCliente(ragione_sociale="Catalogo Globale Srl", partita_iva="10000000099")
    db_session.add(azienda)
    db_session.commit()

    # Nessun link di perimetro esiste: la lista deve comunque proporre il
    # catalogo intero, non un elenco vuoto.
    listing = client.get(f"/api/v1/projects/{project.id}/delivery-companies")
    assert listing.status_code == 200, listing.text
    ids = {item["id"] for item in listing.json()["items"]}
    assert azienda.id in ids

    update = client.put(
        f"/api/v1/projects/{project.id}",
        json={
            "ente_attuatore_id": ente.id,
            "azienda_ids": [azienda.id],
            "allievo_ids": [],
            "azienda_sedi": [],
        },
    )
    assert update.status_code == 200, update.text

    students = client.get(f"/api/v1/projects/{project.id}/delivery-companies/{azienda.id}/students")
    assert students.status_code == 200, students.text
```

Also add a regression test confirming FAPI is untouched (it already exists as
`test_delivery_companies_esclude_fuori_perimetro_e_altro_progetto`; no new
test needed there, just keep it green).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_project_delivery_scope.py::test_formazienda_aziende_selezionabili_dal_catalogo_globale -v`
Expected: FAIL — `listing` returns an empty perimeter (no `AziendaClienteProjectLink` rows exist yet), so `azienda.id not in ids`; the PUT then 422s with "Aziende fuori dal perimetro della convenzione".

- [ ] **Step 3: Write minimal implementation**

In `backend/crud.py`, replace the `azienda_ids` branch inside `_validate_delivery_update`:

```python
    if "azienda_ids" in update_data:
        requested_ids = {int(item) for item in (update_data.get("azienda_ids") or [])}
        perimeter_rows = db.query(models.AziendaClienteProjectLink.azienda_cliente_id).filter(
            models.AziendaClienteProjectLink.project_id == db_project.id
        ).all()
        perimeter_ids = {row[0] for row in perimeter_rows}
        outside_ids = sorted(requested_ids - perimeter_ids)
        if outside_ids:
            raise DeliveryValidationError(
                "Aziende fuori dal perimetro della convenzione: "
                + ", ".join(str(item) for item in outside_ids)
            )
```

with:

```python
    if "azienda_ids" in update_data:
        from services.atto_concessorio_registry import fornisce_aziende_beneficiarie
        if fornisce_aziende_beneficiarie(db_project.ente_erogatore):
            requested_ids = {int(item) for item in (update_data.get("azienda_ids") or [])}
            perimeter_rows = db.query(models.AziendaClienteProjectLink.azienda_cliente_id).filter(
                models.AziendaClienteProjectLink.project_id == db_project.id
            ).all()
            perimeter_ids = {row[0] for row in perimeter_rows}
            outside_ids = sorted(requested_ids - perimeter_ids)
            if outside_ids:
                raise DeliveryValidationError(
                    "Aziende fuori dal perimetro della convenzione: "
                    + ", ".join(str(item) for item in outside_ids)
                )
        # Se il fondo non fornisce aziende beneficiarie (es. Formazienda),
        # l'atto non ha mai popolato un perimetro: la selezione avviene dal
        # catalogo globale, come un progetto senza convenzione FAPI.
```

In `backend/routers/projects.py`, `read_project_delivery_companies` — replace the perimeter-only query with a fund-aware branch:

```python
def read_project_delivery_companies(
    project_id: int,
    q: Optional[str] = Query(default=None, max_length=200),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """Aziende del perimetro progetto, o del catalogo globale se il fondo non ne dichiara."""
    project = _delivery_project_or_422(project_id, db)
    from services.atto_concessorio_registry import fornisce_aziende_beneficiarie

    query = db.query(models.AziendaCliente).options(
        selectinload(models.AziendaCliente.sedi_operative)
    ).filter(models.AziendaCliente.attivo.is_(True))

    if fornisce_aziende_beneficiarie(project.ente_erogatore):
        query = query.join(
            models.AziendaClienteProjectLink,
            models.AziendaClienteProjectLink.azienda_cliente_id == models.AziendaCliente.id,
        ).filter(models.AziendaClienteProjectLink.project_id == project_id)
    # Formazienda (e fondi che non dichiarano aziende): l'atto non porta un
    # perimetro, quindi la ricerca copre il catalogo intero, come un
    # progetto FAPI privo di convenzione userebbe se non fosse bloccato.

    normalized_q = (q or "").strip()
    if normalized_q:
        pattern = f"%{normalized_q}%"
        query = query.filter(or_(
            models.AziendaCliente.ragione_sociale.ilike(pattern),
            models.AziendaCliente.partita_iva.ilike(pattern),
        ))

    total = query.count()
    items = query.order_by(
        models.AziendaCliente.ragione_sociale.asc(),
        models.AziendaCliente.id.asc(),
    ).offset(offset).limit(limit).all()
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(items) < total,
    }
```

Note `_delivery_project_or_422` already returns the `models.Project` row (see its
signature at `routers/projects.py:71`) — reuse that return value instead of
discarding it.

For `read_project_delivery_company_students`, replace the perimeter guard:

```python
    """Allievi caricati soltanto on-demand per un'azienda nel perimetro."""
    project = _delivery_project_or_422(project_id, db)
    from services.atto_concessorio_registry import fornisce_aziende_beneficiarie
    if fornisce_aziende_beneficiarie(project.ente_erogatore):
        in_perimeter = db.query(models.AziendaClienteProjectLink.id).filter(
            models.AziendaClienteProjectLink.project_id == project_id,
            models.AziendaClienteProjectLink.azienda_cliente_id == azienda_id,
        ).first()
        if in_perimeter is None:
            raise HTTPException(
                status_code=404,
                detail="Azienda non presente nel perimetro del progetto",
            )
```

(keep the rest of the function — the `Allievo` query — unchanged).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_project_delivery_scope.py -v`
Expected: PASS, all tests (old perimeter tests for FAPI-like projects with no `ente_erogatore` still restrict correctly since `fornisce_aziende_beneficiarie(None)` is `True`).

- [ ] **Step 5: Commit**

```bash
git add backend/crud.py backend/routers/projects.py backend/tests/test_project_delivery_scope.py
git commit -m "feat(delivery): free azienda selection for funds whose atto declares no aziende"
```

---

## Task 4 — Extract shared document-archival helper

**Files:**
- Modify: `backend/services/documento_progetto.py` (add `archivia_documento_progetto`)
- Modify: `backend/routers/convenzione_upload.py:248-304` (`_archivia_documento` becomes a thin re-export)
- Test: existing `backend/tests/test_project_delivery_scope.py` imports `_archivia_documento` from `routers.convenzione_upload` — must keep working unchanged.

**Interfaces:**
- Produces: `documento_progetto.archivia_documento_progetto(db, *, project, preview, file_path, tipo_documento, current_user) -> models.ProjectDocumento` — identical body to today's `_archivia_documento`.
- Consumes (Task 6): the new `formazienda_upload.py` router calls this same function.

- [ ] **Step 1: Write the failing test**

```python
# add to backend/tests/test_project_delivery_scope.py, or a focused new test
def test_archivia_documento_progetto_e_importabile_da_documento_progetto_service():
    from services.documento_progetto import archivia_documento_progetto
    from routers.convenzione_upload import _archivia_documento
    assert archivia_documento_progetto is _archivia_documento
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_project_delivery_scope.py::test_archivia_documento_progetto_e_importabile_da_documento_progetto_service -v`
Expected: FAIL — `ImportError: cannot import name 'archivia_documento_progetto'`

- [ ] **Step 3: Write minimal implementation**

Add to `backend/services/documento_progetto.py` (needs `hashlib`, `logging`, and the
`models`/`write_audit_log` imports it doesn't have yet — add them at the top of the
file alongside the existing imports):

```python
import hashlib
import logging

import models
from services.audit_log import write_audit_log

logger = logging.getLogger(__name__)


def archivia_documento_progetto(
    db,
    *,
    project,
    preview: dict,
    file_path: str,
    tipo_documento: str,
    current_user,
):
    """Versiona e archivia un documento di progetto, per qualunque fondo.

    Estratta da ``convenzione_upload._archivia_documento`` cosi' che
    ``formazienda_upload.py`` e i futuri router per-fondo condividano la
    stessa regola di versionamento invece di duplicarla.
    """
    from sqlalchemy import func

    versione = (
        db.query(func.max(models.ProjectDocumento.versione))
        .filter(
            models.ProjectDocumento.project_id == project.id,
            models.ProjectDocumento.tipo_documento == tipo_documento,
        )
        .scalar()
        or 0
    ) + 1
    digest = None
    try:
        with open(file_path, "rb") as stream:
            digest = hashlib.sha256(stream.read()).hexdigest()
    except OSError:
        logger.warning("Impossibile calcolare SHA-256 del documento %s", file_path)

    documento = models.ProjectDocumento(
        project_id=project.id,
        tipo_documento=tipo_documento,
        versione=versione,
        file_path=file_path,
        file_name=preview.get("original_filename"),
        mime_type=preview.get("mime_type") or "application/pdf",
        sha256=digest,
        caricato_da_user_id=current_user.id,
    )
    db.add(documento)
    db.flush()
    if tipo_documento in {"convenzione", "atto_concessione", "delibera"}:
        project.convenzione_file_path = file_path
    write_audit_log(
        db,
        user_id=current_user.id,
        azione="documento_progetto_caricato",
        risorsa_tipo="project_document",
        risorsa_id=documento.id,
        dati_dopo={
            "project_id": project.id,
            "tipo_documento": tipo_documento,
            "versione": versione,
            "sha256": digest,
        },
    )
    return documento
```

In `backend/routers/convenzione_upload.py`, delete the body of `_archivia_documento`
(lines 248-304) and replace the whole function with a re-export so the existing
test import keeps working and every call site in this file is untouched:

```python
from services.documento_progetto import archivia_documento_progetto as _archivia_documento
```

Place this import near the top with the other `from services import ...` line, and
delete the old `def _archivia_documento(...):` block entirely (its call sites —
`confirm_convenzione` and `confirm_convenzione_progetto` — already call it as
`_archivia_documento(db, project=..., preview=..., file_path=..., tipo_documento=...,
current_user=...)`, matching the extracted function's signature exactly).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_project_delivery_scope.py tests/test_ux6b_bivio_convenzione.py tests/test_ux6_documento_progetto_esistente.py -v`
Expected: PASS — the re-export makes `_archivia_documento` identity-equal to the
new function, and all FAPI upload/confirm flows behave exactly as before since
the logic didn't change, only its location.

- [ ] **Step 5: Commit**

```bash
git add backend/services/documento_progetto.py backend/routers/convenzione_upload.py backend/tests/test_project_delivery_scope.py
git commit -m "refactor(documenti): share document archival across fund routers"
```

---

## Task 5 — Allegato E parser (Atto di adesione Formazienda)

**Files:**
- Create: `backend/services/parsers/formazienda/atto_adesione_parser.py`
- Test: `backend/tests/test_formazienda_atto_adesione_parser.py`

**Interfaces:**
- Produces: `parse_atto_adesione(pdf_path: str) -> dict[str, Any]` with the same
  shape family as `parse_convenzione`:

```python
{
    "piano": {
        "codice_fapi": None,          # Allegato E non ha un codice progetto FAPI-style
        "id_piano_esterno": "222-S2621",
        "titolo": "WHITE FORM",
        "avviso": "2/2022",
        "delibera_numero": None,      # non presente in Allegato E
        "delibera_data": "2026-06-11",
        "data_sottoscrizione": "2026-07-01",
        "quota_pubblica": 55440.0,
        "cofinanziamento": 0.0,
        "autofinanziamento": 55440.0,
        "costo_totale": 55440.0,      # quota_pubblica + cofinanziamento, coerente con CAMPI_DOCUMENTO
    },
    "ente_attuatore": {
        "ragione_sociale": "NEXT GROUP S.R.L.",
        "codice_fiscale": "06615351217",
        "partita_iva": "06615351217",
        "indirizzo": "VIA SANT'ASPRENO n. 13",
        "cap": "80133",
        "citta": "NAPOLI",
        "provincia": "NA",
        "legale_rappresentante_nome": "FRANCESCO",
        "legale_rappresentante_cognome": "CACCIAPUOTI",
        "legale_rappresentante_luogo_nascita": "NAPOLI",
        "legale_rappresentante_data_nascita": "1974-01-29",
        "legale_rappresentante_comune_residenza": "MUGNANO DI NAPOLI",
        "legale_rappresentante_via_residenza": "VIA DELLA CONCILIAZIONE n. 5",
    },
    "aziende_beneficiarie": [],   # Allegato E non le contiene mai
    "codici_progetto": [],
    "warnings": [...],
}
```

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_formazienda_atto_adesione_parser.py
from pathlib import Path

from services.parsers.formazienda.atto_adesione_parser import parse_atto_adesione

CAMPIONE = Path(__file__).parent.parent.parent / "imports" / "formazienda" / "ALLEGATO E.pdf"


def test_estrae_piano_e_avviso():
    result = parse_atto_adesione(str(CAMPIONE))
    piano = result["piano"]
    assert piano["id_piano_esterno"] == "222-S2621"
    assert piano["titolo"] == "WHITE FORM"
    assert piano["avviso"] == "2/2022"


def test_trappola_data_approvazione_usa_la_delibera_non_il_piede_di_pagina():
    result = parse_atto_adesione(str(CAMPIONE))
    # Il piede di pagina ripete "Data approvazione: 03/08/2022" su ogni
    # pagina (approvazione del MODULO). La data del PIANO e' la delibera
    # citata nelle premesse: 11/06/2026.
    assert result["piano"]["delibera_data"] == "2026-06-11"
    assert result["piano"]["delibera_data"] != "2022-08-03"


def test_trappola_sottoscrizione_e_la_firma_digitale_non_l_emissione():
    result = parse_atto_adesione(str(CAMPIONE))
    # 01/07/2026 = firma PAdES; 10/08/2022 = emissione del modulo (rev. 00).
    assert result["piano"]["data_sottoscrizione"] == "2026-07-01"


def test_importi_a_b_c():
    piano = parse_atto_adesione(str(CAMPIONE))["piano"]
    assert piano["quota_pubblica"] == 55440.0
    assert piano["cofinanziamento"] == 0.0
    assert piano["autofinanziamento"] == 55440.0
    assert piano["costo_totale"] == 55440.0


def test_ente_attuatore_e_legale_rappresentante():
    ente = parse_atto_adesione(str(CAMPIONE))["ente_attuatore"]
    assert ente["ragione_sociale"] == "NEXT GROUP S.R.L."
    assert ente["partita_iva"] == "06615351217"
    assert ente["codice_fiscale"] == "06615351217"
    assert ente["citta"] == "NAPOLI"
    assert ente["cap"] == "80133"
    assert ente["legale_rappresentante_cognome"] == "CACCIAPUOTI"
    assert ente["legale_rappresentante_nome"] == "FRANCESCO"
    assert ente["legale_rappresentante_luogo_nascita"] == "NAPOLI"
    assert ente["legale_rappresentante_data_nascita"] == "1974-01-29"
    assert ente["legale_rappresentante_comune_residenza"] == "MUGNANO DI NAPOLI"


def test_nessuna_azienda_beneficiaria_mai_inventata():
    result = parse_atto_adesione(str(CAMPIONE))
    assert result["aziende_beneficiarie"] == []
    assert result["codici_progetto"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_formazienda_atto_adesione_parser.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/services/parsers/formazienda/__init__.py
```
(empty file — package marker, mirrors `parsers/fapi/__init__.py` and `parsers/fondimpresa/__init__.py`)

```python
# backend/services/parsers/formazienda/atto_adesione_parser.py
"""Parser PDF per l'Atto di adesione Formazienda (Allegato E).

A differenza della convenzione FAPI, l'Allegato E non elenca mai aziende
beneficiarie ne' codici progetto: porta solo l'ente attuatore e i dati
del piano. Due trappole verificate sul documento reale:

1. Il piede di pagina ripete "Data approvazione: DD/MM/YYYY" su ogni
   pagina: e' l'approvazione del MODULO da parte del CDA (coincide con la
   tabella "Stato delle revisioni"), non l'approvazione del PIANO. La data
   del piano e' quella citata nelle premesse come "delibera del DD/MM/YYYY".
2. La data di sottoscrizione e' quella della firma digitale PAdES
   sull'ultima pagina, diversa sia dall'emissione del modulo sia dalla
   delibera: si riconosce dal contesto "Data DD/MM/YYYY" seguito da
   "Il dichiarante" / "Firma digitale", non dall'etichetta "Data" isolata.
"""
import re
from typing import Any

_RE_AVVISO = re.compile(r"Avviso\s+n\.?\s*(\d+/\d{4})", re.IGNORECASE)
_RE_ID_PIANO_TITOLO = re.compile(
    r"Piano Formativo ID\s+([A-Za-z0-9\-]+)\s+dal titolo\s+\"([^\"]+)\"",
    re.IGNORECASE,
)
_RE_DELIBERA_PIANO = re.compile(r"delibera del\s+(\d{1,2}/\d{1,2}/\d{4})", re.IGNORECASE)
_RE_IMPORTI = re.compile(
    r"A\s*-\s*Quota pubblica\s+B\s*-\s*Cofinanziamento\s+C\s*-\s*Autofinanziamento\s+"
    r"([\d.,]+)\s*€\s+([\d.,]+)\s*€\s+([\d.,]+)\s*€",
    re.IGNORECASE,
)
_RE_SOTTOSCRIZIONE = re.compile(
    r"Data\s+(\d{1,2}/\d{1,2}/\d{4})\s+Il dichiarante\s+Firma digitale",
    re.IGNORECASE,
)
_RE_ENTE_BLOCCO = re.compile(
    r"Il sottoscritto\s+(.+?)\s+nato\s+a\s+(.+?)\s+il\s+(\d{1,2}/\d{1,2}/\d{4})"
    r".*?residente in\s+(.+?)\s+Cap\s+\d{5}\s+Comune\s+(.+?)\s+Provincia\s+\S+"
    r".*?avente sede legale in\s+(.+?)\s+Cap\s+(\d{5})\s+Comune\s+(.+?)\s+Provincia\s+(\S+)"
    r".*?dell.{0,2}impresa\s+(.+?)\s+Codice Fiscale:\s*(\S+)\s+Partita IVA:\s*(\d{11})",
    re.IGNORECASE | re.DOTALL,
)


def _clean_importo(raw: str) -> float | None:
    try:
        return float(raw.strip().replace(".", "").replace(",", "."))
    except Exception:
        return None


def _parse_date(raw: str) -> str | None:
    try:
        d, m, y = re.split(r"[/\-.]", raw.strip())
        return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    except Exception:
        return None


def _split_cognome_nome(raw: str) -> tuple[str | None, str | None]:
    parti = raw.split()
    if len(parti) < 2:
        return (raw.strip() or None, None)
    return (" ".join(parti[:-1]), parti[-1])


def parse_atto_adesione(pdf_path: str) -> dict[str, Any]:
    warnings: list[str] = []

    try:
        import pdfplumber
    except ImportError:
        return {
            "piano": {}, "ente_attuatore": {}, "aziende_beneficiarie": [],
            "codici_progetto": [], "warnings": ["pdfplumber non disponibile"],
        }

    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages_text = [p.extract_text() or "" for p in pdf.pages]
    except Exception as exc:
        return {
            "piano": {}, "ente_attuatore": {}, "aziende_beneficiarie": [],
            "codici_progetto": [], "warnings": [f"Impossibile leggere PDF: {exc}"],
        }

    full_text = "\n".join(pages_text)
    flat = re.sub(r"\s+", " ", full_text)

    m = _RE_ID_PIANO_TITOLO.search(flat)
    id_piano_esterno = m.group(1) if m else None
    titolo = m.group(2) if m else None
    if not id_piano_esterno and not titolo:
        warnings.append("ID piano e titolo non trovati")

    m = _RE_AVVISO.search(flat)
    avviso = m.group(1) if m else None
    if not avviso:
        warnings.append("Avviso non trovato")

    m = _RE_DELIBERA_PIANO.search(flat)
    delibera_data = _parse_date(m.group(1)) if m else None
    if not delibera_data:
        warnings.append("Delibera di approvazione del piano non trovata nelle premesse")

    m = _RE_SOTTOSCRIZIONE.search(flat)
    data_sottoscrizione = _parse_date(m.group(1)) if m else None
    if not data_sottoscrizione:
        warnings.append("Data di sottoscrizione (firma digitale) non trovata")

    quota_pubblica = cofinanziamento = autofinanziamento = None
    m = _RE_IMPORTI.search(flat)
    if m:
        quota_pubblica = _clean_importo(m.group(1))
        cofinanziamento = _clean_importo(m.group(2))
        autofinanziamento = _clean_importo(m.group(3))
    else:
        warnings.append("Importi A/B/C non trovati")
    costo_totale = (
        (quota_pubblica or 0) + (cofinanziamento or 0)
        if quota_pubblica is not None or cofinanziamento is not None
        else None
    )

    ente_attuatore: dict[str, Any] = {}
    m = _RE_ENTE_BLOCCO.search(flat)
    if m:
        cognome_lr, nome_lr = _split_cognome_nome(m.group(1).strip())
        luogo_nascita = m.group(2).strip()
        data_nascita = _parse_date(m.group(3))
        via_residenza = m.group(4).strip()
        comune_residenza = m.group(5).strip()
        indirizzo = m.group(6).strip()
        cap = m.group(7).strip()
        citta = m.group(8).strip()
        provincia = m.group(9).strip()
        ragione_sociale = m.group(10).strip()
        codice_fiscale = m.group(11).strip()
        partita_iva = m.group(12).strip()
        ente_attuatore = {
            "ragione_sociale": ragione_sociale,
            "codice_fiscale": codice_fiscale,
            "partita_iva": partita_iva,
            "indirizzo": indirizzo,
            "cap": cap,
            "citta": citta,
            "provincia": provincia,
            "legale_rappresentante_nome": nome_lr,
            "legale_rappresentante_cognome": cognome_lr,
            "legale_rappresentante_luogo_nascita": luogo_nascita,
            "legale_rappresentante_data_nascita": data_nascita,
            "legale_rappresentante_comune_residenza": comune_residenza,
            "legale_rappresentante_via_residenza": via_residenza,
        }
    else:
        warnings.append("Ente attuatore (Soggetto Gestore) non trovato")

    return {
        "piano": {
            "codice_fapi": None,
            "id_piano_esterno": id_piano_esterno,
            "titolo": titolo,
            "avviso": avviso,
            "delibera_numero": None,
            "delibera_data": delibera_data,
            "data_sottoscrizione": data_sottoscrizione,
            "quota_pubblica": quota_pubblica,
            "cofinanziamento": cofinanziamento,
            "autofinanziamento": autofinanziamento,
            "costo_totale": costo_totale,
        },
        "ente_attuatore": ente_attuatore,
        "aziende_beneficiarie": [],
        "codici_progetto": [],
        "warnings": warnings,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_formazienda_atto_adesione_parser.py -v`
Expected: PASS (7 tests). If the ente-block regex doesn't match on the first try
(apostrophe/whitespace quirks from real PDF extraction), print
`repr(flat[flat.find("Il sottoscritto"):flat.find("Il sottoscritto")+600])` to see
the exact flattened text and adjust the regex to it — do not loosen it to the
point it could match garbage; keep every anchor from the real text.

- [ ] **Step 5: Commit**

```bash
git add backend/services/parsers/formazienda/ backend/tests/test_formazienda_atto_adesione_parser.py
git commit -m "feat(formazienda): parse Atto di adesione (Allegato E) with delibera/sottoscrizione trap handling"
```

---

## Task 6 — `formazienda_upload.py` router: Allegato E upload/confirm (create + associate)

**Files:**
- Create: `backend/routers/formazienda_upload.py`
- Modify: `backend/main.py` (register the new router — find how `convenzione_upload`/`fondimpresa_upload` routers are included and add the same line for this one)
- Test: `backend/tests/test_formazienda_upload.py`

**Interfaces:**
- Consumes: `services.parsers.formazienda.atto_adesione_parser.parse_atto_adesione`,
  `services.documento_progetto.archivia_documento_progetto` (Task 4),
  `services.documento_progetto.{confronta_dati, calcola_diff, applica_estratti, documento_riconosciuto}`,
  `services.atto_concessorio_registry.REGISTRY["formazienda"]`.
- Produces endpoints: `POST /api/v1/projects/formazienda/upload-atto-adesione`,
  `POST /api/v1/projects/formazienda/confirm-atto-adesione`,
  `POST /api/v1/projects/{project_id}/formazienda/upload-atto-adesione`,
  `POST /api/v1/projects/{project_id}/formazienda/confirm-atto-adesione`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_formazienda_upload.py
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from auth import get_current_user
from database import Base, get_db
from main import app
import models

CAMPIONE = Path(__file__).parent.parent / "imports" / "formazienda" / "ALLEGATO E.pdf"


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'formazienda_upload.db'}",
        connect_args={"check_same_thread": False},
    )
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: type(
        "TestUser", (), {"id": 1, "username": "op", "email": "op@example.com", "role": "admin", "is_active": True},
    )()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _upload(client):
    with open(CAMPIONE, "rb") as fh:
        return client.post(
            "/api/v1/projects/formazienda/upload-atto-adesione",
            files={"file": ("ALLEGATO E.pdf", fh, "application/pdf")},
        )


def test_upload_espone_ente_e_piano_senza_aziende(client):
    response = _upload(client)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["piano"]["titolo"] == "WHITE FORM"
    assert body["ente_attuatore"]["ragione_sociale"] == "NEXT GROUP S.R.L."
    assert body["aziende_beneficiarie"] == []


def test_confirm_crea_progetto_formazienda_con_ente_derivato_e_nessun_blocco(client, db_session):
    preview = _upload(client).json()
    response = client.post(
        "/api/v1/projects/formazienda/confirm-atto-adesione",
        json={"preview_token": preview["preview_token"], "data_avvio_piano": "2026-07-01"},
    )
    assert response.status_code == 200, response.text
    project_id = response.json()["project_id"]

    project = db_session.query(models.Project).get(project_id)
    assert project.ente_erogatore == "Formazienda"
    assert project.ente_attuatore is not None
    assert project.ente_attuatore.ragione_sociale == "NEXT GROUP S.R.L."
    assert project.ente_attuatore.legale_rappresentante_cognome == "CACCIAPUOTI"

    documento = db_session.query(models.ProjectDocumento).filter(
        models.ProjectDocumento.project_id == project_id,
    ).first()
    assert documento.tipo_documento == "atto_concessione"
    assert documento.stato == "corrente"

    context = client.get(f"/api/v1/projects/{project_id}/delivery-context")
    assert context.status_code == 200, context.text
    assert context.json()["blocked_reason"] is None
    assert context.json()["ente_attuatore"]["ragione_sociale"] == "NEXT GROUP S.R.L."


def test_documento_illeggibile_si_archivia_comunque_e_permette_inserimento_manuale(client, tmp_path):
    junk = tmp_path / "junk.pdf"
    junk.write_bytes(b"%PDF-1.4 not a real pdf")
    with open(junk, "rb") as fh:
        response = client.post(
            "/api/v1/projects/formazienda/upload-atto-adesione",
            files={"file": ("junk.pdf", fh, "application/pdf")},
        )
    # Il parser non deve esplodere: torna un risultato vuoto con warning,
    # l'operatore prosegue a mano (Punto 3e). L'endpoint non deve restituire 500.
    assert response.status_code == 200, response.text
    assert response.json()["ente_attuatore"] == {}
    assert len(response.json()["warnings"]) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_formazienda_upload.py -v`
Expected: FAIL with 404 (route doesn't exist yet).

- [ ] **Step 3: Write minimal implementation**

```python
# backend/routers/formazienda_upload.py
"""Router per upload e conferma dell'Atto di adesione Formazienda (Allegato E).

Stessa forma della convenzione FAPI (upload -> preview -> confirm crea/associa),
con una differenza di dominio non negoziabile: l'Allegato E non porta MAI
aziende beneficiarie. Aziende, sedi e allievi restano selezionabili a mano
nello Step Delivery (vedi crud._validate_delivery_update e
routers.projects.read_project_delivery_companies).
"""
import os
import shutil
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session

import models
import fapi_preview_store as _preview_store
from database import get_db
from auth import get_current_user, User
from services import date_progetto, documento_progetto
from services.parsers.formazienda.atto_adesione_parser import parse_atto_adesione

router = APIRouter(prefix="/api/v1/projects", tags=["formazienda-upload"])

UPLOAD_DIR = os.path.join(os.getenv("UPLOADS_DIR", "/app/uploads"), "formazienda", "atti_adesione")
os.makedirs(UPLOAD_DIR, exist_ok=True)


class ConfirmAttoAdesioneRequest(BaseModel):
    preview_token: str
    data_approvazione: date | None = None
    data_avvio_piano: date | None = None
    data_termine_piano: date | None = None
    data_avvio_attivita_formative: date | None = None
    data_fine_attivita_formative: date | None = None
    data_termine_rendicontazione: date | None = None
    data_chiusura_effettiva: date | None = None
    conferma_creazione_duplicato: bool = False


class AssociaAttoAdesioneRequest(BaseModel):
    preview_token: str
    campi_da_applicare: list[str] = []


def _salva_pdf(file: UploadFile, token: str) -> str:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File deve essere un PDF")
    dest = os.path.join(UPLOAD_DIR, f"{token}.pdf")
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return dest


def _find_ente_in_db(db: Session, piva: str | None, ragione_sociale: str | None):
    if piva:
        ente = db.query(models.ImplementingEntity).filter(
            models.ImplementingEntity.partita_iva == piva
        ).first()
        if ente:
            return ente
    if ragione_sociale:
        return db.query(models.ImplementingEntity).filter(
            models.ImplementingEntity.ragione_sociale.ilike(f"%{ragione_sociale[:20]}%")
        ).first()
    return None


def _get_or_create_ente(db: Session, ente_info: dict) -> models.ImplementingEntity | None:
    if not ente_info:
        return None
    ente = _find_ente_in_db(db, ente_info.get("partita_iva"), ente_info.get("ragione_sociale"))
    campi_ente = {
        "ragione_sociale": ente_info.get("ragione_sociale"),
        "partita_iva": ente_info.get("partita_iva"),
        "codice_fiscale": ente_info.get("codice_fiscale"),
        "indirizzo": ente_info.get("indirizzo"),
        "cap": ente_info.get("cap"),
        "citta": ente_info.get("citta"),
        "provincia": ente_info.get("provincia"),
        "legale_rappresentante_nome": ente_info.get("legale_rappresentante_nome"),
        "legale_rappresentante_cognome": ente_info.get("legale_rappresentante_cognome"),
        "legale_rappresentante_luogo_nascita": ente_info.get("legale_rappresentante_luogo_nascita"),
        "legale_rappresentante_comune_residenza": ente_info.get("legale_rappresentante_comune_residenza"),
        "legale_rappresentante_via_residenza": ente_info.get("legale_rappresentante_via_residenza"),
    }
    data_nascita = ente_info.get("legale_rappresentante_data_nascita")
    if data_nascita:
        campi_ente["legale_rappresentante_data_nascita"] = documento_progetto.parse_data(data_nascita)
    if ente is None:
        if not ente_info.get("partita_iva"):
            return None
        ente = models.ImplementingEntity(**{k: v for k, v in campi_ente.items() if v is not None})
        db.add(ente)
        db.flush()
        return ente
    # Arricchisce solo i campi vuoti: un ente gia' censito non viene ribaltato
    # da un parser, stessa regola non negoziabile di documento_progetto.
    for campo, valore in campi_ente.items():
        if valore is None:
            continue
        if not getattr(ente, campo, None):
            setattr(ente, campo, valore)
    return ente


def _estratti_progetto(preview: dict, ente, file_path: str) -> dict:
    piano = preview.get("piano") or {}
    return {
        "name": piano.get("titolo"),
        "id_piano_esterno": piano.get("id_piano_esterno"),
        "avviso": piano.get("avviso"),
        "delibera_data": piano.get("delibera_data"),
        "data_approvazione": piano.get("delibera_data"),
        "costo_totale": piano.get("costo_totale"),
        "contributo_ente": piano.get("quota_pubblica"),
        "cofinanziamento": piano.get("cofinanziamento"),
        "budget": piano.get("costo_totale"),
        "ente_attuatore_id": ente.id if ente else None,
        "convenzione_file_path": file_path,
    }


@router.post("/formazienda/upload-atto-adesione")
async def upload_atto_adesione(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    token = str(uuid.uuid4())
    dest = _salva_pdf(file, token)
    result = parse_atto_adesione(dest)

    ente_info = result.get("ente_attuatore") or {}
    db_ente = _find_ente_in_db(db, ente_info.get("partita_iva"), ente_info.get("ragione_sociale"))
    ente_info["exists_in_db"] = db_ente is not None
    ente_info["id"] = db_ente.id if db_ente else None

    _preview_store.store(token, {"file_path": dest, "original_filename": file.filename, **result})
    return {"preview_token": token, **result}


@router.post("/formazienda/confirm-atto-adesione")
def confirm_atto_adesione(
    body: ConfirmAttoAdesioneRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    preview = _preview_store.pop(body.preview_token)
    if not preview:
        raise HTTPException(status_code=404, detail="Preview token non trovato o scaduto")

    piano = preview.get("piano") or {}
    if not documento_progetto.documento_riconosciuto(
        {"codice_fapi": piano.get("id_piano_esterno"), "titolo": piano.get("titolo")}
    ):
        try:
            os.remove(preview["file_path"])
        except OSError:
            pass
        raise HTTPException(
            status_code=422,
            detail=(
                "Documento non riconosciuto come Atto di adesione: non e' stato "
                "estratto ne' l'ID del piano ne' il titolo. Se vuoi allegarlo a un "
                "progetto esistente, caricalo dalla scheda di quel progetto."
            ),
        )

    id_piano_esterno = piano.get("id_piano_esterno")
    if id_piano_esterno:
        existing = db.query(models.Project).filter(
            models.Project.id_piano_esterno == id_piano_esterno,
        ).first()
        if existing and not body.conferma_creazione_duplicato:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Progetto con ID piano {id_piano_esterno} gia' esistente "
                    f"(id={existing.id}). Per creare un secondo progetto serve "
                    "la conferma esplicita della duplicazione."
                ),
            )

    try:
        date_progetto.valida_date_progetto(
            {**body.model_dump(), "status": "active"},
            richiedi_date_nuovo_attivo=True,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    file_path = preview["file_path"]
    ente = _get_or_create_ente(db, preview.get("ente_attuatore") or {})

    project = models.Project(
        name=piano.get("titolo") or f"Piano Formazienda {id_piano_esterno or ''}".strip(),
        ente_erogatore="Formazienda",
        ente_attuatore_id=ente.id if ente else None,
        id_piano_esterno=id_piano_esterno,
        avviso=piano.get("avviso"),
        delibera_data=documento_progetto.parse_data(piano.get("delibera_data")),
        costo_totale=piano.get("costo_totale"),
        contributo_ente=piano.get("quota_pubblica"),
        cofinanziamento=piano.get("cofinanziamento"),
        convenzione_file_path=file_path,
        status="active",
        budget=piano.get("costo_totale"),
        data_approvazione=body.data_approvazione or documento_progetto.parse_data(piano.get("delibera_data")),
        data_avvio_piano=body.data_avvio_piano,
        data_termine_piano=body.data_termine_piano,
        data_avvio_attivita_formative=body.data_avvio_attivita_formative,
        data_fine_attivita_formative=body.data_fine_attivita_formative,
        data_termine_rendicontazione=body.data_termine_rendicontazione,
        data_chiusura_effettiva=body.data_chiusura_effettiva,
    )
    db.add(project)
    db.flush()

    documento = documento_progetto.archivia_documento_progetto(
        db,
        project=project,
        preview=preview,
        file_path=file_path,
        tipo_documento="atto_concessione",
        current_user=current_user,
    )
    db.commit()

    return {
        "project_id": project.id,
        "id_piano_esterno": id_piano_esterno,
        "documento_id": documento.id,
        "documento_versione": documento.versione,
    }


@router.post("/{project_id}/formazienda/upload-atto-adesione")
async def upload_atto_adesione_progetto(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Progetto non trovato")

    token = str(uuid.uuid4())
    dest = _salva_pdf(file, token)
    result = parse_atto_adesione(dest)

    ente_info = result.get("ente_attuatore") or {}
    db_ente = _find_ente_in_db(db, ente_info.get("partita_iva"), ente_info.get("ragione_sociale"))
    estratti = _estratti_progetto(result, db_ente, dest)
    diff = documento_progetto.calcola_diff(project, estratti)

    _preview_store.store(token, {
        "project_id": project_id, "file_path": dest, "original_filename": file.filename, **result,
    })
    return {"preview_token": token, "project_id": project_id, "diff": diff, **result}


@router.post("/{project_id}/formazienda/confirm-atto-adesione")
def confirm_atto_adesione_progetto(
    project_id: int,
    body: AssociaAttoAdesioneRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Progetto non trovato")

    preview = _preview_store.pop(body.preview_token)
    if not preview:
        raise HTTPException(status_code=404, detail="Preview token non trovato o scaduto")
    if preview.get("project_id") != project_id:
        raise HTTPException(status_code=400, detail="Token non appartiene a questo progetto")

    file_path = preview["file_path"]
    ente = _get_or_create_ente(db, preview.get("ente_attuatore") or {})
    esito = documento_progetto.applica_estratti(
        project, _estratti_progetto(preview, ente, file_path), body.campi_da_applicare,
    )
    project.ente_erogatore = project.ente_erogatore or "Formazienda"
    documento = documento_progetto.archivia_documento_progetto(
        db, project=project, preview=preview, file_path=file_path,
        tipo_documento="atto_concessione", current_user=current_user,
    )
    db.commit()

    return {
        "project_id": project.id,
        "documento_id": documento.id,
        "documento_versione": documento.versione,
        **esito,
    }
```

Register the router in `backend/main.py`: find the line that includes
`convenzione_upload.router` (search `app.include_router(convenzione_upload`) and add
immediately after it:

```python
from routers import formazienda_upload
app.include_router(formazienda_upload.router)
```

(match whatever import style `main.py` already uses for `convenzione_upload` — some
of these routers are imported at the top with the rest, some inline; follow the
existing convention in that file rather than introducing a new one.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_formazienda_upload.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/routers/formazienda_upload.py backend/main.py backend/tests/test_formazienda_upload.py
git commit -m "feat(formazienda): upload/confirm Atto di adesione creates or enriches a project"
```

---

## Task 7 — Frontend: real Formazienda modal replaces the PlaceholderDocumentModal

**Files:**
- Modify: `frontend/src/services/apiService.js` (add Formazienda upload/confirm functions, mirroring lines 1305-1328)
- Modify: `frontend/src/components/FapiUpload.js` (new `AttoAdesioneFormaziendaModal`, wire it into `NuovoPianoModal`'s `atto-formazienda` card and into `FapiUploadSection`'s `isFormazienda` branch, replacing `PlaceholderDocumentModal`)
- Test: `frontend/src/components/FapiUpload.test.js` (add coverage for the new modal)

**Interfaces:**
- Consumes: Task 6 endpoints via new `apiService` functions
  `uploadAttoAdesioneFormazienda`, `confirmAttoAdesioneFormazienda`,
  `uploadAttoAdesioneFormaziendaProgetto`, `confirmAttoAdesioneFormaziendaProgetto`
  (same 4-function shape as the Fondimpresa pair at
  `apiService.js:1306-1328`).

- [ ] **Step 1: Write the failing test**

Check the existing `frontend/src/components/FapiUpload.test.js` for its current
test style first (it exists per the earlier codebase map) and add a test in the
same style:

```javascript
// add to frontend/src/components/FapiUpload.test.js
import { uploadAttoAdesioneFormazienda, confirmAttoAdesioneFormazienda } from '../services/apiService';

jest.mock('../services/apiService');

test('carica atto adesione Formazienda e crea il progetto senza passare dal placeholder', async () => {
  uploadAttoAdesioneFormazienda.mockResolvedValue({
    preview_token: 'tok-1',
    piano: { titolo: 'WHITE FORM', id_piano_esterno: '222-S2621', avviso: '2/2022' },
    ente_attuatore: { ragione_sociale: 'NEXT GROUP S.R.L.', partita_iva: '06615351217', exists_in_db: false },
    aziende_beneficiarie: [],
    warnings: [],
  });
  confirmAttoAdesioneFormazienda.mockResolvedValue({ project_id: 42 });

  // ... render FapiUploadSection with project=null, autoOpenConvenzione,
  // autoOpenMode="new-piano"; click the "Formazienda" card in NuovoPianoModal;
  // drop a fake File into the dropzone; assert uploadAttoAdesioneFormazienda
  // was called and the confirm button eventually calls confirmAttoAdesioneFormazienda,
  // NOT that a "flusso backend specifico non ancora disponibile" warning appears.
});
```

(Match this to whatever render/testing-library helpers the existing
`FapiUpload.test.js` file already imports and uses — read that file first and
follow its exact setup so the new test is consistent with the others in it.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx jest FapiUpload.test.js -t "atto adesione Formazienda"`
Expected: FAIL — `uploadAttoAdesioneFormazienda` doesn't exist in `apiService.js`
yet and the `atto-formazienda` modal is still the placeholder.

- [ ] **Step 3: Write minimal implementation**

In `frontend/src/services/apiService.js`, add after the Fondimpresa block
(after line 1328, before `export { apiService };`):

```javascript
// ── Formazienda document upload ───────────────────────────────────────────
export const uploadAttoAdesioneFormazienda = (file) => {
  const fd = new FormData();
  fd.append('file', file);
  return http.post('/projects/formazienda/upload-atto-adesione', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data);
};
export const confirmAttoAdesioneFormazienda = (previewToken, options = {}) =>
  http.post('/projects/formazienda/confirm-atto-adesione', {
    preview_token: previewToken,
    ...options,
  }).then(r => r.data);

// UX-6: dalla scheda di un progetto l'atto si ALLEGA al progetto aperto.
export const uploadAttoAdesioneFormaziendaProgetto = (projectId, file) => {
  const fd = new FormData();
  fd.append('file', file);
  return http.post(`/projects/${projectId}/formazienda/upload-atto-adesione`, fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data);
};
export const confirmAttoAdesioneFormaziendaProgetto = (projectId, previewToken, campiDaApplicare = []) =>
  http.post(`/projects/${projectId}/formazienda/confirm-atto-adesione`, {
    preview_token: previewToken,
    campi_da_applicare: campiDaApplicare,
  }).then(r => r.data);
```

In `frontend/src/components/FapiUpload.js`:

1. Add the new imports at the top, alongside the Fondimpresa ones:

```javascript
  uploadAttoAdesioneFormazienda, confirmAttoAdesioneFormazienda,
  uploadAttoAdesioneFormaziendaProgetto, confirmAttoAdesioneFormaziendaProgetto,
```

2. Add a new modal component, modeled directly on `AmmissioneFondimpresaModal`
   (lines 1005-1084) since both are "atto senza aziende" — but skip
   `DiffProgetto`'s azienda-diff assumptions since none apply, and add the
   explicit "nessuna azienda nel documento" hint the spec requires:

```javascript
function AttoAdesioneFormaziendaModal({ projectId, onClose, onSuccess }) {
  const {
    associa, step, preview, error, campiScelti, handleFile, handleConfirm, toggleCampo,
  } = useDocumentoProgetto({
    projectId,
    upload: uploadAttoAdesioneFormazienda,
    uploadProgetto: uploadAttoAdesioneFormaziendaProgetto,
    conferma: confirmAttoAdesioneFormazienda,
    confermaProgetto: confirmAttoAdesioneFormaziendaProgetto,
  });
  const [dataAvvioPiano, setDataAvvioPiano] = useState('');

  async function creaProgetto() {
    await handleConfirm(onSuccess, {
      createPayload: { data_avvio_piano: dataAvvioPiano || undefined },
    });
  }

  return (
    <div className="fapi-modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="fapi-modal">
        <h3>
          {associa ? '📄 Allega Atto di adesione al progetto' : '📄 Carica Atto di adesione (Formazienda)'}
        </h3>
        {associa && <NotaAssociazione />}
        {error && <div className="fapi-error">⚠️ {error}</div>}
        {step === 'pick' && (
          <DropZone accept=".pdf" onFile={handleFile} label="Trascina o clicca per selezionare l'Atto di adesione PDF" />
        )}
        {step === 'uploading' && (
          <div style={{ textAlign: 'center', padding: '2rem', fontSize: 13 }}>⏳ Parsing del PDF…</div>
        )}
        {(step === 'preview' || step === 'confirming') && preview && (
          <div className="fapi-preview">
            {preview.warnings?.map((w, i) => <div key={i} className="fapi-warning">⚠️ {w}</div>)}
            {associa && (
              <DiffProgetto diff={preview.diff} campiScelti={campiScelti} onToggle={toggleCampo} />
            )}
            <div className="fapi-preview-section">
              <strong>Piano Formazienda</strong>
              <table>
                <tbody>
                  <tr><td>ID Piano</td><td>{preview.piano?.id_piano_esterno || '—'}</td></tr>
                  <tr><td>Titolo</td><td>{preview.piano?.titolo || '—'}</td></tr>
                  <tr><td>Avviso</td><td>{preview.piano?.avviso || '—'}</td></tr>
                  <tr><td>Delibera (approvazione piano)</td><td>{preview.piano?.delibera_data || '—'}</td></tr>
                  <tr><td>Sottoscrizione</td><td>{preview.piano?.data_sottoscrizione || '—'}</td></tr>
                  <tr><td>A - Quota pubblica</td><td>{formatEuro(preview.piano?.quota_pubblica)}</td></tr>
                  <tr><td>B - Cofinanziamento</td><td>{formatEuro(preview.piano?.cofinanziamento)}</td></tr>
                  <tr><td>C - Autofinanziamento</td><td>{formatEuro(preview.piano?.autofinanziamento)}</td></tr>
                </tbody>
              </table>
            </div>
            <div className="fapi-preview-section">
              <strong>Ente Attuatore</strong>
              <table>
                <tbody>
                  <tr>
                    <td>{preview.ente_attuatore?.ragione_sociale || '—'}</td>
                    <td>P.IVA {preview.ente_attuatore?.partita_iva || '—'}</td>
                    <td>
                      {preview.ente_attuatore?.exists_in_db
                        ? <span className="badge-exists">Nel sistema</span>
                        : <span className="badge-new">Nuovo</span>}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div className="fapi-domain-note">
              L'Atto di adesione non elenca aziende beneficiarie: aziende, sedi e
              allievi restano da selezionare a mano nello Step Delivery del progetto.
            </div>
            {!associa && (
              <div className="fapi-preview-section fapi-confirm-metadata">
                <strong>Date amministrative</strong>
                <label>
                  Data avvio piano
                  <input
                    aria-label="Data avvio piano"
                    type="date"
                    value={dataAvvioPiano}
                    onChange={event => setDataAvvioPiano(event.target.value)}
                  />
                </label>
              </div>
            )}
          </div>
        )}
        {step === 'done' && preview?._result && (
          <div className="fapi-success">
            {associa ? (
              <EsitoAssociazione result={preview._result} />
            ) : (
              <>✅ Progetto Formazienda creato — ID: <strong>{preview._result.project_id}</strong></>
            )}
          </div>
        )}
        <div className="fapi-modal-footer">
          <button className="fapi-btn" onClick={onClose}>{step === 'done' ? 'Chiudi' : 'Annulla'}</button>
          {step === 'preview' && (
            <button
              className="fapi-btn primary"
              onClick={associa ? () => handleConfirm(onSuccess) : creaProgetto}
            >
              {associa ? '✅ Allega al progetto' : '✅ Conferma e Crea Progetto'}
            </button>
          )}
          {step === 'confirming' && (
            <button className="fapi-btn primary" disabled>⏳ Operazione in corso…</button>
          )}
        </div>
      </div>
    </div>
  );
}
```

3. In `NuovoPianoModal`, the `atto-formazienda` card's `key` already routes to
   `modal === 'atto-formazienda'` — no change needed there, only to what that
   modal key renders.

4. In `FapiUploadSection`, replace the placeholder block:

```javascript
      {!isMobile && modal === 'atto-formazienda' && (
        <PlaceholderDocumentModal
          title="🏢 Carica Atto adesione Formazienda"
          label="Trascina o clicca per selezionare l'atto adesione PDF"
          confirmLabel="✅ Conferma documento"
          doneMessage="✅ Documento acquisito in anteprima. Prosegui con il wizard/manuale operativo."
          onClose={() => { setModal(null); onAutoClose && onAutoClose(); }}
          onSuccess={() => { setModal(null); onAutoClose && onAutoClose(); onRefresh && onRefresh(); }}
        />
      )}
```

with:

```javascript
      {!isMobile && modal === 'atto-formazienda' && (
        <AttoAdesioneFormaziendaModal
          projectId={project?.id}
          onClose={() => { setModal(null); onAutoClose && onAutoClose(); }}
          onSuccess={() => {
            setDocumentRefreshKey(value => value + 1);
            onAutoClose && onAutoClose();
            onRefresh && onRefresh();
          }}
        />
      )}
```

5. In the `isFormazienda` button block (around line 1298-1307), the button
   already calls `setModal('atto-formazienda')` for the primary document — no
   change needed there either.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx jest FapiUpload.test.js`
Expected: PASS, including the new test and all pre-existing ones in the file.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/services/apiService.js frontend/src/components/FapiUpload.js frontend/src/components/FapiUpload.test.js
git commit -m "feat(formazienda): replace placeholder Atto di adesione modal with real upload/confirm flow"
```

---

## Task 8 — Frontend: Delivery step copy reflects the fund, no behavior change for FAPI

**Files:**
- Modify: `frontend/src/components/ProjectManager.js:1030-1036` (the `field-hint` text under `ProjectDeliveryCompanyPicker`)

**Interfaces:** none new — pure copy branch on `formData.ente_erogatore`.

- [ ] **Step 1: Write the failing test**

If `ProjectManager.test.js` exists with a delivery-step render test, add:

```javascript
test('mostra il messaggio di ricerca libera per Formazienda invece del perimetro convenzione', () => {
  // arrange formData.ente_erogatore = 'Formazienda', deliveryContext senza blocked_reason
  // assert screen.getByText(/l'atto di adesione non elenca beneficiarie/i) is present
  // and the FAPI-only copy ("La ricerca usa soltanto le aziende comprese nella convenzione")
  // is absent.
});
```

If no such test file/harness exists for this component yet, skip the automated
test for this cosmetic step and verify manually via `run` (see Task 9) — do not
invent a testing setup that doesn't already exist in the repo for this file.

- [ ] **Step 2: Run test to verify it fails** (only if Step 1 added a test)

- [ ] **Step 3: Write minimal implementation**

Replace:

```jsx
                          <small className="field-hint">
                            La ricerca usa soltanto le aziende comprese nella convenzione del progetto.
                            Gli allievi vengono caricati quando apri la singola azienda.
                          </small>
```

with:

```jsx
                          <small className="field-hint">
                            {formData.ente_erogatore === 'Formazienda'
                              ? "L'atto di adesione non elenca beneficiarie: la ricerca usa l'intero catalogo aziende."
                              : 'La ricerca usa soltanto le aziende comprese nella convenzione del progetto.'}
                            {' '}Gli allievi vengono caricati quando apri la singola azienda.
                          </small>
```

- [ ] **Step 4: Run test to verify it passes** (if applicable)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ProjectManager.js
git commit -m "ui(formazienda): clarify aziende search is catalog-wide, not convenzione-perimeter"
```

---

## Task 9 — End-to-end verification of Allegato E (manual, real backend)

No new files. This is the "prova che funziona" checkpoint for the Allegato E half
of the task before moving to Allegato A.

- [ ] Start the backend and frontend per this project's `run` skill / existing dev
      scripts (check `STATUS.md` / `CLAUDE.md` for the current start command — do
      not invent one).
- [ ] In the browser: "Nuovo progetto" → "Carica Atto / Convenzione" → Formazienda
      card → upload `imports/formazienda/ALLEGATO E.pdf` → confirm. Verify:
  - Ente attuatore shown = NEXT GROUP S.R.L., no "Non disponibile".
  - No residual block message in the Delivery step.
  - Aziende picker lets you pick from the whole catalog, not an empty list.
  - Project is created successfully end to end (aziende/sedi/allievi optional,
    save succeeds).
- [ ] Open the created project's document list: the PDF appears as tipo
      `atto_concessione`, versione 1, with uploader name/date.
- [ ] Create/open a FAPI project with a convenzione: confirm aziende are still
      proposed from the document (no regression) and the picker is still
      perimeter-restricted.
- [ ] Upload a non-PDF or corrupted file as Atto di adesione: confirm it still
      gets processed (warnings shown, no 500) and manual entry remains possible.
- [ ] Record the outcome of all six checks from the user's spec in `STATUS.md`
      and `REMEDIATION_LOG.md` (see Task 13 for exact format), before starting
      Task 10.

---

## Task 10 — Allegato A parser: soggetto gestore / delegato / partner (Sezione 1)

**Files:**
- Create: `backend/services/parsers/formazienda/formulario_parser.py`
- Test: `backend/tests/test_formazienda_formulario_parser.py`

**Interfaces:**
- Produces (this task): `parse_formulario(pdf_path: str) -> dict[str, Any]` with
  at least the `sezione1` keys populated:

```python
{
    "piano": {"titolo": "WHITE FORM", "tipologia": "Territoriale",
              "tematiche": ["Gestione aziendale, amministrazione"]},
    "soggetto_gestore": {
        "ragione_sociale": "NEXT GROUP S.R.L.", "codice_fiscale": "06615351217",
        "partita_iva": "06615351217", "indirizzo": "VIA SANT'ASPRENO n. 13",
        "cap": "80133", "citta": "NAPOLI", "provincia": "NA",
        "telefono": "08119464696", "email": "gciccarelli8@gmail.com",
        "pec": "omniservizi@legalmail.it",
        "legale_rappresentante_cognome": "CACCIAPUOTI", "legale_rappresentante_nome": "FRANCESCO",
    },
    "soggetto_delegato": {
        "ragione_sociale": "A.M.D. S.R.L.", "codice_fiscale": "06296751214",
        "partita_iva": "06296751214", "legale_rappresentante_cognome": "BRUSCINO",
        "legale_rappresentante_nome": "DINO MARIA", "tipologia": "Altro",
        "importo": 14000.0, "percentuale": 25.25,
    },
    "soggetti_partner": [],
    "imprese_beneficiarie": [],   # popolato in Task 11
    "progetti_formativi": [],     # popolato in Task 12
    "riepilogo": {},              # popolato in Task 13
    "warnings": [...],
}
```

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_formazienda_formulario_parser.py
from pathlib import Path

from services.parsers.formazienda.formulario_parser import parse_formulario

CAMPIONE = Path(__file__).parent.parent.parent / "imports" / "formazienda" / "ALLEGATO A.pdf"


def test_titolo_e_tipologia_piano():
    result = parse_formulario(str(CAMPIONE))
    assert result["piano"]["titolo"] == "WHITE FORM"
    assert result["piano"]["tipologia"] == "Territoriale"


def test_soggetto_gestore_non_e_beneficiaria():
    result = parse_formulario(str(CAMPIONE))
    gestore = result["soggetto_gestore"]
    assert gestore["ragione_sociale"] == "NEXT GROUP S.R.L."
    assert gestore["partita_iva"] == "06615351217"
    assert gestore["legale_rappresentante_cognome"] == "CACCIAPUOTI"
    nomi_beneficiarie = [imp.get("ragione_sociale") for imp in result["imprese_beneficiarie"]]
    assert "NEXT GROUP S.R.L." not in nomi_beneficiarie


def test_soggetto_delegato_con_importo_e_percentuale():
    delegato = parse_formulario(str(CAMPIONE))["soggetto_delegato"]
    assert delegato["ragione_sociale"] == "A.M.D. S.R.L."
    assert delegato["partita_iva"] == "06296751214"
    assert delegato["importo"] == 14000.0
    assert delegato["percentuale"] == 25.25


def test_soggetti_partner_vuoto_non_fallisce():
    result = parse_formulario(str(CAMPIONE))
    assert result["soggetti_partner"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_formazienda_formulario_parser.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/services/parsers/formazienda/formulario_parser.py
"""Parser PDF per il Formulario di candidatura Formazienda (Allegato A).

Complementare all'Atto di adesione (Allegato E): l'Allegato E porta l'ente
e gli importi approvati, l'Allegato A porta le imprese beneficiarie, il
progetto formativo e le macrovoci di dettaglio. Nessuno dei due basta da
solo (vedi atto_adesione_parser.py per le trappole sulle date, identiche
qui: il piede di pagina "Data approvazione" e' del MODULO, non del piano).
"""
import re
from typing import Any

_RE_TITOLO_PIANO = re.compile(r"I\.1\.\s*Titolo Piano Formativo\s*\n(.+)")
_RE_TIPOLOGIA_PIANO = re.compile(r"I\.2\.\s*Tipologia Piano Formativo\s*\n(.+)")
_RE_TEMATICHE = re.compile(r"I\.3\.\s*Tematiche di intervento\s*\n((?:•.+\n?)+)")

_RE_ANAGRAFICA = re.compile(
    r"Ragione sociale\s+(.+?)\s*\n"
    r"Sede legale in\s+(.+?)\s+Cap\s+(\d{5})\s+Citt[aà]\s+(.+?)\s+Prov\.\s+(\S+)\s*\n"
    r"Tel\.\s*(\S*)\s*\n"
    r"eMail\s*(\S*)\s*Pec\s*(\S*)\s*\n"
    r"Codice Fiscale\s+(\S+)\s+Partita IVA\s+(\d{11})\s*\n"
    r"Legale rappresentante\s*\([^)]*\)\s*:\s*(.+?)\s*\n",
    re.IGNORECASE,
)

_RE_DELEGA_TIPOLOGIA = re.compile(r"Tipologia Soggetto Delegato\s*\n(.+)")
_RE_DELEGA_IMPORTO = re.compile(
    r"Importo attivit[aà] in delega\s+([\d.,]+)\s*€\s+([\d.,]+)\s*%",
    re.IGNORECASE,
)


def _clean_importo(raw: str) -> float | None:
    try:
        return float(raw.strip().replace(".", "").replace(",", "."))
    except Exception:
        return None


def _clean_pct(raw: str) -> float | None:
    try:
        return float(raw.strip().replace(",", "."))
    except Exception:
        return None


def _parse_anagrafica_blocco(testo: str) -> dict[str, Any] | None:
    m = _RE_ANAGRAFICA.search(testo)
    if not m:
        return None
    legale = m.group(11).strip()
    parti = legale.split()
    cognome, nome = (" ".join(parti[:-1]), parti[-1]) if len(parti) >= 2 else (legale, None)
    return {
        "ragione_sociale": m.group(1).strip(),
        "indirizzo": m.group(2).strip(),
        "cap": m.group(3).strip(),
        "citta": m.group(4).strip(),
        "provincia": m.group(5).strip(),
        "telefono": m.group(6).strip() or None,
        "email": m.group(7).strip() or None,
        "pec": m.group(8).strip() or None,
        "codice_fiscale": m.group(9).strip(),
        "partita_iva": m.group(10).strip(),
        "legale_rappresentante_cognome": cognome,
        "legale_rappresentante_nome": nome,
    }


def parse_formulario(pdf_path: str) -> dict[str, Any]:
    warnings: list[str] = []
    try:
        import pdfplumber
    except ImportError:
        return {"warnings": ["pdfplumber non disponibile"], "imprese_beneficiarie": [],
                "soggetti_partner": [], "progetti_formativi": [], "riepilogo": {}}

    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages_text = [p.extract_text() or "" for p in pdf.pages]
    except Exception as exc:
        return {"warnings": [f"Impossibile leggere PDF: {exc}"], "imprese_beneficiarie": [],
                "soggetti_partner": [], "progetti_formativi": [], "riepilogo": {}}

    full_text = "\n".join(pages_text)

    # Sezione 1 termina all'inizio della Sezione 2: e' il confine che tiene
    # separati Soggetto Gestore/Delegato dalle imprese beneficiarie (trappola
    # #1 e #2 del campione: nessuno dei due e' una beneficiaria).
    idx_sezione2 = full_text.find("Sezione 2.")
    sezione1 = full_text[: idx_sezione2 if idx_sezione2 != -1 else len(full_text)]

    piano: dict[str, Any] = {}
    m = _RE_TITOLO_PIANO.search(sezione1)
    piano["titolo"] = m.group(1).strip() if m else None
    m = _RE_TIPOLOGIA_PIANO.search(sezione1)
    piano["tipologia"] = m.group(1).strip() if m else None
    m = _RE_TEMATICHE.search(sezione1)
    piano["tematiche"] = (
        [riga.lstrip("•").strip() for riga in m.group(1).strip().splitlines() if riga.strip()]
        if m else []
    )
    if not piano["titolo"]:
        warnings.append("Titolo piano non trovato in Sezione 1")

    idx_gestore = sezione1.find("I.4.")
    idx_delega = sezione1.find("I.5.")
    idx_partner = sezione1.find("I.6.")
    blocco_gestore = sezione1[idx_gestore:idx_delega] if idx_gestore != -1 else ""
    blocco_delega = sezione1[idx_delega:idx_partner] if idx_delega != -1 and idx_partner != -1 else ""

    soggetto_gestore = _parse_anagrafica_blocco(blocco_gestore) or {}
    if not soggetto_gestore:
        warnings.append("Soggetto Gestore non trovato in I.4")

    soggetto_delegato: dict[str, Any] = {}
    dati_delega = _parse_anagrafica_blocco(blocco_delega)
    if dati_delega:
        soggetto_delegato = dict(dati_delega)
        m = _RE_DELEGA_TIPOLOGIA.search(blocco_delega)
        soggetto_delegato["tipologia"] = m.group(1).strip() if m else None
        m = _RE_DELEGA_IMPORTO.search(sezione1)
        if m:
            soggetto_delegato["importo"] = _clean_importo(m.group(1))
            soggetto_delegato["percentuale"] = _clean_pct(m.group(2))
        else:
            soggetto_delegato["importo"] = None
            soggetto_delegato["percentuale"] = None
            warnings.append("Importo/percentuale del soggetto delegato non trovati (I.5.2)")
    # I.6 Soggetti Terzi Partner: nel campione e' vuoto. Nessun blocco
    # "Ragione sociale" tra I.6 e la fine della Sezione 1 = nessun partner,
    # non un errore di parsing (trappola #6-stile: campo assente e' vuoto).
    soggetti_partner: list[dict[str, Any]] = []

    return {
        "piano": piano,
        "soggetto_gestore": soggetto_gestore,
        "soggetto_delegato": soggetto_delegato,
        "soggetti_partner": soggetti_partner,
        "imprese_beneficiarie": [],
        "progetti_formativi": [],
        "riepilogo": {},
        "warnings": warnings,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_formazienda_formulario_parser.py -v`
Expected: PASS (4 tests). If `_RE_ANAGRAFICA` doesn't match on the real text
(line-wrap or spacing differences), dump
`repr(blocco_gestore[:400])` in a throwaway `print` during a local run to see
the exact text and adjust the regex to match it literally — keep every anchor,
don't loosen to a catch-all.

- [ ] **Step 5: Commit**

```bash
git add backend/services/parsers/formazienda/formulario_parser.py backend/tests/test_formazienda_formulario_parser.py
git commit -m "feat(formazienda): parse formulario Sezione 1 (gestore/delegato/partner)"
```

---

## Task 11 — Allegato A parser: imprese beneficiarie (Sezione 2)

**Files:**
- Modify: `backend/services/parsers/formazienda/formulario_parser.py`
- Test: `backend/tests/test_formazienda_formulario_parser.py` (extend)

**Interfaces:**
- Produces: `parse_formulario(...)["imprese_beneficiarie"]`, a list of 14 dicts
  (for the sample file), each shaped:

```python
{
    "ragione_sociale": "PAKI UNITED FOREVER S.R.L.S.",
    "indirizzo": "VIA VICINALE FARINA n. 12/E", "cap": "80056",
    "citta": "ERCOLANO", "provincia": "NAPOLI",
    "telefono": None, "email": None, "pec": None,
    "codice_fiscale": "08951911216", "partita_iva": "08951911216",
    "matricola_inps": "5138462742", "codice_ateco": "38.21.40",
    "legale_rappresentante_cognome": "IACOMINO", "legale_rappresentante_nome": "RAFFAELE",
    "classe_dimensionale": "micro",
    "regime_aiuti": "de_minimis",
    "stato_adesione_data": "2025-12-01", "stato_adesione_periodo": "2025/12",
    "descrizione_impresa": "...", "descrizione_impresa_da_verificare": False,
    "ccnl": None, "rsa_rsu": False,
    "numero_dipendenti_totale": 6, "numero_dipendenti_maschi": 0,
    "numero_dipendenti_femmine": 0, "numero_dipendenti_disabili": 0,
    "welfare": None, "fabbisogno_formativo": "...",
}
```

- [ ] **Step 1: Write the failing test**

```python
# extend backend/tests/test_formazienda_formulario_parser.py

def test_quattordici_imprese_beneficiarie_con_dati_reali():
    imprese = parse_formulario(str(CAMPIONE))["imprese_beneficiarie"]
    assert len(imprese) == 14
    ragioni = {imp["ragione_sociale"] for imp in imprese}
    assert "PAKI UNITED FOREVER S.R.L.S." in ragioni
    assert "NEXT GROUP S.R.L." not in ragioni
    assert "A.M.D. S.R.L." not in ragioni

    paki = next(imp for imp in imprese if imp["ragione_sociale"] == "PAKI UNITED FOREVER S.R.L.S.")
    assert paki["partita_iva"] == "08951911216"
    assert paki["codice_fiscale"] == "08951911216"
    assert paki["matricola_inps"] == "5138462742"
    assert paki["codice_ateco"] == "38.21.40"
    assert paki["classe_dimensionale"] == "micro"
    assert paki["regime_aiuti"] == "de_minimis"
    assert paki["legale_rappresentante_cognome"] == "IACOMINO"
    assert paki["numero_dipendenti_totale"] == 6


def test_ditta_individuale_cf_personale_diverso_da_piva():
    imprese = parse_formulario(str(CAMPIONE))["imprese_beneficiarie"]
    pama = next(imp for imp in imprese if imp["ragione_sociale"] == "PAMA DI GUARRACINO MARIANNA")
    assert pama["codice_fiscale"] == "GRRMNN01C70C291M"
    assert pama["partita_iva"] == "04800950612"
    assert pama["codice_fiscale"] != pama["partita_iva"]


def test_campi_vuoti_non_fanno_fallire_il_parser():
    imprese = parse_formulario(str(CAMPIONE))["imprese_beneficiarie"]
    paki = next(imp for imp in imprese if imp["ragione_sociale"] == "PAKI UNITED FOREVER S.R.L.S.")
    assert paki["telefono"] is None
    assert paki["ccnl"] is None
    assert paki["welfare"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_formazienda_formulario_parser.py -k imprese -v`
Expected: FAIL — `imprese_beneficiarie` is still hardcoded to `[]`.

- [ ] **Step 3: Write minimal implementation**

Add to `formulario_parser.py`, and call it from `parse_formulario` replacing the
hardcoded `"imprese_beneficiarie": []`:

```python
_RE_MATRICOLA = re.compile(r"Matricola/e Inps\s+(\S+)")
_RE_ATECO = re.compile(r"Codice Ateco\(Istat \d{4}\)\s+(\S+)")
_RE_STATO_ADESIONE = re.compile(
    r"Aderente a Formazienda dal\s+(\d{1,2}/\d{1,2}/\d{4})\s*-\s*periodo di competenza:\s*(\S+)",
)
_RE_DESCRIZIONE_IMPRESA = re.compile(
    r"II\.5\.[^\n]*\nDescrivere[^\n]*\n(.*?)(?=II\.6\.)", re.DOTALL,
)
_RE_FABBISOGNO = re.compile(
    r"II\.10\.[^\n]*\nDescrivere[^\n]*\n(.*?)(?=Data approvazione:|===|\Z)", re.DOTALL,
)
_RE_CCNL_BODY = re.compile(
    r"II\.6\.[^\n]*\nIndicare[^\n]*\n(.*?)(?=II\.7\.)", re.DOTALL,
)
_RE_WELFARE_BODY = re.compile(
    r"II\.9\.[^\n]*\nSpecificare[^\n]*\n(.*?)(?=II\.10\.)", re.DOTALL,
)
_RE_DIPENDENTI = re.compile(
    r"Numero totale dipendenti:\s*(\d+)\s*"
    r"Di cui maschi:\s*(\d+)\s*"
    r"Di cui femmine:\s*(\d+)\s*"
    r"Di cui con disabilit[aà][^:]*:\s*(\d+)",
)


def _classe_dimensionale(blocco: str) -> str | None:
    for etichetta, chiave in (("☑ Micro", "micro"), ("☑ Piccola", "piccola"),
                              ("☑ Media", "media"), ("☑ Grande", "grande")):
        if etichetta in blocco:
            return chiave
    return None


def _regime_aiuti(blocco: str) -> str | None:
    idx_651 = blocco.find("651/2014")
    idx_minimis = blocco.find("de minimis")
    if idx_651 != -1:
        # Il checkbox del regime 651/2014 sta sulla riga precedente al testo
        # dell'articolo (trappola di layout: checkbox prima dell'etichetta
        # completa, che va a capo). Cerca "☑" prima di "651/2014" nello stesso
        # paragrafo, non altrove nel blocco.
        finestra = blocco[max(0, idx_651 - 80):idx_651]
        if "☑" in finestra:
            return "aiuti_stato_formazione_651_2014"
    if idx_minimis != -1:
        finestra = blocco[idx_minimis:idx_minimis + 80]
        if "☑" in finestra:
            return "de_minimis"
    return None


def _rsa_rsu(blocco: str) -> bool | None:
    idx = blocco.find("Presenza RSA/RSU")
    if idx == -1:
        return None
    finestra = blocco[idx:idx + 60]
    if re.search(r"☑\s*S[iì]", finestra):
        return True
    if re.search(r"☑\s*No", finestra):
        return False
    return None


def _clean_testo_libero(raw: str | None) -> str | None:
    if raw is None:
        return None
    testo = raw.strip()
    if not testo or testo.startswith("II."):
        return None
    return testo


def _parse_imprese_beneficiarie(sezione2: str, warnings: list[str]) -> list[dict[str, Any]]:
    # I blocchi si riconoscono dalla ripetizione di "II.1. Anagrafica impresa",
    # non da un'intestazione univoca (trappola #3): ogni impresa riusa la
    # stessa numerazione II.1...II.10.
    marcatori = [m.start() for m in re.finditer(r"II\.1\.\s*Anagrafica impresa", sezione2)]
    blocchi = [
        sezione2[inizio: (marcatori[i + 1] if i + 1 < len(marcatori) else len(sezione2))]
        for i, inizio in enumerate(marcatori)
    ]

    imprese = []
    for blocco in blocchi:
        anagrafica = _parse_anagrafica_blocco(blocco)
        if not anagrafica:
            warnings.append("Blocco impresa non riconosciuto in Sezione 2 (anagrafica illeggibile)")
            continue
        m = _RE_MATRICOLA.search(blocco)
        anagrafica["matricola_inps"] = m.group(1) if m else None
        m = _RE_ATECO.search(blocco)
        anagrafica["codice_ateco"] = m.group(1) if m else None
        anagrafica["classe_dimensionale"] = _classe_dimensionale(blocco)
        anagrafica["regime_aiuti"] = _regime_aiuti(blocco)
        anagrafica["rsa_rsu"] = _rsa_rsu(blocco)

        m = _RE_STATO_ADESIONE.search(blocco)
        if m:
            d, mo, y = m.group(1).split("/")
            anagrafica["stato_adesione_data"] = f"{y}-{mo.zfill(2)}-{d.zfill(2)}"
            anagrafica["stato_adesione_periodo"] = m.group(2)
        else:
            anagrafica["stato_adesione_data"] = None
            anagrafica["stato_adesione_periodo"] = None

        m = _RE_CCNL_BODY.search(blocco)
        anagrafica["ccnl"] = _clean_testo_libero(m.group(1)) if m else None
        m = _RE_WELFARE_BODY.search(blocco)
        anagrafica["welfare"] = _clean_testo_libero(m.group(1)) if m else None

        m = _RE_DIPENDENTI.search(blocco)
        if m:
            anagrafica["numero_dipendenti_totale"] = int(m.group(1))
            anagrafica["numero_dipendenti_maschi"] = int(m.group(2))
            anagrafica["numero_dipendenti_femmine"] = int(m.group(3))
            anagrafica["numero_dipendenti_disabili"] = int(m.group(4))
        else:
            anagrafica["numero_dipendenti_totale"] = None
            anagrafica["numero_dipendenti_maschi"] = None
            anagrafica["numero_dipendenti_femmine"] = None
            anagrafica["numero_dipendenti_disabili"] = None

        m = _RE_DESCRIZIONE_IMPRESA.search(blocco)
        descrizione = _clean_testo_libero(m.group(1).replace("\n", " ")) if m else None
        # Trappola #8: dati spazzatura (es. una sola lettera) non scartano
        # l'impresa, ma vanno segnalati per verifica.
        anagrafica["descrizione_impresa"] = descrizione
        anagrafica["descrizione_impresa_da_verificare"] = bool(
            descrizione is not None and len(descrizione.strip()) < 15
        )
        if anagrafica["descrizione_impresa_da_verificare"]:
            warnings.append(
                f"Descrizione impresa da verificare per {anagrafica['ragione_sociale']}: troppo corta"
            )

        m = _RE_FABBISOGNO.search(blocco)
        anagrafica["fabbisogno_formativo"] = (
            _clean_testo_libero(m.group(1).replace("\n", " ")) if m else None
        )

        imprese.append(anagrafica)

    if not imprese:
        warnings.append("Nessuna impresa beneficiaria trovata in Sezione 2")
    return imprese
```

Then in `parse_formulario`, before building the return dict, add:

```python
    idx_sezione3 = full_text.find("Sezione 3.")
    sezione2 = full_text[idx_sezione2:idx_sezione3] if idx_sezione2 != -1 and idx_sezione3 != -1 else ""
    imprese_beneficiarie = _parse_imprese_beneficiarie(sezione2, warnings)
```

and replace `"imprese_beneficiarie": []` with `"imprese_beneficiarie": imprese_beneficiarie`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_formazienda_formulario_parser.py -v`
Expected: PASS (7 tests). This is the highest-value/highest-risk regex set in
the whole plan — if any of `_RE_CCNL_BODY` / `_RE_WELFARE_BODY` /
`_RE_DESCRIZIONE_IMPRESA` / `_RE_FABBISOGNO` don't match due to page-break
artifacts (the real text has `=== PAGE N ===`-style joins removed, but page
footers `Data approvazione: ... \nFondo Formazienda` are still inline — see
Task 5's note on those), print the actual `blocco` text for one company and
adjust the lookahead boundaries to match reality rather than guessing twice.

- [ ] **Step 5: Commit**

```bash
git add backend/services/parsers/formazienda/formulario_parser.py backend/tests/test_formazienda_formulario_parser.py
git commit -m "feat(formazienda): parse 14 imprese beneficiarie from formulario Sezione 2"
```

---

## Task 12 — Allegato A parser: progetto formativo + macrovoci + cronoprogramma (Sezione 3-4)

**Files:**
- Modify: `backend/services/parsers/formazienda/formulario_parser.py`
- Test: `backend/tests/test_formazienda_formulario_parser.py` (extend)

**Interfaces:**
- Produces: `parse_formulario(...)["progetti_formativi"]` (list of 1 dict for
  the sample) and `parse_formulario(...)["riepilogo"]`:

```python
"progetti_formativi": [{
    "numero": "1", "titolo": "OPERATORE SEGRETARIALE",
    "tipologia_formativa": "Formazione Base e Trasversale",
    "tematica": "Gestione aziendale, amministrazione",
    "ore_formazione": 24.0, "edizioni": 14,
    "soggetto_erogatore": "NEXT GROUP S.R.L.",
    "regioni": ["Campania", "Lazio", "Veneto"],
    "province": ["Caserta", "Napoli", "Roma", "Verona"],
    "modalita_attuazione": [
        {"tipo": "aula", "ore": 14.0, "percentuale": 58.33},
        {"tipo": "training_on_job", "ore": 10.0, "percentuale": 41.67},
    ],
    "costo_numero_edizioni": 14, "costo_partecipanti_minimo": 1,
    "costo_finanziamento_per_edizione": 3960.0, "costo_totale": 55440.0,
    "quadratura_costo_ok": True,
}],
"riepilogo": {
    "finanziamento_totale": 55440.0,
    "destinatari_totale": 14,
    "costo_complessivo": 55440.0, "quota_pubblica": 55440.0, "quota_privata": 0.0,
    "cronoprogramma": {
        "durata_giorni": 180,
        "attivita": [
            {"nome": "Avvio Piano Formativo", "mese": 5, "anno": 2026},
            {"nome": "Gestione Piano Formativo", "mese": 5, "anno": 2026},
            {"nome": "Chiusura Piano Formativo", "mese": 1, "anno": 2027},
            {"nome": "Presentazione Rendicontazione", "mese": 3, "anno": 2027},
        ],
    },
    "macrovoci": [
        {"codice": "A", "importo": 11088.0, "percentuale": 20.0, "limite_max_pct": 20},
        {"codice": "B", "importo": 27720.0, "percentuale": 50.0, "limite_max_pct": None},
        {"codice": "C", "importo": 16632.0, "percentuale": 30.0, "limite_max_pct": 30},
        {"codice": "D", "importo": 0.0, "percentuale": 0.0, "limite_max_pct": None},
    ],
    "totale_preventivo": 55440.0, "contributo_richiesto": 55440.0, "cofinanziamento": 0.0,
    "quadratura_macrovoci_ok": True,
    "quadratura_finanziamento_per_impresa_ok": True,
},
```

- [ ] **Step 1: Write the failing test**

```python
# extend backend/tests/test_formazienda_formulario_parser.py

def test_progetto_formativo_ore_edizioni_e_modalita():
    progetti = parse_formulario(str(CAMPIONE))["progetti_formativi"]
    assert len(progetti) == 1
    progetto = progetti[0]
    assert progetto["titolo"] == "OPERATORE SEGRETARIALE"
    assert progetto["ore_formazione"] == 24.0
    assert progetto["edizioni"] == 14
    assert progetto["modalita_attuazione"] == [
        {"tipo": "aula", "ore": 14.0, "percentuale": 58.33},
        {"tipo": "training_on_job", "ore": 10.0, "percentuale": 41.67},
    ]


def test_quadratura_costo_progetto():
    progetto = parse_formulario(str(CAMPIONE))["progetti_formativi"][0]
    # 14 edizioni x 3.960,00 = 55.440,00 = totale dichiarato
    assert progetto["quadratura_costo_ok"] is True


def test_macrovoci_e_quadratura():
    riepilogo = parse_formulario(str(CAMPIONE))["riepilogo"]
    macrovoci = {m["codice"]: m for m in riepilogo["macrovoci"]}
    assert macrovoci["A"]["importo"] == 11088.0
    assert macrovoci["A"]["limite_max_pct"] == 20
    assert macrovoci["C"]["limite_max_pct"] == 30
    assert riepilogo["quadratura_macrovoci_ok"] is True
    assert riepilogo["quadratura_finanziamento_per_impresa_ok"] is True


def test_cronoprogramma_mese_anno_senza_giorno():
    cronoprogramma = parse_formulario(str(CAMPIONE))["riepilogo"]["cronoprogramma"]
    assert cronoprogramma["durata_giorni"] == 180
    avvio = next(a for a in cronoprogramma["attivita"] if a["nome"] == "Avvio Piano Formativo")
    assert avvio == {"nome": "Avvio Piano Formativo", "mese": 5, "anno": 2026}
    # Nessun giorno inventato: la chiave "giorno" non deve esistere.
    assert "giorno" not in avvio
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_formazienda_formulario_parser.py -k "progetto_formativo or quadratura or macrovoci or cronoprogramma" -v`
Expected: FAIL — `progetti_formativi` and `riepilogo` are still empty/hardcoded.

- [ ] **Step 3: Write minimal implementation**

Add to `formulario_parser.py`:

```python
_RE_PROGETTO_TITOLO = re.compile(r"Titolo\s+(.+?)\s*\nTipologia formativa")
_RE_PROGETTO_TIPOLOGIA = re.compile(r"Tipologia formativa di\s*\n?\s*intervento\s*\n(.+)")
_RE_PROGETTO_TEMATICA = re.compile(r"Tematica\s+(.+)")
_RE_PROGETTO_ORE = re.compile(r"n\.\s*ore di formazione\s*\n(\d+(?:[.,]\d+)?)\s*ore")
_RE_PROGETTO_EDIZIONI = re.compile(r"n\.\s*edizioni\s+(\d+)")
_RE_SOGGETTO_EROGATORE = re.compile(r"Soggetto Erogatore\s+Ragione sociale:\s*(.+)")
_RE_REGIONI = re.compile(r"Regioni:\s*(.+)")
_RE_PROVINCE = re.compile(r"Province:\s*(.+)")
_RE_MODALITA_RIGHE = re.compile(
    r"(Aula|Training on the job)\s+(\d+(?:[.,]\d+)?)\s+(\d+(?:[.,]\d+)?)\s*%",
)
_RE_COSTO_PROGETTO = re.compile(
    r"Costo del progetto.*?\n(?:.*\n)*?(\d+)\s+(\d+)\s+([\d.,]+)\s*€\s*\n"
    r"Totale\s+(\d+)\s+\d+\s+([\d.,]+)\s*€",
)

_RE_CRONO_DURATA = re.compile(r"Durata in giorni del\s*\nPiano Formativo\s+(\d+)")
_RE_CRONO_ATTIVITA = re.compile(
    r"(Avvio Piano Formativo|Gestione Piano Formativo|Chiusura Piano Formativo|"
    r"Presentazione Rendicontazione)\s+(\d{2})\s+(\d{4})",
)
_RE_MACROVOCE_TOTALE = re.compile(
    r"Totale Macrovoce ([ABCD])\.\s+([\d.,]+)\s*€\s+([\d.,]+)\s*€\s+(\d+(?:[.,]\d+)?)\s*%",
)
_RE_MACROVOCE_LIMITE = {
    "A": re.compile(r"Macrovoce A\..*?max\s*(\d+)%", re.DOTALL),
    "C": re.compile(r"Macrovoce C\..*?max\s*(\d+)%", re.DOTALL),
}
_RE_FINANZIAMENTO_TOTALE_PROGETTI = re.compile(r"TOTALE\s+([\d.,]+)\s*€")
_RE_DESTINATARI_TOTALE = re.compile(r"4\.3\..*?TOTALE\s+(\d+)", re.DOTALL)
_RE_COSTO_COMPLESSIVO = re.compile(r"Costo complessivo del Piano Formativo\s+([\d.,]+)\s*€")
_RE_QUOTA_PUBBLICA = re.compile(r"Quota finanziamento pubblico\s+([\d.,]+)\s*€")
_RE_QUOTA_PRIVATA = re.compile(r"Quota cofinanziamento privato\s+([\d.,]+)\s*€")
_RE_RIEPILOGO_IMPRESA_RIGA = re.compile(
    r"([A-Z0-9À-Ü][A-Z0-9À-Ü .&'\-]+?)\s+([A-Z0-9]{11,16})\s+(Micro|Piccola|Media|Grande)\s+"
    r"([\d.,]+)\s*€\s+([\d.,]+)\s*€",
)
_RE_TOTALE_PREVENTIVO = re.compile(r"Totale preventivo\s+([\d.,]+)\s*€")
_RE_CONTRIBUTO_RICHIESTO = re.compile(r"Contributo richiesto\s+([\d.,]+)\s*€")
_RE_COFINANZIAMENTO_FINALE = re.compile(r"Cofinanziamento\s+([\d.,]+)\s*€\s*Data")


def _quadra(a: float | None, b: float | None, tolleranza: float = 0.5) -> bool:
    if a is None or b is None:
        return False
    return abs(a - b) <= tolleranza


def _parse_progetti_formativi(sezione3: str, warnings: list[str]) -> list[dict[str, Any]]:
    marcatori = [m.start() for m in re.finditer(r"Progetto Formativo n\.", sezione3)]
    blocchi = [
        sezione3[inizio: (marcatori[i + 1] if i + 1 < len(marcatori) else len(sezione3))]
        for i, inizio in enumerate(marcatori)
    ]

    progetti = []
    for blocco in blocchi:
        numero_match = re.search(r"Progetto Formativo n\.\s*\n?(\d+)", blocco)
        m_titolo = _RE_PROGETTO_TITOLO.search(blocco)
        m_ore = _RE_PROGETTO_ORE.search(blocco)
        m_edizioni = _RE_PROGETTO_EDIZIONI.search(blocco)
        m_erogatore = _RE_SOGGETTO_EROGATORE.search(blocco)
        m_regioni = _RE_REGIONI.search(blocco)
        m_province = _RE_PROVINCE.search(blocco)
        m_tematica = _RE_PROGETTO_TEMATICA.search(blocco)

        modalita_attuazione = [
            {
                "tipo": "aula" if riga[0] == "Aula" else "training_on_job",
                "ore": float(riga[1].replace(",", ".")),
                "percentuale": float(riga[2].replace(",", ".")),
            }
            for riga in _RE_MODALITA_RIGHE.findall(blocco)
        ]

        costo = None
        m_costo = _RE_COSTO_PROGETTO.search(blocco)
        if m_costo:
            edizioni_riga = int(m_costo.group(1))
            partecipanti_minimo = int(m_costo.group(2))
            finanziamento_edizione = float(m_costo.group(3).replace(".", "").replace(",", "."))
            totale = float(m_costo.group(5).replace(".", "").replace(",", "."))
            costo = {
                "costo_numero_edizioni": edizioni_riga,
                "costo_partecipanti_minimo": partecipanti_minimo,
                "costo_finanziamento_per_edizione": finanziamento_edizione,
                "costo_totale": totale,
                "quadratura_costo_ok": _quadra(edizioni_riga * finanziamento_edizione, totale),
            }
        else:
            warnings.append("Costo del progetto non trovato o non quadrato (Sezione 3)")
            costo = {
                "costo_numero_edizioni": None, "costo_partecipanti_minimo": None,
                "costo_finanziamento_per_edizione": None, "costo_totale": None,
                "quadratura_costo_ok": False,
            }

        progetti.append({
            "numero": numero_match.group(1) if numero_match else None,
            "titolo": m_titolo.group(1).strip() if m_titolo else None,
            "tipologia_formativa": None,  # riga spezzata su piu' righe nel campione, non affidabile: da verificare a mano
            "tematica": m_tematica.group(1).strip() if m_tematica else None,
            "ore_formazione": float(m_ore.group(1).replace(",", ".")) if m_ore else None,
            "edizioni": int(m_edizioni.group(1)) if m_edizioni else None,
            "soggetto_erogatore": m_erogatore.group(1).strip() if m_erogatore else None,
            "regioni": [r.strip() for r in m_regioni.group(1).split(",")] if m_regioni else [],
            "province": [p.strip() for p in m_province.group(1).split(",")] if m_province else [],
            "modalita_attuazione": modalita_attuazione,
            **costo,
        })

    if not progetti:
        warnings.append("Nessun progetto formativo trovato in Sezione 3")
    return progetti


def _parse_riepilogo(sezione4: str, imprese_beneficiarie: list[dict], warnings: list[str]) -> dict[str, Any]:
    m = _RE_FINANZIAMENTO_TOTALE_PROGETTI.search(sezione4)
    finanziamento_totale = _clean_importo(m.group(1)) if m else None

    m = _RE_DESTINATARI_TOTALE.search(sezione4)
    destinatari_totale = int(m.group(1)) if m else None

    m = _RE_COSTO_COMPLESSIVO.search(sezione4)
    costo_complessivo = _clean_importo(m.group(1)) if m else None
    m = _RE_QUOTA_PUBBLICA.search(sezione4)
    quota_pubblica = _clean_importo(m.group(1)) if m else None
    m = _RE_QUOTA_PRIVATA.search(sezione4)
    quota_privata = _clean_importo(m.group(1)) if m else None

    cronoprogramma = {"durata_giorni": None, "attivita": []}
    m = _RE_CRONO_DURATA.search(sezione4)
    if m:
        cronoprogramma["durata_giorni"] = int(m.group(1))
    cronoprogramma["attivita"] = [
        {"nome": nome, "mese": int(mese), "anno": int(anno)}
        for nome, mese, anno in _RE_CRONO_ATTIVITA.findall(sezione4)
    ]
    if not cronoprogramma["attivita"]:
        warnings.append("Cronoprogramma non trovato in Sezione 4.5")

    macrovoci = []
    for codice, importo_raw, importo_pct_raw, pct_raw in _RE_MACROVOCE_TOTALE.findall(sezione4):
        limite = None
        pattern_limite = _RE_MACROVOCE_LIMITE.get(codice)
        if pattern_limite:
            m_limite = pattern_limite.search(sezione4)
            limite = int(m_limite.group(1)) if m_limite else None
        macrovoci.append({
            "codice": codice,
            "importo": _clean_importo(importo_pct_raw),
            "percentuale": _clean_pct(pct_raw),
            "limite_max_pct": limite,
        })
    # ``findall`` cattura sia la riga "Totale Macrovoce X." (senza %) sia
    # quella con %: dedup per codice tenendo l'ultima occorrenza (quella con
    # percentuale valorizzata), che nel campione e' sempre la seconda riga.
    macrovoci_per_codice = {}
    for voce in macrovoci:
        macrovoci_per_codice[voce["codice"]] = voce
    macrovoci = [macrovoci_per_codice[c] for c in ("A", "B", "C", "D") if c in macrovoci_per_codice]

    m = _RE_TOTALE_PREVENTIVO.search(sezione4)
    totale_preventivo = _clean_importo(m.group(1)) if m else None
    m = _RE_CONTRIBUTO_RICHIESTO.search(sezione4)
    contributo_richiesto = _clean_importo(m.group(1)) if m else None
    m = _RE_COFINANZIAMENTO_FINALE.search(sezione4)
    cofinanziamento = _clean_importo(m.group(1)) if m else None

    somma_macrovoci = sum(v["importo"] for v in macrovoci if v["importo"] is not None) or None
    quadratura_macrovoci_ok = _quadra(somma_macrovoci, totale_preventivo)
    if not quadratura_macrovoci_ok:
        warnings.append(
            f"Le macrovoci (totale {somma_macrovoci}) non quadrano col preventivo totale ({totale_preventivo})"
        )

    somma_per_impresa = sum(
        _clean_importo(riga[3]) or 0
        for riga in _RE_RIEPILOGO_IMPRESA_RIGA.findall(sezione4)
    ) or None
    quadratura_finanziamento_per_impresa_ok = _quadra(somma_per_impresa, costo_complessivo)
    if not quadratura_finanziamento_per_impresa_ok:
        warnings.append(
            f"La somma dei finanziamenti per impresa ({somma_per_impresa}) non coincide "
            f"col costo complessivo ({costo_complessivo})"
        )

    return {
        "finanziamento_totale": finanziamento_totale,
        "destinatari_totale": destinatari_totale,
        "costo_complessivo": costo_complessivo,
        "quota_pubblica": quota_pubblica,
        "quota_privata": quota_privata,
        "cronoprogramma": cronoprogramma,
        "macrovoci": macrovoci,
        "totale_preventivo": totale_preventivo,
        "contributo_richiesto": contributo_richiesto,
        "cofinanziamento": cofinanziamento,
        "quadratura_macrovoci_ok": quadratura_macrovoci_ok,
        "quadratura_finanziamento_per_impresa_ok": quadratura_finanziamento_per_impresa_ok,
    }
```

Then in `parse_formulario`, add after the Sezione 2 block:

```python
    idx_sezione4 = full_text.find("Sezione 4.")
    sezione3 = full_text[idx_sezione3:idx_sezione4] if idx_sezione3 != -1 and idx_sezione4 != -1 else ""
    sezione4 = full_text[idx_sezione4:] if idx_sezione4 != -1 else ""
    progetti_formativi = _parse_progetti_formativi(sezione3, warnings)
    riepilogo = _parse_riepilogo(sezione4, imprese_beneficiarie, warnings)
```

and replace `"progetti_formativi": []` / `"riepilogo": {}` in the return dict with
`progetti_formativi` / `riepilogo`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_formazienda_formulario_parser.py -v`
Expected: PASS (11 tests total). This task has the densest regex surface in the
plan (costo del progetto's multi-line table, macrovoci' doubled totale lines).
If `_RE_COSTO_PROGETTO` doesn't match, print `repr(blocco[blocco.find("Costo del progetto"):blocco.find("Costo del progetto")+300])`
and adjust to the literal text rather than relaxing the quadratura check —
the whole point of trap #10 is catching real mismatches, so the regex must
reflect the real table layout, not paper over it.

- [ ] **Step 5: Commit**

```bash
git add backend/services/parsers/formazienda/formulario_parser.py backend/tests/test_formazienda_formulario_parser.py
git commit -m "feat(formazienda): parse progetto formativo, macrovoci, cronoprogramma with quadratura checks"
```

---

## Task 13 — Migration: `classe_dimensionale` on aziende_clienti + `project_soggetti_delegati` table

**Files:**
- Create: `backend/alembic/versions/0XX_formazienda_classe_dimensionale_e_delega.py`
  (use `alembic history | head -1` to find the current head revision id and set
  `down_revision` to it — do not guess the number; the last migration seen during
  exploration was `068`, but more may have landed since)
- Modify: `backend/models.py` — add `classe_dimensionale = Column(String(10), nullable=True)`
  to `AziendaCliente` (near `matricola_inps`/`regime_aiuto_default`), and add a new
  `ProjectSoggettoDelegato` model class near `ProjectDocumento`.
- Test: `backend/tests/test_formazienda_upload.py` (extend, see Task 14)

**Interfaces:**
- Produces: `models.AziendaCliente.classe_dimensionale: str | None`,
  `models.ProjectSoggettoDelegato(id, project_id, ragione_sociale, codice_fiscale,
  partita_iva, legale_rappresentante_nome, legale_rappresentante_cognome,
  tipologia, importo, percentuale, created_at)`.

- [ ] **Step 1: Write the failing test**

```python
# add to backend/tests/test_formazienda_formulario_parser.py or a new small test file
def test_classe_dimensionale_e_soggetto_delegato_esistono_nello_schema():
    import models
    assert hasattr(models.AziendaCliente, "classe_dimensionale")
    assert hasattr(models, "ProjectSoggettoDelegato")
    delegato = models.ProjectSoggettoDelegato(
        project_id=1, ragione_sociale="Test", importo=100.0, percentuale=10.0,
    )
    assert delegato.ragione_sociale == "Test"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_formazienda_formulario_parser.py::test_classe_dimensionale_e_soggetto_delegato_esistono_nello_schema -v`
Expected: FAIL — `AttributeError`.

- [ ] **Step 3: Write minimal implementation**

In `backend/models.py`, add to `AziendaCliente` right after `matricola_inps`:

```python
    classe_dimensionale = Column(String(10), nullable=True)
    # Valori: "micro", "piccola", "media", "grande" (Allegato A Formazienda II.2)
```

Add a new model near `ProjectDocumento`:

```python
class ProjectSoggettoDelegato(Base):
    """Soggetto terzo in delega su un progetto (Allegato A Formazienda I.5).

    La delega e' soggetta ad autorizzazione preventiva del fondo ed e' un
    elemento verificato in sede di controllo: va registrata, non solo
    mostrata nell'anteprima di caricamento.
    """
    __tablename__ = "project_soggetti_delegati"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    ragione_sociale = Column(String(200), nullable=False)
    codice_fiscale = Column(String(16), nullable=True)
    partita_iva = Column(String(11), nullable=True)
    legale_rappresentante_nome = Column(String(100), nullable=True)
    legale_rappresentante_cognome = Column(String(100), nullable=True)
    tipologia = Column(String(50), nullable=True)
    importo = Column(Numeric(12, 2), nullable=True)
    percentuale = Column(Numeric(5, 2), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    project = relationship("Project", backref="soggetti_delegati", lazy="select")
```

Create the migration (check the real head first with
`cd backend && alembic history | head -1` and use that revision id):

```python
"""Formazienda: classe dimensionale azienda + soggetti delegati progetto."""
from alembic import op
import sqlalchemy as sa

revision = "0XX"
down_revision = "<head-revision-id-from-alembic-history>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("aziende_clienti", sa.Column("classe_dimensionale", sa.String(10), nullable=True))
    op.create_table(
        "project_soggetti_delegati",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("ragione_sociale", sa.String(200), nullable=False),
        sa.Column("codice_fiscale", sa.String(16), nullable=True),
        sa.Column("partita_iva", sa.String(11), nullable=True),
        sa.Column("legale_rappresentante_nome", sa.String(100), nullable=True),
        sa.Column("legale_rappresentante_cognome", sa.String(100), nullable=True),
        sa.Column("tipologia", sa.String(50), nullable=True),
        sa.Column("importo", sa.Numeric(12, 2), nullable=True),
        sa.Column("percentuale", sa.Numeric(5, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("project_soggetti_delegati")
    op.drop_column("aziende_clienti", "classe_dimensionale")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_formazienda_formulario_parser.py::test_classe_dimensionale_e_soggetto_delegato_esistono_nello_schema -v`
Expected: PASS. Then run the full backend suite once
(`cd backend && python -m pytest -q`) to confirm the new column/table don't
break any `Base.metadata.create_all`-based test fixture (they use SQLite
in-memory schemas generated fresh from `models.py`, so this should be
transparent — but confirm rather than assume, per this codebase's own
"nessuna asserzione senza verifica" discipline).

Apply the migration against the real dev DB only if/when the user asks to
deploy — do not run `alembic upgrade head` against a real database from this
plan without that explicit request (Task 15 in this plan surfaces the
question instead of assuming).

- [ ] **Step 5: Commit**

```bash
git add backend/models.py backend/alembic/versions/0XX_formazienda_classe_dimensionale_e_delega.py backend/tests/
git commit -m "feat(formazienda): add classe_dimensionale column and project_soggetti_delegati table"
```

---

## Task 14 — `formazienda_upload.py`: formulario upload/confirm (Allegato A), cross-check with Allegato E

**Files:**
- Modify: `backend/routers/formazienda_upload.py`
- Test: `backend/tests/test_formazienda_upload.py` (extend)

**Interfaces:**
- Consumes: `services.parsers.formazienda.formulario_parser.parse_formulario`,
  `models.ProjectSoggettoDelegato`, `models.ModuloFormativo`,
  `models.PianoFinanziario`, `models.VocePianoFinanziario` (Task 13, and the
  existing models already read in this plan's Task 12 interfaces).
- Produces: `POST /api/v1/projects/{project_id}/formazienda/upload-formulario`,
  `POST /api/v1/projects/{project_id}/formazienda/confirm-formulario`
  (project-scoped only — the formulario always completes an existing project,
  per the spec's "i due documenti sono complementari").

- [ ] **Step 1: Write the failing test**

```python
# extend backend/tests/test_formazienda_upload.py
CAMPIONE_A = Path(__file__).parent.parent / "imports" / "formazienda" / "ALLEGATO A.pdf"


def _crea_progetto_da_allegato_e(client):
    preview = _upload(client).json()
    response = client.post(
        "/api/v1/projects/formazienda/confirm-atto-adesione",
        json={"preview_token": preview["preview_token"], "data_avvio_piano": "2026-07-01"},
    )
    return response.json()["project_id"]


def test_upload_formulario_estrae_14_imprese_e_progetto(client):
    project_id = _crea_progetto_da_allegato_e(client)
    with open(CAMPIONE_A, "rb") as fh:
        response = client.post(
            f"/api/v1/projects/{project_id}/formazienda/upload-formulario",
            files={"file": ("ALLEGATO A.pdf", fh, "application/pdf")},
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["imprese_beneficiarie"]) == 14
    assert body["soggetto_delegato"]["ragione_sociale"] == "A.M.D. S.R.L."
    return body["preview_token"]


def test_confirm_formulario_crea_aziende_link_delega_moduli_e_piano(client, db_session):
    project_id = _crea_progetto_da_allegato_e(client)
    with open(CAMPIONE_A, "rb") as fh:
        upload = client.post(
            f"/api/v1/projects/{project_id}/formazienda/upload-formulario",
            files={"file": ("ALLEGATO A.pdf", fh, "application/pdf")},
        ).json()

    response = client.post(
        f"/api/v1/projects/{project_id}/formazienda/confirm-formulario",
        json={"preview_token": upload["preview_token"]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["aziende_create"] == 14
    assert body["soggetto_delegato_registrato"] is True

    aziende = db_session.query(models.AziendaCliente).filter(
        models.AziendaCliente.partita_iva == "08951911216"
    ).all()
    assert len(aziende) == 1
    assert aziende[0].ragione_sociale == "PAKI UNITED FOREVER S.R.L.S."
    assert aziende[0].classe_dimensionale == "micro"

    delega = db_session.query(models.ProjectSoggettoDelegato).filter(
        models.ProjectSoggettoDelegato.project_id == project_id
    ).first()
    assert delega is not None
    assert delega.importo == 14000.0

    piano = db_session.query(models.PianoFinanziario).filter(
        models.PianoFinanziario.progetto_id == project_id,
        models.PianoFinanziario.tipo_fondo == "formazienda",
    ).first()
    assert piano is not None
    voci = db_session.query(models.VocePianoFinanziario).filter(
        models.VocePianoFinanziario.piano_id == piano.id
    ).all()
    assert {v.macrovoce for v in voci} == {"A", "B", "C", "D"}

    documento = db_session.query(models.ProjectDocumento).filter(
        models.ProjectDocumento.project_id == project_id,
        models.ProjectDocumento.tipo_documento == "formulario",
    ).first()
    assert documento is not None


def test_divergenza_tra_allegato_a_ed_e_viene_segnalata(client, db_session):
    project_id = _crea_progetto_da_allegato_e(client)
    project = db_session.query(models.Project).get(project_id)
    project.costo_totale = 999999
    db_session.commit()

    with open(CAMPIONE_A, "rb") as fh:
        upload = client.post(
            f"/api/v1/projects/{project_id}/formazienda/upload-formulario",
            files={"file": ("ALLEGATO A.pdf", fh, "application/pdf")},
        ).json()

    assert any("divergente" in w.lower() or "diverge" in w.lower() for w in upload["warnings"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_formazienda_upload.py -k formulario -v`
Expected: FAIL with 404 (routes don't exist).

- [ ] **Step 3: Write minimal implementation**

Add to `backend/routers/formazienda_upload.py`:

```python
FORMULARIO_DIR = os.path.join(os.getenv("UPLOADS_DIR", "/app/uploads"), "formazienda", "formulari")
os.makedirs(FORMULARIO_DIR, exist_ok=True)


class ConfirmFormularioRequest(BaseModel):
    preview_token: str


def _trova_o_crea_azienda(db: Session, impresa: dict) -> tuple[models.AziendaCliente, bool]:
    azienda = None
    if impresa.get("partita_iva"):
        azienda = db.query(models.AziendaCliente).filter(
            models.AziendaCliente.partita_iva == impresa["partita_iva"]
        ).first()
    if azienda is None and impresa.get("codice_fiscale"):
        azienda = db.query(models.AziendaCliente).filter(
            models.AziendaCliente.codice_fiscale == impresa["codice_fiscale"]
        ).first()

    campi = {
        "ragione_sociale": impresa.get("ragione_sociale"),
        "partita_iva": impresa.get("partita_iva"),
        "codice_fiscale": impresa.get("codice_fiscale"),
        "indirizzo": impresa.get("indirizzo"),
        "cap": impresa.get("cap"),
        "citta": impresa.get("citta"),
        "provincia": impresa.get("provincia"),
        "telefono": impresa.get("telefono"),
        "email": impresa.get("email"),
        "pec": impresa.get("pec"),
        "matricola_inps": impresa.get("matricola_inps"),
        "settore_codice": impresa.get("codice_ateco"),
        "classe_dimensionale": impresa.get("classe_dimensionale"),
        "regime_aiuto_default": impresa.get("regime_aiuti"),
        "num_dipendenti": impresa.get("numero_dipendenti_totale"),
        "legale_rappresentante_nome": impresa.get("legale_rappresentante_nome"),
        "legale_rappresentante_cognome": impresa.get("legale_rappresentante_cognome"),
    }
    if impresa.get("stato_adesione_data"):
        campi["anno_adesione"] = impresa["stato_adesione_data"][:4]

    if azienda is None:
        azienda = models.AziendaCliente(
            **{k: v for k, v in campi.items() if v is not None}, attivo=True,
        )
        db.add(azienda)
        db.flush()
        return azienda, True

    for campo, valore in campi.items():
        if valore is not None and not getattr(azienda, campo, None):
            setattr(azienda, campo, valore)
    return azienda, False


def _confronta_con_allegato_e(project: models.Project, formulario: dict) -> list[str]:
    """I dati comuni ai due documenti devono coincidere: divergenza = segnalazione, non blocco."""
    divergenze = []
    gestore = formulario.get("soggetto_gestore") or {}
    if (
        project.ente_attuatore
        and gestore.get("partita_iva")
        and project.ente_attuatore.partita_iva
        and gestore["partita_iva"] != project.ente_attuatore.partita_iva
    ):
        divergenze.append(
            f"Ente attuatore divergente: Allegato E={project.ente_attuatore.partita_iva}, "
            f"Allegato A={gestore['partita_iva']}"
        )
    titolo_formulario = (formulario.get("piano") or {}).get("titolo")
    if titolo_formulario and project.name and titolo_formulario != project.name:
        divergenze.append(
            f"Titolo piano divergente: progetto={project.name}, Allegato A={titolo_formulario}"
        )
    riepilogo = formulario.get("riepilogo") or {}
    costo_formulario = riepilogo.get("costo_complessivo")
    if (
        costo_formulario is not None
        and project.costo_totale is not None
        and abs(float(project.costo_totale) - float(costo_formulario)) > 0.5
    ):
        divergenze.append(
            f"Importo totale divergente: Allegato E={project.costo_totale}, "
            f"Allegato A={costo_formulario}"
        )
    return divergenze


@router.post("/{project_id}/formazienda/upload-formulario")
async def upload_formulario_formazienda(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Progetto non trovato")

    token = str(uuid.uuid4())
    dest = os.path.join(FORMULARIO_DIR, f"{token}.pdf")
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    from services.parsers.formazienda.formulario_parser import parse_formulario
    result = parse_formulario(dest)
    result["warnings"] = list(result.get("warnings") or []) + _confronta_con_allegato_e(project, result)

    _preview_store.store(token, {
        "project_id": project_id, "file_path": dest, "original_filename": file.filename, **result,
    })
    return {"preview_token": token, "project_id": project_id, **result}


@router.post("/{project_id}/formazienda/confirm-formulario")
def confirm_formulario_formazienda(
    project_id: int,
    body: ConfirmFormularioRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Progetto non trovato")

    preview = _preview_store.pop(body.preview_token)
    if not preview:
        raise HTTPException(status_code=404, detail="Preview token non trovato o scaduto")
    if preview.get("project_id") != project_id:
        raise HTTPException(status_code=400, detail="Token non appartiene a questo progetto")

    aziende_create = 0
    aziende_associate = 0
    for impresa in preview.get("imprese_beneficiarie", []):
        azienda, creata = _trova_o_crea_azienda(db, impresa)
        aziende_create += int(creata)
        aziende_associate += int(not creata)
        link = db.query(models.AziendaClienteProjectLink).filter(
            models.AziendaClienteProjectLink.azienda_cliente_id == azienda.id,
            models.AziendaClienteProjectLink.project_id == project_id,
        ).first()
        if not link:
            link = models.AziendaClienteProjectLink(azienda_cliente_id=azienda.id, project_id=project_id)
            db.add(link)

    soggetto_delegato_registrato = False
    delega = preview.get("soggetto_delegato") or {}
    if delega.get("ragione_sociale"):
        esistente = db.query(models.ProjectSoggettoDelegato).filter(
            models.ProjectSoggettoDelegato.project_id == project_id,
            models.ProjectSoggettoDelegato.partita_iva == delega.get("partita_iva"),
        ).first()
        if not esistente:
            db.add(models.ProjectSoggettoDelegato(
                project_id=project_id,
                ragione_sociale=delega["ragione_sociale"],
                codice_fiscale=delega.get("codice_fiscale"),
                partita_iva=delega.get("partita_iva"),
                legale_rappresentante_nome=delega.get("legale_rappresentante_nome"),
                legale_rappresentante_cognome=delega.get("legale_rappresentante_cognome"),
                tipologia=delega.get("tipologia"),
                importo=delega.get("importo"),
                percentuale=delega.get("percentuale"),
            ))
        soggetto_delegato_registrato = True

    moduli_creati = 0
    for progetto_formativo in preview.get("progetti_formativi", []):
        obiettivo = (
            f"Edizioni: {progetto_formativo.get('edizioni')}; "
            f"Modalita: {progetto_formativo.get('modalita_attuazione')}; "
            f"Finanziamento/edizione: {progetto_formativo.get('costo_finanziamento_per_edizione')}"
        )
        db.add(models.ModuloFormativo(
            project_id=project_id,
            titolo_modulo=progetto_formativo.get("titolo") or "Progetto Formazienda",
            materia=progetto_formativo.get("tematica"),
            modalita_erogazione="mista_aula_toj",
            tipo_attivita="formativa",
            ore_previste=progetto_formativo.get("ore_formazione") or 0,
            obiettivo=obiettivo,
        ))
        moduli_creati += 1

    piano = db.query(models.PianoFinanziario).filter(
        models.PianoFinanziario.progetto_id == project_id,
        models.PianoFinanziario.tipo_fondo == "formazienda",
    ).first()
    riepilogo = preview.get("riepilogo") or {}
    if not piano:
        from datetime import datetime as _dt
        anno = (project.data_approvazione or _dt.now().date()).year
        piano = models.PianoFinanziario(
            progetto_id=project_id,
            anno=anno,
            ente_erogatore="Formazienda",
            tipo_fondo="formazienda",
            codice_piano=project.id_piano_esterno,
            nome=f"Piano Finanziario Formazienda - {project.name}",
            budget_totale=riepilogo.get("totale_preventivo") or project.costo_totale or 0.0,
            budget_approvato=riepilogo.get("contributo_richiesto") or project.contributo_ente or 0.0,
            data_inizio=_dt.now(),
            data_fine=_dt(anno + 1, 12, 31),
            data_approvazione=project.data_approvazione,
            stato="bozza",
        )
        db.add(piano)
        db.flush()

    voci_create = 0
    for macrovoce in riepilogo.get("macrovoci", []):
        esiste = db.query(models.VocePianoFinanziario).filter(
            models.VocePianoFinanziario.piano_id == piano.id,
            models.VocePianoFinanziario.macrovoce == macrovoce["codice"],
        ).first()
        if esiste:
            continue
        db.add(models.VocePianoFinanziario(
            piano_id=piano.id,
            macrovoce=macrovoce["codice"],
            voce_codice=macrovoce["codice"],
            categoria="altro",
            descrizione=(
                f"Totale Macrovoce {macrovoce['codice']}"
                + (f" (max {macrovoce['limite_max_pct']}%)" if macrovoce.get("limite_max_pct") else "")
            ),
            ore=0, ore_previste=0,
            importo_preventivo=macrovoce.get("importo") or 0,
            stato="previsto",
        ))
        voci_create += 1

    documento = documento_progetto.archivia_documento_progetto(
        db, project=project, preview=preview, file_path=preview["file_path"],
        tipo_documento="formulario", current_user=current_user,
    )
    db.commit()

    return {
        "project_id": project_id,
        "aziende_create": aziende_create,
        "aziende_associate": aziende_associate,
        "soggetto_delegato_registrato": soggetto_delegato_registrato,
        "moduli_creati": moduli_creati,
        "voci_piano_create": voci_create,
        "documento_id": documento.id,
        "warnings": preview.get("warnings", []),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_formazienda_upload.py -v`
Expected: PASS (6 tests total across Task 6 + this task).

- [ ] **Step 5: Commit**

```bash
git add backend/routers/formazienda_upload.py backend/tests/test_formazienda_upload.py
git commit -m "feat(formazienda): confirm-formulario creates aziende, delega, moduli and piano finanziario"
```

---

## Task 15 — Frontend: Formulario upload for Formazienda projects

**Files:**
- Modify: `frontend/src/services/apiService.js` (add `uploadFormularioFormazienda`, `confirmFormularioFormazienda`)
- Modify: `frontend/src/components/FapiUpload.js` (new `FormularioFormaziendaModal`, wire into the `isFormazienda` button block replacing the `piano-formazienda` placeholder button — check what that button currently opens; the existing `FapiUploadSection` at line ~1303 wires `piano-formazienda` to the generic `PianoFinanziarioModal`, which expects XLSX, not this PDF formulario — add a distinct `modal === 'formulario-formazienda'` case and a distinct button)
- Test: `frontend/src/components/FapiUpload.test.js` (extend)

**Interfaces:**
- Consumes: Task 14 endpoints.

- [ ] **Step 1: Write the failing test**

Follow the same pattern as Task 7 Step 1, targeting the formulario upload
button/modal instead of the atto adesione one. Read the current state of
`FapiUpload.test.js` first (it will already contain the Task 7 additions) and
add a sibling test in the same style.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx jest FapiUpload.test.js -t "formulario"`
Expected: FAIL — no such button/modal yet.

- [ ] **Step 3: Write minimal implementation**

In `apiService.js`, add next to the Formazienda block from Task 7:

```javascript
export const uploadFormularioFormazienda = (projectId, file) => {
  const fd = new FormData();
  fd.append('file', file);
  return http.post(`/projects/${projectId}/formazienda/upload-formulario`, fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).then(r => r.data);
};
export const confirmFormularioFormazienda = (projectId, previewToken) =>
  http.post(`/projects/${projectId}/formazienda/confirm-formulario`, { preview_token: previewToken }).then(r => r.data);
```

In `FapiUpload.js`, add a modal modeled on `FormularioModal` (lines 791-894) but
pointed at the Formazienda endpoints and showing imprese/delega/macrovoci
instead of moduli — reuse the existing table-rendering idioms already in the
file (`formatEuro`, `<table><tbody>` blocks) rather than inventing new ones.
Wire it into `FapiUploadSection`'s `isFormazienda` block as a second button
("💰 Carica Formulario (Allegato A)") next to the existing `atto-formazienda`
one, opening `modal === 'formulario-formazienda'`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx jest FapiUpload.test.js`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/services/apiService.js frontend/src/components/FapiUpload.js frontend/src/components/FapiUpload.test.js
git commit -m "feat(formazienda): wire formulario (Allegato A) upload into the project document panel"
```

---

## Task 16 — End-to-end verification of Allegato A + closing documentation

- [ ] Run the full backend suite: `cd backend && python -m pytest -q`. Expected:
      all green, including every pre-existing FAPI/Fondimpresa/UX-6 test.
- [ ] Run the full frontend suite touching these files: `cd frontend && npx jest FapiUpload.test.js ProjectManager.test.js` (or whatever the project's actual test command is per `package.json` — check before assuming `npx jest`).
- [ ] Manual walkthrough (real backend/frontend, per this project's `run` skill):
  1. Create a Formazienda project from `ALLEGATO E.pdf` → ente derived, no residual block.
  2. Select aziende/sedi/allievi manually → project saves without errors.
  3. Verify extracted data: `data_approvazione` on the project = 2026-06-11 (the
     delibera), NOT 2022-08-03 (the footer); check the document's stored dates
     via the project detail API or DB directly.
  4. Confirm the Allegato E file appears in the project's document list and
     (if this repo's "Archivio Risorse" surfaces project documents at all —
     confirm first, since Task investigation found Archivio Risorse today is
     Avvisi-only, not project documents; if so, state that explicitly rather
     than claiming a false positive).
  5. Create a FAPI project with a convenzione → no regression, aziende still
     proposed from the document, picker still perimeter-restricted.
  6. Upload a corrupted/illegible file as Atto di adesione → still archived,
     manual entry still possible.
  7. Upload `ALLEGATO A.pdf` on the Formazienda project → 14 imprese extracted
     with ragione sociale/PIVA/ATECO/matricola INPS/classe dimensionale/regime
     de minimis; NEXT GROUP S.R.L. (gestore) absent from the list; A.M.D.
     S.R.L. registered as soggetto delegato with its importo.
  8. Confirm the macrovoci quadrano and the cronoprogramma proposes the four
     dates from the sample without inventing a day-of-month.
  9. Both PDFs appear archived on the project (`GET /{project_id}/documenti`).
- [ ] Update `STATUS.md`: append (do not rewrite existing content) a new
      `## ✅ FORMAZIENDA — ATTO DI ADESIONE E FORMULARIO RICONOSCIUTI — <date>`
      section following this repo's established format (see the existing
      entries for the section skeleton): what was found, what was built, test
      counts (backend passed, frontend suites), the confutatore paragraph
      (what was tried to disprove and survived), real-deploy verification
      notes, commit hashes, and close with:
      `**ATTO DI ADESIONE FORMAZIENDA RICONOSCIUTO COME ATTO CONCESSORIO: SÌ**`
      followed by the outcome of all six Allegato-E test cases and the eight
      Allegato-A test cases from the user's spec, each marked pass/fail with
      the real observed value (e.g. "data approvazione = 2026-06-11, non
      2022-08-03: confermato").
- [ ] Update `REMEDIATION_LOG.md` with an entry in its declared format
      (`data | finding ID | cosa fatto | file toccati | test/verifiche
      eseguiti`) — pick the next finding ID following this repo's existing
      numbering convention (check the last `NEW-0NN` used in the log).
- [ ] Do not push. Confirm all commits are local only, per this project's own
      "nessun push" convention seen throughout `STATUS.md`.
