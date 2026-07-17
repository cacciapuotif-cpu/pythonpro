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
