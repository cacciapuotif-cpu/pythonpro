"""Genera e invia la risposta automatica per documenti non validi."""
from __future__ import annotations

import logging
from typing import List

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
