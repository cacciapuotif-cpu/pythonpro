"""Test suite per Email Agent."""
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

        class FakeAziendaCliente(Base):
            __tablename__ = "aziende_clienti"
            id = Column(Integer, primary_key=True)
            email = Column(String(100), unique=True)
            pec = Column(String(100), unique=True)
            referente_email = Column(String(100), unique=True)
            legale_rappresentante_email = Column(String(100), unique=True)
            attivo = Column(Boolean, default=True)

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        db = Session(engine)
        db.add(FakeCollaborator(id=10, email="mario@example.com", is_active=True))
        db.add(FakeAllievo(id=20, email="luigi@example.com", is_active=True))
        db.add(FakeAziendaCliente(id=30, pec="visure@azienda.it", attivo=True))
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

    def test_finds_azienda_cliente_by_pec(self):
        from services.inbox_router import InboxRouter
        db = self._make_db()
        router = InboxRouter(db)
        entity_type, entity_id = router.route("visure@azienda.it")
        assert entity_type == "azienda_cliente"
        assert entity_id == 30

    def test_durc_subject_is_recognized_as_company_document(self):
        from services.document_intake_agent import DocumentIntakeAgent

        agent = DocumentIntakeAgent()
        inferred = agent.infer_expected_doc_type(
            db=None,
            entity_type="azienda_cliente",
            entity_id=30,
            subject="Invio DURC aggiornato",
            attachment_name="durc_aprile.pdf",
        )
        assert inferred == "durc"


# ===========================================================
# DocumentProcessor
# ===========================================================

class TestDocumentProcessor:

    def _mock_llm_response(self, valid: bool, doc_type: str = "cv", issues=None):
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


# ===========================================================
# DocumentIntakeAgent
# ===========================================================

class TestDocumentIntakeAgent:

    def _make_real_db(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        import models

        engine = create_engine("sqlite:///:memory:")
        models.Base.metadata.create_all(
            engine,
            tables=[
                models.Collaborator.__table__,
                models.DocumentoRichiesto.__table__,
                models.EmailInboxItem.__table__,
                models.AziendaCliente.__table__,
            ],
        )
        db = Session(engine)
        collaborator = models.Collaborator(
            id=1,
            first_name="Mario",
            last_name="Rossi",
            email="mario@example.com",
            fiscal_code="RSSMRA80A01H501Z",
        )
        db.add(collaborator)
        db.commit()
        return db, collaborator

    def test_infers_expected_doc_type_from_pending_requirement(self):
        import models
        from services.document_intake_agent import DocumentIntakeAgent

        db, _ = self._make_real_db()
        db.add(
            models.DocumentoRichiesto(
                collaboratore_id=1,
                tipo_documento="documento_identita",
                stato="richiesto",
            )
        )
        db.commit()

        agent = DocumentIntakeAgent()
        inferred = agent.infer_expected_doc_type(
            db,
            entity_type="collaborator",
            entity_id=1,
            subject="Invio documentazione",
            attachment_name="allegato.pdf",
        )

        assert inferred == "documento_identita"

    def test_valid_curriculum_updates_document_and_collaborator(self):
        from ai_agents.document_processor import DocumentResult
        from services.document_intake_agent import DocumentIntakeAgent

        db, _ = self._make_real_db()
        agent = DocumentIntakeAgent()
        result = DocumentResult(
            valid=True,
            doc_type="cv",
            issues=[],
            extracted_data={
                "profilo_professionale": "Project manager digitale",
                "skills": ["Python", "Gestione progetti"],
                "education": "Laurea magistrale",
            },
        )

        outcome = agent.apply_document_result(
            db,
            entity_type="collaborator",
            entity_id=1,
            attachment_path="/tmp/cv.pdf",
            attachment_name="cv.pdf",
            result=result,
            expected_doc_type="curriculum",
        )

        import models
        collaborator = db.query(models.Collaborator).filter(models.Collaborator.id == 1).first()
        documento = db.query(models.DocumentoRichiesto).filter(models.DocumentoRichiesto.collaboratore_id == 1).first()

        assert outcome.processing_status == "valid"
        assert outcome.resolved_doc_type == "curriculum"
        assert documento is not None
        assert documento.stato == "validato"
        assert collaborator.curriculum_filename == "cv.pdf"
        assert collaborator.curriculum_path == "/tmp/cv.pdf"
        assert collaborator.profilo_professionale == "Project manager digitale"
        assert "Python" in collaborator.competenze_principali

    def test_invalid_identity_document_marks_requirement_rejected(self):
        import models
        from ai_agents.document_processor import DocumentResult
        from services.document_intake_agent import DocumentIntakeAgent

        db, _ = self._make_real_db()
        db.add(
            models.DocumentoRichiesto(
                collaboratore_id=1,
                tipo_documento="documento_identita",
                stato="richiesto",
            )
        )
        db.commit()

        agent = DocumentIntakeAgent()
        result = DocumentResult(
            valid=False,
            doc_type="documento_identita",
            issues=["documento scaduto"],
            extracted_data={"data_scadenza": "2025-01-01T00:00:00"},
        )

        outcome = agent.apply_document_result(
            db,
            entity_type="collaborator",
            entity_id=1,
            attachment_path="/tmp/id.pdf",
            attachment_name="id.pdf",
            result=result,
            expected_doc_type="documento_identita",
        )

        documento = db.query(models.DocumentoRichiesto).filter(models.DocumentoRichiesto.collaboratore_id == 1).first()
        assert outcome.processing_status == "invalid"
        assert documento.stato == "rifiutato"
        assert "scaduto" in (documento.note_operatore or "")

    def test_visura_camerale_updates_azienda_cliente(self):
        import models
        from ai_agents.document_processor import DocumentResult
        from services.document_intake_agent import DocumentIntakeAgent

        db, _ = self._make_real_db()
        azienda = models.AziendaCliente(
            id=55,
            ragione_sociale="Azienda Demo",
            partita_iva="12345678901",
            pec="visure@azienda.it",
            attivo=True,
        )
        db.add(azienda)
        db.commit()

        agent = DocumentIntakeAgent()
        result = DocumentResult(
            valid=True,
            doc_type="visura_camerale",
            issues=[],
            extracted_data={
                "ragione_sociale": "Azienda Demo SRL",
                "codice_fiscale": "12345678901",
                "codice_ateco": "62.01",
                "indirizzo": "Via Roma 1",
                "citta": "Milano",
                "cap": "20100",
                "provincia": "mi",
                "pec": "pec@aziendademo.it",
                "telefono": "021234567",
                "legale_rappresentante_nome": "Mario",
                "legale_rappresentante_cognome": "Rossi",
                "legale_rappresentante_codice_fiscale": "RSSMRA80A01H501Z",
                "oggetto_sociale": "Consulenza informatica",
            },
        )

        outcome = agent.apply_document_result(
            db,
            entity_type="azienda_cliente",
            entity_id=55,
            attachment_path="/tmp/visura.pdf",
            attachment_name="visura_camerale.pdf",
            result=result,
            expected_doc_type="visura_camerale",
        )

        refreshed = db.query(models.AziendaCliente).filter(models.AziendaCliente.id == 55).first()
        assert outcome.processing_status == "valid"
        assert refreshed.ragione_sociale == "Azienda Demo SRL"
        assert refreshed.settore_ateco == "62.01"
        assert refreshed.indirizzo == "Via Roma 1"
        assert refreshed.citta == "Milano"
        assert refreshed.cap == "20100"
        assert refreshed.provincia == "MI"
        assert refreshed.pec == "pec@aziendademo.it"
        assert refreshed.legale_rappresentante_nome == "Mario"
        assert refreshed.attivita_erogate == "Consulenza informatica"

    def test_durc_updates_company_generic_fields_and_audit_note(self):
        import models
        from ai_agents.document_processor import DocumentResult
        from services.document_intake_agent import DocumentIntakeAgent

        db, _ = self._make_real_db()
        azienda = models.AziendaCliente(
            id=77,
            ragione_sociale="Beta SRL",
            partita_iva="98765432109",
            email="amministrazione@beta.it",
            attivo=True,
        )
        db.add(azienda)
        db.commit()

        agent = DocumentIntakeAgent()
        result = DocumentResult(
            valid=True,
            doc_type="durc",
            issues=[],
            extracted_data={
                "ragione_sociale": "Beta SRL",
                "partita_iva": "98765432109",
                "numero_protocollo": "DURC-12345",
                "data_scadenza": "2026-12-31",
                "esito_regolarita": "regolare",
                "pec": "pec@beta.it",
            },
        )

        outcome = agent.apply_document_result(
            db,
            entity_type="azienda_cliente",
            entity_id=77,
            attachment_path="/tmp/durc.pdf",
            attachment_name="durc.pdf",
            result=result,
            expected_doc_type="durc",
        )

        refreshed = db.query(models.AziendaCliente).filter(models.AziendaCliente.id == 77).first()
        assert outcome.processing_status == "valid"
        assert refreshed.pec == "pec@beta.it"
        assert refreshed.note is not None
        assert "[durc]" in refreshed.note
        assert "numero_protocollo=DURC-12345" in refreshed.note

    def test_certificato_attribuzione_partita_iva_updates_company_address_fields(self):
        import models
        from ai_agents.document_processor import DocumentResult
        from services.document_intake_agent import DocumentIntakeAgent

        db, _ = self._make_real_db()
        azienda = models.AziendaCliente(
            id=88,
            ragione_sociale="Gamma SRL",
            partita_iva="11122233344",
            attivo=True,
        )
        db.add(azienda)
        db.commit()

        agent = DocumentIntakeAgent()
        result = DocumentResult(
            valid=True,
            doc_type="certificato_attribuzione_partita_iva",
            issues=[],
            extracted_data={
                "ragione_sociale": "Gamma Consulting SRL",
                "partita_iva": "11122233344",
                "codice_fiscale": "11122233344",
                "indirizzo": "Via Milano 10",
                "citta": "Torino",
                "cap": "10121",
                "provincia": "to",
                "attivita": "Servizi consulenziali",
            },
        )

        outcome = agent.apply_document_result(
            db,
            entity_type="azienda_cliente",
            entity_id=88,
            attachment_path="/tmp/attribuzione_piva.pdf",
            attachment_name="attribuzione_piva.pdf",
            result=result,
            expected_doc_type="certificato_attribuzione_partita_iva",
        )

        refreshed = db.query(models.AziendaCliente).filter(models.AziendaCliente.id == 88).first()
        assert outcome.processing_status == "valid"
        assert refreshed.ragione_sociale == "Gamma Consulting SRL"
        assert refreshed.indirizzo == "Via Milano 10"
        assert refreshed.citta == "Torino"
        assert refreshed.cap == "10121"
        assert refreshed.provincia == "TO"
        assert refreshed.attivita_erogate == "Servizi consulenziali"

    def test_statuto_updates_company_activity_and_note(self):
        import models
        from ai_agents.document_processor import DocumentResult
        from services.document_intake_agent import DocumentIntakeAgent

        db, _ = self._make_real_db()
        azienda = models.AziendaCliente(
            id=99,
            ragione_sociale="Delta SRL",
            partita_iva="55566677788",
            attivo=True,
        )
        db.add(azienda)
        db.commit()

        agent = DocumentIntakeAgent()
        result = DocumentResult(
            valid=True,
            doc_type="statuto",
            issues=[],
            extracted_data={
                "ragione_sociale": "Delta Tech SRL",
                "oggetto_sociale": "Sviluppo software e consulenza IT",
                "forma_giuridica": "SRL",
                "capitale_sociale": "10000 EUR",
            },
        )

        outcome = agent.apply_document_result(
            db,
            entity_type="azienda_cliente",
            entity_id=99,
            attachment_path="/tmp/statuto.pdf",
            attachment_name="statuto.pdf",
            result=result,
            expected_doc_type="statuto",
        )

        refreshed = db.query(models.AziendaCliente).filter(models.AziendaCliente.id == 99).first()
        assert outcome.processing_status == "valid"
        assert refreshed.ragione_sociale == "Delta Tech SRL"
        assert refreshed.attivita_erogate == "Sviluppo software e consulenza IT"
        assert refreshed.note is not None
        assert "[statuto]" in refreshed.note


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
        msg["Message-ID"] = f"<test-{from_addr.replace('@','_')}-{subject.replace(' ','_')}@test>"
        msg["Date"] = "Thu, 10 Apr 2026 10:00:00 +0000"
        msg.attach(MIMEText("See attachment", "plain"))
        part = MIMEBase("application", "pdf")
        part.set_payload(pdf_content)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename="test_doc.pdf")
        msg.attach(part)
        return msg.as_bytes()

    def _make_sqlite_db(self, with_collaborator_email: str = None):
        """Crea un DB SQLite in-memory con le tabelle necessarie per i test."""
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
        if with_collaborator_email:
            db.add(FakeCollaborator(id=1, email=with_collaborator_email))
            db.commit()
        return db, FakeEmailInboxItem

    def test_known_sender_creates_db_record(self, tmp_path):
        """Pipeline completa con mittente noto -> record in DB."""
        db, FakeEmailInboxItem = self._make_sqlite_db(with_collaborator_email="mario@example.com")
        email_bytes = self._make_fake_email_bytes("mario@example.com", "Invio documento")

        mock_imap = MagicMock()
        mock_imap.__enter__ = MagicMock(return_value=mock_imap)
        mock_imap.__exit__ = MagicMock(return_value=False)
        mock_imap.select.return_value = ("OK", [b"1"])
        mock_imap.search.return_value = ("OK", [b"1"])
        mock_imap.fetch.return_value = ("OK", [(b"1 (RFC822 {100})", email_bytes)])
        mock_imap.store.return_value = ("OK", [])
        mock_imap.login.return_value = ("OK", [])
        mock_imap.logout.return_value = ("OK", [])

        with patch("imaplib.IMAP4_SSL", return_value=mock_imap), \
             patch("services.document_intake_agent.DocumentIntakeAgent.infer_expected_doc_type", return_value="curriculum"), \
             patch("services.document_intake_agent.DocumentIntakeAgent.apply_document_result") as mock_apply, \
             patch("ai_agents.document_processor.call_llm_for_document",
                   return_value='{"valid": true, "doc_type": "cv", "issues": [], "extracted_data": {}}'):
            mock_apply.return_value.to_dict.return_value = {
                "expected_doc_type": "curriculum",
                "resolved_doc_type": "curriculum",
                "processing_status": "valid",
            }
            mock_apply.return_value.processing_status = "valid"
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
        assert items[0].processing_status in ("valid", "manual_review")
        saved_payload = json.loads(items[0].llm_result)
        assert saved_payload["intake_outcome"]["resolved_doc_type"] == "curriculum"

    def test_unknown_sender_no_record(self, tmp_path):
        """Mittente sconosciuto -> nessun record creato."""
        db, FakeEmailInboxItem = self._make_sqlite_db()
        email_bytes = self._make_fake_email_bytes("stranger@unknown.com", "Test")

        mock_imap = MagicMock()
        mock_imap.__enter__ = MagicMock(return_value=mock_imap)
        mock_imap.__exit__ = MagicMock(return_value=False)
        mock_imap.select.return_value = ("OK", [b"1"])
        mock_imap.search.return_value = ("OK", [b"1"])
        mock_imap.fetch.return_value = ("OK", [(b"1 (RFC822 {100})", email_bytes)])
        mock_imap.login.return_value = ("OK", [])
        mock_imap.logout.return_value = ("OK", [])

        with patch("imaplib.IMAP4_SSL", return_value=mock_imap):
            from services.email_inbox_worker import EmailInboxWorker
            worker = EmailInboxWorker(
                imap_user="inbox@company.com",
                imap_password="secret",
                upload_base_dir=tmp_path,
            )
            worker._run_poll_cycle(db)

        items = db.query(FakeEmailInboxItem).all()
        assert len(items) == 0
