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
