"""
Agente Contract Generator.
Monitora le pratiche documentali completate e propone bozze contratto
quando tutti i documenti obbligatori sono validati.

Il collector NON scrive su DB: ritorna {"summary", "suggestions"} e la
persistenza (AgentRun + AgentSuggestion) avviene solo dentro
`agent_workflows.run_agent_workflow`.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import models
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

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


def collect_contract_suggestions(
    db: Session,
    *,
    project_id: Optional[int] = None,
    assignment_id: Optional[int] = None,
    collaborator_id: Optional[int] = None,
) -> dict[str, Any]:
    """
    Scansiona gli assignment con documenti completi e propone suggerimenti contratto.
    """
    query = db.query(models.Assignment).filter(
        models.Assignment.is_active == True,
    )
    if project_id:
        query = query.filter(models.Assignment.project_id == project_id)
    if assignment_id:
        query = query.filter(models.Assignment.id == assignment_id)
    if collaborator_id:
        query = query.filter(models.Assignment.collaborator_id == collaborator_id)

    assignments = query.all()

    suggestions: list[dict[str, Any]] = []
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

        suggestions.append({
            "entity_type": "assignment",
            "entity_id": assignment.id,
            "suggestion_type": "contract_ready",
            "severity": "medium",
            "title": "Bozza contratto pronta — {}".format(nome_collab),
            "description": (
                "Tutti i documenti obbligatori di {} sono validati. "
                "Il contratto {} per il progetto {} può essere generato."
            ).format(
                nome_collab,
                assignment.contract_type or "professionale",
                project.name if project else assignment.project_id,
            ),
            "confidence": 0.95,
            "payload": {
                "assignment_id": assignment.id,
                "collaborator_id": assignment.collaborator_id,
                "collaborator_name": nome_collab,
                "project_id": assignment.project_id,
                "project_name": project.name if project else None,
                "contract_type": assignment.contract_type,
                "role": assignment.role,
                "generate_url": "/api/v1/assignments/{}/contract".format(assignment.id),
            },
        })
        logger.info(
            "ContractAgent: bozza contratto pronta per assignment %s — %s",
            assignment.id, nome_collab
        )

    summary = {
        "assignments_scansionati": len(assignments),
        "suggerimenti_creati": len(suggestions),
        "gia_pronti": gia_pronti,
        "documenti_incompleti": documenti_incompleti,
    }
    return {"summary": summary, "suggestions": suggestions}
