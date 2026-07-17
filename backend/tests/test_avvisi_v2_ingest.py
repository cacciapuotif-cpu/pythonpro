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
