"""Hard-delete controllato delle aziende clienti (solo amministratori)."""
from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

import models
from services.audit_log import write_audit_log


def build_azienda_deletion_impact(db: Session, azienda_id: int) -> dict | None:
    azienda = db.query(models.AziendaCliente).filter_by(id=azienda_id).first()
    if azienda is None:
        return None
    inspector = inspect(db.bind)
    links = []
    for table in inspector.get_table_names():
        for fk in inspector.get_foreign_keys(table):
            if fk.get("referred_table") != "aziende_clienti":
                continue
            for column, referred in zip(fk.get("constrained_columns", []), fk.get("referred_columns", [])):
                if referred != "id":
                    continue
                count = db.execute(
                    text(f'SELECT count(*) FROM "{table}" WHERE "{column}" = :id'),
                    {"id": azienda_id},
                ).scalar_one()
                if count:
                    links.append({"table": table, "column": column, "count": int(count)})
    phrase = f"ELIMINA {azienda.ragione_sociale}"
    return {
        "azienda_id": azienda.id,
        "ragione_sociale": azienda.ragione_sociale,
        "confirmation_phrase": phrase,
        "eliminabile": not links,
        "collegamenti": links,
    }


def permanently_delete_azienda(db: Session, azienda_id: int, *, user_id: int) -> dict | None:
    impact = build_azienda_deletion_impact(db, azienda_id)
    if impact is None:
        return None
    if not impact["eliminabile"]:
        return {"blocked": True, **impact}
    azienda = db.query(models.AziendaCliente).filter_by(id=azienda_id).one()
    try:
        closed = db.query(models.AgentSuggestion).filter(
            models.AgentSuggestion.entity_type == "azienda_cliente",
            models.AgentSuggestion.entity_id == azienda_id,
            models.AgentSuggestion.status == "pending",
        ).update({models.AgentSuggestion.status: "non_applicabile", models.AgentSuggestion.description: "Azienda eliminata definitivamente"}, synchronize_session=False)
        write_audit_log(db, user_id=user_id, azione="azienda_hard_delete", risorsa_tipo="azienda_cliente", risorsa_id=azienda_id, dati_prima=impact, dati_dopo={"deleted": True, "suggestions_closed": closed})
        db.delete(azienda)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"message": "Azienda eliminata definitivamente", "id": azienda_id, "suggestions_closed": closed, **impact}
