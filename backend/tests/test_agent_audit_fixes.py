from __future__ import annotations

from sqlalchemy import text
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from database import Base
import models
import schemas


def make_db(*tables):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=list(tables))
    return Session(engine)


def test_data_quality_emits_distinct_suggestion_types_for_documents_and_profile_fields():
    from ai_agents.data_quality import DataQualityAgent

    db = make_db(
        models.Collaborator.__table__,
        models.Assignment.__table__,
        models.Attendance.__table__,
    )
    collaborator = models.Collaborator(
        first_name="Mario",
        last_name="Rossi",
        email="mario@example.com",
        fiscal_code="",
    )
    db.add(collaborator)
    db.commit()

    result = DataQualityAgent().run(db)

    types = {item["suggestion_type"] for item in result.suggestions}

    assert "missing_identity_document" in types
    assert "missing_profile_fields" in types
    assert len([item for item in result.suggestions if item["entity_id"] == collaborator.id]) == 2


def test_ensure_collaborator_draft_creates_whatsapp_without_email():
    from agent_workflows import _ensure_collaborator_draft

    db = make_db(
        models.Collaborator.__table__,
        models.AgentRun.__table__,
        models.AgentSuggestion.__table__,
        models.AgentCommunicationDraft.__table__,
    )
    collaborator = models.Collaborator(
        first_name="Mario",
        last_name="Rossi",
        email="placeholder@example.com",
        phone="+393331112233",
        fiscal_code="RSSMRA80A01H501Z",
        address="Via Roma 1",
    )
    db.add(collaborator)
    db.flush()
    db.execute(
        text("UPDATE collaborators SET email = '' WHERE id = :collaborator_id"),
        {"collaborator_id": collaborator.id},
    )
    db.refresh(collaborator)

    run = models.AgentRun(agent_type="mail_recovery", status="completed")
    db.add(run)
    db.flush()

    suggestion = models.AgentSuggestion(
        run_id=run.id,
        entity_type="collaborator",
        entity_id=collaborator.id,
        suggestion_type="missing_curriculum",
        severity="medium",
        status="pending",
        title="Richiedi curriculum",
        description="Serve curriculum",
        payload="{}",
    )
    db.add(suggestion)
    db.commit()

    draft = _ensure_collaborator_draft(
        db,
        run_id=run.id,
        suggestion=suggestion,
        channel="whatsapp",
    )

    assert draft is not None
    assert draft.channel == "whatsapp"
    assert draft.recipient_email == collaborator.phone


def test_ensure_collaborator_draft_keeps_email_blocked_without_email():
    from agent_workflows import _ensure_collaborator_draft

    db = make_db(
        models.Collaborator.__table__,
        models.AgentRun.__table__,
        models.AgentSuggestion.__table__,
        models.AgentCommunicationDraft.__table__,
    )
    collaborator = models.Collaborator(
        first_name="Mario",
        last_name="Rossi",
        email="placeholder@example.com",
        phone="+393331112233",
        fiscal_code="RSSMRA80A01H501Z",
        address="Via Roma 1",
    )
    db.add(collaborator)
    db.flush()
    db.execute(
        text("UPDATE collaborators SET email = '' WHERE id = :collaborator_id"),
        {"collaborator_id": collaborator.id},
    )
    db.refresh(collaborator)

    run = models.AgentRun(agent_type="mail_recovery", status="completed")
    db.add(run)
    db.flush()

    suggestion = models.AgentSuggestion(
        run_id=run.id,
        entity_type="collaborator",
        entity_id=collaborator.id,
        suggestion_type="missing_curriculum",
        severity="medium",
        status="pending",
        title="Richiedi curriculum",
        description="Serve curriculum",
        payload="{}",
    )
    db.add(suggestion)
    db.commit()

    draft = _ensure_collaborator_draft(
        db,
        run_id=run.id,
        suggestion=suggestion,
        channel="email",
    )

    assert draft is None


def test_accept_suggestion_uses_workflow_path_for_email_approval():
    from routers.agents import accept_suggestion

    db = object()
    payload = schemas.AgentWorkflowActionRequest(
        action="accepted",
        reviewed_by_user_id=9,
        notes="ok",
    )

    import routers.agents as agents_router

    captured = {}

    def fake_apply_workflow_action(db_arg, *, suggestion_id, action, reviewed_by_user_id, notes):
        captured.update({
            "db": db_arg,
            "suggestion_id": suggestion_id,
            "action": action,
            "reviewed_by_user_id": reviewed_by_user_id,
            "notes": notes,
        })
        return {"id": suggestion_id}

    original = agents_router.apply_workflow_action
    agents_router.apply_workflow_action = fake_apply_workflow_action
    try:
        response = accept_suggestion(17, payload, db)
    finally:
        agents_router.apply_workflow_action = original

    assert response == {"id": 17}
    assert captured == {
        "db": db,
        "suggestion_id": 17,
        "action": "approve_email",
        "reviewed_by_user_id": 9,
        "notes": "ok",
    }
