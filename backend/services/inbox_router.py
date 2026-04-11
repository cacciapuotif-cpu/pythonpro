"""Abbina il mittente email a un'entità nel DB (collaborator o allievo)."""
from __future__ import annotations

import logging
from typing import Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class InboxRouter:
    def __init__(self, db: Session) -> None:
        self.db = db

    def route(self, sender_email: str) -> Tuple[Optional[str], Optional[int]]:
        """
        Cerca sender_email (case-insensitive) in collaborators, allievi e aziende clienti.
        Ritorna ('collaborator', id), ('allievo', id), ('azienda_cliente', id) o (None, None).
        """
        normalized = sender_email.strip().lower()

        # Cerca nei collaboratori
        try:
            row = self.db.execute(
                text("SELECT id FROM collaborators WHERE lower(email) = :email AND is_active = true LIMIT 1"),
                {"email": normalized}
            ).fetchone()
            if row:
                logger.debug("InboxRouter: %s -> collaborator %s", sender_email, row[0])
                return "collaborator", row[0]
        except Exception as exc:
            logger.warning("InboxRouter: query collaborators fallita: %s", exc)

        # Cerca negli allievi
        try:
            row = self.db.execute(
                text("SELECT id FROM allievi WHERE lower(email) = :email AND is_active = true LIMIT 1"),
                {"email": normalized}
            ).fetchone()
            if row:
                logger.debug("InboxRouter: %s -> allievo %s", sender_email, row[0])
                return "allievo", row[0]
        except Exception as exc:
            logger.warning("InboxRouter: query allievi fallita: %s", exc)

        # Cerca nelle aziende clienti
        try:
            row = self.db.execute(
                text(
                    """
                    SELECT id
                    FROM aziende_clienti
                    WHERE attivo = true
                      AND (
                        lower(email) = :email
                        OR lower(pec) = :email
                        OR lower(referente_email) = :email
                        OR lower(legale_rappresentante_email) = :email
                      )
                    LIMIT 1
                    """
                ),
                {"email": normalized}
            ).fetchone()
            if row:
                logger.debug("InboxRouter: %s -> azienda_cliente %s", sender_email, row[0])
                return "azienda_cliente", row[0]
        except Exception as exc:
            logger.warning("InboxRouter: query aziende_clienti fallita: %s", exc)

        logger.info("InboxRouter: mittente sconosciuto %s, ignorato", sender_email)
        return None, None
