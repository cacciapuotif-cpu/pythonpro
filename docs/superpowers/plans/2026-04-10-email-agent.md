# Email Agent — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementare un agente che riceve email con allegati via Gmail IMAP, analizza i documenti con LLM e risponde automaticamente o notifica l'operatore.

**Architecture:** Loop di polling IMAP (ogni 5 min) avviato come thread di background dallo startup FastAPI. La pipeline per ogni email: `InboxRouter` → `AttachmentHandler` → `DocumentProcessor` → `InboxReplyComposer` (se doc non valido). Ogni email processata produce un record in `email_inbox_items` per audit trail e deduplication.

**Tech Stack:** Python stdlib `imaplib`/`email`, SQLAlchemy (legacy ORM), `pdfplumber` (estrazione testo PDF), `httpx` (chiamate LLM), Jinja2 (template email), pytest (TDD)

---

## File Structure

### Nuovi file
- `backend/alembic/versions/030_add_email_inbox_items.py` — migration tabella audit trail
- `backend/services/attachment_handler.py` — download + persist allegati (whitelist tipi, limit dimensione)
- `backend/services/inbox_router.py` — match sender_email → collaborator/allievo
- `backend/ai_agents/document_processor.py` — analisi documento con LLM, output JSON strutturato
- `backend/services/inbox_reply_composer.py` — genera testo risposta automatica per doc non valido
- `backend/services/email_inbox_worker.py` — loop IMAP polling, orchestrazione pipeline
- `backend/routers/email_inbox.py` — API endpoints audit trail + trigger manuale + status worker
- `backend/templates/email/richiesta_integrazioni.html` — template Jinja2 risposta non valido
- `backend/templates/email/richiesta_integrazioni.txt` — versione plain text
- `backend/tests/test_email_agent.py` — tutti i test unit + integration

### File da modificare
- `backend/models.py` — aggiunge classe `EmailInboxItem`
- `backend/schemas.py` — aggiunge schema `EmailInboxItemOut`, `EmailInboxListResponse`
- `backend/main.py` — import + `include_router(email_inbox.router)` + avvio thread worker in `startup_event`
- `backend/requirements.txt` — aggiunge `pdfplumber>=0.10`

---

## Task 1: Dipendenze + Migration DB

**Files:**
- Create: `backend/alembic/versions/030_add_email_inbox_items.py`
- Modify: `backend/requirements.txt`
- Modify: `backend/models.py`

- [ ] **Step 1: Aggiungi `pdfplumber` a requirements.txt**

In `backend/requirements.txt`, dopo la riga `httpx>=0.27.0`:
```
pdfplumber>=0.10
```

- [ ] **Step 2: Crea la migration 030**

Crea `backend/alembic/versions/030_add_email_inbox_items.py`:
```python
"""Add email_inbox_items table.

Revision ID: 030
Revises: 029
Create Date: 2026-04-10
"""

from alembic import op
import sqlalchemy as sa


revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None


def _has_table(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _create_index_if_missing(table_name: str, index_name: str, columns: list) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {index["name"] for index in inspector.get_indexes(table_name)}
    if index_name not in existing:
        op.create_index(index_name, table_name, columns, unique=False)


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, "email_inbox_items"):
        op.create_table(
            "email_inbox_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("message_id", sa.String(length=500), nullable=False, unique=True),
            sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("sender_email", sa.String(length=255), nullable=False),
            sa.Column("subject", sa.String(length=500), nullable=True),
            sa.Column("entity_type", sa.String(length=50), nullable=True),
            sa.Column("entity_id", sa.Integer(), nullable=True),
            sa.Column("attachment_path", sa.String(length=1000), nullable=True),
            sa.Column("attachment_name", sa.String(length=255), nullable=True),
            sa.Column("processing_status", sa.String(length=50), nullable=False),
            sa.Column("llm_result", sa.Text(), nullable=True),
            sa.Column("reply_sent", sa.Boolean(), server_default="false", nullable=False),
            sa.Column("reply_sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    for table_name, index_name, columns in [
        ("email_inbox_items", "ix_email_inbox_items_message_id", ["message_id"]),
        ("email_inbox_items", "ix_email_inbox_items_entity", ["entity_type", "entity_id"]),
        ("email_inbox_items", "ix_email_inbox_items_status", ["processing_status"]),
        ("email_inbox_items", "ix_email_inbox_items_sender", ["sender_email"]),
    ]:
        _create_index_if_missing(table_name, index_name, columns)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _has_table(inspector, "email_inbox_items"):
        for index_name in [
            "ix_email_inbox_items_sender",
            "ix_email_inbox_items_status",
            "ix_email_inbox_items_entity",
            "ix_email_inbox_items_message_id",
        ]:
            try:
                op.drop_index(index_name, table_name="email_inbox_items")
            except Exception:
                pass
        op.drop_table("email_inbox_items")
```

- [ ] **Step 3: Aggiungi il modello SQLAlchemy in `backend/models.py`**

Alla fine del file, prima dell'eventuale `__all__` o come ultima classe:
```python
class EmailInboxItem(Base):
    __tablename__ = "email_inbox_items"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(String(500), unique=True, nullable=False, index=True)
    received_at = Column(DateTime(timezone=True), nullable=False)
    sender_email = Column(String(255), nullable=False, index=True)
    subject = Column(String(500), nullable=True)
    entity_type = Column(String(50), nullable=True)   # 'collaborator' | 'allievo' | None
    entity_id = Column(Integer, nullable=True)
    attachment_path = Column(String(1000), nullable=True)
    attachment_name = Column(String(255), nullable=True)
    processing_status = Column(String(50), nullable=False)  # pending|valid|invalid|manual_review|skipped|error
    llm_result = Column(Text, nullable=True)          # raw JSON da LLM
    reply_sent = Column(Boolean, default=False, nullable=False)
    reply_sent_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
```

- [ ] **Step 4: Verifica sintassi**

```bash
docker compose exec backend python -m py_compile \
    alembic/versions/030_add_email_inbox_items.py \
    models.py
```

Atteso: nessun output (successo).

- [ ] **Step 5: Applica la migration**

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend alembic current
```

Atteso: `030 (head)`

- [ ] **Step 6: Commit**

```bash
git add backend/requirements.txt \
    backend/alembic/versions/030_add_email_inbox_items.py \
    backend/models.py
git commit -m "feat: add email_inbox_items table and EmailInboxItem model"
```

---

## Task 2: `AttachmentHandler`

**Files:**
- Create: `backend/services/attachment_handler.py`
- Modify: `backend/tests/test_email_agent.py` (creato qui, esteso nei task seguenti)

**Responsabilità:** riceve un oggetto `email.message.Message` Python, estrae allegati validi (whitelist tipi, limite dimensione), li salva in `uploads/email_inbox/<entity_type>/<entity_id>/<timestamp>_<filename>` e restituisce il path salvato.

- [ ] **Step 1: Scrivi il test (crea il file)**

Crea `backend/tests/test_email_agent.py`:
```python
"""Test suite per Email Agent (AttachmentHandler, InboxRouter, DocumentProcessor, InboxReplyComposer, EmailInboxWorker)."""
from __future__ import annotations

import email
import io
import json
import os
import sys
import tempfile
from email.message import EmailMessage
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Permette import dei moduli backend dallo stile legacy (working dir = /app nel container)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ===========================================================
# AttachmentHandler
# ===========================================================

class TestAttachmentHandler:

    def _make_email_with_attachment(self, filename: str, content: bytes, mime_type: str = "application/pdf") -> EmailMessage:
        msg = EmailMessage()
        msg["From"] = "test@example.com"
        msg["To"] = "inbox@company.com"
        msg["Subject"] = "Test doc"
        msg.set_content("See attachment")
        maintype, subtype = mime_type.split("/")
        msg.add_attachment(content, maintype=maintype, subtype=subtype, filename=filename)
        return msg

    def test_saves_pdf_attachment(self, tmp_path):
        from services.attachment_handler import AttachmentHandler
        handler = AttachmentHandler(upload_base_dir=tmp_path)
        msg = self._make_email_with_attachment("cv.pdf", b"%PDF-1.4 fake content")

        result = handler.extract_and_save(msg, entity_type="collaborator", entity_id=42)

        assert result is not None
        saved_path, saved_name = result
        assert saved_name == "cv.pdf"
        assert Path(saved_path).exists()
        assert "collaborator" in saved_path
        assert "42" in saved_path

    def test_rejects_unknown_mime_type(self, tmp_path):
        from services.attachment_handler import AttachmentHandler
        handler = AttachmentHandler(upload_base_dir=tmp_path)
        msg = self._make_email_with_attachment("script.exe", b"MZ", mime_type="application/octet-stream")

        result = handler.extract_and_save(msg, entity_type="collaborator", entity_id=1)

        assert result is None

    def test_rejects_oversized_attachment(self, tmp_path):
        from services.attachment_handler import AttachmentHandler
        handler = AttachmentHandler(upload_base_dir=tmp_path, max_bytes=100)
        msg = self._make_email_with_attachment("big.pdf", b"X" * 200)

        result = handler.extract_and_save(msg, entity_type="collaborator", entity_id=1)

        assert result is None

    def test_returns_none_when_no_attachment(self, tmp_path):
        from services.attachment_handler import AttachmentHandler
        handler = AttachmentHandler(upload_base_dir=tmp_path)
        msg = EmailMessage()
        msg["From"] = "test@example.com"
        msg.set_content("No attachment here")

        result = handler.extract_and_save(msg, entity_type="collaborator", entity_id=1)

        assert result is None
```

- [ ] **Step 2: Esegui il test per verificare che fallisca**

```bash
docker compose exec backend python -m pytest tests/test_email_agent.py::TestAttachmentHandler -v
```

Atteso: `ModuleNotFoundError: No module named 'services.attachment_handler'`

- [ ] **Step 3: Implementa `AttachmentHandler`**

Crea `backend/services/attachment_handler.py`:
```python
"""Estrae e salva allegati da email in arrivo."""
from __future__ import annotations

import logging
import os
from datetime import datetime
from email.message import Message
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
}

DEFAULT_MAX_BYTES = int(os.getenv("MAX_ATTACHMENT_MB", "10")) * 1024 * 1024
_DEFAULT_UPLOAD_BASE = Path(os.getenv("UPLOAD_BASE_DIR", "uploads")) / "email_inbox"


class AttachmentHandler:
    def __init__(
        self,
        upload_base_dir: Optional[Path] = None,
        max_bytes: int = DEFAULT_MAX_BYTES,
    ) -> None:
        self.upload_base_dir = Path(upload_base_dir) if upload_base_dir else _DEFAULT_UPLOAD_BASE
        self.max_bytes = max_bytes

    def extract_and_save(
        self,
        msg: Message,
        entity_type: Optional[str],
        entity_id: Optional[int],
    ) -> Optional[Tuple[str, str]]:
        """
        Scansiona msg alla ricerca del primo allegato valido.
        Restituisce (path_assoluto, nome_file_originale) o None.
        """
        for part in msg.walk():
            if part.get_content_disposition() != "attachment":
                continue

            filename = part.get_filename()
            if not filename:
                continue

            content_type = (part.get_content_type() or "").lower()
            if content_type not in ALLOWED_CONTENT_TYPES:
                logger.info("AttachmentHandler: tipo %s non supportato, skip", content_type)
                continue

            payload = part.get_payload(decode=True)
            if payload is None:
                continue

            if len(payload) > self.max_bytes:
                logger.warning(
                    "AttachmentHandler: allegato '%s' supera %d bytes, skip",
                    filename, self.max_bytes,
                )
                return None

            dest_dir = self.upload_base_dir
            if entity_type:
                dest_dir = dest_dir / entity_type
            if entity_id is not None:
                dest_dir = dest_dir / str(entity_id)
            dest_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            safe_name = _sanitize_filename(filename)
            dest_path = dest_dir / f"{timestamp}_{safe_name}"

            dest_path.write_bytes(payload)
            logger.info("AttachmentHandler: salvato '%s' → %s", filename, dest_path)
            return str(dest_path), filename

        return None


def _sanitize_filename(name: str) -> str:
    """Rimuove caratteri non sicuri dal nome file."""
    import re
    name = Path(name).name  # no directory traversal
    name = re.sub(r"[^\w.\-]", "_", name)
    return name[:200] or "attachment"
```

- [ ] **Step 4: Esegui i test e verifica che passino**

```bash
docker compose exec backend python -m pytest tests/test_email_agent.py::TestAttachmentHandler -v
```

Atteso: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/services/attachment_handler.py backend/tests/test_email_agent.py
git commit -m "feat: add AttachmentHandler with type whitelist and size limit"
```

---

## Task 3: `InboxRouter`

**Files:**
- Create: `backend/services/inbox_router.py`
- Modify: `backend/tests/test_email_agent.py`

**Responsabilità:** dato `sender_email`, cerca prima in `collaborators.email` poi in `allievi.email`. Ritorna `(entity_type, entity_id)` o `(None, None)`.

- [ ] **Step 1: Aggiungi i test a `test_email_agent.py`**

Appendi alla fine di `backend/tests/test_email_agent.py`:
```python
# ===========================================================
# InboxRouter
# ===========================================================

class TestInboxRouter:

    def _make_db(self):
        """DB SQLite in-memory con le sole tabelle necessarie."""
        from sqlalchemy import create_engine, Column, Integer, String, Boolean
        from sqlalchemy.orm import declarative_base, Session

        Base = declarative_base()

        class FakeCollaborator(Base):
            __tablename__ = "collaborators"
            id = Column(Integer, primary_key=True)
            email = Column(String(100), unique=True)
            is_active = Column(Boolean, default=True)

        class FakeAllievo(Base):
            __tablename__ = "allievi"
            id = Column(Integer, primary_key=True)
            email = Column(String(100), unique=True)
            is_active = Column(Boolean, default=True)

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        db = Session(engine)
        db.add(FakeCollaborator(id=10, email="mario@example.com", is_active=True))
        db.add(FakeAllievo(id=20, email="luigi@example.com", is_active=True))
        db.commit()
        return db

    def test_finds_collaborator(self):
        from services.inbox_router import InboxRouter
        db = self._make_db()
        router = InboxRouter(db)
        entity_type, entity_id = router.route("mario@example.com")
        assert entity_type == "collaborator"
        assert entity_id == 10

    def test_finds_allievo(self):
        from services.inbox_router import InboxRouter
        db = self._make_db()
        router = InboxRouter(db)
        entity_type, entity_id = router.route("luigi@example.com")
        assert entity_type == "allievo"
        assert entity_id == 20

    def test_returns_none_for_unknown(self):
        from services.inbox_router import InboxRouter
        db = self._make_db()
        router = InboxRouter(db)
        entity_type, entity_id = router.route("stranger@example.com")
        assert entity_type is None
        assert entity_id is None

    def test_case_insensitive_match(self):
        from services.inbox_router import InboxRouter
        db = self._make_db()
        router = InboxRouter(db)
        entity_type, entity_id = router.route("MARIO@EXAMPLE.COM")
        assert entity_type == "collaborator"
        assert entity_id == 10
```

- [ ] **Step 2: Esegui per verificare che fallisca**

```bash
docker compose exec backend python -m pytest tests/test_email_agent.py::TestInboxRouter -v
```

Atteso: `ModuleNotFoundError: No module named 'services.inbox_router'`

- [ ] **Step 3: Implementa `InboxRouter`**

Crea `backend/services/inbox_router.py`:
```python
"""Abbina il mittente email a un'entità nel DB (collaborator o allievo)."""
from __future__ import annotations

import logging
from typing import Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import func

logger = logging.getLogger(__name__)


class InboxRouter:
    def __init__(self, db: Session) -> None:
        self.db = db

    def route(self, sender_email: str) -> Tuple[Optional[str], Optional[int]]:
        """
        Cerca sender_email (case-insensitive) in collaborators e allievi.
        Ritorna ('collaborator', id), ('allievo', id) o (None, None).
        """
        normalized = sender_email.strip().lower()

        # Importa modelli a runtime per compatibilità con stile legacy
        try:
            import models
        except ImportError:
            from backend import models  # type: ignore

        collab = (
            self.db.query(models.Collaborator)
            .filter(func.lower(models.Collaborator.email) == normalized)
            .filter(models.Collaborator.is_active.is_(True))
            .first()
        )
        if collab:
            logger.debug("InboxRouter: %s → collaborator %s", sender_email, collab.id)
            return "collaborator", collab.id

        try:
            allievo = (
                self.db.query(models.Allievo)
                .filter(func.lower(models.Allievo.email) == normalized)
                .filter(models.Allievo.is_active.is_(True))
                .first()
            )
            if allievo:
                logger.debug("InboxRouter: %s → allievo %s", sender_email, allievo.id)
                return "allievo", allievo.id
        except Exception as exc:
            logger.warning("InboxRouter: query allievi fallita: %s", exc)

        logger.info("InboxRouter: mittente sconosciuto %s, ignorato", sender_email)
        return None, None
```

- [ ] **Step 4: Esegui i test e verifica che passino**

```bash
docker compose exec backend python -m pytest tests/test_email_agent.py::TestInboxRouter -v
```

Atteso: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/services/inbox_router.py backend/tests/test_email_agent.py
git commit -m "feat: add InboxRouter with case-insensitive entity lookup"
```

---

## Task 4: `DocumentProcessor`

**Files:**
- Create: `backend/ai_agents/document_processor.py`
- Modify: `backend/tests/test_email_agent.py`

**Responsabilità:** dato un path file, estrae testo (pdfplumber per PDF, fallback su nome file) e chiama LLM. Ritorna un `DocumentResult` dataclass con `valid`, `doc_type`, `issues`, `extracted_data`, `raw_llm_output`.

- [ ] **Step 1: Aggiungi i test**

Appendi a `backend/tests/test_email_agent.py`:
```python
# ===========================================================
# DocumentProcessor
# ===========================================================

class TestDocumentProcessor:

    def _mock_llm_response(self, valid: bool, doc_type: str = "cv", issues=None):
        """Genera la risposta mock che il LLM restituirebbe."""
        return json.dumps({
            "valid": valid,
            "doc_type": doc_type,
            "issues": issues or [],
            "extracted_data": {"nome": "Mario Rossi"},
        })

    def test_valid_document_parsed(self, tmp_path):
        from ai_agents.document_processor import DocumentProcessor, DocumentResult
        pdf_path = tmp_path / "cv.pdf"
        pdf_path.write_bytes(b"fake pdf content")

        llm_json = self._mock_llm_response(valid=True, doc_type="cv")
        with patch("ai_agents.document_processor.call_llm_for_document", return_value=llm_json):
            processor = DocumentProcessor()
            result = processor.process(str(pdf_path), entity_name="Mario Rossi", expected_doc_type="cv")

        assert isinstance(result, DocumentResult)
        assert result.valid is True
        assert result.doc_type == "cv"
        assert result.issues == []
        assert result.raw_llm_output == llm_json

    def test_invalid_document_returns_issues(self, tmp_path):
        from ai_agents.document_processor import DocumentProcessor, DocumentResult
        pdf_path = tmp_path / "doc.pdf"
        pdf_path.write_bytes(b"fake pdf content")

        llm_json = self._mock_llm_response(valid=False, issues=["firma mancante", "data scaduta"])
        with patch("ai_agents.document_processor.call_llm_for_document", return_value=llm_json):
            processor = DocumentProcessor()
            result = processor.process(str(pdf_path), entity_name="Luigi", expected_doc_type="documento_identita")

        assert result.valid is False
        assert len(result.issues) == 2

    def test_llm_timeout_returns_manual_review(self, tmp_path):
        from ai_agents.document_processor import DocumentProcessor, DocumentResult
        pdf_path = tmp_path / "doc.pdf"
        pdf_path.write_bytes(b"content")

        with patch("ai_agents.document_processor.call_llm_for_document", side_effect=TimeoutError("timeout")):
            processor = DocumentProcessor()
            result = processor.process(str(pdf_path), entity_name="Test", expected_doc_type="cv")

        assert result.valid is None
        assert result.raw_llm_output is None

    def test_malformed_llm_json_returns_manual_review(self, tmp_path):
        from ai_agents.document_processor import DocumentProcessor
        pdf_path = tmp_path / "doc.pdf"
        pdf_path.write_bytes(b"content")

        with patch("ai_agents.document_processor.call_llm_for_document", return_value="not json at all"):
            processor = DocumentProcessor()
            result = processor.process(str(pdf_path), entity_name="Test", expected_doc_type="cv")

        assert result.valid is None

    def test_no_attachment_returns_skipped(self):
        from ai_agents.document_processor import DocumentProcessor, DocumentResult
        processor = DocumentProcessor()
        result = processor.process(None, entity_name="Test", expected_doc_type="cv")
        assert result.valid is None
        assert result.doc_type == "none"
```

- [ ] **Step 2: Esegui per verificare che fallisca**

```bash
docker compose exec backend python -m pytest tests/test_email_agent.py::TestDocumentProcessor -v
```

Atteso: `ModuleNotFoundError: No module named 'ai_agents.document_processor'`

- [ ] **Step 3: Implementa `DocumentProcessor`**

Crea `backend/ai_agents/document_processor.py`:
```python
"""Analizza un documento allegato tramite LLM e restituisce un risultato strutturato."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DocumentResult:
    valid: Optional[bool]          # True=valido, False=non valido, None=indeterminato (manual review / no attachment)
    doc_type: str                  # tipo documento rilevato, es. 'cv', 'documento_identita', 'none'
    issues: List[str] = field(default_factory=list)
    extracted_data: Dict[str, Any] = field(default_factory=dict)
    raw_llm_output: Optional[str] = None


class DocumentProcessor:
    def process(
        self,
        file_path: Optional[str],
        entity_name: str,
        expected_doc_type: str,
    ) -> DocumentResult:
        """
        Analizza il documento a file_path con LLM.
        Se file_path è None, restituisce valid=None, doc_type='none'.
        Se LLM non disponibile o timeout: valid=None (manual review).
        """
        if not file_path:
            return DocumentResult(valid=None, doc_type="none")

        text_content = _extract_text(file_path)

        try:
            raw = call_llm_for_document(
                file_path=file_path,
                text_content=text_content,
                entity_name=entity_name,
                expected_doc_type=expected_doc_type,
            )
        except Exception as exc:
            logger.warning("DocumentProcessor: LLM non disponibile (%s), manual review", exc)
            return DocumentResult(valid=None, doc_type=expected_doc_type, raw_llm_output=None)

        return _parse_llm_result(raw, expected_doc_type)


def call_llm_for_document(
    *,
    file_path: str,
    text_content: str,
    entity_name: str,
    expected_doc_type: str,
) -> str:
    """
    Chiama il provider LLM configurato e ritorna la risposta raw (stringa JSON).
    Lancia eccezione se LLM non disponibile o timeout.
    """
    from .llm import get_agent_llm_config, _call_ollama, _call_openclaw  # noqa: PLC0415

    config = get_agent_llm_config()
    if not config.enabled:
        raise RuntimeError("Provider LLM non abilitato")

    filename = Path(file_path).name
    system_prompt = (
        "Sei un assistente per la verifica di documenti amministrativi. "
        "Analizza il documento fornito e rispondi SOLO con JSON valido. "
        "Non aggiungere testo fuori dal JSON."
    )
    user_prompt = (
        f"Documento allegato: '{filename}'\n"
        f"Mittente: {entity_name}\n"
        f"Tipo documento atteso: {expected_doc_type}\n"
        f"Contenuto estratto (parziale):\n{text_content[:2000]}\n\n"
        "Rispondi con JSON:\n"
        '{"valid": true/false, "doc_type": "tipo_rilevato", "issues": ["problema1"], "extracted_data": {}}'
    )

    if config.provider == "ollama":
        result = _call_ollama(config, system_prompt=system_prompt, user_prompt=user_prompt)
    else:
        result = _call_openclaw(config, system_prompt=system_prompt, user_prompt=user_prompt)

    # _call_ollama/_call_openclaw restituiscono AgentLlmResult con subject/body.
    # Per document_processor ci serve la risposta raw JSON — la ricostruiamo dal body.
    return result.raw_text or result.body


def _extract_text(file_path: str) -> str:
    """Estrae testo dal file. Fallback su nome file se pdfplumber non disponibile."""
    path = Path(file_path)
    if path.suffix.lower() == ".pdf":
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                pages_text = []
                for page in pdf.pages[:5]:  # max 5 pagine
                    t = page.extract_text()
                    if t:
                        pages_text.append(t)
            return "\n".join(pages_text)[:4000]
        except Exception as exc:
            logger.debug("pdfplumber non disponibile o errore (%s), fallback su nome file", exc)
    return f"[File: {path.name}]"


def _parse_llm_result(raw: str, expected_doc_type: str) -> DocumentResult:
    """Parsa la stringa raw JSON dal LLM. In caso di errore: valid=None."""
    if not raw:
        return DocumentResult(valid=None, doc_type=expected_doc_type, raw_llm_output=raw)

    try:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("nessun oggetto JSON trovato")
        data = json.loads(raw[start:end + 1])
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("DocumentProcessor: JSON malformato (%s), manual review", exc)
        return DocumentResult(valid=None, doc_type=expected_doc_type, raw_llm_output=raw)

    return DocumentResult(
        valid=bool(data.get("valid")) if data.get("valid") is not None else None,
        doc_type=str(data.get("doc_type") or expected_doc_type),
        issues=list(data.get("issues") or []),
        extracted_data=dict(data.get("extracted_data") or {}),
        raw_llm_output=raw,
    )
```

- [ ] **Step 4: Esegui i test e verifica che passino**

```bash
docker compose exec backend python -m pytest tests/test_email_agent.py::TestDocumentProcessor -v
```

Atteso: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/ai_agents/document_processor.py backend/tests/test_email_agent.py
git commit -m "feat: add DocumentProcessor with LLM analysis and fallback to manual_review"
```

---

## Task 5: `InboxReplyComposer` + template Jinja2

**Files:**
- Create: `backend/services/inbox_reply_composer.py`
- Create: `backend/templates/email/richiesta_integrazioni.html`
- Create: `backend/templates/email/richiesta_integrazioni.txt`
- Modify: `backend/tests/test_email_agent.py`

**Responsabilità:** dato `issues` list e nome destinatario, genera subject + body HTML/text. Usa LLM se disponibile, fallback deterministico se LLM down. Chiama `EmailSender.send_template_email()`.

- [ ] **Step 1: Crea i template Jinja2**

Crea `backend/templates/email/richiesta_integrazioni.html`:
```html
<!DOCTYPE html>
<html lang="it">
<head><meta charset="UTF-8"></head>
<body style="font-family: Arial, sans-serif; font-size: 14px; color: #333;">
  <p>Ciao {{ recipient_name }},</p>
  <p>abbiamo ricevuto il documento che hai inviato, ma purtroppo non è possibile elaborarlo per i seguenti motivi:</p>
  <ul>
    {% for issue in issues %}
    <li>{{ issue }}</li>
    {% endfor %}
  </ul>
  <p>Ti chiediamo di inviarci nuovamente il documento corretto rispondendo a questa email.</p>
  <p>Grazie per la collaborazione.</p>
</body>
</html>
```

Crea `backend/templates/email/richiesta_integrazioni.txt`:
```
Ciao {{ recipient_name }},

abbiamo ricevuto il documento che hai inviato, ma purtroppo non è possibile elaborarlo per i seguenti motivi:

{% for issue in issues %}- {{ issue }}
{% endfor %}
Ti chiediamo di inviarci nuovamente il documento corretto rispondendo a questa email.

Grazie per la collaborazione.
```

- [ ] **Step 2: Aggiungi i test**

Appendi a `backend/tests/test_email_agent.py`:
```python
# ===========================================================
# InboxReplyComposer
# ===========================================================

class TestInboxReplyComposer:

    def test_send_called_with_issues(self):
        from services.inbox_reply_composer import InboxReplyComposer
        mock_sender = MagicMock()
        mock_sender.send_template_email.return_value = True

        composer = InboxReplyComposer(email_sender=mock_sender)
        sent = composer.send_reply(
            to="mario@example.com",
            recipient_name="Mario Rossi",
            issues=["firma mancante", "data illeggibile"],
            original_subject="CV Allegato",
        )

        assert sent is True
        mock_sender.send_template_email.assert_called_once()
        call_kwargs = mock_sender.send_template_email.call_args
        assert call_kwargs[1]["to"] == "mario@example.com"
        context = call_kwargs[1]["context"]
        assert context["recipient_name"] == "Mario Rossi"
        assert "firma mancante" in context["issues"]

    def test_send_returns_false_on_sender_failure(self):
        from services.inbox_reply_composer import InboxReplyComposer
        mock_sender = MagicMock()
        mock_sender.send_template_email.return_value = False

        composer = InboxReplyComposer(email_sender=mock_sender)
        sent = composer.send_reply(
            to="luigi@example.com",
            recipient_name="Luigi",
            issues=["documento scaduto"],
            original_subject="Documento",
        )

        assert sent is False
```

- [ ] **Step 3: Esegui per verificare che fallisca**

```bash
docker compose exec backend python -m pytest tests/test_email_agent.py::TestInboxReplyComposer -v
```

Atteso: `ModuleNotFoundError: No module named 'services.inbox_reply_composer'`

- [ ] **Step 4: Implementa `InboxReplyComposer`**

Crea `backend/services/inbox_reply_composer.py`:
```python
"""Genera e invia la risposta automatica per documenti non validi."""
from __future__ import annotations

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class InboxReplyComposer:
    def __init__(self, email_sender=None) -> None:
        if email_sender is None:
            from services.email_sender import EmailSender
            email_sender = EmailSender()
        self._sender = email_sender

    def send_reply(
        self,
        to: str,
        recipient_name: str,
        issues: List[str],
        original_subject: str,
    ) -> bool:
        """
        Invia email di risposta chiedendo le integrazioni mancanti.
        Ritorna True se email inviata con successo, False altrimenti.
        """
        subject = f"Re: {original_subject} — integrazioni richieste"
        context = {
            "subject": subject,
            "recipient_name": recipient_name or to,
            "issues": issues,
        }
        try:
            result = self._sender.send_template_email(
                to=to,
                template_name="richiesta_integrazioni",
                context=context,
            )
            if result:
                logger.info("InboxReplyComposer: risposta inviata a %s", to)
            else:
                logger.warning("InboxReplyComposer: invio fallito verso %s", to)
            return result
        except Exception as exc:
            logger.exception("InboxReplyComposer: errore invio risposta a %s: %s", to, exc)
            return False
```

- [ ] **Step 5: Esegui i test e verifica che passino**

```bash
docker compose exec backend python -m pytest tests/test_email_agent.py::TestInboxReplyComposer -v
```

Atteso: `2 passed`

- [ ] **Step 6: Commit**

```bash
git add backend/services/inbox_reply_composer.py \
    backend/templates/email/richiesta_integrazioni.html \
    backend/templates/email/richiesta_integrazioni.txt \
    backend/tests/test_email_agent.py
git commit -m "feat: add InboxReplyComposer and Jinja2 templates for invalid document reply"
```

---

## Task 6: `EmailInboxWorker`

**Files:**
- Create: `backend/services/email_inbox_worker.py`
- Modify: `backend/tests/test_email_agent.py`

**Responsabilità:** loop IMAP polling, orchestra pipeline per ogni email UNSEEN, scrive record in `email_inbox_items`, marca email come letta solo a pipeline completata con successo.

- [ ] **Step 1: Aggiungi i test di integrazione**

Appendi a `backend/tests/test_email_agent.py`:
```python
# ===========================================================
# EmailInboxWorker — integration tests con IMAP mock
# ===========================================================

class TestEmailInboxWorker:

    def _make_fake_email_bytes(self, from_addr: str, subject: str, pdf_content: bytes = b"%PDF fake") -> bytes:
        """Costruisce una email RFC 2822 con allegato PDF."""
        from email.mime.multipart import MIMEMultipart
        from email.mime.base import MIMEBase
        from email.mime.text import MIMEText
        from email import encoders
        msg = MIMEMultipart()
        msg["From"] = from_addr
        msg["To"] = "inbox@company.com"
        msg["Subject"] = subject
        msg["Message-ID"] = f"<test-{from_addr}-{subject}@test>"
        msg["Date"] = "Thu, 10 Apr 2026 10:00:00 +0000"
        msg.attach(MIMEText("See attachment", "plain"))
        part = MIMEBase("application", "pdf")
        part.set_payload(pdf_content)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename="test_doc.pdf")
        msg.attach(part)
        return msg.as_bytes()

    def test_known_sender_creates_db_record(self, tmp_path):
        """Pipeline completa con mittente noto → record in DB con status corretto."""
        from sqlalchemy import create_engine, Column, Integer, String, Boolean, Text, DateTime
        from sqlalchemy.orm import declarative_base, Session

        Base = declarative_base()

        class FakeCollaborator(Base):
            __tablename__ = "collaborators"
            id = Column(Integer, primary_key=True)
            email = Column(String(100), unique=True)
            is_active = Column(Boolean, default=True)
            first_name = Column(String(50), default="Mario")
            last_name = Column(String(50), default="Rossi")

        class FakeAllievo(Base):
            __tablename__ = "allievi"
            id = Column(Integer, primary_key=True)
            email = Column(String(100), unique=True)
            is_active = Column(Boolean, default=True)

        class FakeEmailInboxItem(Base):
            __tablename__ = "email_inbox_items"
            id = Column(Integer, primary_key=True)
            message_id = Column(String(500), unique=True, nullable=False)
            received_at = Column(DateTime)
            sender_email = Column(String(255))
            subject = Column(String(500))
            entity_type = Column(String(50))
            entity_id = Column(Integer)
            attachment_path = Column(String(1000))
            attachment_name = Column(String(255))
            processing_status = Column(String(50))
            llm_result = Column(Text)
            reply_sent = Column(Boolean, default=False)
            reply_sent_at = Column(DateTime)
            error_message = Column(Text)

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        db = Session(engine)
        db.add(FakeCollaborator(id=1, email="mario@example.com"))
        db.commit()

        email_bytes = self._make_fake_email_bytes("mario@example.com", "Invio documento")

        mock_imap = MagicMock()
        mock_imap.select.return_value = ("OK", [b"1"])
        mock_imap.search.return_value = ("OK", [b"1"])
        mock_imap.fetch.return_value = ("OK", [(b"1 (RFC822 {100})", email_bytes)])
        mock_imap.store.return_value = ("OK", [])

        from ai_agents.document_processor import DocumentResult

        with patch("imaplib.IMAP4_SSL", return_value=mock_imap), \
             patch("ai_agents.document_processor.call_llm_for_document",
                   return_value='{"valid": true, "doc_type": "cv", "issues": [], "extracted_data": {}}'), \
             patch("services.email_inbox_worker.EmailInboxWorker._get_db", return_value=db):

            from services.email_inbox_worker import EmailInboxWorker
            worker = EmailInboxWorker(
                imap_user="inbox@company.com",
                imap_password="secret",
                upload_base_dir=tmp_path,
            )
            worker._run_poll_cycle(db)

        items = db.query(FakeEmailInboxItem).all()
        assert len(items) == 1
        assert items[0].sender_email == "mario@example.com"
        assert items[0].entity_type == "collaborator"
        assert items[0].processing_status in ("valid", "manual_review", "error")

    def test_unknown_sender_no_record(self, tmp_path):
        """Mittente sconosciuto → nessun record creato."""
        from sqlalchemy import create_engine, Column, Integer, String, Boolean, Text, DateTime
        from sqlalchemy.orm import declarative_base, Session

        Base = declarative_base()

        class FakeCollaborator(Base):
            __tablename__ = "collaborators"
            id = Column(Integer, primary_key=True)
            email = Column(String(100))
            is_active = Column(Boolean, default=True)

        class FakeAllievo(Base):
            __tablename__ = "allievi"
            id = Column(Integer, primary_key=True)
            email = Column(String(100))
            is_active = Column(Boolean, default=True)

        class FakeEmailInboxItem(Base):
            __tablename__ = "email_inbox_items"
            id = Column(Integer, primary_key=True)
            message_id = Column(String(500), unique=True)
            received_at = Column(DateTime)
            sender_email = Column(String(255))
            subject = Column(String(500))
            entity_type = Column(String(50))
            entity_id = Column(Integer)
            attachment_path = Column(String(1000))
            attachment_name = Column(String(255))
            processing_status = Column(String(50))
            llm_result = Column(Text)
            reply_sent = Column(Boolean, default=False)
            reply_sent_at = Column(DateTime)
            error_message = Column(Text)

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        db = Session(engine)

        email_bytes = self._make_fake_email_bytes("stranger@unknown.com", "Test")
        mock_imap = MagicMock()
        mock_imap.select.return_value = ("OK", [b"1"])
        mock_imap.search.return_value = ("OK", [b"1"])
        mock_imap.fetch.return_value = ("OK", [(b"1 (RFC822 {100})", email_bytes)])

        with patch("imaplib.IMAP4_SSL", return_value=mock_imap), \
             patch("services.email_inbox_worker.EmailInboxWorker._get_db", return_value=db):

            from services.email_inbox_worker import EmailInboxWorker
            worker = EmailInboxWorker(
                imap_user="inbox@company.com",
                imap_password="secret",
                upload_base_dir=tmp_path,
            )
            worker._run_poll_cycle(db)

        items = db.query(FakeEmailInboxItem).all()
        assert len(items) == 0
```

- [ ] **Step 2: Esegui per verificare che fallisca**

```bash
docker compose exec backend python -m pytest tests/test_email_agent.py::TestEmailInboxWorker -v
```

Atteso: `ModuleNotFoundError: No module named 'services.email_inbox_worker'`

- [ ] **Step 3: Implementa `EmailInboxWorker`**

Crea `backend/services/email_inbox_worker.py`:
```python
"""Worker IMAP polling per email in arrivo con allegati documenti."""
from __future__ import annotations

import email
import imaplib
import logging
import os
import threading
import time
from datetime import datetime, timezone
from email.header import decode_header
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_WORKER_INSTANCE: Optional["EmailInboxWorker"] = None
_WORKER_STATUS: dict = {"last_poll_at": None, "last_error": None, "running": False}


class EmailInboxWorker:
    def __init__(
        self,
        imap_user: Optional[str] = None,
        imap_password: Optional[str] = None,
        imap_host: str = "imap.gmail.com",
        imap_port: int = 993,
        poll_interval: int = 300,
        upload_base_dir: Optional[Path] = None,
    ) -> None:
        self.imap_user = imap_user or os.getenv("GMAIL_IMAP_USER", "")
        self.imap_password = imap_password or os.getenv("GMAIL_IMAP_APP_PASSWORD", "")
        self.imap_host = imap_host
        self.imap_port = imap_port
        self.poll_interval = poll_interval or int(os.getenv("INBOX_POLL_INTERVAL_SECONDS", "300"))
        self.upload_base_dir = Path(upload_base_dir) if upload_base_dir else Path("uploads") / "email_inbox"
        self._stop_event = threading.Event()

    def start_background(self) -> None:
        t = threading.Thread(target=self._loop, daemon=True, name="email-inbox-worker")
        t.start()
        _WORKER_STATUS["running"] = True
        logger.info("EmailInboxWorker: avviato in background (poll ogni %ds)", self.poll_interval)

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                db = self._get_db()
                self._run_poll_cycle(db)
                db.close()
                _WORKER_STATUS["last_poll_at"] = datetime.now(timezone.utc).isoformat()
                _WORKER_STATUS["last_error"] = None
            except Exception as exc:
                logger.exception("EmailInboxWorker: errore ciclo polling: %s", exc)
                _WORKER_STATUS["last_error"] = str(exc)
            self._stop_event.wait(self.poll_interval)

    def _run_poll_cycle(self, db) -> None:
        if not self.imap_user or not self.imap_password:
            logger.warning("EmailInboxWorker: GMAIL_IMAP_USER o GMAIL_IMAP_APP_PASSWORD non configurati, skip")
            return

        try:
            imap = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
            imap.login(self.imap_user, self.imap_password)
        except Exception as exc:
            logger.warning("EmailInboxWorker: connessione IMAP fallita: %s", exc)
            return

        try:
            imap.select("INBOX")
            status, data = imap.search(None, "UNSEEN")
            if status != "OK" or not data or not data[0]:
                return

            msg_ids = data[0].split()
            logger.info("EmailInboxWorker: %d email non lette trovate", len(msg_ids))

            for msg_id in msg_ids:
                try:
                    self._process_single_message(imap, msg_id, db)
                except Exception as exc:
                    logger.exception("EmailInboxWorker: errore su msg %s: %s", msg_id, exc)
        finally:
            try:
                imap.logout()
            except Exception:
                pass

    def _process_single_message(self, imap, msg_id: bytes, db) -> None:
        from services.attachment_handler import AttachmentHandler
        from services.inbox_router import InboxRouter
        from ai_agents.document_processor import DocumentProcessor
        from services.inbox_reply_composer import InboxReplyComposer

        _, msg_data = imap.fetch(msg_id, "(RFC822)")
        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)

        message_id = msg.get("Message-ID", "").strip()
        if not message_id:
            logger.warning("EmailInboxWorker: email senza Message-ID, skip")
            return

        # Deduplication
        if self._is_already_processed(db, message_id):
            logger.debug("EmailInboxWorker: message_id già processato, skip: %s", message_id)
            imap.store(msg_id, "+FLAGS", "\\Seen")
            return

        sender_email = _extract_address(msg.get("From", ""))
        subject = _decode_header_str(msg.get("Subject", ""))
        received_at = datetime.now(timezone.utc)

        router = InboxRouter(db)
        entity_type, entity_id = router.route(sender_email)

        if entity_type is None:
            logger.info("EmailInboxWorker: mittente sconosciuto %s, ignorato", sender_email)
            return

        handler = AttachmentHandler(upload_base_dir=self.upload_base_dir)
        attachment_result = handler.extract_and_save(msg, entity_type=entity_type, entity_id=entity_id)
        attachment_path = attachment_result[0] if attachment_result else None
        attachment_name = attachment_result[1] if attachment_result else None

        processor = DocumentProcessor()
        doc_result = processor.process(
            attachment_path,
            entity_name=_get_entity_name(db, entity_type, entity_id),
            expected_doc_type="documento",
        )

        if doc_result.valid is True:
            processing_status = "valid"
            reply_sent = False
        elif doc_result.valid is False:
            processing_status = "invalid"
            composer = InboxReplyComposer()
            reply_sent = composer.send_reply(
                to=sender_email,
                recipient_name=_get_entity_name(db, entity_type, entity_id),
                issues=doc_result.issues,
                original_subject=subject,
            )
        else:
            processing_status = "manual_review"
            reply_sent = False

        self._save_record(
            db,
            message_id=message_id,
            received_at=received_at,
            sender_email=sender_email,
            subject=subject,
            entity_type=entity_type,
            entity_id=entity_id,
            attachment_path=attachment_path,
            attachment_name=attachment_name,
            processing_status=processing_status,
            llm_result=doc_result.raw_llm_output,
            reply_sent=reply_sent,
        )

        imap.store(msg_id, "+FLAGS", "\\Seen")

    def _is_already_processed(self, db, message_id: str) -> bool:
        try:
            import models
        except ImportError:
            from backend import models
        return db.query(models.EmailInboxItem).filter_by(message_id=message_id).first() is not None

    def _save_record(self, db, *, message_id, received_at, sender_email, subject,
                     entity_type, entity_id, attachment_path, attachment_name,
                     processing_status, llm_result, reply_sent) -> None:
        import json
        try:
            import models
        except ImportError:
            from backend import models

        item = models.EmailInboxItem(
            message_id=message_id,
            received_at=received_at,
            sender_email=sender_email,
            subject=subject,
            entity_type=entity_type,
            entity_id=entity_id,
            attachment_path=attachment_path,
            attachment_name=attachment_name,
            processing_status=processing_status,
            llm_result=json.dumps(llm_result) if isinstance(llm_result, dict) else llm_result,
            reply_sent=reply_sent,
            reply_sent_at=datetime.now(timezone.utc) if reply_sent else None,
        )
        db.add(item)
        db.commit()

    def _get_db(self):
        from database import SessionLocal
        return SessionLocal()


def get_worker_status() -> dict:
    return dict(_WORKER_STATUS)


def start_email_inbox_worker() -> None:
    """Da chiamare in startup_event se GMAIL_IMAP_USER è configurato."""
    global _WORKER_INSTANCE
    imap_user = os.getenv("GMAIL_IMAP_USER", "")
    if not imap_user:
        logger.info("EmailInboxWorker: GMAIL_IMAP_USER non configurato, worker non avviato")
        return
    _WORKER_INSTANCE = EmailInboxWorker()
    _WORKER_INSTANCE.start_background()


def _extract_address(from_header: str) -> str:
    """Estrae l'indirizzo email dal campo From."""
    import re
    match = re.search(r"<([^>]+)>", from_header)
    if match:
        return match.group(1).strip().lower()
    return from_header.strip().lower()


def _decode_header_str(header: str) -> str:
    parts = decode_header(header or "")
    result = []
    for part, enc in parts:
        if isinstance(part, bytes):
            result.append(part.decode(enc or "utf-8", errors="replace"))
        else:
            result.append(str(part))
    return "".join(result)


def _get_entity_name(db, entity_type: Optional[str], entity_id: Optional[int]) -> str:
    if not entity_type or not entity_id:
        return ""
    try:
        import models
    except ImportError:
        from backend import models
    try:
        if entity_type == "collaborator":
            obj = db.query(models.Collaborator).get(entity_id)
            if obj:
                return f"{obj.first_name or ''} {obj.last_name or ''}".strip()
        elif entity_type == "allievo":
            obj = db.query(models.Allievo).get(entity_id)
            if obj:
                return getattr(obj, "first_name", "") or getattr(obj, "nome", "") or ""
    except Exception:
        pass
    return ""
```

- [ ] **Step 4: Esegui i test e verifica che passino**

```bash
docker compose exec backend python -m pytest tests/test_email_agent.py::TestEmailInboxWorker -v
```

Atteso: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/services/email_inbox_worker.py backend/tests/test_email_agent.py
git commit -m "feat: add EmailInboxWorker with IMAP polling and full pipeline orchestration"
```

---

## Task 7: Router API `email_inbox.py` + registrazione in `main.py`

**Files:**
- Create: `backend/routers/email_inbox.py`
- Modify: `backend/main.py`
- Modify: `backend/schemas.py`

**Responsabilità:** espone 4 endpoint per consultare l'audit trail e triggare polling manuale.

- [ ] **Step 1: Aggiungi gli schema Pydantic a `backend/schemas.py`**

Alla fine di `backend/schemas.py` (prima dell'eventuale `__all__`):
```python
# ---- Email Inbox ----

class EmailInboxItemOut(BaseModel):
    id: int
    message_id: str
    received_at: datetime
    sender_email: str
    subject: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    attachment_name: Optional[str] = None
    processing_status: str
    reply_sent: bool
    reply_sent_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class EmailInboxListResponse(BaseModel):
    items: list[EmailInboxItemOut]
    total: int


class EmailInboxStatusResponse(BaseModel):
    running: bool
    last_poll_at: Optional[str] = None
    last_error: Optional[str] = None
```

- [ ] **Step 2: Crea il router**

Crea `backend/routers/email_inbox.py`:
```python
"""Router per audit trail email in arrivo e controllo worker IMAP."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

import models
import schemas
from auth import get_current_user, require_admin
from database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/email-inbox", tags=["Email Inbox"])


@router.get("/items", response_model=schemas.EmailInboxListResponse)
def list_items(
    status: Optional[str] = Query(None, description="Filtra per processing_status"),
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    q = db.query(models.EmailInboxItem)
    if status:
        q = q.filter(models.EmailInboxItem.processing_status == status)
    if entity_type:
        q = q.filter(models.EmailInboxItem.entity_type == entity_type)
    if entity_id is not None:
        q = q.filter(models.EmailInboxItem.entity_id == entity_id)
    total = q.count()
    items = q.order_by(models.EmailInboxItem.received_at.desc()).offset(skip).limit(limit).all()
    return schemas.EmailInboxListResponse(items=items, total=total)


@router.get("/items/{item_id}", response_model=schemas.EmailInboxItemOut)
def get_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    item = db.query(models.EmailInboxItem).filter(models.EmailInboxItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item non trovato")
    return item


@router.post("/trigger-poll", status_code=202)
def trigger_poll(
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    """Triggera immediatamente un ciclo di polling IMAP (admin only)."""
    try:
        from services.email_inbox_worker import EmailInboxWorker
        worker = EmailInboxWorker()
        worker._run_poll_cycle(db)
        return {"message": "Polling completato"}
    except Exception as exc:
        logger.exception("trigger-poll fallito: %s", exc)
        raise HTTPException(status_code=500, detail=f"Polling fallito: {exc}")


@router.get("/status", response_model=schemas.EmailInboxStatusResponse)
def get_status(current_user=Depends(get_current_user)):
    from services.email_inbox_worker import get_worker_status
    return get_worker_status()
```

- [ ] **Step 3: Registra il router e avvia il worker in `main.py`**

In `backend/main.py`, nella sezione degli import dei router (cerca `from routers import (`):
```python
# Aggiungere nella lista import dei router:
from routers import email_inbox
```

Subito dopo l'ultimo `app.include_router(...)` (es. dopo `app.include_router(stats.router)`):
```python
app.include_router(email_inbox.router)
```

In `startup_event`, dopo il blocco `check_db_health`:
```python
    # Avvia worker IMAP email in arrivo (se configurato)
    try:
        from services.email_inbox_worker import start_email_inbox_worker
        start_email_inbox_worker()
    except Exception as e:
        logger.error(f"Error starting email inbox worker: {e}")
```

- [ ] **Step 4: Verifica sintassi**

```bash
docker compose exec backend python -m py_compile \
    routers/email_inbox.py \
    schemas.py \
    main.py
```

Atteso: nessun output.

- [ ] **Step 5: Rebuild e test container**

```bash
docker compose up -d --build backend
docker compose exec backend python -m pytest tests/test_email_agent.py -v
```

Atteso: tutti i test passano.

- [ ] **Step 6: Verifica endpoint disponibili**

```bash
curl -s http://localhost:8000/api/v1/email-inbox/status | python3 -m json.tool
```

Atteso: `{"running": false, "last_poll_at": null, "last_error": null}` (o `running: true` se `GMAIL_IMAP_USER` è impostato)

- [ ] **Step 7: Commit**

```bash
git add backend/routers/email_inbox.py backend/schemas.py backend/main.py
git commit -m "feat: add email_inbox router with audit trail endpoints and worker startup"
```

---

## Task 8: Configurazione Docker + variabili d'ambiente

**Files:**
- Modify: `docker-compose.yml`

**Responsabilità:** aggiunge le env vars IMAP al servizio backend senza valori reali (da impostare via `.env` o secret manager).

- [ ] **Step 1: Aggiungi le env vars al servizio `backend` in `docker-compose.yml`**

Trova il blocco `environment:` del servizio `backend` e aggiunge:
```yaml
      # Email Inbox Worker (IMAP)
      - GMAIL_IMAP_USER=${GMAIL_IMAP_USER:-}
      - GMAIL_IMAP_APP_PASSWORD=${GMAIL_IMAP_APP_PASSWORD:-}
      - INBOX_POLL_INTERVAL_SECONDS=${INBOX_POLL_INTERVAL_SECONDS:-300}
      - MAX_ATTACHMENT_MB=${MAX_ATTACHMENT_MB:-10}
```

- [ ] **Step 2: Verifica che il compose sia valido**

```bash
docker compose config > /dev/null && echo "OK"
```

Atteso: `OK`

- [ ] **Step 3: Restart backend e verifica log**

```bash
docker compose up -d backend
docker compose logs --tail=20 backend | grep -i "email\|IMAP\|inbox"
```

Atteso: `EmailInboxWorker: GMAIL_IMAP_USER non configurato, worker non avviato` (oppure avviato se env è impostata)

- [ ] **Step 4: Commit finale**

```bash
git add docker-compose.yml
git commit -m "feat: add IMAP env vars to docker-compose for EmailInboxWorker"
```

---

## Self-Review

### Spec coverage
| Requisito spec | Task che lo implementa |
|---|---|
| IMAP polling ogni 5 min | Task 6 `EmailInboxWorker._loop` |
| Deduplication su `message_id` | Task 6 `_is_already_processed` |
| `InboxRouter` collaborator/allievo | Task 3 |
| `AttachmentHandler` whitelist + size limit | Task 2 |
| `DocumentProcessor` LLM + fallback | Task 4 |
| `InboxReplyComposer` + template | Task 5 |
| Tabella `email_inbox_items` | Task 1 |
| Enum status: pending/valid/invalid/manual_review/skipped/error | Task 6 `_save_record` |
| Endpoint GET `/items` | Task 7 |
| Endpoint GET `/items/{id}` | Task 7 |
| Endpoint POST `/trigger-poll` | Task 7 |
| Endpoint GET `/status` | Task 7 |
| Env vars `GMAIL_IMAP_*` | Task 8 |
| `pdfplumber` dipendenza | Task 1 |
| Mittente sconosciuto ignorato (no reply) | Task 6 `_process_single_message` |
| Worker avviato da `startup_event` | Task 7 |
| Marca email come `\Seen` solo a successo | Task 6 `_process_single_message` |

### Placeholder scan
Nessun "TBD", "TODO", "implement later" trovato.

### Type consistency
- `AttachmentHandler.extract_and_save` → restituisce `Optional[Tuple[str, str]]` → usato in Task 6 come `attachment_result[0]`, `attachment_result[1]` ✓
- `DocumentProcessor.process` → restituisce `DocumentResult` → usato in Task 6 con `.valid`, `.issues`, `.raw_llm_output` ✓
- `InboxRouter.route` → restituisce `Tuple[Optional[str], Optional[int]]` → usato in Task 6 come `entity_type, entity_id` ✓
- `models.EmailInboxItem` → creato in Task 1, usato in Task 6 `_save_record` e Task 7 router ✓
- `schemas.EmailInboxItemOut` → `from_attributes = True` compatibile con SQLAlchemy model ✓
