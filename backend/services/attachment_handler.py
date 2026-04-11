"""Estrae e salva allegati da email in arrivo."""
from __future__ import annotations

import logging
import os
import re
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
                continue

            dest_dir = self.upload_base_dir
            if entity_type:
                dest_dir = dest_dir / entity_type
            if entity_id is not None:
                dest_dir = dest_dir / str(entity_id)
            # Sicurezza: verifica che il path rimanga dentro upload_base_dir
            resolved = dest_dir.resolve()
            base_resolved = self.upload_base_dir.resolve()
            if not str(resolved).startswith(str(base_resolved)):
                raise ValueError(f"entity_type '{entity_type}' causa path traversal")
            dest_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            safe_name = _sanitize_filename(filename)
            dest_path = dest_dir / f"{timestamp}_{safe_name}"

            dest_path.write_bytes(payload)
            logger.info("AttachmentHandler: salvato '%s' -> %s", filename, dest_path)
            logger.debug("AttachmentHandler: allegati successivi a '%s' ignorati (se presenti)", filename)
            return str(dest_path), filename

        return None


def _sanitize_filename(name: str) -> str:
    """Rimuove caratteri non sicuri dal nome file."""
    name = Path(name).name  # no directory traversal
    name = re.sub(r"[^\w.\-]", "_", name)
    return name[:200] or "attachment"
