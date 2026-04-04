from __future__ import annotations

from typing import Any, Optional

import models


def _build_suggestion(
    *,
    entity_type: str,
    entity_id: Optional[int],
    suggestion_type: str,
    severity: str,
    title: str,
    description: str,
    payload: Optional[dict[str, Any]] = None,
    confidence: float = 0.9,
) -> dict[str, Any]:
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "suggestion_type": suggestion_type,
        "severity": severity,
        "title": title,
        "description": description,
        "payload": payload or {},
        "confidence": confidence,
    }


def _analyze_project(project: models.Project) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    missing_fields = []
    if not project.description:
        missing_fields.append("description")
    if not project.atto_approvazione:
        missing_fields.append("atto_approvazione")
    if not project.ente_attuatore_id:
        missing_fields.append("ente_attuatore_id")
    if not project.ente_erogatore:
        missing_fields.append("ente_erogatore")
    if not (project.avviso_id or project.avviso):
        missing_fields.append("avviso")

    if missing_fields:
        suggestions.append(_build_suggestion(
            entity_type="project",
            entity_id=project.id,
            suggestion_type="missing_fields",
            severity="high",
            title=f"Progetto #{project.id} con campi delivery incompleti",
            description=(
                f"Il progetto \"{project.name}\" ha campi incompleti che limitano contratti, piani "
                f"o reporting: {', '.join(missing_fields)}."
            ),
            payload={"missing_fields": missing_fields, "project_name": project.name},
            confidence=0.98,
        ))

    if project.start_date and project.end_date and project.end_date < project.start_date:
        suggestions.append(_build_suggestion(
            entity_type="project",
            entity_id=project.id,
            suggestion_type="date_range_invalid",
            severity="high",
            title=f"Date incoerenti sul progetto #{project.id}",
            description=f"Il progetto \"{project.name}\" ha una data fine precedente alla data inizio.",
            payload={"start_date": str(project.start_date), "end_date": str(project.end_date)},
            confidence=0.99,
        ))

    if project.ente_erogatore and not project.template_piano_finanziario_id:
        suggestions.append(_build_suggestion(
            entity_type="project",
            entity_id=project.id,
            suggestion_type="missing_financial_template",
            severity="medium",
            title=f"Progetto #{project.id} senza template piano collegato",
            description=(
                f"Il progetto \"{project.name}\" ha ente erogatore valorizzato ma non ha un "
                "template piano finanziario associato."
            ),
            payload={"ente_erogatore": project.ente_erogatore},
            confidence=0.9,
        ))

    return suggestions


def _analyze_collaborator(collaborator: models.Collaborator) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    missing_fields = []
    if not collaborator.phone:
        missing_fields.append("phone")
    if not collaborator.city:
        missing_fields.append("city")
    if not collaborator.address:
        missing_fields.append("address")
    if not collaborator.profilo_professionale:
        missing_fields.append("profilo_professionale")

    if missing_fields:
        suggestions.append(_build_suggestion(
            entity_type="collaborator",
            entity_id=collaborator.id,
            suggestion_type="profile_incomplete",
            severity="medium",
            title=f"Collaboratore #{collaborator.id} con profilo incompleto",
            description=(
                f"{collaborator.full_name} ha campi anagrafici/professionali mancanti: "
                f"{', '.join(missing_fields)}."
            ),
            payload={"missing_fields": missing_fields, "full_name": collaborator.full_name},
            confidence=0.92,
        ))

    if not collaborator.documento_identita_path or not collaborator.documento_identita_scadenza:
        suggestions.append(_build_suggestion(
            entity_type="collaborator",
            entity_id=collaborator.id,
            suggestion_type="missing_identity_document",
            severity="high",
            title=f"Documento identita incompleto per collaboratore #{collaborator.id}",
            description=(
                f"{collaborator.full_name} non ha documento di identita completo o con scadenza registrata."
            ),
            payload={
                "has_document": bool(collaborator.documento_identita_path),
                "has_expiry_date": bool(collaborator.documento_identita_scadenza),
            },
            confidence=0.97,
        ))

    if not collaborator.curriculum_path:
        suggestions.append(_build_suggestion(
            entity_type="collaborator",
            entity_id=collaborator.id,
            suggestion_type="missing_curriculum",
            severity="medium",
            title=f"Curriculum mancante per collaboratore #{collaborator.id}",
            description=f"{collaborator.full_name} non ha un curriculum caricato.",
            payload={"full_name": collaborator.full_name},
            confidence=0.88,
        ))

    return suggestions


def _analyze_azienda(azienda: models.AziendaCliente) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    missing_fields = []
    if not azienda.partita_iva:
        missing_fields.append("partita_iva")
    if not azienda.indirizzo:
        missing_fields.append("indirizzo")
    if not azienda.citta:
        missing_fields.append("citta")
    if not azienda.pec:
        missing_fields.append("pec")

    if missing_fields:
        suggestions.append(_build_suggestion(
            entity_type="azienda_cliente",
            entity_id=azienda.id,
            suggestion_type="company_registry_incomplete",
            severity="high",
            title=f"Azienda #{azienda.id} con anagrafica incompleta",
            description=(
                f"L'azienda \"{azienda.ragione_sociale}\" ha dati amministrativi incompleti: "
                f"{', '.join(missing_fields)}."
            ),
            payload={"missing_fields": missing_fields, "ragione_sociale": azienda.ragione_sociale},
            confidence=0.96,
        ))

    if not azienda.referente_nome or not azienda.referente_email:
        suggestions.append(_build_suggestion(
            entity_type="azienda_cliente",
            entity_id=azienda.id,
            suggestion_type="missing_primary_contact",
            severity="medium",
            title=f"Referente operativo mancante per azienda #{azienda.id}",
            description=(
                f"L'azienda \"{azienda.ragione_sociale}\" non ha un referente principale completo "
                "per contatti operativi."
            ),
            payload={
                "has_referente_nome": bool(azienda.referente_nome),
                "has_referente_email": bool(azienda.referente_email),
            },
            confidence=0.9,
        ))

    return suggestions


def run_data_quality_agent(db, *, entity_type: Optional[str] = None, entity_id: Optional[int] = None, limit: int = 25) -> dict[str, Any]:
    suggestions: list[dict[str, Any]] = []
    normalized_entity_type = (entity_type or "").strip().lower() or None

    if normalized_entity_type in (None, "project", "projects"):
        query = db.query(models.Project).filter(models.Project.is_active == True).order_by(models.Project.id.desc())
        if entity_id is not None:
            query = query.filter(models.Project.id == entity_id)
        else:
            query = query.limit(limit)
        for project in query.all():
            suggestions.extend(_analyze_project(project))

    if normalized_entity_type in (None, "collaborator", "collaborators"):
        query = db.query(models.Collaborator).filter(models.Collaborator.is_active == True).order_by(models.Collaborator.id.desc())
        if entity_id is not None and normalized_entity_type in ("collaborator", "collaborators"):
            query = query.filter(models.Collaborator.id == entity_id)
        elif normalized_entity_type is None:
            query = query.limit(limit)
        for collaborator in query.all():
            suggestions.extend(_analyze_collaborator(collaborator))

    if normalized_entity_type in (None, "azienda_cliente", "aziende_clienti", "company"):
        query = db.query(models.AziendaCliente).filter(models.AziendaCliente.attivo == True).order_by(models.AziendaCliente.id.desc())
        if entity_id is not None and normalized_entity_type in ("azienda_cliente", "aziende_clienti", "company"):
            query = query.filter(models.AziendaCliente.id == entity_id)
        elif normalized_entity_type is None:
            query = query.limit(limit)
        for azienda in query.all():
            suggestions.extend(_analyze_azienda(azienda))

    summary = {
        "checked_entity_type": normalized_entity_type or "global",
        "checked_entity_id": entity_id,
        "suggestions_found": len(suggestions),
        "high_severity": sum(1 for item in suggestions if item["severity"] == "high"),
    }
    return {"summary": summary, "suggestions": suggestions}
