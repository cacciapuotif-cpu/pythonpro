"""AGENT-07: il cron mail_recovery deve passare dal workflow persistente.

Prima chiamava run_mail_recovery_agent direttamente: nessun AgentRun
tracciato, esecuzioni invisibili in dashboard (bypass censito nel piano,
fatto #7).
"""
from __future__ import annotations

import asyncio
import json

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import auth  # noqa: F401 — registra users nella Base come nel processo ARQ
import models
from database import Base


def make_db(*tables):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=list(tables))
    return Session(engine)


def test_mail_recovery_cron_creates_persistent_run(monkeypatch):
    import agent_workflows
    import arq_worker

    db = make_db(
        auth.User.__table__,
        models.AgentRun.__table__,
        models.AgentSuggestion.__table__,
        models.AgentCommunicationDraft.__table__,
        models.AgentReviewAction.__table__,
        models.AuditLog.__table__,
    )
    monkeypatch.setattr(db, "close", lambda: None)
    monkeypatch.setattr(arq_worker, "SessionLocal", lambda: db)

    def fake_registered_agent(db_arg, *, agent_name, **kwargs):
        assert agent_name == "mail_recovery"
        return {"summary": {"collaborators_scanned": 0}, "suggestions": []}

    monkeypatch.setattr(agent_workflows, "run_registered_agent", fake_registered_agent)

    def fail_direct_call(*args, **kwargs):
        raise AssertionError("bypass: run_mail_recovery_agent chiamato direttamente dal cron")

    import ai_agents.mail_recovery as mail_recovery_module

    monkeypatch.setattr(mail_recovery_module, "run_mail_recovery_agent", fail_direct_call)

    result = asyncio.run(arq_worker.run_mail_recovery_cron({}))

    assert result["status"] == "completed"
    runs = db.query(models.AgentRun).filter(models.AgentRun.agent_type == "mail_recovery").all()
    assert len(runs) == 1
    run = runs[0]
    assert run.status == "completed"
    payload = json.loads(run.input_payload or "{}")
    assert payload.get("trigger_mode") == "automatic"
    assert result.get("run_id") == run.id


def test_mail_recovery_cron_skips_when_disabled(monkeypatch):
    import arq_worker

    monkeypatch.setenv("AGENT_MAIL_RECOVERY_ENABLED", "false")
    result = asyncio.run(arq_worker.run_mail_recovery_cron({}))
    assert result["status"] == "skipped"
