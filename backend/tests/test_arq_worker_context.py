"""AGENT-06: il processo ARQ deve avere la tabella users nella metadata SQLAlchemy.

Root cause (A2a): AgentReviewAction.reviewed_by_user_id ha FK verso users.id;
User è dichiarato in auth.py (stessa Base). Il worker ARQ importava solo models
via agent_workflows, quindi la tabella users non entrava nella metadata e ogni
flush di AgentReviewAction falliva con NoReferencedTableError.
"""
from __future__ import annotations

import subprocess
import sys
from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import models
from database import Base
from time_utils import utc_now


def make_db(*tables):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=list(tables))
    return Session(engine)


def test_arq_worker_import_registers_users_table():
    """Simula il processo ARQ: import di arq_worker da interprete pulito."""
    code = (
        "import arq_worker; "
        "from database import Base; "
        "assert 'users' in Base.metadata.tables, sorted(Base.metadata.tables)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd="/app",
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"


def test_promote_due_followups_flushes_review_action_without_users_error():
    """Draft sent da >7 giorni: la review action deve essere flushata senza
    NoReferencedTableError (users presente nella metadata)."""
    import auth  # noqa: F401 — registra users nella Base, come fa arq_worker

    db = make_db(
        auth.User.__table__,
        models.AgentRun.__table__,
        models.AgentSuggestion.__table__,
        models.AgentCommunicationDraft.__table__,
        models.AgentReviewAction.__table__,
        models.AuditLog.__table__,
    )
    run = models.AgentRun(agent_type="mail_recovery", status="completed")
    db.add(run)
    db.flush()
    suggestion = models.AgentSuggestion(
        run_id=run.id,
        suggestion_type="mail_recovery",
        status="sent",
        entity_type="collaborator",
        title="Richiesta documenti",
    )
    db.add(suggestion)
    db.flush()
    draft = models.AgentCommunicationDraft(
        run_id=run.id,
        suggestion_id=suggestion.id,
        agent_name="mail_recovery",
        channel="email",
        recipient_type="collaborator",
        recipient_id=1,
        recipient_name="Mario Rossi",
        recipient_email="mario.rossi@example.com",
        subject="Richiesta documenti",
        body="Test",
        status="sent",
        sent_at=utc_now() - timedelta(days=8),
    )
    db.add(draft)
    db.commit()

    from agent_workflows import promote_due_followups

    promoted = promote_due_followups(db)

    assert promoted == 1
    db.refresh(draft)
    assert draft.status == "followup_due"
    actions = db.query(models.AgentReviewAction).filter(
        models.AgentReviewAction.suggestion_id == suggestion.id
    ).all()
    assert len(actions) == 1
    assert actions[0].action == "followup_due"
