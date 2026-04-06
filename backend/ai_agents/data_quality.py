from __future__ import annotations

import re
from datetime import datetime, timedelta

from sqlalchemy import func

import models
from .registry import BaseAgent, AgentRunResult, agent_registry


_FISCAL_CODE_PATTERN = re.compile(r"^(?:[A-Z0-9]{16}|\d{11})$")


class DataQualityAgent(BaseAgent):
    agent_type = "data_quality"
    version = "1.0"
    description = "Verifica completezza e coerenza dati anagrafici"

    def run(self, db) -> AgentRunResult:
        suggestions = []
        processed_items = 0

        collaborators = (
            db.query(models.Collaborator)
            .filter(models.Collaborator.is_active == True)
            .all()
        )
        processed_items += len(collaborators)

        for collaborator in collaborators:
            missing_documents = []
            if not (collaborator.documento_identita_path or collaborator.documento_identita_filename):
                missing_documents.append("Documento identita")
            if not (collaborator.curriculum_path or collaborator.curriculum_filename):
                missing_documents.append("Curriculum")

            if missing_documents:
                suggestions.append({
                    "suggestion_type": "missing_data",
                    "priority": "high",
                    "entity_type": "collaborator",
                    "entity_id": collaborator.id,
                    "title": f"Documenti obbligatori mancanti per {collaborator.full_name}",
                    "description": f"Documenti mancanti: {', '.join(missing_documents)}.",
                    "suggested_action": "Richiedere e caricare i documenti obbligatori mancanti del collaboratore.",
                    "confidence_score": 0.98,
                    "auto_fix_available": False,
                })

            missing_fields = []
            fiscal_code = (collaborator.fiscal_code or "").strip().upper()
            if not fiscal_code or not _FISCAL_CODE_PATTERN.match(fiscal_code):
                missing_fields.append("codice fiscale")
            if not collaborator.birth_date:
                missing_fields.append("data di nascita")
            if not (collaborator.address or "").strip():
                missing_fields.append("indirizzo")

            if missing_fields:
                suggestions.append({
                    "suggestion_type": "missing_data",
                    "priority": "medium",
                    "entity_type": "collaborator",
                    "entity_id": collaborator.id,
                    "title": f"Dati anagrafici incompleti per {collaborator.full_name}",
                    "description": f"Campi mancanti o non validi: {', '.join(missing_fields)}.",
                    "suggested_action": "Completare i dati anagrafici obbligatori del collaboratore.",
                    "confidence_score": 0.93,
                    "auto_fix_available": False,
                })

        threshold_date = datetime.now() - timedelta(days=7)
        assignments_without_hours = (
            db.query(models.Assignment)
            .options()
            .filter(
                models.Assignment.is_active == True,
                models.Assignment.start_date < threshold_date,
                func.coalesce(models.Assignment.completed_hours, 0.0) == 0.0,
            )
            .all()
        )
        processed_items += len(assignments_without_hours)

        for assignment in assignments_without_hours:
            suggestions.append({
                "suggestion_type": "warning",
                "priority": "low",
                "entity_type": "assignment",
                "entity_id": assignment.id,
                "title": f"Assegnazione senza presenze registrate: {assignment.role}",
                "description": (
                    f"Assegnazione attiva iniziata il {assignment.start_date:%d/%m/%Y} "
                    "con 0 ore completate da oltre 7 giorni."
                ),
                "suggested_action": "Verificare l'avvio operativo dell'assegnazione o registrare le presenze mancanti.",
                "confidence_score": 0.88,
                "auto_fix_available": False,
            })

        active_project_ids_subquery = (
            db.query(models.Assignment.project_id)
            .filter(models.Assignment.is_active == True)
            .distinct()
            .subquery()
        )
        orphan_attendances = (
            db.query(models.Attendance)
            .filter(
                models.Attendance.assignment_id.is_(None),
                models.Attendance.project_id.in_(active_project_ids_subquery),
            )
            .all()
        )
        processed_items += len(orphan_attendances)

        for attendance in orphan_attendances:
            suggestions.append({
                "suggestion_type": "inconsistency",
                "priority": "low",
                "entity_type": "attendance",
                "entity_id": attendance.id,
                "title": "Presenza orfana senza assegnazione collegata",
                "description": (
                    f"Presenza del {attendance.date:%d/%m/%Y} sul progetto {attendance.project_id} "
                    "senza assignment_id, nonostante il progetto abbia assegnazioni attive."
                ),
                "suggested_action": "Collegare la presenza all'assegnazione corretta o verificare il dato inserito.",
                "confidence_score": 0.9,
                "auto_fix_available": False,
            })

        return AgentRunResult(
            items_processed=processed_items,
            items_with_issues=len(suggestions),
            suggestions=suggestions,
            error=None,
        )


agent_registry.register(DataQualityAgent())
