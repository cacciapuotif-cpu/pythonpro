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

import json
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

    project_ids = [p.id for p in projects]

    # Pre-carica in batch i link allievo-progetto (una sola query), raggruppati
    # per progetto preservando l'ordine.
    links_by_project: dict[int, list] = {pid: [] for pid in project_ids}
    if project_ids and hasattr(models, 'AllievoProject'):
        all_links = db.query(models.AllievoProject).filter(
            models.AllievoProject.project_id.in_(project_ids)
        ).all()
        for link in all_links:
            links_by_project.setdefault(link.project_id, []).append(link)

    # Pre-carica in batch gli allievi coinvolti (una sola query).
    allievo_ids = {link.allievo_id for links in links_by_project.values() for link in links}
    allievi_by_id: dict[int, Any] = {}
    if allievo_ids:
        allievi_by_id = {
            a.id: a
            for a in db.query(models.Allievo).filter(
                models.Allievo.id.in_(allievo_ids)
            ).all()
        }

    # Dedup STRUTTURATO: una sola query per tutte le suggestion pending del
    # certification agent; chiave esatta (allievo_id, project_id) estratta dal
    # payload JSON, non substring del payload (che darebbe falsi positivi, es.
    # project.id=5 che matcha "25.0" nelle ore).
    already_suggested: set[tuple[int, int]] = set()
    if project_ids:
        pending = db.query(
            models.AgentSuggestion.entity_id,
            models.AgentSuggestion.payload,
        ).filter(
            models.AgentSuggestion.entity_type == "allievo_project",
            models.AgentSuggestion.suggestion_type.in_(["attestato_pronto", "frequenza_insufficiente"]),
            models.AgentSuggestion.status == "pending",
        ).all()
        for entity_id, raw_payload in pending:
            pid = None
            if isinstance(raw_payload, dict):
                pid = raw_payload.get("project_id")
            elif isinstance(raw_payload, str) and raw_payload:
                try:
                    pid = json.loads(raw_payload).get("project_id")
                except (ValueError, AttributeError):
                    pid = None
            if entity_id is not None and pid is not None:
                already_suggested.add((int(entity_id), int(pid)))

    for project in projects:
        ore_totali = _calcola_ore_progetto(db, project.id)
        if ore_totali <= 0:
            continue

        soglia = _get_soglia_frequenza(project)

        allievi_links = links_by_project.get(project.id, [])

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

            if (link.allievo_id, project.id) in already_suggested:
                continue

            allievo = allievi_by_id.get(link.allievo_id)
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
