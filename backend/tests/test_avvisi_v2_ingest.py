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
