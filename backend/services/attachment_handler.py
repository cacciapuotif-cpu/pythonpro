"""Estrae e salva allegati da email in arrivo."""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from email.message import Message
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

DEFAULT_MAX_BYTES = int(os.getenv("MAX_ATTACHMENT_MB", "10")) * 1024 * 1024
_DEFAULT_UPLOAD_BASE = Path(os.getenv("UPLOAD_BASE_DIR", "uploads")) / "email_inbox"
INLINE_IMAGE_MAX_BYTES = 50 * 1024
PREFERRED_CONTENT_TYPES = {
    "application/pdf": 30,
    "application/msword": 20,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": 20,
}

FILE_SIGNATURES = {
    "application/pdf": (b"%PDF-",),
    "application/msword": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),
}


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
        Scansiona msg alla ricerca del miglior allegato valido.
        Restituisce (path_assoluto, nome_file_originale) o None.
        """
        best_candidate: Optional[tuple[int, int, str, bytes, str]] = None

        for part in msg.walk():
            disposition = (part.get_content_disposition() or "").lower()
            content_type = (part.get_content_type() or "").lower()
            filename = part.get_filename()

            if _should_skip_part(disposition, content_type, filename, part):
                continue

            if not filename:
                continue

            if content_type not in ALLOWED_CONTENT_TYPES:
                logger.info("AttachmentHandler: tipo %s non supportato, skip", content_type)
                continue

            payload = part.get_payload(decode=True)
            if payload is None:
                continue

            if not _has_valid_magic_bytes(content_type, payload):
                logger.warning("AttachmentHandler: allegato '%s' non corrisponde ai magic bytes attesi, skip", filename)
                continue

            if len(payload) > self.max_bytes:
                logger.warning(
                    "AttachmentHandler: allegato '%s' supera %d bytes, skip",
                    filename, self.max_bytes,
                )
                continue

            score = PREFERRED_CONTENT_TYPES.get(content_type, 0)
            size = len(payload)
            if best_candidate is None or (score, size) > (best_candidate[0], best_candidate[1]):
                best_candidate = (score, size, filename, payload, content_type)

        if best_candidate:
            _, _, filename, payload, content_type = best_candidate
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

            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            safe_name = _sanitize_filename(filename)
            dest_path = dest_dir / f"{timestamp}_{safe_name}"

            dest_path.write_bytes(payload)
            logger.info("AttachmentHandler: salvato '%s' (%s, %d bytes) -> %s", filename, content_type, len(payload), dest_path)
            return str(dest_path), filename

        return None


def _has_valid_magic_bytes(content_type: str, payload: bytes) -> bool:
    signatures = FILE_SIGNATURES.get(content_type)
    if not signatures or not payload:
        return False
    return any(payload.startswith(signature) for signature in signatures)


def _sanitize_filename(name: str) -> str:
    """Rimuove caratteri non sicuri dal nome file."""
    name = Path(name).name  # no directory traversal
    name = re.sub(r"[^\w.\-]", "_", name)
    return name[:200] or "attachment"


def _should_skip_part(disposition: str, content_type: str, filename: Optional[str], part: Message) -> bool:
    if disposition not in {"attachment", "inline"}:
        return True

    payload = part.get_payload(decode=True) or b""
    if disposition == "inline" and not _has_meaningful_filename(filename):
        logger.info("AttachmentHandler: inline senza filename significativo, skip")
        return True

    if content_type.startswith("image/") and len(payload) < INLINE_IMAGE_MAX_BYTES:
        logger.info(
            "AttachmentHandler: inline/logo image '%s' sotto 50KB (%d bytes), skip",
            filename or "",
            len(payload),
        )
        return True

    return False


def _has_meaningful_filename(filename: Optional[str]) -> bool:
    if not filename:
        return False
    normalized = filename.strip().lower()
    if not normalized:
        return False
    if normalized.startswith("risorsa ") or normalized.startswith("image") or normalized.startswith("logo"):
        return False
    return Path(normalized).suffix.lower() in {".pdf", ".doc", ".docx"}
