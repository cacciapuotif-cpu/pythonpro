"""B5.2: timesheet_agent proposal-only (guardia di coerenza) + flag enforcement.

- collector PURO: rileva incoerenze senza scrivere su DB
- NON propone quando i dati sono coerenti
- kill-switch AGENT_TIMESHEET_ENABLED spegne l'agente (via workflow)
- flag AGENT_TIMESHEET_ENFORCEMENT_ENABLED default false (solo warning)
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import models
from database import Base


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        models.Collaborator.__table__,
        models.Project.__table__,
        models.Assignment.__table__,
        models.Attendance.__table__,
        models.TimesheetGenerato.__table__,
        models.TimesheetRiga.__table__,
        models.AgentRun.__table__,
        models.AgentSuggestion.__table__,
        models.AuditLog.__table__,
    ])
    return Session(engine)


def _seed_assignment(db, *, assigned_hours=40.0):
    collaborator = models.Collaborator(
        first_name="Mario", last_name="Rossi", email="mario@example.com",
        fiscal_code="RSSMRA80A01H501U", is_active=True,
    )
    project = models.Project(name="Progetto Test", status="active")
    db.add_all([collaborator, project])
    db.flush()
    assignment = models.Assignment(
        collaborator_id=collaborator.id, project_id=project.id, role="Docente",
        assigned_hours=assigned_hours, start_date=datetime(2026, 1, 1),
        end_date=datetime(2026, 12, 31), hourly_rate=50.0, is_active=True,
    )
    db.add(assignment)
    db.flush()
    return collaborator, project, assignment


def _add_attendance(db, collaborator, project, assignment, *, hours, day=1):
    """Registra `hours` ore totali, spezzate in righe <= 8h su giorni distinti
    (il validator Attendance rifiuta ore > 24 e la FK unique vuole start_time
    distinti)."""
    remaining = float(hours)
    d = day
    while remaining > 1e-9:
        chunk = min(8.0, remaining)
        start = datetime(2026, 2, d, 9, 0)
        db.add(models.Attendance(
            collaborator_id=collaborator.id, project_id=project.id,
            assignment_id=assignment.id, date=datetime(2026, 2, d),
            start_time=start, end_time=start + timedelta(hours=chunk),
            hours=chunk,
        ))
        remaining -= chunk
        d += 1


# --- Guardia 1: timesheet incoerente con presenze correnti -----------------


def test_collector_rileva_timesheet_incoerente_ed_e_puro():
    from ai_agents.timesheet_agent import collect_timesheet_suggestions

    db = make_db()
    collab, project, assignment = _seed_assignment(db, assigned_hours=40.0)
    # Timesheet generato con snapshot totale 20h.
    db.add(models.TimesheetGenerato(
        assignment_id=assignment.id, pdf_path="/x.pdf", pdf_filename="x.pdf",
        totale_ore=20.0, presenze_count=1,
    ))
    # Presenze modificate DOPO la generazione: ora somma 30h (drift).
    _add_attendance(db, collab, project, assignment, hours=30.0, day=1)
    db.commit()

    result = collect_timesheet_suggestions(db)
    db.commit()

    tipi = [s["suggestion_type"] for s in result["suggestions"]]
    assert "timesheet_incoerente" in tipi
    inc = next(s for s in result["suggestions"] if s["suggestion_type"] == "timesheet_incoerente")
    assert inc["severity"] == "warning"
    assert inc["entity_type"] == "assignment"
    assert inc["payload"]["atteso_totale_ore"] == 20.0
    assert inc["payload"]["trovato_ore_presenze"] == 30.0
    # collector puro: nessuna riga persistita
    assert db.query(models.AgentSuggestion).count() == 0
    assert db.query(models.AgentRun).count() == 0


def test_collector_non_propone_quando_coerente():
    from ai_agents.timesheet_agent import collect_timesheet_suggestions

    db = make_db()
    collab, project, assignment = _seed_assignment(db, assigned_hours=40.0)
    db.add(models.TimesheetGenerato(
        assignment_id=assignment.id, pdf_path="/x.pdf", pdf_filename="x.pdf",
        totale_ore=30.0, presenze_count=1,
    ))
    _add_attendance(db, collab, project, assignment, hours=30.0, day=1)
    db.commit()

    result = collect_timesheet_suggestions(db)

    assert result["suggestions"] == []
    assert result["summary"]["timesheet_incoerenti"] == 0
    assert result["summary"]["ore_oltre_assegnato"] == 0


# --- Guardia 2: ore registrate oltre le assegnate --------------------------


def test_collector_rileva_ore_oltre_assegnato():
    from ai_agents.timesheet_agent import collect_timesheet_suggestions

    db = make_db()
    collab, project, assignment = _seed_assignment(db, assigned_hours=10.0)
    _add_attendance(db, collab, project, assignment, hours=8.0, day=1)
    _add_attendance(db, collab, project, assignment, hours=7.0, day=2)
    db.commit()

    result = collect_timesheet_suggestions(db)

    oltre = next(s for s in result["suggestions"] if s["suggestion_type"] == "ore_oltre_assegnato")
    assert oltre["severity"] == "warning"
    assert oltre["payload"]["atteso_assigned_hours"] == 10.0
    assert oltre["payload"]["trovato_ore_presenze"] == 15.0
    assert oltre["payload"]["delta_ore"] == 5.0


def test_collector_filtra_per_progetto():
    from ai_agents.timesheet_agent import collect_timesheet_suggestions

    db = make_db()
    collab, project, assignment = _seed_assignment(db, assigned_hours=10.0)
    _add_attendance(db, collab, project, assignment, hours=15.0, day=1)
    db.commit()

    # Progetto inesistente: nessun assignment scansionato, nessuna proposta.
    result = collect_timesheet_suggestions(db, project_id=99999)
    assert result["suggestions"] == []
    assert result["summary"]["assignment_scansionati"] == 0


# --- Flag enforcement (default false) --------------------------------------


def test_enforcement_flag_default_false(monkeypatch):
    from ai_agents.control import timesheet_enforcement_enabled

    monkeypatch.delenv("AGENT_TIMESHEET_ENFORCEMENT_ENABLED", raising=False)
    assert timesheet_enforcement_enabled() is False


def test_enforcement_flag_attivabile(monkeypatch):
    from ai_agents.control import timesheet_enforcement_enabled

    monkeypatch.setenv("AGENT_TIMESHEET_ENFORCEMENT_ENABLED", "true")
    assert timesheet_enforcement_enabled() is True


def test_enforcement_true_non_blocca_resta_warning(monkeypatch):
    """Il flag e' predisposto ma non collegato a blocchi: solo warning."""
    from ai_agents.timesheet_agent import collect_timesheet_suggestions

    monkeypatch.setenv("AGENT_TIMESHEET_ENFORCEMENT_ENABLED", "true")
    db = make_db()
    collab, project, assignment = _seed_assignment(db, assigned_hours=10.0)
    _add_attendance(db, collab, project, assignment, hours=15.0, day=1)
    db.commit()

    result = collect_timesheet_suggestions(db)
    assert result["summary"]["enforcement_enabled"] is True
    # Nessun blocco: continua a produrre solo warning.
    assert all(s["severity"] == "warning" for s in result["suggestions"])


# --- Kill-switch AGENT_TIMESHEET_ENABLED -----------------------------------


def test_kill_switch_env_name():
    from ai_agents.control import agent_enabled, agent_env_name

    assert agent_env_name("timesheet") == "AGENT_TIMESHEET_ENABLED"
    assert agent_enabled("timesheet") is True  # default abilitato come gli altri


def test_kill_switch_disabilita_agente(monkeypatch):
    from ai_agents.control import agent_enabled, disabled_reason

    monkeypatch.delenv("AGENTS_ENABLED", raising=False)
    monkeypatch.setenv("AGENT_TIMESHEET_ENABLED", "false")
    assert agent_enabled("timesheet") is False
    assert "AGENT_TIMESHEET_ENABLED" in disabled_reason("timesheet")


def test_workflow_blocked_when_agent_disabled(monkeypatch):
    from agent_workflows import run_agent_workflow

    monkeypatch.setenv("AGENT_TIMESHEET_ENABLED", "false")
    db = make_db()
    with pytest.raises(ValueError) as exc:
        run_agent_workflow(db, agent_type="timesheet")
    assert "AGENT_TIMESHEET_ENABLED" in str(exc.value)
    assert db.query(models.AgentRun).count() == 0


# --- Via workflow: persistenza e apply no-op -------------------------------


def test_timesheet_via_workflow_persiste_suggestion(monkeypatch):
    from agent_workflows import run_agent_workflow

    monkeypatch.delenv("AGENTS_ENABLED", raising=False)
    monkeypatch.delenv("AGENT_TIMESHEET_ENABLED", raising=False)
    db = make_db()
    collab, project, assignment = _seed_assignment(db, assigned_hours=10.0)
    _add_attendance(db, collab, project, assignment, hours=15.0, day=1)
    db.commit()

    run = run_agent_workflow(
        db, agent_type="timesheet", entity_type="project", entity_id=project.id,
    )
    assert run.status == "completed"
    suggestions = db.query(models.AgentSuggestion).filter(
        models.AgentSuggestion.run_id == run.id
    ).all()
    assert len(suggestions) == 1
    assert suggestions[0].suggestion_type == "ore_oltre_assegnato"


def test_apply_timesheet_verifica_e_noop():
    from services.suggestion_apply import apply_suggestion

    db = make_db()
    suggestion = models.AgentSuggestion(
        entity_type="assignment", entity_id=1, suggestion_type="ore_oltre_assegnato",
        severity="warning", status="pending", title="x", description="y",
        auto_fix_payload='{"kind": "timesheet_verifica"}',
    )
    result = apply_suggestion(db, suggestion, user_id=1)
    assert result["applied"] == []
    assert result["skipped"][0]["reason"] == "informativa_nessuna_mutazione"
