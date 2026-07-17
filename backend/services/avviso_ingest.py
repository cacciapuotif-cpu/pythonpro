"""Pipeline di ingestione avvisi V2: pulizia, segmentazione, storage, orchestrazione.

Le funzioni di pulizia/segmentazione sono pure. Lo storage scrive sotto
UPLOAD_DIR con storage key relative compatibili con crud_avvisi._storage_key.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

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
