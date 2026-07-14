"""AGENT-01: kill switch globale (AGENTS_ENABLED) e per-agente (AGENT_<NOME>_ENABLED).

Il kill switch deve fermare TUTTI i trigger (manuale, cron ARQ, sync da evento)
senza toccare il DB, mantenendo consultabile la UI (endpoint GET non gattati).
"""
from __future__ import annotations

import asyncio

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import models
from ai_agents.control import agent_enabled, agent_env_name, agents_enabled, disabled_reason
from database import Base


def make_db(*tables):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=list(tables))
    return Session(engine)


def test_agents_enabled_default_true(monkeypatch):
    monkeypatch.delenv("AGENTS_ENABLED", raising=False)
    assert agents_enabled() is True
    assert agent_enabled("mail_recovery") is True


def test_agent_env_name_normalization():
    assert agent_env_name("mail_recovery") == "AGENT_MAIL_RECOVERY_ENABLED"
    assert agent_env_name("contract-agent") == "AGENT_CONTRACT_AGENT_ENABLED"


def test_global_switch_disables_every_agent(monkeypatch):
    monkeypatch.setenv("AGENTS_ENABLED", "false")
    assert agents_enabled() is False
    assert agent_enabled("data_quality") is False
    assert "AGENTS_ENABLED" in disabled_reason("data_quality")


def test_single_agent_switch(monkeypatch):
    monkeypatch.delenv("AGENTS_ENABLED", raising=False)
    monkeypatch.setenv("AGENT_MAIL_RECOVERY_ENABLED", "false")
    assert agent_enabled("mail_recovery") is False
    assert agent_enabled("data_quality") is True
    assert "AGENT_MAIL_RECOVERY_ENABLED" in disabled_reason("mail_recovery")


def test_run_agent_workflow_blocked_when_disabled(monkeypatch):
    from agent_workflows import run_agent_workflow

    monkeypatch.setenv("AGENTS_ENABLED", "false")
    db = make_db(models.AgentRun.__table__)

    try:
        run_agent_workflow(db, agent_type="data_quality")
        raised = False
    except ValueError as exc:
        raised = True
        assert "AGENTS_ENABLED" in str(exc)
    assert raised
    assert db.query(models.AgentRun).count() == 0


def test_sync_data_quality_skips_when_agent_disabled(monkeypatch):
    from agent_workflows import sync_collaborator_data_quality

    monkeypatch.setenv("AGENT_DATA_QUALITY_ENABLED", "false")
    db = make_db(models.Collaborator.__table__, models.AgentRun.__table__)

    result = sync_collaborator_data_quality(db, collaborator_id=1)
    assert result is None


def test_mail_recovery_cron_skips_when_disabled(monkeypatch):
    import arq_worker

    monkeypatch.setenv("AGENTS_ENABLED", "false")
    result = asyncio.run(arq_worker.run_mail_recovery_cron({}))
    assert result["status"] == "skipped"
    assert "AGENTS_ENABLED" in result["reason"]


def test_contract_cron_skips_when_agent_disabled(monkeypatch):
    import arq_worker

    monkeypatch.delenv("AGENTS_ENABLED", raising=False)
    monkeypatch.setenv("AGENT_CONTRACT_AGENT_ENABLED", "false")
    result = asyncio.run(arq_worker.run_contract_agent_cron({}))
    assert result["status"] == "skipped"


def test_certification_cron_skips_when_agent_disabled(monkeypatch):
    import arq_worker

    monkeypatch.delenv("AGENTS_ENABLED", raising=False)
    monkeypatch.setenv("AGENT_CERTIFICATION_ENABLED", "false")
    result = asyncio.run(arq_worker.run_certification_agent_cron({}))
    assert result["status"] == "skipped"


def test_poll_email_inbox_skips_when_disabled(monkeypatch):
    import arq_worker

    monkeypatch.setenv("AGENTS_ENABLED", "false")
    monkeypatch.setenv("GMAIL_IMAP_USER", "inbox@example.com")
    result = asyncio.run(arq_worker.poll_email_inbox({}))
    assert result["status"] == "skipped"
    assert "reason" in result


def test_followup_cron_skips_when_disabled(monkeypatch):
    import arq_worker

    monkeypatch.setenv("AGENTS_ENABLED", "false")
    result = asyncio.run(arq_worker.promote_agent_followups({}))
    # promote_due_followups internamente ritorna 0 senza toccare il DB
    assert result["promoted"] == 0


def test_data_retention_cron_skips_when_disabled(monkeypatch):
    import arq_worker

    monkeypatch.setenv("AGENTS_ENABLED", "false")
    result = asyncio.run(arq_worker.data_retention_cleanup({}))
    assert result["status"] == "skipped"
