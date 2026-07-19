"""Pipeline di ingestione avvisi V2: pulizia, segmentazione, storage, orchestrazione.

Le funzioni di pulizia/segmentazione sono pure. Lo storage scrive sotto
UPLOAD_DIR con storage key relative compatibili con crud_avvisi._storage_key.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import models
from agent_workflows import run_agent_workflow
from ai_agents.avviso_extractor import TUTTE_CATEGORIE
from ai_agents.prompts.avviso_extractor_v1 import GRUPPI_CATEGORIE
from file_upload import MAX_FILE_SIZE, UPLOAD_DIR

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


def _get_revision(db, revision_id: int) -> "models.AvvisoRevisione":
    revision = (
        db.query(models.AvvisoRevisione)
        .filter(models.AvvisoRevisione.id == revision_id)
        .first()
    )
    if revision is None:
        raise ValueError(f"Revisione avviso {revision_id} non trovata")
    return revision


def _set_stato(db, revision, stato: str, *, progress: Optional[dict] = None) -> None:
    revision.stato_estrazione = stato
    if progress is not None:
        revision.extraction_progress = progress
    db.commit()


def _build_extraction_progress(summary: dict, previous: Optional[dict] = None) -> tuple[str, dict]:
    """Unisce un tentativo al progresso precedente e calcola lo stato onesto."""
    previous = previous if isinstance(previous, dict) else {}
    section_status = dict(previous.get("sezioni_status") or {})
    discarded_by_section = dict(previous.get("elementi_scartati_per_sezione") or {})
    errors_by_section = dict(previous.get("errori_sezioni") or {})
    requested = summary.get("sezioni_richieste") or list(GRUPPI_CATEGORIE)
    attempt_status = summary.get("sezioni_status") or {}

    for section in requested:
        section_status[section] = attempt_status.get(section, "fallita")
        discarded_by_section[section] = int(
            (summary.get("elementi_scartati_per_sezione") or {}).get(section, 0) or 0
        )
        error = (summary.get("errori_sezioni") or {}).get(section)
        if error:
            errors_by_section[section] = error
        else:
            errors_by_section.pop(section, None)

    for section in GRUPPI_CATEGORIE:
        section_status.setdefault(section, "non_eseguita")

    processed_sections = [
        section
        for section in GRUPPI_CATEGORIE
        if section_status[section] in {"completa", "parziale"}
    ]
    completed_sections = [
        section for section in GRUPPI_CATEGORIE if section_status[section] == "completa"
    ]
    missing_sections = [
        section for section in GRUPPI_CATEGORIE if section_status[section] != "completa"
    ]
    covered_categories = [
        category
        for section in completed_sections
        for category in (GRUPPI_CATEGORIE[section] or ["scadenze"])
    ]

    if len(completed_sections) == len(GRUPPI_CATEGORIE):
        state = "completata"
    elif not processed_sections:
        state = "fallita"
    else:
        state = "parziale"

    progress = {
        "version": 1,
        "sezioni_totali": len(GRUPPI_CATEGORIE),
        "sezioni_status": section_status,
        "sezioni_processate": len(processed_sections),
        "sezioni_processate_nomi": processed_sections,
        "sezioni_complete": len(completed_sections),
        "sezioni_complete_nomi": completed_sections,
        "sezioni_mancanti": missing_sections,
        "categorie_totali": len(TUTTE_CATEGORIE),
        "categorie_coperte": covered_categories,
        "categorie_coperte_count": len(covered_categories),
        "categorie_mancanti": [
            category for category in TUTTE_CATEGORIE if category not in covered_categories
        ],
        "elementi_scartati_per_sezione": discarded_by_section,
        "elementi_scartati": sum(discarded_by_section.values()),
        "errori_sezioni": errors_by_section,
        "ultimo_run_id": summary.get("run_id"),
    }
    return state, progress


def _failed_extraction_progress(error: str) -> dict:
    return {
        "version": 1,
        "sezioni_totali": len(GRUPPI_CATEGORIE),
        "sezioni_status": {section: "fallita" for section in GRUPPI_CATEGORIE},
        "sezioni_processate": 0,
        "sezioni_processate_nomi": [],
        "sezioni_complete": 0,
        "sezioni_complete_nomi": [],
        "sezioni_mancanti": list(GRUPPI_CATEGORIE),
        "categorie_totali": len(TUTTE_CATEGORIE),
        "categorie_coperte": [],
        "categorie_coperte_count": 0,
        "categorie_mancanti": list(TUTTE_CATEGORIE),
        "elementi_scartati_per_sezione": {},
        "elementi_scartati": 0,
        "errori_sezioni": {"pipeline": error[:500]},
    }


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


def run_extraction_pipeline(
    db,
    revision_id: int,
    *,
    user_id: Optional[int] = None,
    sezioni: Optional[list[str]] = None,
):
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
            input_payload={"sezioni": sezioni} if sezioni else None,
        )
    except Exception as exc:
        _set_stato(
            db,
            revision,
            "fallita",
            progress=_failed_extraction_progress(str(exc) or exc.__class__.__name__),
        )
        raise
    revision.extraction_run_id = run.id
    summary = json.loads(run.result_summary) if run.result_summary else {}
    summary["run_id"] = run.id
    state, progress = _build_extraction_progress(summary, revision.extraction_progress)
    _set_stato(db, revision, state, progress=progress)
    return run
