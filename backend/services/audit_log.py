import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

import models

PII_KEYS = {
    "nome", "cognome", "first_name", "last_name", "email", "phone", "telefono",
    "fiscal_code", "codice_fiscale", "cf", "address", "indirizzo", "birth_date",
    "data_nascita", "ip_address", "token", "password", "secret",
}


def hash_ip(ip_address: str | None) -> str | None:
    if not ip_address:
        return None
    return hashlib.sha256(ip_address.encode("utf-8")).hexdigest()


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if str(key).lower() in PII_KEYS:
                result[key] = "***REDACTED***"
            else:
                result[key] = _redact(item)
        return result
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def safe_json(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(_redact(value), ensure_ascii=False, default=str)


def write_audit_log(
    db: Session,
    *,
    user_id: int | None,
    azione: str,
    risorsa_tipo: str,
    risorsa_id: str | int | None = None,
    dati_prima: Any = None,
    dati_dopo: Any = None,
    ip_address: str | None = None,
    esito: str = "success",
) -> models.SecurityAuditLog:
    entry = models.SecurityAuditLog(
        user_id=user_id,
        azione=azione,
        risorsa_tipo=risorsa_tipo,
        risorsa_id=str(risorsa_id) if risorsa_id is not None else None,
        dati_prima=safe_json(dati_prima),
        dati_dopo=safe_json(dati_dopo),
        ip_address_hash=hash_ip(ip_address),
        esito=esito,
    )
    db.add(entry)
    db.flush()
    return entry
