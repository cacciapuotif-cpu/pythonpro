"""
Agente Certification.
Verifica la frequenza degli allievi e propone l'emissione dell'attestato.
La soglia minima di frequenza viene letta dall'avviso del progetto.
Default: 70% se non specificato dall'avviso.

Il collector NON scrive su DB: ritorna {"summary", "suggestions"} e la
persistenza (AgentRun + AgentSuggestion) avviene solo dentro
`agent_workflows.run_agent_workflow`.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import models
from sqlalchemy.orm import Session
from sqlalchemy import func

logger = logging.getLogger(__name__)

SOGLIA_DEFAULT = 0.70


def _get_soglia_frequenza(project: models.Project) -> float:
    """
    Legge la soglia minima di frequenza dall'avviso del progetto.
    Fallback a 70% se non configurata.
    """
    if not project:
        return SOGLIA_DEFAULT
    try:
        avviso_vincoli = getattr(project, 'avviso_vincoli', None)
        if avviso_vincoli and hasattr(avviso_vincoli, 'freq_minima'):
            soglia = float(avviso_vincoli.freq_minima)
            if 0 < soglia <= 1:
                return soglia
    except Exception:
        pass
    return SOGLIA_DEFAULT


def _calcola_ore_progetto(db: Session, project_id: int) -> float:
    """Calcola il totale ore del progetto dagli assignment."""
    result = db.query(
        func.coalesce(func.sum(models.Assignment.assigned_hours), 0.0)
    ).filter(
        models.Assignment.project_id == project_id,
        models.Assignment.is_active == True,
        models.Assignment.role.ilike("%docen%"),
    ).scalar()
    return float(result or 0)


def collect_certification_suggestions(
    db: Session,
    *,
    project_id: Optional[int] = None,
) -> dict[str, Any]:
    """
    Verifica frequenza allievi e propone suggerimenti attestato.
    """
    query = db.query(models.Project).filter(
        models.Project.status == "active"
    )
    if project_id:
        query = query.filter(models.Project.id == project_id)

    projects = query.all()

    suggestions: list[dict[str, Any]] = []
    attestati_pronti = 0
    frequenza_insufficiente = 0
    nessuna_presenza = 0
    totale_allievi = 0

    for project in projects:
        ore_totali = _calcola_ore_progetto(db, project.id)
        if ore_totali <= 0:
            continue

        soglia = _get_soglia_frequenza(project)

        allievi_links = db.query(models.AllievoProject).filter(
            models.AllievoProject.project_id == project.id
        ).all() if hasattr(models, 'AllievoProject') else []

        for link in allievi_links:
            totale_allievi += 1

            ore_frequentate = float(getattr(link, 'ore_frequentate', 0) or 0)

            if ore_totali > 0:
                percentuale = ore_frequentate / ore_totali
            else:
                percentuale = 0

            if ore_frequentate == 0:
                nessuna_presenza += 1
                continue

            attestato_emesso = getattr(link, 'attestato_emesso', False)
            if attestato_emesso:
                continue

            already_suggested = db.query(models.AgentSuggestion).filter(
                models.AgentSuggestion.entity_type == "allievo_project",
                models.AgentSuggestion.entity_id == link.allievo_id,
                models.AgentSuggestion.suggestion_type.in_(["attestato_pronto", "frequenza_insufficiente"]),
                models.AgentSuggestion.status == "pending",
            ).filter(
                models.AgentSuggestion.payload.contains(str(project.id))
            ).first()

            if already_suggested:
                continue

            allievo = db.query(models.Allievo).filter(
                models.Allievo.id == link.allievo_id
            ).first()
            if not allievo:
                continue

            nome_allievo = "{} {}".format(
                allievo.nome or "",
                allievo.cognome or ""
            ).strip()

            payload = {
                "allievo_id": link.allievo_id,
                "project_id": project.id,
                "ore_frequentate": ore_frequentate,
                "ore_totali": ore_totali,
                "percentuale": round(percentuale * 100, 1),
                "soglia": round(soglia * 100, 1),
            }

            if percentuale >= soglia:
                suggestions.append({
                    "entity_type": "allievo_project",
                    "entity_id": link.allievo_id,
                    "suggestion_type": "attestato_pronto",
                    "severity": "low",
                    "title": "Attestato pronto — {}".format(nome_allievo),
                    "description": (
                        "{} ha frequentato {:.0f}% delle ore ({:.1f}/{:.1f}h) "
                        "del progetto {}. Soglia richiesta: {:.0f}%. "
                        "Attestato può essere emesso."
                    ).format(
                        nome_allievo,
                        percentuale * 100,
                        ore_frequentate,
                        ore_totali,
                        project.name,
                        soglia * 100,
                    ),
                    "confidence": 0.95,
                    "payload": payload,
                })
                attestati_pronti += 1
            else:
                suggestions.append({
                    "entity_type": "allievo_project",
                    "entity_id": link.allievo_id,
                    "suggestion_type": "frequenza_insufficiente",
                    "severity": "high",
                    "title": "Frequenza insufficiente — {}".format(nome_allievo),
                    "description": (
                        "{} ha frequentato solo {:.0f}% delle ore ({:.1f}/{:.1f}h) "
                        "del progetto {}. Soglia richiesta: {:.0f}%. "
                        "Attestato NON può essere emesso."
                    ).format(
                        nome_allievo,
                        percentuale * 100,
                        ore_frequentate,
                        ore_totali,
                        project.name,
                        soglia * 100,
                    ),
                    "confidence": 0.95,
                    "payload": payload,
                })
                frequenza_insufficiente += 1

    summary = {
        "progetti_scansionati": len(projects),
        "allievi_verificati": totale_allievi,
        "attestati_pronti": attestati_pronti,
        "frequenza_insufficiente": frequenza_insufficiente,
        "nessuna_presenza": nessuna_presenza,
    }
    return {"summary": summary, "suggestions": suggestions}
