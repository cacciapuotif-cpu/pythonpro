# Archivio Avvisi V2 — Pipeline Ingestione — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pipeline completa upload MD → pulizia → segmentazione → estrazione LLM per categoria → AgentRun/AgentSuggestion → apply umano che materializza regole/scadenze validate sulla revisione.

**Architecture:** Nessuna migration: il modello V1 (migration 057) già prevede `source_md_path`, `cleaned_md_path`, `source_sha256`, `stato_estrazione`, `extraction_run_id` su `AvvisoRevisione`. La pipeline è composta da funzioni pure in `backend/services/avviso_ingest.py` (pulizia, segmentazione, storage), un nuovo agente `avviso_extractor` nel registry dichiarativo `backend/ai_agents/__init__.py` (collector puro, persistenza SOLO via `run_agent_workflow`), un endpoint upload nel router `backend/routers/avvisi.py`, e l'estensione di `backend/services/suggestion_apply.py` per materializzare regole/scadenze all'apply umano.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic v2 (`schemas_avvisi.py`), LLM via `ai_agents.llm.call_ollama_json` (kill switch `AGENT_AVVISO_EXTRACTOR_ENABLED` + `AGENTS_ENABLED`), pytest con SQLite tmp (pattern `tests/test_avvisi_v1.py`).

## Global Constraints

- **Mai push.** Solo commit locali atomici `feat(AVVISI-NN): ...`.
- Suite completa sempre verde prima di dichiarare chiuso il gate (baseline: **434 passed, 1 skipped**).
- Il collector agente NON scrive su DB (regola registry, vedi `backend/ai_agents/__init__.py` docstring). Persistenza solo in `agent_workflows.run_agent_workflow`.
- Nessuna regola/scadenza entra nelle query operative senza validazione umana: la materializzazione avviene SOLO in `apply_suggestion` con `user_id` autenticato obbligatorio.
- Storage key sempre relative (validate da `crud_avvisi._storage_key`), root fisica `UPLOAD_DIR` (`backend/file_upload.py:48`, default `uploads/`).
- Test eseguiti dal container: `docker compose exec -T backend python -m pytest tests/<file> -v` (oppure localmente da `backend/` se l'ambiente lo permette; i test usano SQLite e non richiedono Postgres).
- LLM sempre mockato nei test (`monkeypatch` su `ai_agents.avviso_extractor.call_ollama_json`).
- Enum e vincoli DB esistenti: `stato_estrazione` ∈ caricato|pulito|segmentato|in_estrazione|estratto|errore; categorie regola in `schemas_avvisi.CategoriaRegola`; tipi scadenza in `TipoScadenza`.

---

## File Structure

| File | Responsabilità |
|------|----------------|
| `backend/services/avviso_ingest.py` (nuovo) | pulizia MD, segmentazione, storage source/cleaned, orchestrazione pipeline |
| `backend/ai_agents/prompts/avviso_extractor_v1.py` (nuovo) | prompt di estrazione per gruppo di categorie |
| `backend/ai_agents/avviso_extractor.py` (nuovo) | collector puro: legge cleaned MD, chiama LLM per gruppo, ritorna suggestions |
| `backend/ai_agents/llm_schemas.py` (modifica) | schemi Pydantic per output LLM estrazione |
| `backend/ai_agents/__init__.py` (modifica) | registrazione `avviso_extractor` |
| `backend/routers/avvisi.py` (modifica) | endpoint ingest + lettura revisioni/estrazione, RBAC admin/manager |
| `backend/schemas_avvisi.py` (modifica) | schema risposta ingest |
| `backend/services/suggestion_apply.py` (modifica) | apply umano → materializza regola/scadenza validata |
| `backend/tests/test_avvisi_v2_ingest.py` (nuovo) | test pulizia/segmentazione/storage |
| `backend/tests/test_avvisi_v2_extractor.py` (nuovo) | test collector, pipeline, apply |
| `backend/tests/test_avvisi_v2_api.py` (nuovo) | test endpoint con TestClient e override deps |
| `imports/avvisi/README.md` (nuovo) | directory di appoggio per i 4 avvisi MD reali (ingestione = V5) |

---

### Task 1: Pulizia markdown (AVVISI-02)

**Files:**
- Create: `backend/services/avviso_ingest.py`
- Test: `backend/tests/test_avvisi_v2_ingest.py`

**Interfaces:**
- Produces: `clean_markdown(raw: str) -> str` — normalizza newline, rimuove commenti HTML e artefatti di pagina, collassa righe vuote multiple; output termina con `\n` singolo (o stringa vuota).

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_avvisi_v2_ingest.py
"""ONDATA ARCHIVIO AVVISI — V2 pipeline ingestione: pulizia, segmentazione, storage."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.avviso_ingest import clean_markdown


def test_clean_markdown_normalizes_newlines_and_blank_runs():
    raw = "# Titolo\r\n\r\n\r\n\r\nTesto   \r\ncontinua\r"
    assert clean_markdown(raw) == "# Titolo\n\nTesto\ncontinua\n"


def test_clean_markdown_removes_html_comments_and_page_artifacts():
    raw = (
        "# Avviso\n"
        "<!-- intestazione export\nmultilinea -->\n"
        "Pagina 3 di 12\n"
        "pag. 4\n"
        "Contenuto utile\n"
    )
    assert clean_markdown(raw) == "# Avviso\n\nContenuto utile\n"


def test_clean_markdown_empty_input_returns_empty_string():
    assert clean_markdown("   \n\n  ") == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T backend python -m pytest tests/test_avvisi_v2_ingest.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'services.avviso_ingest'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/services/avviso_ingest.py
"""Pipeline di ingestione avvisi V2: pulizia, segmentazione, storage, orchestrazione.

Le funzioni di pulizia/segmentazione sono pure. Lo storage scrive sotto
UPLOAD_DIR con storage key relative compatibili con crud_avvisi._storage_key.
"""
from __future__ import annotations

import re

_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_PAGE_ARTIFACT_RE = re.compile(r"^\s*(pagina|pag\.)\s+\d+(\s+di\s+\d+)?\s*$", re.IGNORECASE)


def clean_markdown(raw: str) -> str:
    """Normalizza il markdown sorgente prima della segmentazione."""
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    text = _HTML_COMMENT_RE.sub("", text)
    lines = []
    for line in text.split("\n"):
        stripped = line.rstrip()
        if _PAGE_ARTIFACT_RE.match(stripped):
            continue
        lines.append(stripped)
    cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    return cleaned + "\n" if cleaned else ""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec -T backend python -m pytest tests/test_avvisi_v2_ingest.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/avviso_ingest.py backend/tests/test_avvisi_v2_ingest.py
git commit -m "feat(AVVISI-02): pulizia markdown sorgente per ingestione avvisi"
```

---

### Task 2: Segmentazione (AVVISI-03)

**Files:**
- Modify: `backend/services/avviso_ingest.py`
- Test: `backend/tests/test_avvisi_v2_ingest.py`

**Interfaces:**
- Consumes: `clean_markdown` (Task 1).
- Produces: `Segment` dataclass frozen con campi `ordine: int`, `titolo: str`, `livello: int`, `testo: str`; `segment_markdown(cleaned: str, *, max_chars: int = 8000) -> list[Segment]` — split su heading `#..######`; testo prima del primo heading → segmento "Preambolo" livello 0; segmenti oltre `max_chars` suddivisi su righe vuote; input vuoto → lista vuota.

- [ ] **Step 1: Write the failing tests** (append al file esistente)

```python
from services.avviso_ingest import Segment, segment_markdown


def test_segment_markdown_splits_on_headings_with_preamble():
    cleaned = "Premessa breve.\n\n# Art. 1 Oggetto\ntesto uno\n\n## 1.1 Dettaglio\ntesto due\n"
    segments = segment_markdown(cleaned)
    assert [s.titolo for s in segments] == ["Preambolo", "Art. 1 Oggetto", "1.1 Dettaglio"]
    assert [s.livello for s in segments] == [0, 1, 2]
    assert [s.ordine for s in segments] == [1, 2, 3]
    assert segments[1].testo == "testo uno"


def test_segment_markdown_splits_oversized_sections_on_blank_lines():
    body = "\n\n".join("paragrafo " + str(i) + " " + "x" * 40 for i in range(10))
    cleaned = "# Unica sezione\n" + body + "\n"
    segments = segment_markdown(cleaned, max_chars=120)
    assert len(segments) > 1
    assert all(len(s.testo) <= 120 for s in segments)
    assert all(s.titolo.startswith("Unica sezione") for s in segments)


def test_segment_markdown_empty_returns_empty_list():
    assert segment_markdown("") == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T backend python -m pytest tests/test_avvisi_v2_ingest.py -v`
Expected: FAIL con `ImportError: cannot import name 'Segment'`

- [ ] **Step 3: Write minimal implementation** (append a `avviso_ingest.py`)

```python
from dataclasses import dataclass

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")


@dataclass(frozen=True)
class Segment:
    ordine: int
    titolo: str
    livello: int
    testo: str


def _split_oversized(titolo: str, livello: int, testo: str, max_chars: int) -> list[tuple[str, int, str]]:
    if len(testo) <= max_chars:
        return [(titolo, livello, testo)]
    parts: list[str] = []
    current = ""
    for block in testo.split("\n\n"):
        candidate = (current + "\n\n" + block).strip() if current else block
        if current and len(candidate) > max_chars:
            parts.append(current)
            current = block
        else:
            current = candidate
    if current:
        parts.append(current)
    return [
        (f"{titolo} (parte {i})" if len(parts) > 1 else titolo, livello, part)
        for i, part in enumerate(parts, start=1)
    ]


def segment_markdown(cleaned: str, *, max_chars: int = 8000) -> list[Segment]:
    if not cleaned.strip():
        return []
    sections: list[tuple[str, int, list[str]]] = [("Preambolo", 0, [])]
    for line in cleaned.split("\n"):
        match = _HEADING_RE.match(line)
        if match:
            sections.append((match.group(2).strip(), len(match.group(1)), []))
        else:
            sections[-1][2].append(line)
    segments: list[Segment] = []
    ordine = 0
    for titolo, livello, lines in sections:
        testo = "\n".join(lines).strip()
        if not testo:
            continue
        for sub_titolo, sub_livello, sub_testo in _split_oversized(titolo, livello, testo, max_chars):
            ordine += 1
            segments.append(Segment(ordine=ordine, titolo=sub_titolo, livello=sub_livello, testo=sub_testo))
    return segments
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec -T backend python -m pytest tests/test_avvisi_v2_ingest.py -v`
Expected: 6 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/avviso_ingest.py backend/tests/test_avvisi_v2_ingest.py
git commit -m "feat(AVVISI-03): segmentazione markdown per sezioni con limite dimensione"
```

---

### Task 3: Storage ingest (AVVISI-04)

**Files:**
- Modify: `backend/services/avviso_ingest.py`
- Test: `backend/tests/test_avvisi_v2_ingest.py`

**Interfaces:**
- Consumes: `UPLOAD_DIR`, `MAX_FILE_SIZE`, `sanitize_filename` da `backend/file_upload.py`.
- Produces:
  - `StoredMarkdown` dataclass frozen: `storage_key: str`, `absolute_path: Path`, `sha256: str`, `size_bytes: int`.
  - `save_ingest_markdown(avviso_id: int, original_filename: str, contents: bytes) -> StoredMarkdown` — valida estensione `.md`, dimensione ≤ `MAX_FILE_SIZE`, decodifica UTF-8; key `avvisi/<avviso_id>/<sha12>_source.md`.
  - `save_cleaned_markdown(avviso_id: int, source_sha256: str, cleaned: str) -> StoredMarkdown` — key `avvisi/<avviso_id>/<sha12>_cleaned.md` dove `sha12 = source_sha256[:12]`.
  - Errori di validazione: `ValueError` con messaggio in italiano.

- [ ] **Step 1: Write the failing tests** (append; nota il fixture `tmp_upload_dir`)

```python
import hashlib

from services import avviso_ingest
from services.avviso_ingest import save_cleaned_markdown, save_ingest_markdown


@pytest.fixture
def tmp_upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(avviso_ingest, "UPLOAD_DIR", tmp_path)
    return tmp_path


def test_save_ingest_markdown_writes_under_avvisi_root(tmp_upload_dir):
    contents = "# Avviso FAPI 1/2026\ntesto\n".encode("utf-8")
    stored = save_ingest_markdown(7, "Avviso FAPI 1-2026.md", contents)
    expected_sha = hashlib.sha256(contents).hexdigest()
    assert stored.sha256 == expected_sha
    assert stored.storage_key == f"avvisi/7/{expected_sha[:12]}_source.md"
    assert stored.absolute_path == tmp_upload_dir / stored.storage_key
    assert stored.absolute_path.read_bytes() == contents
    assert stored.size_bytes == len(contents)


def test_save_ingest_markdown_rejects_non_md_and_non_utf8(tmp_upload_dir):
    with pytest.raises(ValueError, match="\\.md"):
        save_ingest_markdown(7, "avviso.pdf", b"%PDF-")
    with pytest.raises(ValueError, match="UTF-8"):
        save_ingest_markdown(7, "avviso.md", b"\xff\xfe\x00bad")


def test_save_ingest_markdown_rejects_oversized(tmp_upload_dir, monkeypatch):
    monkeypatch.setattr(avviso_ingest, "MAX_FILE_SIZE", 10)
    with pytest.raises(ValueError, match="grande"):
        save_ingest_markdown(7, "avviso.md", b"x" * 11)


def test_save_cleaned_markdown_uses_source_sha_prefix(tmp_upload_dir):
    stored = save_cleaned_markdown(7, "a" * 64, "# Pulito\n")
    assert stored.storage_key == f"avvisi/7/{'a' * 12}_cleaned.md"
    assert stored.absolute_path.read_text(encoding="utf-8") == "# Pulito\n"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T backend python -m pytest tests/test_avvisi_v2_ingest.py -v`
Expected: FAIL con `ImportError: cannot import name 'save_ingest_markdown'`

- [ ] **Step 3: Write minimal implementation** (append a `avviso_ingest.py`)

```python
import hashlib
from pathlib import Path

from file_upload import MAX_FILE_SIZE, UPLOAD_DIR  # noqa: E402  (root uploads condivisa)


@dataclass(frozen=True)
class StoredMarkdown:
    storage_key: str
    absolute_path: Path
    sha256: str
    size_bytes: int


def _write_markdown(avviso_id: int, filename: str, contents: bytes) -> StoredMarkdown:
    storage_key = f"avvisi/{avviso_id}/{filename}"
    absolute_path = UPLOAD_DIR / storage_key
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    absolute_path.write_bytes(contents)
    return StoredMarkdown(
        storage_key=storage_key,
        absolute_path=absolute_path,
        sha256=hashlib.sha256(contents).hexdigest(),
        size_bytes=len(contents),
    )


def save_ingest_markdown(avviso_id: int, original_filename: str, contents: bytes) -> StoredMarkdown:
    if not (original_filename or "").lower().endswith(".md"):
        raise ValueError("Sono ammessi solo file markdown (.md)")
    if len(contents) > MAX_FILE_SIZE:
        raise ValueError(f"File troppo grande. Massimo: {MAX_FILE_SIZE / 1024 / 1024:.1f}MB")
    try:
        contents.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Il file markdown deve essere codificato UTF-8") from exc
    sha = hashlib.sha256(contents).hexdigest()
    return _write_markdown(avviso_id, f"{sha[:12]}_source.md", contents)


def save_cleaned_markdown(avviso_id: int, source_sha256: str, cleaned: str) -> StoredMarkdown:
    return _write_markdown(avviso_id, f"{source_sha256[:12]}_cleaned.md", cleaned.encode("utf-8"))
```

Nota: `MAX_FILE_SIZE` va riletto via modulo (`avviso_ingest.MAX_FILE_SIZE`) perché i test lo monkeypatchano: in `save_ingest_markdown` usare `import sys`-free accesso al globale del modulo (il codice sopra funziona perché monkeypatch sostituisce il globale del modulo `avviso_ingest`). Stessa cosa per `UPLOAD_DIR` in `_write_markdown`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec -T backend python -m pytest tests/test_avvisi_v2_ingest.py -v`
Expected: 10 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/avviso_ingest.py backend/tests/test_avvisi_v2_ingest.py
git commit -m "feat(AVVISI-04): storage markdown sorgente e pulito sotto uploads/avvisi"
```

---

### Task 4: Schemi LLM e prompt estrazione (AVVISI-05)

**Files:**
- Modify: `backend/ai_agents/llm_schemas.py`
- Create: `backend/ai_agents/prompts/avviso_extractor_v1.py`
- Test: `backend/tests/test_avvisi_v2_extractor.py`

**Interfaces:**
- Produces:
  - `AvvisoRegolaLLM(BaseModel)`: `chiave: str`, `sottocategoria: Optional[str] = None`, `valore: Any` (dict raw dal LLM), `unita: Optional[str] = None`, `testo_originale: str`, `riferimento_articolo: Optional[str] = None`, `confidence: float` (clampata 0..1, default 0.5).
  - `AvvisoScadenzaLLM(BaseModel)`: `tipo: str` (coercizione a valori `TipoScadenza`, fallback `"altro"`), `data: str` (ISO), `descrizione: str`, `tassativa: bool = False`, `testo_originale: str`, `riferimento_articolo: Optional[str] = None`, `confidence: float` (clampata, default 0.5).
  - `AvvisoEstrazioneLLM(BaseModel)`: `regole: list[AvvisoRegolaLLM] = []`, `scadenze: list[AvvisoScadenzaLLM] = []` — elementi non validi scartati (validator `mode="before"` che tenta la validazione item per item).
  - Prompt: `SYSTEM_PROMPT_ESTRAZIONE: str`; `GRUPPI_CATEGORIE: dict[str, list[str]]` con chiavi `economiche` (massimali, parametri_costo), `soggetti` (destinatari, beneficiari, aiuti_di_stato), `procedura` (presentazione, valutazione), `gestione` (attuazione, rendicontazione, delega, variazioni), `scadenze` (lista vuota: estrae scadenze); `build_extraction_prompt(gruppo: str, categorie: list[str], testo: str) -> str`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_avvisi_v2_extractor.py
"""ONDATA ARCHIVIO AVVISI — V2: schemi LLM, collector avviso_extractor, pipeline, apply."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_agents.llm_schemas import AvvisoEstrazioneLLM
from ai_agents.prompts.avviso_extractor_v1 import (
    GRUPPI_CATEGORIE,
    SYSTEM_PROMPT_ESTRAZIONE,
    build_extraction_prompt,
)


def test_estrazione_schema_clamps_confidence_and_drops_invalid_items():
    parsed = AvvisoEstrazioneLLM.model_validate({
        "regole": [
            {
                "chiave": "contributo_massimo",
                "valore": {"tipo": "denaro", "importo": "50000", "valuta": "EUR"},
                "testo_originale": "Il contributo massimo è 50.000 euro",
                "confidence": 1.7,
            },
            {"senza_campi_obbligatori": True},
        ],
        "scadenze": [
            {
                "tipo": "tipologia_ignota",
                "data": "2026-09-30",
                "descrizione": "Termine presentazione",
                "testo_originale": "entro il 30/09/2026",
                "confidence": -3,
            }
        ],
    })
    assert len(parsed.regole) == 1
    assert parsed.regole[0].confidence == 1.0
    assert len(parsed.scadenze) == 1
    assert parsed.scadenze[0].tipo == "altro"
    assert parsed.scadenze[0].confidence == 0.0


def test_gruppi_categorie_cover_expected_categories():
    flat = [c for cats in GRUPPI_CATEGORIE.values() for c in cats]
    assert "massimali" in flat and "rendicontazione" in flat
    assert GRUPPI_CATEGORIE["scadenze"] == []


def test_build_extraction_prompt_mentions_categories_and_text():
    prompt = build_extraction_prompt("economiche", ["massimali", "parametri_costo"], "# Art. 5\nMassimale 50k")
    assert "massimali" in prompt and "parametri_costo" in prompt
    assert "Massimale 50k" in prompt
    assert "JSON" in SYSTEM_PROMPT_ESTRAZIONE
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T backend python -m pytest tests/test_avvisi_v2_extractor.py -v`
Expected: FAIL con `ImportError: cannot import name 'AvvisoEstrazioneLLM'`

- [ ] **Step 3: Write minimal implementation**

Append a `backend/ai_agents/llm_schemas.py` (usare gli import già presenti nel file; aggiungere se mancanti `Any`, `field_validator`, `model_validator`):

```python
_TIPI_SCADENZA_VALIDI = {"presentazione", "avvio", "chiusura", "rendicontazione", "altro"}


def _clamp01(value: Any, default: float = 0.5) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


class AvvisoRegolaLLM(BaseModel):
    chiave: str
    sottocategoria: Optional[str] = None
    valore: Any = None
    unita: Optional[str] = None
    testo_originale: str
    riferimento_articolo: Optional[str] = None
    confidence: float = 0.5

    @field_validator("confidence", mode="before")
    @classmethod
    def _clamp_confidence(cls, value: Any) -> float:
        return _clamp01(value)


class AvvisoScadenzaLLM(BaseModel):
    tipo: str = "altro"
    data: str
    descrizione: str
    tassativa: bool = False
    testo_originale: str
    riferimento_articolo: Optional[str] = None
    confidence: float = 0.5

    @field_validator("tipo", mode="before")
    @classmethod
    def _coerce_tipo(cls, value: Any) -> str:
        normalized = str(value or "").strip().lower()
        return normalized if normalized in _TIPI_SCADENZA_VALIDI else "altro"

    @field_validator("confidence", mode="before")
    @classmethod
    def _clamp_confidence(cls, value: Any) -> float:
        return _clamp01(value)


class AvvisoEstrazioneLLM(BaseModel):
    regole: list[AvvisoRegolaLLM] = []
    scadenze: list[AvvisoScadenzaLLM] = []

    @field_validator("regole", "scadenze", mode="before")
    @classmethod
    def _drop_invalid_items(cls, value: Any, info) -> list:
        if not isinstance(value, list):
            return []
        model = AvvisoRegolaLLM if info.field_name == "regole" else AvvisoScadenzaLLM
        valid = []
        for item in value:
            try:
                valid.append(model.model_validate(item))
            except Exception:
                continue
        return valid
```

Create `backend/ai_agents/prompts/avviso_extractor_v1.py`:

```python
"""Prompt v1 per l'agente avviso_extractor (estrazione regole/scadenze da avvisi MD)."""

SYSTEM_PROMPT_ESTRAZIONE = (
    "Sei un estrattore di regole normative da avvisi di fondi interprofessionali italiani "
    "(Fondimpresa, Formazienda, FAPI, bandi regionali). Rispondi SOLO con un oggetto JSON valido, "
    "senza testo aggiuntivo. Non inventare valori: estrai solo cio' che e' scritto nel testo e "
    "riporta sempre la citazione esatta in 'testo_originale'. Se un dato non e' presente, ometti la voce. "
    "Formato valori regola: oggetto con campo 'tipo' tra: testo, denaro (importo, valuta), "
    "percentuale (valore), numero (valore), ore (valore), durata_giorni (valore), data (valore ISO), "
    "booleano (valore), insieme (valori), intervallo (minimo, massimo), formula (espressione)."
)

GRUPPI_CATEGORIE: dict[str, list[str]] = {
    "economiche": ["massimali", "parametri_costo"],
    "soggetti": ["destinatari", "beneficiari", "aiuti_di_stato"],
    "procedura": ["presentazione", "valutazione"],
    "gestione": ["attuazione", "rendicontazione", "delega", "variazioni"],
    "scadenze": [],
}


def build_extraction_prompt(gruppo: str, categorie: list[str], testo: str) -> str:
    if gruppo == "scadenze":
        istruzione = (
            "Estrai tutte le scadenze e finestre temporali. Rispondi con: "
            '{"scadenze": [{"tipo": "presentazione|avvio|chiusura|rendicontazione|altro", '
            '"data": "YYYY-MM-DD", "descrizione": "...", "tassativa": true/false, '
            '"testo_originale": "citazione esatta", "riferimento_articolo": "...", "confidence": 0.0-1.0}]}'
        )
    else:
        istruzione = (
            f"Estrai le regole delle categorie: {', '.join(categorie)}. Rispondi con: "
            '{"regole": [{"chiave": "snake_case", "sottocategoria": "...", '
            '"valore": {"tipo": "..."}, "unita": "...", "testo_originale": "citazione esatta", '
            '"riferimento_articolo": "...", "confidence": 0.0-1.0}]}'
        )
    return f"{istruzione}\n\nTESTO AVVISO:\n{testo}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec -T backend python -m pytest tests/test_avvisi_v2_extractor.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/ai_agents/llm_schemas.py backend/ai_agents/prompts/avviso_extractor_v1.py backend/tests/test_avvisi_v2_extractor.py
git commit -m "feat(AVVISI-05): schemi LLM e prompt estrazione avviso per categoria"
```

---

### Task 5: Collector avviso_extractor + registrazione registry (AVVISI-06)

**Files:**
- Create: `backend/ai_agents/avviso_extractor.py`
- Modify: `backend/ai_agents/__init__.py`
- Test: `backend/tests/test_avvisi_v2_extractor.py`

**Interfaces:**
- Consumes: `clean-file` letto da `UPLOAD_DIR / revision.cleaned_md_path`; `segment_markdown`; `call_ollama_json(system_prompt=..., user_prompt=...)` (da mockare); `GRUPPI_CATEGORIE`, `build_extraction_prompt`, `SYSTEM_PROMPT_ESTRAZIONE`; `AvvisoEstrazioneLLM`; `avvisi_schemas.RuleValue` (TypeAdapter) per validare `valore`.
- Produces: `collect_avviso_extraction_suggestions(db, *, entity_type=None, entity_id=None, input_payload=None) -> dict` con `{"summary": {...}, "suggestions": [...]}`. Ogni suggestion regola:
  - `suggestion_type="avviso_regola_proposta"`, `entity_type="avviso_revisione"`, `entity_id=<revision_id>`, `severity="medium"`, `title`, `description`, `payload` (dati raw), `confidence_score`, `auto_fix_available=True`, `auto_fix_payload={"kind": "avviso_estrazione", "target": "regola", "revision_id": N, "proposal": {campi conformi a AvvisoRegolaProposal}}`.
  - Scadenze: `suggestion_type="avviso_scadenza_proposta"`, `target: "scadenza"`, proposal conforme a `AvvisoScadenzaProposal` (data con timezone Europe/Rome se il LLM dà solo la data).
  - `needs_careful_review=True` nel proposal se confidence < 0.75 o valore non conforme a `RuleValue` (in quel caso fallback `{"tipo": "testo", "valore": json.dumps(raw)}`).
  - Registry: agente `avviso_extractor`, `supported_entity_types=["avviso_revisione"]`, `triggers=["manual", "event:avviso_revisione_ingest"]`, `allowed_roles=["admin", "manager"]`, `version="1.0"`, kill switch `agent_env_name("avviso_extractor")` → `AGENT_AVVISO_EXTRACTOR_ENABLED`.
  - Errore LLM su un gruppo: non fallisce il run; incrementa `summary["gruppi_falliti"]`.

- [ ] **Step 1: Write the failing tests** (append a `test_avvisi_v2_extractor.py`)

```python
import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

import models
import crud_avvisi
import schemas_avvisi as avvisi_schemas
from database import Base

from ai_agents import get_agent_definition
from ai_agents import avviso_extractor as extractor_module
from services import avviso_ingest


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine(
        "sqlite:///{}".format(tmp_path / "avvisi_v2.db"),
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def user(db_session):
    import auth
    record = models.User(
        username="revisore",
        email="revisore@example.com",
        hashed_password=auth.get_password_hash("Password1!"),
        role="admin",
        is_active=True,
    )
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)
    return record


@pytest.fixture
def revision_with_cleaned_md(db_session, user, tmp_path, monkeypatch):
    monkeypatch.setattr(avviso_ingest, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(extractor_module, "UPLOAD_DIR", tmp_path)
    avviso = models.Avviso(
        codice="1/2026", ente_erogatore="fapi", fondo="fapi", numero="1", anno=2026,
        titolo="Avviso FAPI 1/2026", stato="bozza",
    )
    db_session.add(avviso)
    db_session.commit()
    contents = "# Art. 5 Massimali\nContributo massimo 50.000 euro.\n".encode("utf-8")
    sha = hashlib.sha256(contents).hexdigest()
    stored = avviso_ingest.save_ingest_markdown(avviso.id, "avviso.md", contents)
    cleaned = avviso_ingest.save_cleaned_markdown(avviso.id, sha, contents.decode("utf-8"))
    revision = crud_avvisi.create_next_revision(
        db_session,
        avviso.id,
        avvisi_schemas.AvvisoRevisioneCreate(
            titolo="Avviso FAPI 1/2026",
            source_md_path=stored.storage_key,
            cleaned_md_path=cleaned.storage_key,
            original_filename="avviso.md",
            source_sha256=sha,
        ),
        created_by_user_id=user.id,
    )
    return revision


def _fake_llm_factory(calls):
    def fake_call_ollama_json(*, system_prompt, user_prompt):
        calls.append(user_prompt)
        if "scadenze" in user_prompt.split("TESTO AVVISO:")[0]:
            return {
                "scadenze": [{
                    "tipo": "presentazione",
                    "data": "2026-09-30",
                    "descrizione": "Termine presentazione piani",
                    "tassativa": True,
                    "testo_originale": "entro il 30/09/2026",
                    "confidence": 0.9,
                }]
            }
        if "massimali" in user_prompt:
            return {
                "regole": [{
                    "chiave": "contributo_massimo",
                    "valore": {"tipo": "denaro", "importo": "50000", "valuta": "EUR"},
                    "testo_originale": "Contributo massimo 50.000 euro.",
                    "riferimento_articolo": "Art. 5",
                    "confidence": 0.9,
                }]
            }
        return {"regole": []}
    return fake_call_ollama_json


def test_registry_exposes_avviso_extractor():
    definition = get_agent_definition("avviso_extractor")
    assert definition is not None
    assert definition["supported_entity_types"] == ["avviso_revisione"]
    assert definition["kill_switch_env"] == "AGENT_AVVISO_EXTRACTOR_ENABLED"
    assert "runner" not in definition


def test_collector_builds_suggestions_from_llm(db_session, revision_with_cleaned_md, monkeypatch):
    calls = []
    monkeypatch.setattr(extractor_module, "call_ollama_json", _fake_llm_factory(calls))
    result = extractor_module.collect_avviso_extraction_suggestions(
        db_session, entity_type="avviso_revisione", entity_id=revision_with_cleaned_md.id,
    )
    assert len(calls) == 5  # 4 gruppi regole + 1 scadenze
    tipi = {s["suggestion_type"] for s in result["suggestions"]}
    assert tipi == {"avviso_regola_proposta", "avviso_scadenza_proposta"}
    regola = next(s for s in result["suggestions"] if s["suggestion_type"] == "avviso_regola_proposta")
    fix = regola["auto_fix_payload"]
    assert fix["kind"] == "avviso_estrazione"
    assert fix["target"] == "regola"
    assert fix["revision_id"] == revision_with_cleaned_md.id
    proposal = avvisi_schemas.AvvisoRegolaProposal.model_validate(fix["proposal"])
    assert proposal.categoria == "massimali"
    assert proposal.needs_careful_review is False
    scadenza = next(s for s in result["suggestions"] if s["suggestion_type"] == "avviso_scadenza_proposta")
    sc_proposal = avvisi_schemas.AvvisoScadenzaProposal.model_validate(scadenza["auto_fix_payload"]["proposal"])
    assert sc_proposal.data.tzinfo is not None


def test_collector_marks_invalid_rule_value_for_careful_review(db_session, revision_with_cleaned_md, monkeypatch):
    def bad_llm(*, system_prompt, user_prompt):
        if "massimali" in user_prompt:
            return {"regole": [{
                "chiave": "contributo_massimo",
                "valore": {"tipo": "inesistente", "x": 1},
                "testo_originale": "Contributo massimo 50.000 euro.",
                "confidence": 0.9,
            }]}
        return {"regole": [], "scadenze": []}
    monkeypatch.setattr(extractor_module, "call_ollama_json", bad_llm)
    result = extractor_module.collect_avviso_extraction_suggestions(
        db_session, entity_type="avviso_revisione", entity_id=revision_with_cleaned_md.id,
    )
    regola = next(s for s in result["suggestions"] if s["suggestion_type"] == "avviso_regola_proposta")
    proposal = regola["auto_fix_payload"]["proposal"]
    assert proposal["needs_careful_review"] is True
    assert proposal["valore"]["tipo"] == "testo"


def test_collector_tolerates_llm_failure_per_group(db_session, revision_with_cleaned_md, monkeypatch):
    def flaky(*, system_prompt, user_prompt):
        raise RuntimeError("LLM down")
    monkeypatch.setattr(extractor_module, "call_ollama_json", flaky)
    result = extractor_module.collect_avviso_extraction_suggestions(
        db_session, entity_type="avviso_revisione", entity_id=revision_with_cleaned_md.id,
    )
    assert result["suggestions"] == []
    assert result["summary"]["gruppi_falliti"] == 5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T backend python -m pytest tests/test_avvisi_v2_extractor.py -v`
Expected: FAIL con `ImportError: cannot import name 'avviso_extractor'`

- [ ] **Step 3: Write minimal implementation**

Create `backend/ai_agents/avviso_extractor.py`:

```python
"""Collector puro per l'estrazione LLM di regole/scadenze da una revisione avviso.

NON scrive su DB: ritorna {"summary", "suggestions"}; la persistenza avviene
solo in agent_workflows.run_agent_workflow (regola registry).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional
from zoneinfo import ZoneInfo

from pydantic import TypeAdapter

import models
import schemas_avvisi as avvisi_schemas
from file_upload import UPLOAD_DIR

from .llm import call_ollama_json
from .llm_schemas import AvvisoEstrazioneLLM
from .prompts.avviso_extractor_v1 import (
    GRUPPI_CATEGORIE,
    SYSTEM_PROMPT_ESTRAZIONE,
    build_extraction_prompt,
)

logger = logging.getLogger(__name__)

CONFIDENCE_REVIEW_THRESHOLD = 0.75
MAX_PROMPT_CHARS = 24000
_TZ_ROME = ZoneInfo("Europe/Rome")
_rule_value_adapter = TypeAdapter(avvisi_schemas.RuleValue)


def _normalize_rule_value(raw: Any) -> tuple[dict, bool]:
    """Ritorna (valore validato, needs_careful_review per valore non conforme)."""
    try:
        validated = _rule_value_adapter.validate_python(raw)
        return validated.model_dump(mode="json"), False
    except Exception:
        return {"tipo": "testo", "valore": json.dumps(raw, ensure_ascii=False, default=str)}, True


def _parse_deadline_date(raw: str):
    from datetime import datetime
    value = datetime.fromisoformat(str(raw).strip())
    if value.tzinfo is None:
        value = value.replace(tzinfo=_TZ_ROME)
    return value


def _categoria_for(chiave_gruppo: str, categorie: list[str], sottocategoria: Optional[str]) -> str:
    if sottocategoria and sottocategoria in categorie:
        return sottocategoria
    return categorie[0] if categorie else "altro"


def collect_avviso_extraction_suggestions(
    db,
    *,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    input_payload: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    if entity_type != "avviso_revisione" or not entity_id:
        raise ValueError("avviso_extractor richiede entity_type=avviso_revisione ed entity_id")
    revision = (
        db.query(models.AvvisoRevisione)
        .filter(models.AvvisoRevisione.id == entity_id)
        .first()
    )
    if revision is None:
        raise ValueError(f"Revisione avviso {entity_id} non trovata")
    if not revision.cleaned_md_path:
        raise ValueError("La revisione non ha un markdown pulito: eseguire prima la pulizia")
    cleaned = (UPLOAD_DIR / revision.cleaned_md_path).read_text(encoding="utf-8")
    testo = cleaned[:MAX_PROMPT_CHARS]

    suggestions: list[dict[str, Any]] = []
    gruppi_falliti = 0
    for gruppo, categorie in GRUPPI_CATEGORIE.items():
        prompt = build_extraction_prompt(gruppo, categorie, testo)
        try:
            raw = call_ollama_json(system_prompt=SYSTEM_PROMPT_ESTRAZIONE, user_prompt=prompt)
        except Exception as exc:
            gruppi_falliti += 1
            logger.warning("avviso_extractor: gruppo %s fallito: %s", gruppo, exc)
            continue
        parsed = AvvisoEstrazioneLLM.model_validate(raw if isinstance(raw, dict) else {})
        for regola in parsed.regole:
            valore, valore_sospetto = _normalize_rule_value(regola.valore)
            needs_review = valore_sospetto or regola.confidence < CONFIDENCE_REVIEW_THRESHOLD
            proposal = {
                "categoria": _categoria_for(gruppo, categorie, regola.sottocategoria),
                "sottocategoria": regola.sottocategoria,
                "chiave": regola.chiave,
                "valore": valore,
                "unita": regola.unita,
                "testo_originale": regola.testo_originale,
                "riferimento_articolo": regola.riferimento_articolo,
                "confidence": round(regola.confidence, 4),
                "needs_careful_review": needs_review,
            }
            suggestions.append({
                "suggestion_type": "avviso_regola_proposta",
                "entity_type": "avviso_revisione",
                "entity_id": revision.id,
                "severity": "medium",
                "title": f"Regola proposta: {regola.chiave}",
                "description": regola.testo_originale[:500],
                "payload": {"gruppo": gruppo, "raw": regola.model_dump(mode="json")},
                "confidence_score": regola.confidence,
                "auto_fix_available": True,
                "auto_fix_payload": {
                    "kind": "avviso_estrazione",
                    "target": "regola",
                    "revision_id": revision.id,
                    "proposal": proposal,
                },
            })
        for scadenza in parsed.scadenze:
            try:
                data = _parse_deadline_date(scadenza.data)
            except ValueError:
                logger.warning("avviso_extractor: data scadenza non parsabile: %r", scadenza.data)
                continue
            proposal = {
                "tipo": scadenza.tipo,
                "data": data.isoformat(),
                "descrizione": scadenza.descrizione,
                "tassativa": scadenza.tassativa,
                "testo_originale": scadenza.testo_originale,
                "riferimento_articolo": scadenza.riferimento_articolo,
                "confidence": round(scadenza.confidence, 4),
                "needs_careful_review": scadenza.confidence < CONFIDENCE_REVIEW_THRESHOLD,
            }
            suggestions.append({
                "suggestion_type": "avviso_scadenza_proposta",
                "entity_type": "avviso_revisione",
                "entity_id": revision.id,
                "severity": "medium",
                "title": f"Scadenza proposta: {scadenza.tipo} {data.date().isoformat()}",
                "description": scadenza.descrizione[:500],
                "payload": {"raw": scadenza.model_dump(mode="json")},
                "confidence_score": scadenza.confidence,
                "auto_fix_available": True,
                "auto_fix_payload": {
                    "kind": "avviso_estrazione",
                    "target": "scadenza",
                    "revision_id": revision.id,
                    "proposal": proposal,
                },
            })

    summary = {
        "revision_id": revision.id,
        "gruppi_totali": len(GRUPPI_CATEGORIE),
        "gruppi_falliti": gruppi_falliti,
        "regole_proposte": sum(1 for s in suggestions if s["suggestion_type"] == "avviso_regola_proposta"),
        "scadenze_proposte": sum(1 for s in suggestions if s["suggestion_type"] == "avviso_scadenza_proposta"),
    }
    return {"summary": summary, "suggestions": suggestions}
```

Modify `backend/ai_agents/__init__.py` — aggiungere import e definizione:

```python
from .avviso_extractor import collect_avviso_extraction_suggestions
```

runner wrapper (accanto agli altri `_run_*`):

```python
def _run_avviso_extractor(db, *, entity_type=None, entity_id=None, input_payload=None):
    return collect_avviso_extraction_suggestions(
        db, entity_type=entity_type, entity_id=entity_id, input_payload=input_payload
    )
```

voce in `_AGENT_DEFINITIONS`:

```python
    "avviso_extractor": {
        "name": "avviso_extractor",
        "description": "Estrae regole e scadenze da una revisione avviso in markdown",
        "supported_entity_types": ["avviso_revisione"],
        "triggers": ["manual", "event:avviso_revisione_ingest"],
        "kill_switch_env": agent_env_name("avviso_extractor"),
        "allowed_roles": ["admin", "manager"],
        "version": "1.0",
        "runner": _run_avviso_extractor,
    },
```

e aggiungere `"collect_avviso_extraction_suggestions"` a `__all__`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec -T backend python -m pytest tests/test_avvisi_v2_extractor.py -v`
Expected: tutti PASS (7 test nel file finora)

- [ ] **Step 5: Run existing registry tests (no regressioni)**

Run: `docker compose exec -T backend python -m pytest tests/test_agents_registry_workflow.py tests/test_agent_kill_switch.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/ai_agents/avviso_extractor.py backend/ai_agents/__init__.py backend/tests/test_avvisi_v2_extractor.py
git commit -m "feat(AVVISI-06): agente avviso_extractor nel registry con collector puro"
```

---

### Task 6: Orchestrazione pipeline (AVVISI-07)

**Files:**
- Modify: `backend/services/avviso_ingest.py`
- Test: `backend/tests/test_avvisi_v2_extractor.py`

**Interfaces:**
- Consumes: `clean_markdown`, `segment_markdown`, `save_cleaned_markdown`, `agent_workflows.run_agent_workflow`, modelli `AvvisoRevisione`/`AgentRun`.
- Produces:
  - `prepare_revision_content(db, revision_id: int) -> models.AvvisoRevisione` — legge il source MD, pulisce, salva cleaned, transita `caricato → pulito → segmentato`; se il testo pulito è vuoto o senza segmenti → `stato_estrazione="errore"` e `ValueError`.
  - `run_extraction_pipeline(db, revision_id: int, *, user_id: Optional[int] = None) -> models.AgentRun` — chiama `prepare_revision_content` se `stato_estrazione == "caricato"`, poi `in_estrazione`, esegue `run_agent_workflow(agent_type="avviso_extractor", entity_type="avviso_revisione", entity_id=revision_id, requested_by_user_id=user_id)`, collega `revision.extraction_run_id`, stato finale `estratto` (run `completed`) o `errore`.

- [ ] **Step 1: Write the failing tests** (append a `test_avvisi_v2_extractor.py`)

```python
import agent_workflows
from services.avviso_ingest import prepare_revision_content, run_extraction_pipeline


@pytest.fixture
def revision_caricata(db_session, user, tmp_path, monkeypatch):
    """Revisione con solo source_md_path (stato caricato), senza cleaned."""
    monkeypatch.setattr(avviso_ingest, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(extractor_module, "UPLOAD_DIR", tmp_path)
    avviso = models.Avviso(
        codice="2/2026", ente_erogatore="fapi", fondo="fapi", numero="2", anno=2026,
        titolo="Avviso FAPI 2/2026", stato="bozza",
    )
    db_session.add(avviso)
    db_session.commit()
    contents = "# Art. 5 Massimali\r\n\r\n\r\nContributo massimo 50.000 euro.\n".encode("utf-8")
    stored = avviso_ingest.save_ingest_markdown(avviso.id, "avviso.md", contents)
    revision = crud_avvisi.create_next_revision(
        db_session,
        avviso.id,
        avvisi_schemas.AvvisoRevisioneCreate(
            titolo="Avviso FAPI 2/2026",
            source_md_path=stored.storage_key,
            original_filename="avviso.md",
            source_sha256=stored.sha256,
        ),
        created_by_user_id=user.id,
    )
    assert revision.stato_estrazione == "caricato"
    return revision


def test_prepare_revision_content_transitions_and_writes_cleaned(db_session, revision_caricata):
    revision = prepare_revision_content(db_session, revision_caricata.id)
    assert revision.stato_estrazione == "segmentato"
    assert revision.cleaned_md_path
    cleaned_text = (avviso_ingest.UPLOAD_DIR / revision.cleaned_md_path).read_text(encoding="utf-8")
    assert "\r" not in cleaned_text and "\n\n\n" not in cleaned_text


def test_run_extraction_pipeline_completes_and_links_run(db_session, revision_caricata, monkeypatch):
    monkeypatch.setattr(extractor_module, "call_ollama_json", _fake_llm_factory([]))
    run = run_extraction_pipeline(db_session, revision_caricata.id, user_id=None)
    db_session.refresh(revision_caricata)
    assert run.status == "completed"
    assert revision_caricata.extraction_run_id == run.id
    assert revision_caricata.stato_estrazione == "estratto"
    assert run.suggestions_count >= 2  # regola massimali + scadenza


def test_run_extraction_pipeline_marks_errore_on_workflow_failure(db_session, revision_caricata, monkeypatch):
    def boom(db, **kwargs):
        raise ValueError("Agente non supportato")
    monkeypatch.setattr(avviso_ingest, "run_agent_workflow", boom)
    with pytest.raises(ValueError):
        run_extraction_pipeline(db_session, revision_caricata.id, user_id=None)
    db_session.refresh(revision_caricata)
    assert revision_caricata.stato_estrazione == "errore"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T backend python -m pytest tests/test_avvisi_v2_extractor.py -v`
Expected: FAIL con `ImportError: cannot import name 'prepare_revision_content'`

- [ ] **Step 3: Write minimal implementation** (append a `avviso_ingest.py`)

```python
from typing import Optional

import models
from agent_workflows import run_agent_workflow


def _get_revision(db, revision_id: int) -> "models.AvvisoRevisione":
    revision = (
        db.query(models.AvvisoRevisione)
        .filter(models.AvvisoRevisione.id == revision_id)
        .first()
    )
    if revision is None:
        raise ValueError(f"Revisione avviso {revision_id} non trovata")
    return revision


def _set_stato(db, revision, stato: str) -> None:
    revision.stato_estrazione = stato
    db.commit()


def prepare_revision_content(db, revision_id: int):
    revision = _get_revision(db, revision_id)
    raw = (UPLOAD_DIR / revision.source_md_path).read_text(encoding="utf-8")
    cleaned = clean_markdown(raw)
    if not cleaned:
        _set_stato(db, revision, "errore")
        raise ValueError("Il markdown sorgente è vuoto dopo la pulizia")
    stored = save_cleaned_markdown(revision.avviso_id, revision.source_sha256, cleaned)
    revision.cleaned_md_path = stored.storage_key
    _set_stato(db, revision, "pulito")
    if not segment_markdown(cleaned):
        _set_stato(db, revision, "errore")
        raise ValueError("Nessun segmento estraibile dal markdown pulito")
    _set_stato(db, revision, "segmentato")
    return revision


def run_extraction_pipeline(db, revision_id: int, *, user_id: Optional[int] = None):
    revision = _get_revision(db, revision_id)
    if revision.stato_estrazione == "caricato":
        revision = prepare_revision_content(db, revision_id)
    _set_stato(db, revision, "in_estrazione")
    try:
        run = run_agent_workflow(
            db,
            agent_type="avviso_extractor",
            entity_type="avviso_revisione",
            entity_id=revision_id,
            requested_by_user_id=user_id,
        )
    except Exception:
        _set_stato(db, revision, "errore")
        raise
    revision.extraction_run_id = run.id
    _set_stato(db, revision, "estratto" if run.status == "completed" else "errore")
    return run
```

Nota: `run_agent_workflow` va referenziato come attributo di modulo (il test lo monkeypatcha su `avviso_ingest.run_agent_workflow`) — l'import a livello modulo come sopra è corretto.

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec -T backend python -m pytest tests/test_avvisi_v2_extractor.py tests/test_avvisi_v2_ingest.py -v`
Expected: tutti PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/avviso_ingest.py backend/tests/test_avvisi_v2_extractor.py
git commit -m "feat(AVVISI-07): orchestrazione pipeline estrazione con stati revisione"
```

---

### Task 7: Apply umano → materializzazione regole/scadenze (AVVISI-08)

**Files:**
- Modify: `backend/services/suggestion_apply.py`
- Test: `backend/tests/test_avvisi_v2_extractor.py`

**Interfaces:**
- Consumes: `crud_avvisi.create_rule_proposal(db, revision_id, payload, commit=False)`, `crud_avvisi.review_rule(db, rule_id, action="approva", reviewer_user_id=...)`, `crud_avvisi.create_deadline_proposal`, `crud_avvisi.review_deadline`; payload `auto_fix_payload` con `kind="avviso_estrazione"` (Task 5).
- Produces: `apply_avviso_extraction_suggestion(db, suggestion, *, user_id) -> dict` — richiede `user_id` (revisore umano) non nullo; valida il proposal con `AvvisoRegolaProposal`/`AvvisoScadenzaProposal` impostando `origin_suggestion_id=suggestion.id`; crea la proposta e la approva transazionalmente col medesimo revisore; ritorna `{"applied": ["avviso_regola:<id>"], "skipped": []}` (o `avviso_scadenza:<id>`). Dispatch aggiunto in `apply_suggestion` per `kind == "avviso_estrazione"`.

- [ ] **Step 1: Write the failing tests** (append a `test_avvisi_v2_extractor.py`)

```python
from services.suggestion_apply import apply_suggestion


def _make_suggestion(db_session, revision, target, proposal):
    run = models.AgentRun(agent_type="avviso_extractor", status="completed")
    db_session.add(run)
    db_session.flush()
    suggestion = models.AgentSuggestion(
        run_id=run.id,
        suggestion_type=f"avviso_{target}_proposta",
        entity_type="avviso_revisione",
        entity_id=revision.id,
        severity="medium",
        status="pending",
        title="proposta",
        auto_fix_available=True,
        auto_fix_payload=json.dumps({
            "kind": "avviso_estrazione",
            "target": target,
            "revision_id": revision.id,
            "proposal": proposal,
        }),
    )
    db_session.add(suggestion)
    db_session.commit()
    return suggestion


def test_apply_rule_suggestion_materializes_validated_rule(db_session, user, revision_with_cleaned_md):
    proposal = {
        "categoria": "massimali",
        "chiave": "contributo_massimo",
        "valore": {"tipo": "denaro", "importo": "50000.00", "valuta": "EUR"},
        "testo_originale": "Contributo massimo 50.000 euro.",
        "confidence": "0.9",
        "needs_careful_review": False,
    }
    suggestion = _make_suggestion(db_session, revision_with_cleaned_md, "regola", proposal)
    result = apply_suggestion(db_session, suggestion, user_id=user.id)
    assert result["applied"] and result["applied"][0].startswith("avviso_regola:")
    rule = db_session.query(models.AvvisoRegola).one()
    assert rule.stato == "validata"
    assert rule.validata_da_user_id == user.id
    assert rule.origin_suggestion_id == suggestion.id


def test_apply_deadline_suggestion_materializes_validated_deadline(db_session, user, revision_with_cleaned_md):
    proposal = {
        "tipo": "presentazione",
        "data": "2026-09-30T23:59:00+02:00",
        "descrizione": "Termine presentazione piani",
        "tassativa": True,
        "testo_originale": "entro il 30/09/2026",
        "confidence": "0.9",
        "needs_careful_review": False,
    }
    suggestion = _make_suggestion(db_session, revision_with_cleaned_md, "scadenza", proposal)
    result = apply_suggestion(db_session, suggestion, user_id=user.id)
    assert result["applied"] and result["applied"][0].startswith("avviso_scadenza:")
    deadline = db_session.query(models.AvvisoScadenza).one()
    assert deadline.stato == "validata"
    assert deadline.validata_da_user_id == user.id


def test_apply_avviso_suggestion_requires_human_reviewer(db_session, user, revision_with_cleaned_md):
    proposal = {
        "categoria": "massimali",
        "chiave": "contributo_massimo",
        "valore": {"tipo": "denaro", "importo": "50000.00", "valuta": "EUR"},
        "testo_originale": "Contributo massimo 50.000 euro.",
    }
    suggestion = _make_suggestion(db_session, revision_with_cleaned_md, "regola", proposal)
    with pytest.raises(ValueError, match="[Rr]evisore"):
        apply_suggestion(db_session, suggestion, user_id=None)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T backend python -m pytest tests/test_avvisi_v2_extractor.py -v`
Expected: i 3 nuovi test FAIL con `ValueError: Auto-fix senza payload strutturato applicabile`

- [ ] **Step 3: Write minimal implementation** (in `backend/services/suggestion_apply.py`)

Aggiungere costante e funzione:

```python
AVVISO_ESTRAZIONE_KIND = "avviso_estrazione"


def apply_avviso_extraction_suggestion(db, suggestion, *, user_id: Optional[int] = None) -> dict:
    if not user_id:
        raise ValueError("Revisore umano obbligatorio per materializzare dati avviso")
    import crud_avvisi
    import schemas_avvisi as avvisi_schemas

    payload = json.loads(suggestion.auto_fix_payload or "")
    target = payload.get("target")
    revision_id = payload.get("revision_id") or suggestion.entity_id
    proposal_data = dict(payload.get("proposal") or {})
    proposal_data["origin_suggestion_id"] = suggestion.id
    if target == "regola":
        proposal = avvisi_schemas.AvvisoRegolaProposal.model_validate(proposal_data)
        rule = crud_avvisi.create_rule_proposal(db, revision_id, proposal, commit=False)
        db.commit()
        crud_avvisi.review_rule(db, rule.id, action="approva", reviewer_user_id=user_id)
        return {"applied": [f"avviso_regola:{rule.id}"], "skipped": []}
    if target == "scadenza":
        proposal = avvisi_schemas.AvvisoScadenzaProposal.model_validate(proposal_data)
        deadline = crud_avvisi.create_deadline_proposal(db, revision_id, proposal)
        crud_avvisi.review_deadline(db, deadline.id, action="approva", reviewer_user_id=user_id)
        return {"applied": [f"avviso_scadenza:{deadline.id}"], "skipped": []}
    raise ValueError(f"Target estrazione avviso non supportato: {target}")
```

e in `apply_suggestion`, prima del ramo `PAYLOAD_KIND`:

```python
    if kind == AVVISO_ESTRAZIONE_KIND:
        return apply_avviso_extraction_suggestion(db, suggestion, user_id=user_id)
```

Nota: verificare la firma reale di `create_deadline_proposal` (`backend/crud_avvisi.py:216`) — se ha `commit` kwarg allinearsi al pattern della regola.

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec -T backend python -m pytest tests/test_avvisi_v2_extractor.py -v`
Expected: tutti PASS

- [ ] **Step 5: Regression sugli apply esistenti**

Run: `docker compose exec -T backend python -m pytest tests/test_agent_audit_fixes.py tests/test_agents_e2e.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/services/suggestion_apply.py backend/tests/test_avvisi_v2_extractor.py
git commit -m "feat(AVVISI-08): apply umano materializza regole e scadenze validate"
```

---

### Task 8: Endpoint ingest + lettura revisioni (AVVISI-09)

**Files:**
- Modify: `backend/routers/avvisi.py`
- Modify: `backend/schemas_avvisi.py`
- Test: `backend/tests/test_avvisi_v2_api.py`

**Interfaces:**
- Consumes: `save_ingest_markdown`, `crud_avvisi.create_next_revision`, `run_extraction_pipeline`, `prepare_revision_content`, `ai_agents.control.agent_enabled`, `file_upload.sanitize_filename`.
- Produces:
  - `POST /api/v1/avvisi/{avviso_id}/revisioni/ingest` (multipart): campi `file` (UploadFile .md), `titolo` (Form, obbligatorio), `etichetta_revisione` (Form, opzionale), `esegui_estrazione` (Form bool, default True). RBAC: admin/manager (403 altrimenti). 404 avviso inesistente; 409 se esiste già una revisione dello stesso avviso con lo stesso `source_sha256`; 422 file non valido. Risposta 201 `AvvisoRevisioneIngestResponse`.
  - `GET /api/v1/avvisi/{avviso_id}/revisioni` → `list[AvvisoRevisioneRead]` ordinate per `numero_revisione` desc.
  - Schema `AvvisoRevisioneIngestResponse(_Schema)`: `revisione: AvvisoRevisioneRead`, `estrazione: Optional[dict[str, Any]] = None` (`{"run_id", "status", "suggestions_count", "summary"}` o `{"skipped": "<motivo>"}`).

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_avvisi_v2_api.py
"""ONDATA ARCHIVIO AVVISI — V2: endpoint ingest revisione con app FastAPI minimale."""

from pathlib import Path
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

import models
from database import Base, get_db
from routers import avvisi as avvisi_router_module
from services import avviso_ingest
from ai_agents import avviso_extractor as extractor_module


@pytest.fixture
def client_factory(tmp_path, monkeypatch):
    monkeypatch.setattr(avviso_ingest, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(extractor_module, "UPLOAD_DIR", tmp_path)
    engine = create_engine(
        "sqlite:///{}".format(tmp_path / "api.db"), connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine, "connect")
    def _fk(dbapi_connection, _):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    session = factory()

    import auth as auth_module

    def make(role="admin"):
        user = session.query(models.User).filter(models.User.username == f"u_{role}").first()
        if user is None:
            user = models.User(
                username=f"u_{role}", email=f"{role}@example.com",
                hashed_password=auth_module.get_password_hash("Password1!"),
                role=role, is_active=True,
            )
            session.add(user)
            session.commit()
            session.refresh(user)
        app = FastAPI()
        # il router ha già prefix="/api/v1/avvisi" (backend/routers/avvisi.py:11)
        app.include_router(avvisi_router_module.router)
        app.dependency_overrides[get_db] = lambda: session
        app.dependency_overrides[avvisi_router_module.get_current_user] = lambda: user
        return TestClient(app), session, user
    yield make
    session.close()


def _crea_avviso(session):
    avviso = models.Avviso(
        codice="1/2026", ente_erogatore="fapi", fondo="fapi", numero="1", anno=2026,
        titolo="Avviso FAPI 1/2026", stato="bozza",
    )
    session.add(avviso)
    session.commit()
    return avviso


def test_ingest_creates_revision_without_extraction(client_factory, monkeypatch):
    client, session, _ = client_factory("admin")
    avviso = _crea_avviso(session)
    monkeypatch.setenv("AGENT_AVVISO_EXTRACTOR_ENABLED", "false")
    response = client.post(
        f"/api/v1/avvisi/{avviso.id}/revisioni/ingest",
        data={"titolo": "Avviso FAPI 1/2026", "esegui_estrazione": "true"},
        files={"file": ("avviso.md", b"# Art. 1\nTesto avviso.\n", "text/markdown")},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["revisione"]["numero_revisione"] == 1
    assert body["revisione"]["stato_estrazione"] == "segmentato"
    assert body["estrazione"]["skipped"]


def test_ingest_duplicate_sha_returns_409(client_factory, monkeypatch):
    client, session, _ = client_factory("admin")
    avviso = _crea_avviso(session)
    monkeypatch.setenv("AGENT_AVVISO_EXTRACTOR_ENABLED", "false")
    payload = {"titolo": "Avviso", "esegui_estrazione": "false"}
    files = {"file": ("avviso.md", b"# Art. 1\nTesto avviso.\n", "text/markdown")}
    assert client.post(f"/api/v1/avvisi/{avviso.id}/revisioni/ingest", data=payload, files=files).status_code == 201
    response = client.post(f"/api/v1/avvisi/{avviso.id}/revisioni/ingest", data=payload, files=files)
    assert response.status_code == 409


def test_ingest_rejects_non_admin_manager(client_factory):
    client, session, _ = client_factory("viewer")
    avviso = _crea_avviso(session)
    response = client.post(
        f"/api/v1/avvisi/{avviso.id}/revisioni/ingest",
        data={"titolo": "X"},
        files={"file": ("avviso.md", b"# A\ntesto\n", "text/markdown")},
    )
    assert response.status_code == 403


def test_ingest_invalid_file_returns_422(client_factory):
    client, session, _ = client_factory("admin")
    avviso = _crea_avviso(session)
    response = client.post(
        f"/api/v1/avvisi/{avviso.id}/revisioni/ingest",
        data={"titolo": "X"},
        files={"file": ("avviso.pdf", b"%PDF-", "application/pdf")},
    )
    assert response.status_code == 422


def test_list_revisioni_ordered_desc(client_factory, monkeypatch):
    client, session, _ = client_factory("admin")
    avviso = _crea_avviso(session)
    monkeypatch.setenv("AGENT_AVVISO_EXTRACTOR_ENABLED", "false")
    for i in (1, 2):
        client.post(
            f"/api/v1/avvisi/{avviso.id}/revisioni/ingest",
            data={"titolo": f"Rev {i}", "esegui_estrazione": "false"},
            files={"file": ("avviso.md", f"# Art. {i}\ntesto {i}\n".encode(), "text/markdown")},
        )
    response = client.get(f"/api/v1/avvisi/{avviso.id}/revisioni")
    assert response.status_code == 200
    numeri = [r["numero_revisione"] for r in response.json()]
    assert numeri == [2, 1]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T backend python -m pytest tests/test_avvisi_v2_api.py -v`
Expected: FAIL (endpoint inesistente → 404/AttributeError su `get_current_user`)

- [ ] **Step 3: Write implementation**

In `backend/schemas_avvisi.py` (in coda, dopo `AvvisoRevisioneRead`):

```python
class AvvisoRevisioneIngestResponse(_Schema):
    revisione: AvvisoRevisioneRead
    estrazione: Optional[dict[str, Any]] = None
```

(aggiungere `Any` all'import `typing` se manca.)

In `backend/routers/avvisi.py` — aggiungere import (allineati allo stile di `routers/agents.py` per `get_current_user`/`User`):

```python
import json

from fastapi import File, Form, UploadFile, status

import crud_avvisi
import schemas_avvisi as avvisi_schemas
from auth import get_current_user
from models import User
from ai_agents.control import agent_enabled, disabled_reason
from file_upload import sanitize_filename
from services.avviso_ingest import run_extraction_pipeline, prepare_revision_content, save_ingest_markdown
import models


def require_avvisi_write(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in {"admin", "manager"}:
        raise HTTPException(status_code=403, detail="Ruolo non autorizzato alla gestione avvisi")
    return current_user
```

endpoint:

```python
@router.get("/{avviso_id}/revisioni", response_model=list[avvisi_schemas.AvvisoRevisioneRead])
def list_revisioni(avviso_id: int, db: Session = Depends(get_db)):
    if not crud_avvisi.get_avviso(db, avviso_id):
        raise HTTPException(status_code=404, detail="Avviso non trovato")
    return (
        db.query(models.AvvisoRevisione)
        .filter(models.AvvisoRevisione.avviso_id == avviso_id)
        .order_by(models.AvvisoRevisione.numero_revisione.desc())
        .all()
    )


@router.post(
    "/{avviso_id}/revisioni/ingest",
    response_model=avvisi_schemas.AvvisoRevisioneIngestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_revisione(
    avviso_id: int,
    file: UploadFile = File(...),
    titolo: str = Form(..., min_length=1, max_length=300),
    etichetta_revisione: Optional[str] = Form(None, max_length=50),
    esegui_estrazione: bool = Form(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_avvisi_write),
):
    if not crud_avvisi.get_avviso(db, avviso_id):
        raise HTTPException(status_code=404, detail="Avviso non trovato")
    contents = await file.read()
    try:
        stored = save_ingest_markdown(avviso_id, file.filename or "", contents)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    duplicate = (
        db.query(models.AvvisoRevisione.id)
        .filter(
            models.AvvisoRevisione.avviso_id == avviso_id,
            models.AvvisoRevisione.source_sha256 == stored.sha256,
        )
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="Documento sorgente già ingerito per questo avviso")
    payload = avvisi_schemas.AvvisoRevisioneCreate(
        titolo=titolo,
        etichetta_revisione=etichetta_revisione,
        source_md_path=stored.storage_key,
        original_filename=sanitize_filename(file.filename or "avviso.md"),
        source_sha256=stored.sha256,
    )
    try:
        revision = crud_avvisi.create_next_revision(db, avviso_id, payload, created_by_user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    estrazione: Optional[dict] = None
    if esegui_estrazione and agent_enabled("avviso_extractor"):
        run = run_extraction_pipeline(db, revision.id, user_id=current_user.id)
        summary = json.loads(run.result_summary) if run.result_summary else {}
        estrazione = {
            "run_id": run.id,
            "status": run.status,
            "suggestions_count": run.suggestions_count,
            "summary": summary,
        }
    else:
        prepare_revision_content(db, revision.id)
        motivo = (
            disabled_reason("avviso_extractor")
            if esegui_estrazione
            else "Estrazione non richiesta"
        )
        estrazione = {"skipped": motivo}
    db.refresh(revision)
    return avvisi_schemas.AvvisoRevisioneIngestResponse(
        revisione=avvisi_schemas.AvvisoRevisioneRead.model_validate(revision),
        estrazione=estrazione,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec -T backend python -m pytest tests/test_avvisi_v2_api.py -v`
Expected: 5 PASS

- [ ] **Step 5: Regressione router avvisi esistente**

Run: `docker compose exec -T backend python -m pytest tests/test_avvisi_v1.py test_main.py -v -k "avvis or main" --tb=short`
Expected: PASS (nessuna rottura import router)

- [ ] **Step 6: Commit**

```bash
git add backend/routers/avvisi.py backend/schemas_avvisi.py backend/tests/test_avvisi_v2_api.py
git commit -m "feat(AVVISI-09): endpoint ingest revisione con RBAC, dedup sha e lista revisioni"
```

---

### Task 9: Directory ingest, gate finale e chiusura V2 (AVVISI-10)

**Files:**
- Create: `imports/avvisi/README.md`
- Modify: `REMEDIATION_LOG.md`, `STATUS.md` (append sezione chiusura V2)

**Interfaces:**
- Consumes: tutto quanto sopra.
- Produces: gate V2 dichiarato chiuso con suite completa verde.

- [ ] **Step 1: Create ingest directory README**

```markdown
# imports/avvisi — Avvisi sorgente per ingestione

Depositare qui i file markdown (.md, UTF-8) degli avvisi da ingerire nella
piattaforma (V5 dell'ondata ARCHIVIO AVVISI ingerirà i 4 avvisi reali).

Flusso: `POST /api/v1/avvisi/{avviso_id}/revisioni/ingest` (multipart, ruoli
admin/manager) → pulizia → segmentazione → estrazione LLM (agente
`avviso_extractor`, kill switch `AGENT_AVVISO_EXTRACTOR_ENABLED`) →
suggerimenti in revisione umana → apply che materializza regole/scadenze
validate sulla revisione.

I file qui presenti NON vengono ingeriti automaticamente.
```

- [ ] **Step 2: Full test suite (gate)**

Run: `docker compose exec -T backend python -m pytest test_main.py tests/ --tb=short -q`
Expected: **almeno 434 passed + i nuovi test V2, 1 skipped, 0 failed**. Se fallisce qualcosa: fermarsi e sistemare prima di procedere.

- [ ] **Step 3: Verifica import runtime backend**

Run: `docker compose exec -T backend python -c "import main; import ai_agents; print(sorted(d['name'] for d in ai_agents.list_agent_definitions()))"`
Expected: lista include `avviso_extractor`, nessun errore import.

- [ ] **Step 4: Aggiornare REMEDIATION_LOG.md e STATUS.md**

Append a `REMEDIATION_LOG.md` sezione `## 2026-07-17 | ONDATA ARCHIVIO AVVISI | V2 pipeline ingestione CHIUSA` con: task implementati (AVVISI-02..10), esito suite, nessuna migration necessaria, kill switch, mai push. Append a `STATUS.md` lo stato V2 chiusa e prossimo punto (GATE V3 full-text vs pgvector).

- [ ] **Step 5: Commit finale**

```bash
git add imports/avvisi/README.md REMEDIATION_LOG.md STATUS.md
git commit -m "docs(AVVISI-10): chiude gate V2 pipeline ingestione"
```

---

## Note di verifica finali (fuori task, gate umano)

- La revisione umana dei suggerimenti passa dalla UI esistente `/agents/review` (generica su `AgentSuggestion`): verificare a runtime che i nuovi `suggestion_type` compaiano; eventuali ritocchi UI sono fuori scope V2.
- V3 (ricerca full-text vs pgvector) richiede GATE architetturale esplicito con l'utente prima di qualsiasi implementazione.
- V4 (`avviso_advisor`, kill switch `AGENT_AVVISO_ADVISOR_ENABLED`) e V5 (ingestione 4 avvisi reali + `AVVISI_PLATFORM.md`) dopo V2/V3.
- Mai push.
