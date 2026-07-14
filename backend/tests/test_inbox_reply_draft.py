"""AGENT-03: la reply automatica dell'email intake diventa bozza approvabile.

Documento invalido o allegato non supportato NON generano piu' un invio SMTP
diretto: creano AgentRun + AgentSuggestion + AgentCommunicationDraft in stato
'draft'. L'invio avviene solo dal flusso di revisione UI.
"""
from __future__ import annotations

from email.message import EmailMessage
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import models
from auth import User
from database import Base


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        User.__table__,
        models.Collaborator.__table__,
        models.DocumentoRichiesto.__table__,
        models.EmailInboxItem.__table__,
        models.AgentRun.__table__,
        models.AgentSuggestion.__table__,
        models.AgentCommunicationDraft.__table__,
        models.AgentReviewAction.__table__,
        models.AuditLog.__table__,
        models.SecurityAuditLog.__table__,
    ])
    return Session(engine)


def _add_collaborator(db) -> models.Collaborator:
    collaborator = models.Collaborator(
        first_name="Mario",
        last_name="Rossi",
        email="mario@example.com",
        fiscal_code="RSSMRA80A01H501U",
        is_active=True,
        consenso_email_agenti=True,
    )
    db.add(collaborator)
    db.commit()
    return collaborator


def _fake_imap_for(msg: EmailMessage):
    imap = MagicMock()
    imap.fetch.return_value = ("OK", [(b"1 (RFC822)", msg.as_bytes())])
    return imap


def _pdf_message(message_id: str = "<msg-1@example.com>") -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = "Mario Rossi <mario@example.com>"
    msg["Subject"] = "Documento identita"
    msg["Message-ID"] = message_id
    msg.set_content("In allegato il documento.")
    msg.add_attachment(b"%PDF-1.4 fake", maintype="application", subtype="pdf", filename="carta_identita.pdf")
    return msg


def _txt_attachment_message(message_id: str = "<msg-2@example.com>") -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = "Mario Rossi <mario@example.com>"
    msg["Subject"] = "Documento"
    msg["Message-ID"] = message_id
    msg.set_content("In allegato il documento.")
    msg.add_attachment(b"testo non pdf", maintype="text", subtype="plain", filename="documento.txt")
    return msg


def _run_worker_on(msg: EmailMessage, db, tmp_path):
    from services.email_inbox_worker import EmailInboxWorker

    worker = EmailInboxWorker(
        imap_user="inbox@example.com",
        imap_password="x",
        upload_base_dir=tmp_path,
    )
    worker._process_single_message(_fake_imap_for(msg), b"1", db)


def test_invalid_document_creates_reply_draft_no_send(tmp_path):
    from ai_agents.document_processor import DocumentResult

    db = make_db()
    _add_collaborator(db)

    invalid_result = DocumentResult(
        valid=False,
        doc_type="documento_identita",
        issues=["Documento illeggibile"],
        confidence=0.9,
    )

    with patch("ai_agents.document_processor.DocumentProcessor.process", return_value=invalid_result), \
         patch("services.inbox_reply_composer.InboxReplyComposer.send_reply") as send_mock:
        _run_worker_on(_pdf_message(), db, tmp_path)

    send_mock.assert_not_called()

    draft = db.query(models.AgentCommunicationDraft).one()
    assert draft.status == "draft"
    assert draft.channel == "email"
    assert draft.recipient_email == "mario@example.com"
    assert "Documento illeggibile" in draft.body
    assert draft.sent_at is None

    suggestion = db.query(models.AgentSuggestion).filter_by(id=draft.suggestion_id).one()
    assert suggestion.status == "pending"
    assert suggestion.suggestion_type == "inbox_reply_needed"

    run = db.query(models.AgentRun).filter_by(id=suggestion.run_id).one()
    assert run.agent_type == "email_intake"

    item = db.query(models.EmailInboxItem).one()
    assert item.reply_sent is False


def test_unsupported_attachment_creates_reply_draft_no_send(tmp_path):
    db = make_db()
    _add_collaborator(db)

    with patch("services.inbox_reply_composer.InboxReplyComposer.send_reply") as send_mock:
        _run_worker_on(_txt_attachment_message(), db, tmp_path)

    send_mock.assert_not_called()

    draft = db.query(models.AgentCommunicationDraft).one()
    assert draft.status == "draft"
    assert draft.recipient_email == "mario@example.com"
    assert "PDF" in draft.body

    item = db.query(models.EmailInboxItem).one()
    assert item.reply_sent is False


def test_reply_draft_sent_only_via_workflow_action(tmp_path):
    from agent_workflows import apply_workflow_action
    from ai_agents.document_processor import DocumentResult

    db = make_db()
    _add_collaborator(db)

    invalid_result = DocumentResult(
        valid=False,
        doc_type="documento_identita",
        issues=["Documento scaduto"],
        confidence=0.9,
    )

    with patch("ai_agents.document_processor.DocumentProcessor.process", return_value=invalid_result), \
         patch("services.inbox_reply_composer.InboxReplyComposer.send_reply") as send_mock:
        _run_worker_on(_pdf_message("<msg-3@example.com>"), db, tmp_path)
    send_mock.assert_not_called()

    draft = db.query(models.AgentCommunicationDraft).one()

    with patch("agent_workflows._send_email", return_value=(True, "Email inviata")) as send_mock:
        updated = apply_workflow_action(
            db,
            suggestion_id=draft.suggestion_id,
            action="approve_email",
            reviewed_by_user_id=1,
        )

    send_mock.assert_called_once()
    assert updated.status == "sent"
    db.refresh(draft)
    assert draft.status == "sent"


def test_compose_renders_subject_and_body():
    from services.inbox_reply_composer import InboxReplyComposer

    subject, body = InboxReplyComposer().compose(
        recipient_name="Mario Rossi",
        issues=["Serve un PDF"],
        original_subject="Documento",
    )
    assert subject.startswith("Re: Documento")
    assert "Mario Rossi" in body
    assert "Serve un PDF" in body
