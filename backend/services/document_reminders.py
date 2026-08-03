"""Invio server-side dei solleciti per i documenti collaboratore."""

from __future__ import annotations

import os
from collections import defaultdict
from datetime import date, datetime
from urllib.parse import urlsplit

from services.email_sender import EmailSender


REMINDABLE_STATES = {"richiesto", "scaduto"}


def _format_deadline(value: date | datetime | None) -> str:
    if value is None:
        return "Senza scadenza"
    return value.strftime("%d/%m/%Y")


def _public_app_base_url() -> str:
    configured = os.getenv("DOCUMENT_UPLOAD_URL_BASE", "").strip().rstrip("/")
    if configured:
        parsed = urlsplit(configured)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            return configured
        raise RuntimeError("DOCUMENT_UPLOAD_URL_BASE non configurato correttamente")

    reset_url = os.getenv("PASSWORD_RESET_URL_BASE", "").strip()
    parsed = urlsplit(reset_url)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    raise RuntimeError("URL pubblico dell'applicazione non configurato")


def build_document_upload_url(collaborator_id: int) -> str:
    return f"{_public_app_base_url()}/collaborators/{collaborator_id}/documents"


def send_document_reminders(documents, *, email_sender: EmailSender | None = None) -> dict:
    """Invia una sola email per collaboratore e restituisce esiti senza PII."""

    grouped = defaultdict(list)
    for document in documents:
        grouped[document.collaboratore_id].append(document)

    sender = email_sender or EmailSender()
    results = []
    for collaborator_id, collaborator_documents in grouped.items():
        collaborator = collaborator_documents[0].collaboratore
        email = (getattr(collaborator, "email", None) or "").strip()
        if not email:
            results.append({
                "collaboratore_id": collaborator_id,
                "sent": False,
                "detail": "Email del collaboratore non disponibile",
            })
            continue

        full_name = (getattr(collaborator, "full_name", None) or "Collaboratore").strip()
        context = {
            "subject": "Sollecito caricamento documenti",
            "collaboratore_nome": full_name,
            "documenti": [
                {
                    "nome": document.tipo_documento,
                    "scadenza": _format_deadline(document.data_scadenza),
                }
                for document in collaborator_documents
            ],
            "link_upload": build_document_upload_url(collaborator_id),
        }
        sent = sender.send_template_email(
            to=email,
            template_name="sollecito_documento",
            context=context,
        )
        results.append({
            "collaboratore_id": collaborator_id,
            "sent": bool(sent),
            "detail": "Sollecito inviato" if sent else "Invio email non riuscito",
        })

    sent_count = sum(1 for result in results if result["sent"])
    return {
        "sent_count": sent_count,
        "failed_count": len(results) - sent_count,
        "results": results,
    }
