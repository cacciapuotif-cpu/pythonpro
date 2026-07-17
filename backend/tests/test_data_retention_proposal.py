"""NEW-006: retention propone; anonimizza solo dopo apply umano."""
import asyncio
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import auth
import models
from database import Base
import pytest

@pytest.fixture(autouse=True)
def enable_retention(monkeypatch):
    monkeypatch.setenv("AGENTS_ENABLED", "true")
    monkeypatch.setenv("AGENT_DATA_RETENTION_ENABLED", "true")



def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[auth.User.__table__, models.Collaborator.__table__,
        models.Project.__table__, models.Assignment.__table__, models.AgentRun.__table__,
        models.AgentSuggestion.__table__, models.AgentReviewAction.__table__, models.AuditLog.__table__, models.SecurityAuditLog.__table__])
    return Session(engine)


def seed(db):
    collaborator = models.Collaborator(first_name="Mario", last_name="Rossi",
        email="retention@example.com", fiscal_code="RSSMRA80A01H501U", anonimizzato=False)
    project = models.Project(name="Storico", status="completed")
    db.add_all([collaborator, project]); db.flush()
    db.add(models.Assignment(collaborator_id=collaborator.id, project_id=project.id,
        role="Docente", assigned_hours=1, start_date=datetime(2019, 1, 1),
        end_date=datetime(2020, 1, 1), hourly_rate=1)); db.commit()
    return collaborator, project


def test_proposal_only_and_deduplicated():
    from agent_workflows import run_agent_workflow
    db = make_db(); collaborator, _ = seed(db)
    collaborator_id = collaborator.id
    run_agent_workflow(db, agent_type="data_retention", auto_mode=True)
    run_agent_workflow(db, agent_type="data_retention", auto_mode=True)
    collaborator = db.get(models.Collaborator, collaborator_id)
    suggestion = db.query(models.AgentSuggestion).one()
    assert collaborator.anonimizzato is False
    assert suggestion.status == "pending"
    assert suggestion.auto_fix_available is True
    assert suggestion.suggestion_type == "data_retention_anonymization"


def test_apply_anonymizes_after_review():
    from agent_workflows import run_agent_workflow
    from services.suggestion_apply import apply_suggestion
    db = make_db(); collaborator, _ = seed(db)
    collaborator_id = collaborator.id
    run_agent_workflow(db, agent_type="data_retention", auto_mode=True)
    result = apply_suggestion(db, db.query(models.AgentSuggestion).one(), user_id=None)
    collaborator = db.get(models.Collaborator, collaborator_id)
    assert result["applied"] == ["anonimizzato"]
    assert collaborator.anonimizzato is True


def test_apply_rechecks_retention():
    from agent_workflows import run_agent_workflow
    from services.suggestion_apply import apply_suggestion
    db = make_db(); collaborator, project = seed(db)
    collaborator_id = collaborator.id
    run_agent_workflow(db, agent_type="data_retention", auto_mode=True)
    suggestion = db.query(models.AgentSuggestion).one()
    db.add(models.Assignment(collaborator_id=collaborator.id, project_id=project.id,
        role="Recente", assigned_hours=1, start_date=datetime.now() - timedelta(days=10),
        end_date=datetime.now() - timedelta(days=1), hourly_rate=1)); db.commit()
    result = apply_suggestion(db, suggestion, user_id=None)
    collaborator = db.get(models.Collaborator, collaborator_id)
    assert result["applied"] == []
    assert collaborator.anonimizzato is False

def test_cron_creates_proposal_without_anonymization_or_email(monkeypatch):
    import agent_workflows
    import arq_worker

    db = make_db()
    collaborator, _ = seed(db)
    collaborator_id = collaborator.id
    monkeypatch.setattr(arq_worker, "SessionLocal", lambda: db)

    def fail_email(*args, **kwargs):
        raise AssertionError("Il cron retention non deve inviare email")

    monkeypatch.setattr(agent_workflows, "_send_email", fail_email)
    result = asyncio.run(arq_worker.data_retention_cleanup({}))

    collaborator = db.get(models.Collaborator, collaborator_id)
    assert result["status"] == "completed"
    assert result["anonymized"] == 0
    assert result["suggestions_created"] == 1
    assert collaborator.anonimizzato is False
    assert db.query(models.AgentSuggestion).one().status == "pending"
