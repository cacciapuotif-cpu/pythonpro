import hashlib
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

import models
from services.audit_log import write_audit_log


def hash_value(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def export_collaborator_data(db: Session, collaboratore: models.Collaborator) -> dict[str, Any]:
    return {
        "id": collaboratore.id,
        "first_name": collaboratore.first_name,
        "last_name": collaboratore.last_name,
        "email": collaboratore.email,
        "phone": collaboratore.phone,
        "fiscal_code": collaboratore.fiscal_code,
        "city": collaboratore.city,
        "address": collaboratore.address,
        "consensi": [
            {
                "tipo_consenso": c.tipo_consenso,
                "data_consenso": c.data_consenso,
                "revocato": c.revocato,
                "data_revoca": c.data_revoca,
            }
            for c in db.query(models.GDPRConsenso).filter(models.GDPRConsenso.collaboratore_id == collaboratore.id).all()
        ],
    }


def anonymize_collaborator(db: Session, collaboratore: models.Collaborator, *, user_id: int | None, ip_address: str | None = None) -> models.Collaborator:
    before = {"id": collaboratore.id, "anonimizzato": collaboratore.anonimizzato}
    suffix = hash_value(f"collaborator:{collaboratore.id}:{collaboratore.fiscal_code}")[:12]
    collaboratore.first_name = f"anon_{suffix}"
    collaboratore.last_name = f"anon_{suffix}"
    collaboratore.fiscal_code = hash_value(collaboratore.fiscal_code)[:16].upper()
    collaboratore.email = f"anon_{suffix}@anon.local"
    collaboratore.phone = None
    collaboratore.address = None
    collaboratore.city = None
    collaboratore.anonimizzato = True
    collaboratore.data_anonimizzazione = datetime.now(timezone.utc)
    write_audit_log(
        db, user_id=user_id, azione="gdpr_anonimizza", risorsa_tipo="collaborator",
        risorsa_id=collaboratore.id, dati_prima=before, dati_dopo={"id": collaboratore.id, "anonimizzato": True},
        ip_address=ip_address, esito="success"
    )
    return collaboratore
