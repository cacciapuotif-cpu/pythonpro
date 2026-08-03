"""Operazioni di dominio per le sedi di erogazione dei progetti."""

from sqlalchemy.orm import Session

import models
import schemas


def create_azienda_sede_operativa(
    db: Session,
    azienda_id: int,
    payload: schemas.AziendaClienteSedeOperativaWrite,
) -> models.AziendaClienteSedeOperativa:
    azienda = db.query(models.AziendaCliente).filter(models.AziendaCliente.id == azienda_id).first()
    if not azienda:
        raise LookupError("Azienda cliente non trovata")

    normalized_name = payload.nome.strip()
    duplicate = db.query(models.AziendaClienteSedeOperativa).filter(
        models.AziendaClienteSedeOperativa.azienda_cliente_id == azienda_id,
        models.AziendaClienteSedeOperativa.nome.ilike(normalized_name),
    ).first()
    if duplicate:
        raise ValueError(f"Esiste gia' una sede '{normalized_name}' per questa azienda")

    data = payload.model_dump(exclude={"id"})
    data["nome"] = normalized_name
    sede = models.AziendaClienteSedeOperativa(azienda_cliente_id=azienda_id, **data)
    db.add(sede)
    db.commit()
    db.refresh(sede)
    return sede


def resolve_attendance_delivery_sede(
    db: Session,
    project_id: int,
    delivery_sede_id: int | None,
) -> models.AziendaClienteProjectDeliverySede | None:
    """Risolve la sede di una presenza senza permettere sedi di altri progetti."""
    query = db.query(models.AziendaClienteProjectDeliverySede).join(
        models.AziendaClienteProjectLink,
        models.AziendaClienteProjectLink.id == models.AziendaClienteProjectDeliverySede.azienda_project_link_id,
    ).filter(models.AziendaClienteProjectLink.project_id == project_id)
    if delivery_sede_id is not None:
        row = query.filter(models.AziendaClienteProjectDeliverySede.id == delivery_sede_id).first()
        if not row:
            raise ValueError("La sede di erogazione scelta non appartiene a questo progetto")
        return row

    rows = query.order_by(models.AziendaClienteProjectDeliverySede.id).limit(2).all()
    if len(rows) == 1:
        return rows[0]
    if len(rows) > 1:
        raise ValueError("Seleziona la sede di erogazione: il progetto ha piu' sedi disponibili")
    return None
