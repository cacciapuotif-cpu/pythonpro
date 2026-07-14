"""AGENT-02: nessun invio automatico dagli agenti.

Ogni comunicazione mail_recovery resta bozza (status=draft) finche' un umano
non approva dal flusso UI (apply_workflow_action). Il percorso auto_send non
deve esistere nel codice.
"""
from __future__ import annotations

import inspect
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import models
from auth import User
from database import Base


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        User.__table__,
        models.Collaborator.__table__,
        models.DocumentoRichiesto.__table__,
        models.AgentRun.__table__,
        models.AgentSuggestion.__table__,
        models.AgentCommunicationDraft.__table__,
        models.AgentReviewAction.__table__,
        models.AuditLog.__table__,
        models.SecurityAuditLog.__table__,
    ])
    return Session(engine)


def _collaborator_with_missing_data(db) -> models.Collaborator:
    collaborator = models.Collaborator(
        first_name="Mario",
        last_name="Rossi",
        email="mario@example.com",
        fiscal_code="RSSMRA80A01H501U",
        consenso_email_agenti=True,
    )
    db.add(collaborator)
    db.commit()
    return collaborator


def test_mail_recovery_high_confidence_creates_draft_not_send(monkeypatch):
    from agent_workflows import run_agent_workflow

    db = make_db()
    collaborator = _collaborator_with_missing_data(db)

    with patch("agent_workflows._send_email") as send_mock:
        run = run_agent_workflow(
            db,
            agent_type="mail_recovery",
            entity_type="collaborator",
            entity_id=collaborator.id,
        )

    send_mock.assert_not_called()

    drafts = db.query(models.AgentCommunicationDraft).all()
    assert drafts, "attesa almeno una bozza email"
    assert all(d.status == "draft" for d in drafts)
    assert all(d.sent_at is None for d in drafts)

    suggestions = db.query(models.AgentSuggestion).all()
    assert suggestions
    # Nessuna suggestion nasce gia' "sent": tutte in attesa di revisione umana.
    assert all(s.status == "pending" for s in suggestions)
    assert run.status == "completed"


def test_mail_recovery_summary_has_no_autosend_counter():
    from agent_workflows import run_agent_workflow
    import json

    db = make_db()
    collaborator = _collaborator_with_missing_data(db)

    with patch("agent_workflows._send_email") as send_mock:
        run = run_agent_workflow(
            db,
            agent_type="mail_recovery",
            entity_type="collaborator",
            entity_id=collaborator.id,
        )

    send_mock.assert_not_called()
    summary = json.loads(run.result_summary)
    assert "auto_sent_emails" not in summary
    assert summary.get("draft_emails", 0) >= 1


def test_no_autosend_code_path_left():
    import agent_workflows

    source = inspect.getsource(agent_workflows)
    assert "auto_send" not in source, "percorso auto_send ancora presente in agent_workflows"


def test_send_happens_only_via_workflow_approval():
    from agent_workflows import apply_workflow_action, run_agent_workflow

    db = make_db()
    collaborator = _collaborator_with_missing_data(db)

    with patch("agent_workflows._send_email") as send_mock:
        run_agent_workflow(
            db,
            agent_type="mail_recovery",
            entity_type="collaborator",
            entity_id=collaborator.id,
        )
    send_mock.assert_not_called()

    suggestion = db.query(models.AgentSuggestion).first()

    with patch("agent_workflows._send_email", return_value=(True, "Email inviata")) as send_mock:
        updated = apply_workflow_action(
            db,
            suggestion_id=suggestion.id,
            action="approve_email",
            reviewed_by_user_id=1,
        )

    send_mock.assert_called_once()
    assert updated.status == "sent"
    draft = db.query(models.AgentCommunicationDraft).filter_by(suggestion_id=suggestion.id, channel="email").first()
    assert draft.status == "sent"
    review_actions = db.query(models.AgentReviewAction).filter_by(suggestion_id=suggestion.id).all()
    assert any(a.action == "approve_email" for a in review_actions)
