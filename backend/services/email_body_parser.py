"""Parsing conservativo del testo delle risposte email."""
from __future__ import annotations

import re
from email.message import Message
from html import unescape
from typing import Any, Dict, Optional


VAT_KEYWORD_RE = re.compile(r"\b(?:partita\s*iva|p\.?\s*iva|piva)\b[\s:=-]*(?:IT\s*)?([0-9][0-9\s.\-]{9,18}[0-9])", re.IGNORECASE)
FISCAL_CODE_RE = re.compile(r"\b[A-Z]{6}[0-9]{2}[A-Z][0-9]{2}[A-Z][0-9]{3}[A-Z]\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\d)(?:\+39\s*)?(?:0\d{1,3}[\s./-]?\d{5,8}|3\d{2}[\s./-]?\d{6,7})(?!\d)")


def extract_email_body_text(msg: Message) -> str:
    """Restituisce il body testuale preferendo text/plain e ignorando allegati."""
    plain_parts: list[str] = []
    html_parts: list[str] = []

    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        if part.get_content_disposition() == "attachment":
            continue

        content_type = (part.get_content_type() or "").lower()
        if content_type not in {"text/plain", "text/html"}:
            continue

        payload = part.get_payload(decode=True)
        if payload is None:
            continue
        charset = part.get_content_charset() or "utf-8"
        text = payload.decode(charset, errors="replace").strip()
        if not text:
            continue
        if content_type == "text/plain":
            plain_parts.append(text)
        else:
            html_parts.append(_html_to_text(text))

    return "\n".join(plain_parts or html_parts).strip()


def extract_structured_contact_data(body_text: str) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    if not body_text:
        return data

    vat = _extract_vat_number(body_text)
    if vat:
        data["partita_iva"] = vat

    fiscal_code = _extract_fiscal_code(body_text)
    if fiscal_code:
        data["codice_fiscale"] = fiscal_code

    phone = _extract_phone(_text_without_vat_fragments(body_text))
    if phone:
        data["phone"] = phone

    return data


def _extract_vat_number(text: str) -> Optional[str]:
    match = VAT_KEYWORD_RE.search(text)
    if not match:
        return None
    digits = re.sub(r"\D", "", match.group(1))
    if len(digits) == 11:
        return digits
    return None


def _extract_fiscal_code(text: str) -> Optional[str]:
    match = FISCAL_CODE_RE.search(text)
    return match.group(0).upper() if match else None


def _extract_phone(text: str) -> Optional[str]:
    match = PHONE_RE.search(text)
    if not match:
        return None
    raw = match.group(0).strip()
    prefix = "+39" if raw.startswith("+39") else ""
    digits = re.sub(r"\D", "", raw)
    if prefix and digits.startswith("39"):
        digits = digits[2:]
    if len(digits) < 8 or len(digits) > 11:
        return None
    return f"{prefix}{digits}" if prefix else digits


def _text_without_vat_fragments(text: str) -> str:
    return VAT_KEYWORD_RE.sub(" ", text)


def _html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    html = re.sub(r"(?i)<br\s*/?>", "\n", html)
    html = re.sub(r"(?i)</p>", "\n", html)
    return unescape(re.sub(r"<[^>]+>", " ", html))
