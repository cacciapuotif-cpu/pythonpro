"""
Agente Contract Generator.
Monitora le pratiche documentali completate e genera bozze contratto
quando tutti i documenti obbligatori sono validati.
"""
from __future__ import annotations

from time_utils import utc_now
import logging
import json
from datetime import datetime
from typing import Any, Optional

import models
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

DOCUMENTI_OBBLIGATORI_DEFAULT = {"curriculum", "documento_identita"}


def _pratica_completa(db: Session, collaboratore_id: int) -> bool:
    """
    Verifica se tutti i documenti obbligatori del collaboratore sono validati.
    """
    richieste = db.query(models.DocumentoRichiesto).filter(
        models.DocumentoRichiesto.collaboratore_id == collaboratore_id,
        models.DocumentoRichiesto.obbligatorio == True,
    ).all()

    if not richieste:
        return False

    tipi_validati = {r.tipo_documento for r in richieste if r.stato == "validato"}
    tipi_obbligatori = {r.tipo_documento for r in richieste}

    return tipi_obbligatori.issubset(tipi_validati)


def _contratto_gia_generato(db: Session, assignment_id: int) -> bool:
    """Verifica se esiste già una suggestion di contratto pending per questo assignment."""
    existing = db.query(models.AgentSuggestion).filter(
        models.AgentSuggestion.entity_type == "assignment",
        models.AgentSuggestion.entity_id == assignment_id,
        models.AgentSuggestion.suggestion_type == "contract_ready",
        models.AgentSuggestion.status == "pending",
    ).first()
    return existing is not None


def run_contract_agent(
    db: Session,
    *,
    project_id: Optional[int] = None,
    assignment_id: Optional[int] = None,
) -> dict[str, Any]:
    """
    Scansiona gli assignment con documenti completi e genera suggerimenti contratto.
    """
    run = models.AgentRun(
        agent_type="contract_agent",
        status="running",
        triggered_by="document_validation" if assignment_id else "scheduled",
        entity_type="assignment" if assignment_id else ("project" if project_id else None),
        entity_id=assignment_id or project_id,
        started_at=utc_now(),
    )
    db.add(run)
    db.flush()

    query = db.query(models.Assignment).filter(
        models.Assignment.is_active == True,
    )
    if project_id:
        query = query.filter(models.Assignment.project_id == project_id)
    if assignment_id:
        query = query.filter(models.Assignment.id == assignment_id)

    assignments = query.all()

    suggerimenti_creati = 0
    gia_pronti = 0
    documenti_incompleti = 0

    for assignment in assignments:
        if _contratto_gia_generato(db, assignment.id):
            gia_pronti += 1
            continue

        if not _pratica_completa(db, assignment.collaborator_id):
            documenti_incompleti += 1
            continue

        collaboratore = db.query(models.Collaborator).filter(
            models.Collaborator.id == assignment.collaborator_id
        ).first()
        if not collaboratore:
            continue

        project = db.query(models.Project).filter(
            models.Project.id == assignment.project_id
        ).first()

        nome_collab = "{} {}".format(
            collaboratore.first_name or "",
            collaboratore.last_name or ""
        ).strip()

        suggestion = models.AgentSuggestion(
            run_id=run.id,
            entity_type="assignment",
            entity_id=assignment.id,
            suggestion_type="contract_ready",
            severity="medium",
            status="pending",
            title="Bozza contratto pronta — {}".format(nome_collab),
            description=(
                "Tutti i documenti obbligatori di {} sono validati. "
                "Il contratto {} per il progetto {} può essere generato."
            ).format(
                nome_collab,
                assignment.contract_type or "professionale",
                project.name if project else assignment.project_id,
            ),
            confidence=0.95,
            payload=json.dumps({
                "assignment_id": assignment.id,
                "collaborator_id": assignment.collaborator_id,
                "collaborator_name": nome_collab,
                "project_id": assignment.project_id,
                "project_name": project.name if project else None,
                "contract_type": assignment.contract_type,
                "role": assignment.role,
                "generate_url": "/api/v1/assignments/{}/contract".format(assignment.id),
            }, ensure_ascii=True),
            created_at=utc_now(),
        )
        db.add(suggestion)
        suggerimenti_creati += 1
        logger.info(
            "ContractAgent: bozza contratto pronta per assignment %s — %s",
            assignment.id, nome_collab
        )

    run.status = "completed"
    run.completed_at = utc_now()
    run.items_processed = len(assignments)
    run.items_with_issues = documenti_incompleti
    run.suggestions_created = suggerimenti_creati
    run.suggestions_count = suggerimenti_creati
    run.result_summary = json.dumps({
        "assignments_scansionati": len(assignments),
        "suggerimenti_creati": suggerimenti_creati,
        "gia_pronti": gia_pronti,
        "documenti_incompleti": documenti_incompleti,
    }, ensure_ascii=True)
    db.add(run)
    db.commit()

    return {
        "assignments_scansionati": len(assignments),
        "suggerimenti_creati": suggerimenti_creati,
        "gia_pronti": gia_pronti,
        "documenti_incompleti": documenti_incompleti,
    }


def run_contract_agent_for_collaborator(db: Session, collaborator_id: int) -> dict[str, Any]:
    """Esegue il contract agent solo sugli assignment attivi di un collaboratore."""
    assignments = db.query(models.Assignment).filter(
        models.Assignment.collaborator_id == collaborator_id,
        models.Assignment.is_active == True,
    ).all()
    totals = {
        "assignments_scansionati": 0,
        "suggerimenti_creati": 0,
        "gia_pronti": 0,
        "documenti_incompleti": 0,
    }
    for assignment in assignments:
        result = run_contract_agent(db, assignment_id=assignment.id)
        for key in totals:
            totals[key] += int(result.get(key, 0) or 0)
    logger.info("ContractAgent: trigger collaboratore %s -> %s", collaborator_id, totals)
    return totals
