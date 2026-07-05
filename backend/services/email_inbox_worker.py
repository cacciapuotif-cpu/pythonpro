"""Worker IMAP polling per email in arrivo con allegati documenti."""
from __future__ import annotations

from time_utils import utc_now
import email
import imaplib
import json
import logging
import os
import threading
from datetime import datetime, timezone
from email.header import decode_header
from email.message import Message
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

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
        if _WORKER_STATUS["running"]:
            logger.warning("EmailInboxWorker: worker gia' in esecuzione, skip avvio duplicato")
            return
        t = threading.Thread(target=self._loop, daemon=True, name="email-inbox-worker")
        t.start()
        _WORKER_STATUS["running"] = True
        logger.info("EmailInboxWorker: avviato in background (poll ogni %ds)", self.poll_interval)

    def _loop(self) -> None:
        try:
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
        finally:
            _WORKER_STATUS["running"] = False
            logger.info("EmailInboxWorker: thread terminato")

    def _run_poll_cycle(self, db) -> None:
        if not self.imap_user or not self.imap_password:
            logger.warning("EmailInboxWorker: credenziali IMAP non configurate, skip")
            return

        try:
            imap = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
            imap.login(self.imap_user, self.imap_password)
        except Exception as exc:
            logger.warning("EmailInboxWorker: connessione IMAP fallita: %s", exc)
            return

        try:
            imap.select("INBOX")
            status, data = imap.search(None, "ALL")
            if status != "OK" or not data or not data[0]:
                return

            msg_ids = data[0].split()
            logger.info("EmailInboxWorker: %d email trovate in inbox per controllo deduplica", len(msg_ids))

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
        from services.email_body_parser import extract_email_body_text, extract_structured_contact_data
        from services.inbox_router import InboxRouter
        from services.document_intake_agent import DocumentIntakeAgent
        from ai_agents.document_processor import DocumentProcessor
        from services.inbox_reply_composer import InboxReplyComposer

        _, msg_data = imap.fetch(msg_id, "(RFC822)")
        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)

        message_id = msg.get("Message-ID", "").strip()
        if not message_id:
            logger.warning("EmailInboxWorker: email senza Message-ID, skip")
            return

        if self._is_already_processed(db, message_id):
            logger.debug("EmailInboxWorker: message_id gia processato: %s", message_id)
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
        entity_name = _get_entity_name(db, entity_type, entity_id)
        body_text = extract_email_body_text(msg)
        body_data = extract_structured_contact_data(body_text)
        body_updated_fields = _apply_body_extracted_data(
            db,
            entity_type=entity_type,
            entity_id=entity_id,
            extracted_data=body_data,
        )
        if body_data:
            logger.info(
                "EmailInboxWorker: dati body estratti per %s/%s: %s; campi aggiornati: %s",
                entity_type,
                entity_id,
                sorted(body_data.keys()),
                body_updated_fields,
            )

        unsupported_attachment = _find_unsupported_meaningful_attachment(msg)
        if unsupported_attachment and not attachment_path:
            unsupported_name, unsupported_content_type = unsupported_attachment
            issues = [
                "Accettiamo documenti in formato PDF, DOC o DOCX.",
                f"L'allegato ricevuto ('{unsupported_name}') non e' un PDF ({unsupported_content_type or 'tipo sconosciuto'}).",
                "Reinvia il documento allegando un file PDF, DOC o DOCX.",
            ]
            composer = InboxReplyComposer()
            reply_sent = composer.send_reply(
                to=sender_email,
                recipient_name=entity_name,
                issues=issues,
                original_subject=subject,
            )
            self._save_record(
                db,
                message_id=message_id,
                received_at=received_at,
                sender_email=sender_email,
                subject=subject,
                entity_type=entity_type,
                entity_id=entity_id,
                attachment_path=None,
                attachment_name=unsupported_name,
                processing_status="invalid" if not body_updated_fields else "valid",
                llm_result={
                    "raw_llm_output": None,
                    "valid": False,
                    "doc_type": "unsupported_attachment",
                    "issues": issues,
                    "extracted_data": body_data,
                    "body_updated_fields": body_updated_fields,
                },
                reply_sent=reply_sent,
            )
            imap.store(msg_id, "+FLAGS", "\\Seen")
            return

        intake_agent = DocumentIntakeAgent()
        expected_doc_type = intake_agent.infer_expected_doc_type(
            db,
            entity_type=entity_type,
            entity_id=entity_id,
            subject=subject,
            attachment_name=attachment_name,
        )
        processor = DocumentProcessor()
        doc_result = processor.process(
            attachment_path,
            entity_name=entity_name,
            expected_doc_type=expected_doc_type,
        )
        doc_result.extracted_data = {
            **body_data,
            **(doc_result.extracted_data or {}),
        }

        intake_outcome = intake_agent.apply_document_result(
            db,
            entity_type=entity_type,
            entity_id=entity_id,
            attachment_path=attachment_path,
            attachment_name=attachment_name,
            result=doc_result,
            expected_doc_type=expected_doc_type,
        )

        if doc_result.valid is True:
            processing_status = "valid"
            reply_sent = False
        elif doc_result.valid is False:
            processing_status = "invalid"
            composer = InboxReplyComposer()
            reply_sent = composer.send_reply(
                to=sender_email,
                recipient_name=entity_name,
                issues=doc_result.issues,
                original_subject=subject,
            )
        else:
            processing_status = "manual_review"
            reply_sent = False

        if body_updated_fields and processing_status == "manual_review":
            processing_status = "valid"

        auto_updated = bool(
            body_updated_fields or intake_outcome.collaborator_updated_fields
        )
        if auto_updated and intake_outcome.processing_status in ("manual_review", "valid", None):
            final_status = "auto_processed"
        else:
            final_status = intake_outcome.processing_status or processing_status

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
            processing_status=final_status,
            llm_result={
                "raw_llm_output": doc_result.raw_llm_output,
                "valid": doc_result.valid,
                "doc_type": doc_result.doc_type,
                    "issues": doc_result.issues,
                    "extracted_data": doc_result.extracted_data,
                    "body_updated_fields": body_updated_fields,
                    "intake_outcome": intake_outcome.to_dict(),
                },
            reply_sent=reply_sent,
        )

        if final_status in ("valid", "auto_processed") and entity_type == "collaborator" and entity_id:
            self._create_auto_update_suggestion(
                db,
                entity_id=entity_id,
                entity_name=entity_name,
                updated_fields=body_updated_fields + intake_outcome.collaborator_updated_fields,
                doc_type=intake_outcome.resolved_doc_type,
            )

        imap.store(msg_id, "+FLAGS", "\\Seen")

    def _create_auto_update_suggestion(
        self,
        db,
        *,
        entity_id: int,
        entity_name: str,
        updated_fields: list,
        doc_type: str,
    ) -> None:
        try:
            import models
            from datetime import datetime

            collab = db.query(models.Collaborator).filter(models.Collaborator.id == entity_id).first()
            display_name = entity_name or (
                f"{collab.first_name} {collab.last_name}" if collab else f"collaboratore {entity_id}"
            )

            # Close pending "request_missing_collaborator_data" suggestions for this collaborator
            pending = (
                db.query(models.AgentSuggestion)
                .filter(
                    models.AgentSuggestion.entity_type == "collaborator",
                    models.AgentSuggestion.entity_id == entity_id,
                    models.AgentSuggestion.suggestion_type == "request_missing_collaborator_data",
                    models.AgentSuggestion.status == "pending",
                )
                .all()
            )
            for s in pending:
                s.status = "resolved"
                s.reviewed_at = utc_now()
            if pending:
                db.commit()

            # Create AgentRun for this auto-intake event
            run = models.AgentRun(
                agent_type="email_intake",
                status="completed",
                entity_type="collaborator",
                entity_id=entity_id,
                triggered_by="email_inbox_worker",
                items_processed=1,
                suggestions_created=1,
            )
            db.add(run)
            db.commit()
            db.refresh(run)

            fields_desc = ", ".join(updated_fields) if updated_fields else doc_type
            suggestion = models.AgentSuggestion(
                run_id=run.id,
                suggestion_type="auto_update_applied",
                status="completed",
                severity="low",
                entity_type="collaborator",
                entity_id=entity_id,
                title=f"Dati auto-aggiornati — {display_name}",
                description=f"Aggiornamento automatico da email: {fields_desc}",
                priority="low",
                auto_fix_available=False,
            )
            db.add(suggestion)
            run.suggestions_count = 1
            db.add(run)
            db.commit()
        except Exception:
            logger.exception("_create_auto_update_suggestion fallita per collaborator %s", entity_id)

    def _is_already_processed(self, db, message_id: str) -> bool:
        from sqlalchemy import text
        row = db.execute(
            text("SELECT id FROM email_inbox_items WHERE message_id = :mid LIMIT 1"),
            {"mid": message_id}
        ).fetchone()
        return row is not None

    def _save_record(self, db, *, message_id, received_at, sender_email, subject,
                     entity_type, entity_id, attachment_path, attachment_name,
                     processing_status, llm_result, reply_sent) -> None:
        from sqlalchemy import text
        db.execute(
            text("""
                INSERT INTO email_inbox_items
                (message_id, received_at, sender_email, subject, entity_type, entity_id,
                 attachment_path, attachment_name, processing_status, llm_result,
                 reply_sent, reply_sent_at)
                VALUES (:message_id, :received_at, :sender_email, :subject, :entity_type, :entity_id,
                        :attachment_path, :attachment_name, :processing_status, :llm_result,
                        :reply_sent, :reply_sent_at)
            """),
            {
                "message_id": message_id,
                "received_at": received_at,
                "sender_email": sender_email,
                "subject": subject,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "attachment_path": attachment_path,
                "attachment_name": attachment_name,
                "processing_status": processing_status,
                "llm_result": json.dumps(llm_result) if isinstance(llm_result, dict) else llm_result,
                "reply_sent": reply_sent,
                "reply_sent_at": datetime.now(timezone.utc) if reply_sent else None,
            }
        )
        db.commit()

    def _get_db(self):
        from database import SessionLocal
        return SessionLocal()


def get_worker_status() -> dict:
    return dict(_WORKER_STATUS)


def start_email_inbox_worker() -> None:
    """Da chiamare in startup_event se GMAIL_IMAP_USER è configurato."""
    imap_user = os.getenv("GMAIL_IMAP_USER", "")
    if not imap_user:
        logger.info("EmailInboxWorker: GMAIL_IMAP_USER non configurato, worker non avviato")
        return
    worker = EmailInboxWorker()
    worker.start_background()


def _extract_address(from_header: str) -> str:
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


def _find_unsupported_meaningful_attachment(msg: Message) -> Optional[tuple[str, str]]:
    from services.attachment_handler import ALLOWED_CONTENT_TYPES, _should_skip_part

    for part in msg.walk():
        disposition = (part.get_content_disposition() or "").lower()
        content_type = (part.get_content_type() or "").lower()
        filename = part.get_filename() or "allegato"
        if _should_skip_part(disposition, content_type, part.get_filename(), part):
            continue
        if content_type not in ALLOWED_CONTENT_TYPES:
            return filename, content_type
    return None


def _apply_body_extracted_data(db, *, entity_type: Optional[str], entity_id: Optional[int], extracted_data: dict) -> list[str]:
    if entity_type != "collaborator" or not entity_id or not extracted_data:
        return []

    import models

    collaborator = db.query(models.Collaborator).filter(models.Collaborator.id == entity_id).first()
    if not collaborator:
        return []

    updated: list[str] = []

    partita_iva = _normalize_vat(extracted_data.get("partita_iva"))
    if partita_iva and not collaborator.partita_iva:
        conflict = (
            db.query(models.Collaborator)
            .filter(models.Collaborator.partita_iva == partita_iva, models.Collaborator.id != entity_id)
            .first()
        )
        if conflict:
            logger.warning("EmailInboxWorker: partita IVA %s gia presente su collaborator %s, skip", partita_iva, conflict.id)
        else:
            collaborator.partita_iva = partita_iva
            updated.append("partita_iva")

    fiscal_code = _normalize_fiscal_code(extracted_data.get("codice_fiscale") or extracted_data.get("fiscal_code"))
    if fiscal_code and not collaborator.fiscal_code:
        collaborator.fiscal_code = fiscal_code
        updated.append("fiscal_code")

    phone = _normalize_phone(extracted_data.get("phone") or extracted_data.get("telefono"))
    if phone and not collaborator.phone:
        collaborator.phone = phone
        updated.append("phone")

    if updated:
        db.add(collaborator)
        db.commit()
    return updated


def _normalize_vat(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    digits = "".join(ch for ch in str(value).upper().replace("IT", "") if ch.isdigit())
    return digits if len(digits) == 11 else None


def _normalize_fiscal_code(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    normalized = str(value).replace(" ", "").upper()
    return normalized if len(normalized) == 16 else None


def _normalize_phone(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    raw = str(value).strip()
    prefix = "+39" if raw.startswith("+39") else ""
    digits = "".join(ch for ch in raw if ch.isdigit())
    if prefix and digits.startswith("39"):
        digits = digits[2:]
    if len(digits) < 8 or len(digits) > 11:
        return None
    return f"{prefix}{digits}" if prefix else digits


def _get_entity_name(db, entity_type: Optional[str], entity_id: Optional[int]) -> str:
    if not entity_type or not entity_id:
        return ""
    from sqlalchemy import text
    try:
        if entity_type == "collaborator":
            row = db.execute(
                text("SELECT first_name, last_name FROM collaborators WHERE id = :id LIMIT 1"),
                {"id": entity_id}
            ).fetchone()
            if row:
                return f"{row[0] or ''} {row[1] or ''}".strip()
        elif entity_type == "azienda_cliente":
            row = db.execute(
                text("SELECT ragione_sociale FROM aziende_clienti WHERE id = :id LIMIT 1"),
                {"id": entity_id}
            ).fetchone()
            if row:
                return row[0] or ""
        elif entity_type == "allievo":
            row = db.execute(
                text("SELECT first_name FROM allievi WHERE id = :id LIMIT 1"),
                {"id": entity_id}
            ).fetchone()
            if row:
                return row[0] or ""
    except Exception:
        pass
    return ""
