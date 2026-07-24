"""Agente Timesheet (guardia di coerenza), proposal-only.

Confronta, in sola lettura, i dati di timesheet/presenze contro i valori di
riferimento dell'assignment e segnala INCOERENZE come *warning*. Non blocca
mai nulla e non scrive su DB: ritorna {"summary", "suggestions"} e la
persistenza (AgentRun + AgentSuggestion) avviene solo dentro
`agent_workflows.run_agent_workflow`.

Guardie implementate (campi reali, verificabili):

1. `timesheet_incoerente` — per ogni `TimesheetGenerato` (snapshot bloccato)
   confronta lo snapshot `TimesheetGenerato.totale_ore` con la somma CORRENTE
   delle ore presenza dell'assignment (`sum(Attendance.hours)` filtrate per
   `assignment_id`). Se divergono oltre la tolleranza significa che le presenze
   sono state modificate dopo la generazione del timesheet: il documento
   congelato non riflette piu' la realta'. -> warning.

2. `ore_oltre_assegnato` — per gli assignment attivi con presenze, se la somma
   corrente delle ore presenza supera `Assignment.assigned_hours` le ore
   registrate eccedono quelle assegnate. -> warning.

Il flag di ENFORCEMENT (`AGENT_TIMESHEET_ENFORCEMENT_ENABLED`, default false,
vedi `ai_agents.control.timesheet_enforcement_enabled`) e' predisposto ma NON
collegato ad alcun blocco in questa task: con default false l'agente resta
solo warning. Il flag viene letto e riportato nel summary per essere testato,
ma non altera il comportamento (nessun blocco, nessun auto-apply).
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

import models
from ai_agents.control import timesheet_enforcement_enabled

logger = logging.getLogger(__name__)

# Tolleranza in ore per assorbire arrotondamenti Numeric(x,2) prima di
# considerare due totali "incoerenti".
TOLLERANZA_ORE = 0.01


def _sum_attendance_hours(db: Session, assignment_ids: list[int]) -> dict[int, float]:
    """Somma corrente delle ore presenza raggruppate per assignment (1 query)."""
    if not assignment_ids:
        return {}
    rows = (
        db.query(
            models.Attendance.assignment_id,
            func.coalesce(func.sum(models.Attendance.hours), 0.0),
        )
        .filter(models.Attendance.assignment_id.in_(assignment_ids))
        .group_by(models.Attendance.assignment_id)
        .all()
    )
    return {aid: float(total or 0) for aid, total in rows if aid is not None}


def collect_timesheet_suggestions(
    db: Session,
    *,
    project_id: Optional[int] = None,
) -> dict[str, Any]:
    """Guardie di coerenza timesheet/presenze, proposal-only (mai blocco)."""
    enforcement = timesheet_enforcement_enabled()

    # Assignment attivi (guardia ore_oltre_assegnato).
    assign_q = db.query(models.Assignment).filter(models.Assignment.is_active == True)  # noqa: E712
    if project_id:
        assign_q = assign_q.filter(models.Assignment.project_id == project_id)
    assignments = assign_q.all()

    # Timesheet generati (guardia timesheet_incoerente); join su Assignment per
    # poter filtrare per progetto.
    ts_q = db.query(models.TimesheetGenerato).join(
        models.Assignment,
        models.TimesheetGenerato.assignment_id == models.Assignment.id,
    )
    if project_id:
        ts_q = ts_q.filter(models.Assignment.project_id == project_id)
    timesheets = ts_q.all()

    relevant_ids = {a.id for a in assignments} | {t.assignment_id for t in timesheets}
    hours_by_assignment = _sum_attendance_hours(db, list(relevant_ids))

    suggestions: list[dict[str, Any]] = []
    timesheet_incoerenti = 0
    ore_oltre_assegnato = 0

    # --- Guardia 1: timesheet snapshot vs presenze correnti -----------------
    for ts in timesheets:
        current = hours_by_assignment.get(ts.assignment_id, 0.0)
        snapshot = float(ts.totale_ore or 0)
        if abs(current - snapshot) <= TOLLERANZA_ORE:
            continue
        suggestions.append({
            "entity_type": "assignment",
            "entity_id": ts.assignment_id,
            "suggestion_type": "timesheet_incoerente",
            "severity": "warning",
            "title": "Timesheet incoerente con le presenze correnti",
            "description": (
                "Il timesheet #{ts_id} (assignment {aid}) e' stato generato con "
                "totale {snap:.2f}h, ma la somma corrente delle presenze e' "
                "{cur:.2f}h. Le presenze risultano modificate dopo la "
                "generazione: verificare/rigenerare il timesheet."
            ).format(ts_id=ts.id, aid=ts.assignment_id, snap=snapshot, cur=current),
            "confidence": 0.9,
            "payload": {
                "assignment_id": ts.assignment_id,
                "timesheet_id": ts.id,
                "atteso_totale_ore": round(snapshot, 2),
                "trovato_ore_presenze": round(current, 2),
                "delta_ore": round(current - snapshot, 2),
                "enforcement_enabled": enforcement,
            },
        })
        timesheet_incoerenti += 1

    # --- Guardia 2: ore registrate oltre le assegnate -----------------------
    for a in assignments:
        current = hours_by_assignment.get(a.id, 0.0)
        if current <= 0:
            continue
        assigned = float(a.assigned_hours or 0)
        if current - assigned <= TOLLERANZA_ORE:
            continue
        suggestions.append({
            "entity_type": "assignment",
            "entity_id": a.id,
            "suggestion_type": "ore_oltre_assegnato",
            "severity": "warning",
            "title": "Ore registrate oltre le assegnate",
            "description": (
                "L'assignment {aid} ha {cur:.2f}h di presenze registrate contro "
                "{assigned:.2f}h assegnate (eccedenza {delta:.2f}h). Verificare "
                "presenze o rivedere le ore assegnate."
            ).format(aid=a.id, cur=current, assigned=assigned, delta=current - assigned),
            "confidence": 0.9,
            "payload": {
                "assignment_id": a.id,
                "atteso_assigned_hours": round(assigned, 2),
                "trovato_ore_presenze": round(current, 2),
                "delta_ore": round(current - assigned, 2),
                "enforcement_enabled": enforcement,
            },
        })
        ore_oltre_assegnato += 1

    summary = {
        "assignment_scansionati": len(assignments),
        "timesheet_scansionati": len(timesheets),
        "timesheet_incoerenti": timesheet_incoerenti,
        "ore_oltre_assegnato": ore_oltre_assegnato,
        # Predisposto ma non collegato a blocchi: default false = solo warning.
        "enforcement_enabled": enforcement,
    }
    return {"summary": summary, "suggestions": suggestions}
