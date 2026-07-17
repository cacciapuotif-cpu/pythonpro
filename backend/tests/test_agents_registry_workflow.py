"""AGENT-09/10: registry unico dichiarativo, contract/certification via workflow.

- ogni agente e' descritto in _AGENT_DEFINITIONS (runner non esposto)
- i collector sono puri: nessuna scrittura DB fuori da run_agent_workflow
- cron contract/certification e trigger da validazione umana passano dal
  workflow persistente
- registry legacy (ai_agents/registry.py) e jobs/run_agents.py eliminati
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import auth  # noqa: F401 — registra users nella Base come nel processo ARQ
import models
from database import Base

REQUIRED_DEFINITION_KEYS = {
    "name",
    "description",
    "supported_entity_types",
    "triggers",
    "kill_switch_env",
    "allowed_roles",
    "version",
}


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        auth.User.__table__,
        models.Collaborator.__table__,
        models.Project.__table__,
        models.Assignment.__table__,
        models.DocumentoRichiesto.__table__,
        models.Allievo.__table__,
        models.AllievoProject.__table__,
        models.AgentRun.__table__,
        models.AgentSuggestion.__table__,
        models.AgentCommunicationDraft.__table__,
        models.AgentReviewAction.__table__,
        models.AuditLog.__table__,
    ])
    return Session(engine)


def _seed_contract_ready(db):
    collaborator = models.Collaborator(
        first_name="Mario",
        last_name="Rossi",
        email="mario@example.com",
        fiscal_code="RSSMRA80A01H501U",
        is_active=True,
    )
    project = models.Project(name="Progetto Test", status="active")
    db.add_all([collaborator, project])
    db.flush()
    assignment = models.Assignment(
        collaborator_id=collaborator.id,
        project_id=project.id,
        role="Docente",
        assigned_hours=40.0,
        start_date=datetime(2026, 1, 1),
        end_date=datetime(2026, 12, 31),
        hourly_rate=50.0,
        contract_type="professionale",
        is_active=True,
    )
    db.add(assignment)
    db.flush()
    for tipo in ("curriculum", "documento_identita"):
        db.add(models.DocumentoRichiesto(
            collaboratore_id=collaborator.id,
            tipo_documento=tipo,
            obbligatorio=True,
            stato="validato",
        ))
    db.commit()
    return collaborator, project, assignment


# --- Registry dichiarativo ----------------------------------------------


def test_registry_definitions_complete():
    from ai_agents import list_agent_definitions

    definitions = {item["name"]: item for item in list_agent_definitions()}
    assert set(definitions) == {"data_quality", "mail_recovery", "contract_agent", "certification", "data_retention"}
    for name, definition in definitions.items():
        missing = REQUIRED_DEFINITION_KEYS - set(definition)
        assert not missing, f"{name}: campi mancanti {missing}"
        assert "runner" not in definition, f"{name}: runner non deve essere esposto"
        assert definition["kill_switch_env"].startswith("AGENT_")


def test_legacy_registry_removed():
    import importlib
    import pytest

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("ai_agents.registry")

    from pathlib import Path

    assert not (Path(__file__).resolve().parents[1] / "jobs" / "run_agents.py").exists()


def test_codice_fiscale_checksum_validation():
    """Hunk pre-esistente adottato con AGENT-10: validazione CF con check digit."""
    from ai_agents.data_quality import is_valid_codice_fiscale

    assert is_valid_codice_fiscale("RSSMRA80A01H501U") is True
    assert is_valid_codice_fiscale("rssmra80a01h501u") is True
    assert is_valid_codice_fiscale("RSSMRA80A01H501Z") is False  # check digit errato
    assert is_valid_codice_fiscale("RSSMRA80A01H501") is False  # troppo corto
    assert is_valid_codice_fiscale("") is False
    assert is_valid_codice_fiscale(None) is False


# --- Collector puri -------------------------------------------------------


def test_contract_collector_is_pure():
    from ai_agents.contract_agent import collect_contract_suggestions

    db = make_db()
    _seed_contract_ready(db)

    result = collect_contract_suggestions(db)
    db.commit()

    assert result["summary"]["suggerimenti_creati"] == 1
    item = result["suggestions"][0]
    assert item["suggestion_type"] == "contract_ready"
    assert item["entity_type"] == "assignment"
    # collector puro: nessuna riga scritta
    assert db.query(models.AgentSuggestion).count() == 0
    assert db.query(models.AgentRun).count() == 0


def test_certification_collector_is_pure():
    from ai_agents.certification_agent import collect_certification_suggestions

    db = make_db()
    project = models.Project(name="Corso Python", status="active")
    allievo = models.Allievo(nome="Anna", cognome="Verdi")
    collaborator = models.Collaborator(
        first_name="Doc",
        last_name="Ente",
        email="doc@example.com",
        fiscal_code="DCNNTE80A01H501X",
        is_active=True,
    )
    db.add_all([project, allievo, collaborator])
    db.flush()
    db.add(models.Assignment(
        collaborator_id=collaborator.id,
        project_id=project.id,
        role="Docente",
        assigned_hours=100.0,
        start_date=datetime(2026, 1, 1),
        end_date=datetime(2026, 12, 31),
        hourly_rate=50.0,
        is_active=True,
    ))
    db.add(models.AllievoProject(
        allievo_id=allievo.id,
        project_id=project.id,
        ore_frequentate=80.0,
    ))
    db.commit()

    result = collect_certification_suggestions(db)
    db.commit()

    assert result["summary"]["attestati_pronti"] == 1
    assert result["suggestions"][0]["suggestion_type"] == "attestato_pronto"
    assert db.query(models.AgentSuggestion).count() == 0
    assert db.query(models.AgentRun).count() == 0


# --- Esecuzione via workflow ----------------------------------------------


def test_contract_agent_via_workflow_creates_run_and_suggestion():
    from agent_workflows import run_agent_workflow

    db = make_db()
    collaborator, _, assignment = _seed_contract_ready(db)

    run = run_agent_workflow(
        db,
        agent_type="contract_agent",
        entity_type="collaborator",
        entity_id=collaborator.id,
        auto_mode=True,
    )

    assert run.status == "completed"
    suggestions = db.query(models.AgentSuggestion).filter(
        models.AgentSuggestion.run_id == run.id
    ).all()
    assert len(suggestions) == 1
    assert suggestions[0].suggestion_type == "contract_ready"
    assert suggestions[0].entity_id == assignment.id


def test_certification_unsupported_entity_type_rejected():
    from agent_workflows import run_agent_workflow
    import pytest

    db = make_db()
    with pytest.raises(ValueError):
        run_agent_workflow(
            db,
            agent_type="certification",
            entity_type="collaborator",
            entity_id=1,
        )


# --- Cron via workflow -----------------------------------------------------


def _assert_cron_uses_workflow(monkeypatch, cron_name: str, agent_type: str):
    import arq_worker

    db = make_db()
    monkeypatch.setattr(db, "close", lambda: None)
    monkeypatch.setattr(arq_worker, "SessionLocal", lambda: db)

    import agent_workflows

    def fake_registered_agent(db_arg, *, agent_name, **kwargs):
        assert agent_name == agent_type
        return {"summary": {}, "suggestions": []}

    monkeypatch.setattr(agent_workflows, "run_registered_agent", fake_registered_agent)

    result = asyncio.run(getattr(arq_worker, cron_name)({}))

    assert result["status"] == "completed"
    runs = db.query(models.AgentRun).filter(models.AgentRun.agent_type == agent_type).all()
    assert len(runs) == 1
    assert result.get("run_id") == runs[0].id


def test_contract_cron_uses_workflow(monkeypatch):
    _assert_cron_uses_workflow(monkeypatch, "run_contract_agent_cron", "contract_agent")


def test_certification_cron_uses_workflow(monkeypatch):
    _assert_cron_uses_workflow(monkeypatch, "run_certification_agent_cron", "certification")
