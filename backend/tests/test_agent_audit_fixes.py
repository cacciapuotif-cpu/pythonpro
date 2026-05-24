from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from datetime import timezone

from sqlalchemy import text
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import crud
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


def test_run_agent_workflow_marks_run_failed_when_agent_crashes():
    from agent_workflows import AgentWorkflowExecutionError, run_agent_workflow
    from auth import User

    db = make_db(
        User.__table__,
        models.AgentRun.__table__,
        models.AgentSuggestion.__table__,
        models.AgentCommunicationDraft.__table__,
        models.AgentReviewAction.__table__,
        models.AuditLog.__table__,
    )

    import agent_workflows

    original = agent_workflows.run_registered_agent

    def fake_run_registered_agent(*args, **kwargs):
        raise RuntimeError("kaboom")

    agent_workflows.run_registered_agent = fake_run_registered_agent
    try:
        try:
            run_agent_workflow(db, agent_type="data_quality")
        except AgentWorkflowExecutionError as exc:
            assert "kaboom" in str(exc)
        else:
            raise AssertionError("Expected AgentWorkflowExecutionError")
    finally:
        agent_workflows.run_registered_agent = original

    runs = db.query(models.AgentRun).all()
    assert len(runs) == 1
    assert runs[0].status == "failed"
    assert "kaboom" in (runs[0].error_message or "")


def test_run_agent_manually_uses_workflow_path():
    from routers.agents import run_agent_manually

    db = object()

    import routers.agents as agents_router

    captured = {}

    def fake_run_agent_workflow(db_arg, *, agent_type, entity_type, entity_id, requested_by_user_id, input_payload):
        captured.update({
            "db": db_arg,
            "agent_type": agent_type,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "requested_by_user_id": requested_by_user_id,
            "input_payload": input_payload,
        })

        class FakeRun:
            id = 33

        return FakeRun()

    original_run_agent_workflow = agents_router.run_agent_workflow
    original_get_agent_run = agents_router.crud.get_agent_run
    agents_router.run_agent_workflow = fake_run_agent_workflow
    agents_router.crud.get_agent_run = lambda db_arg, run_id: {"id": run_id}
    try:
        response = run_agent_manually("data_quality", db)
    finally:
        agents_router.run_agent_workflow = original_run_agent_workflow
        agents_router.crud.get_agent_run = original_get_agent_run

    assert response == {"id": 33}
    assert captured == {
        "db": db,
        "agent_type": "data_quality",
        "entity_type": None,
        "entity_id": None,
        "requested_by_user_id": None,
        "input_payload": {},
    }


def test_agent_review_action_created_at_aliases_reviewed_at():
    reviewed_at = datetime(2026, 4, 19, 12, 30, 0)
    action = models.AgentReviewAction(action="approved", reviewed_at=reviewed_at)

    assert action.created_at == reviewed_at


def test_promote_due_followups_marks_sent_draft_and_suggestion_as_followup_due():
    from auth import User
    from agent_workflows import promote_due_followups

    db = make_db(
        User.__table__,
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
        entity_type="collaborator",
        entity_id=1,
        suggestion_type="missing_curriculum",
        severity="medium",
        status="sent",
        title="Richiedi curriculum",
        description="Serve curriculum",
        payload="{}",
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
        recipient_email="mario@example.com",
        recipient_name="Mario Rossi",
        subject="Richiesta curriculum",
        body="Test",
        status="sent",
        sent_at=datetime.utcnow() - timedelta(days=8),
    )
    db.add(draft)
    db.commit()

    due_count = promote_due_followups(db)

    db.refresh(draft)
    db.refresh(suggestion)
    assert due_count == 1
    assert draft.status == "followup_due"
    assert suggestion.status == "followup_due"


def test_mail_copy_accepts_generic_documentazione_for_curriculum_request():
    from ai_agents.llm import _is_mail_copy_acceptable

    accepted = _is_mail_copy_acceptable(
        context_label="missing_collaborator_data",
        body="Ciao Mario, per completare il profilo inviaci il curriculum aggiornato e la documentazione richiesta.",
        missing_fields=["curriculum"],
    )

    assert accepted is True


def test_mail_copy_rejects_identity_document_request_when_not_missing():
    from ai_agents.llm import _is_mail_copy_acceptable

    accepted = _is_mail_copy_acceptable(
        context_label="missing_collaborator_data",
        body="Ciao Mario, inviaci il curriculum aggiornato e il documento di identita.",
        missing_fields=["curriculum"],
    )

    assert accepted is False


def test_update_collaborator_reports_partita_iva_conflict():
    db = make_db(models.Collaborator.__table__)

    first = models.Collaborator(
        first_name="Mario",
        last_name="Rossi",
        email="mario@example.com",
        fiscal_code="RSSMRA80A01H501Z",
        partita_iva="12345678901",
    )
    second = models.Collaborator(
        first_name="Luigi",
        last_name="Verdi",
        email="luigi@example.com",
        fiscal_code="VRDLGU80A01H501Z",
    )
    db.add_all([first, second])
    db.commit()

    try:
        crud.update_collaborator(
            db,
            second.id,
            schemas.CollaboratorUpdate(partita_iva="12345678901"),
        )
    except ValueError as exc:
        assert "partita iva" in str(exc).lower()
    else:
        raise AssertionError("Expected partita IVA conflict")


def test_complete_agent_run_normalizes_naive_started_at():
    db = make_db(models.AgentRun.__table__)
    run = models.AgentRun(
        agent_type="mail_recovery",
        status="running",
        started_at=datetime(2026, 4, 19, 10, 30, 0),
    )
    db.add(run)
    db.commit()

    completed = crud.complete_agent_run(
        db,
        run.id,
        status="completed",
        items_processed=3,
        items_with_issues=1,
        suggestions_created=2,
    )

    assert completed is not None
    assert completed.status == "completed"
    assert completed.execution_time_ms is not None
    assert completed.execution_time_ms >= 0


def test_create_preventivo_retries_on_duplicate_number_conflict():
    db = make_db(models.DocumentCounter.__table__, models.Preventivo.__table__)
    existing = models.Preventivo(
        numero="PRV-2026-001",
        anno=2026,
        numero_progressivo=1,
        stato="bozza",
    )
    db.add(existing)
    db.commit()

    original = crud._next_preventivo_number
    original_get_preventivo = crud.get_preventivo
    calls = {"count": 0}

    def fake_next_preventivo_number(db_arg, anno):
        calls["count"] += 1
        if calls["count"] == 1:
            return anno, 1, f"PRV-{anno}-001"
        return anno, 2, f"PRV-{anno}-002"

    crud._next_preventivo_number = fake_next_preventivo_number
    crud.get_preventivo = lambda db_arg, preventivo_id: db_arg.query(models.Preventivo).filter(models.Preventivo.id == preventivo_id).first()
    try:
        created = crud.create_preventivo(
            db,
            schemas.PreventivoCreate(oggetto="Retry preventivo"),
        )
    finally:
        crud._next_preventivo_number = original
        crud.get_preventivo = original_get_preventivo

    assert created.numero == "PRV-2026-002"
    assert created.numero_progressivo == 2
    assert calls["count"] == 2


def test_document_counter_generates_sequential_numbers():
    db = make_db(models.DocumentCounter.__table__, models.Preventivo.__table__)

    original_get_preventivo = crud.get_preventivo
    crud.get_preventivo = lambda db_arg, preventivo_id: db_arg.query(models.Preventivo).filter(models.Preventivo.id == preventivo_id).first()
    try:
        first = crud.create_preventivo(db, schemas.PreventivoCreate(oggetto="Uno"))
        second = crud.create_preventivo(db, schemas.PreventivoCreate(oggetto="Due"))
    finally:
        crud.get_preventivo = original_get_preventivo

    counter = db.query(models.DocumentCounter).filter(
        models.DocumentCounter.document_type == "preventivo",
        models.DocumentCounter.anno == first.anno,
    ).first()

    assert first.numero_progressivo == 1
    assert second.numero_progressivo == 2
    assert counter is not None
    assert counter.last_number == 2


def test_agent_run_uses_agent_metadata_column():
    db = make_db(models.AgentRun.__table__)

    run = models.AgentRun(
        agent_type="mail_recovery",
        status="running",
        metadata_json='{"source":"test"}',
    )
    db.add(run)
    db.commit()

    row = db.execute(text("SELECT agent_metadata FROM agent_runs WHERE id = :run_id"), {"run_id": run.id}).fetchone()
    assert row is not None
    assert row[0] == '{"source":"test"}'


def test_create_attendance_returns_assignment_range_error_before_overlap():
    db = make_db(
        models.Collaborator.__table__,
        models.Project.__table__,
        models.Assignment.__table__,
        models.Attendance.__table__,
    )

    collaborator = models.Collaborator(
        first_name="Mario",
        last_name="Rossi",
        email="attendance@example.com",
        fiscal_code="RSSMRA80A01H501A",
    )
    project = models.Project(name="Progetto Test", status="active")
    db.add_all([collaborator, project])
    db.commit()

    assignment = models.Assignment(
        collaborator_id=collaborator.id,
        project_id=project.id,
        role="Docente",
        assigned_hours=10,
        start_date=datetime(2026, 4, 1, 0, 0, 0),
        end_date=datetime(2026, 4, 10, 0, 0, 0),
        hourly_rate=50,
    )
    db.add(assignment)
    db.commit()

    existing = models.Attendance(
        collaborator_id=collaborator.id,
        project_id=project.id,
        assignment_id=assignment.id,
        date=datetime(2026, 4, 15, 0, 0, 0),
        start_time=datetime(2026, 4, 15, 9, 0, 0),
        end_time=datetime(2026, 4, 15, 13, 0, 0),
        hours=4,
    )
    db.add(existing)
    db.commit()

    try:
        crud.create_attendance(
            db,
            schemas.AttendanceCreate(
                collaborator_id=collaborator.id,
                project_id=project.id,
                assignment_id=assignment.id,
                date=datetime(2026, 4, 15, 0, 0, 0, tzinfo=timezone.utc),
                start_time=datetime(2026, 4, 15, 9, 30, 0, tzinfo=timezone.utc),
                end_time=datetime(2026, 4, 15, 11, 30, 0, tzinfo=timezone.utc),
                hours=2,
            ),
        )
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected assignment range error")

    assert "non rientra nel periodo" in message


def test_create_piano_finanziario_commits_audit_before_non_blocking_event():
    db = make_db(
        models.Project.__table__,
        models.AziendaCliente.__table__,
        models.ModuloFormativo.__table__,
        models.PianoFinanziario.__table__,
        models.VocePianoFinanziario.__table__,
        models.AuditLog.__table__,
    )
    project = models.Project(
        name="PF Test",
        status="active",
        ente_erogatore="Formazienda",
    )
    db.add(project)
    db.commit()

    original_emit = crud._emit_piano_budget_threshold_event
    original_get_project = crud.get_project
    original_get_piano_finanziario = crud.get_piano_finanziario
    crud.get_project = lambda db_arg, project_id: db_arg.query(models.Project).filter(models.Project.id == project_id).first()
    crud.get_piano_finanziario = lambda db_arg, piano_id: db_arg.query(models.PianoFinanziario).filter(models.PianoFinanziario.id == piano_id).first()
    crud._emit_piano_budget_threshold_event = lambda db_arg, piano_obj: (_ for _ in ()).throw(RuntimeError("webhook down"))
    try:
        created = crud.create_piano_finanziario(
            db,
            schemas.PianoFinanziarioCreate(
                progetto_id=project.id,
                nome="Piano Test",
                tipo_fondo="formazienda",
                budget_totale=1000.0,
                data_inizio=datetime(2026, 4, 1, 0, 0, 0),
                data_fine=datetime(2026, 4, 30, 0, 0, 0),
            ),
        )
    finally:
        crud._emit_piano_budget_threshold_event = original_emit
        crud.get_project = original_get_project
        crud.get_piano_finanziario = original_get_piano_finanziario

    assert created is not None
    assert db.query(models.PianoFinanziario).count() == 1
    assert db.query(models.VocePianoFinanziario).count() > 0
    audit_logs = db.query(models.AuditLog).filter(models.AuditLog.entity == "piano_finanziario").all()
    assert len(audit_logs) == 1
    assert audit_logs[0].action == "create"


def test_update_piano_finanziario_commits_data_and_audit_once_before_event():
    db = make_db(
        models.Project.__table__,
        models.AziendaCliente.__table__,
        models.ModuloFormativo.__table__,
        models.PianoFinanziario.__table__,
        models.VocePianoFinanziario.__table__,
        models.AuditLog.__table__,
    )
    project = models.Project(
        name="PF Update Test",
        status="active",
        ente_erogatore="Formazienda",
    )
    db.add(project)
    db.commit()

    piano = models.PianoFinanziario(
        progetto_id=project.id,
        nome="Prima",
        tipo_fondo="formazienda",
        anno=2026,
        ente_erogatore="Formazienda",
        avviso="",
        budget_totale=1000.0,
        budget_approvato=1000.0,
        budget_utilizzato=0.0,
        budget_rimanente=1000.0,
        data_inizio=datetime(2026, 4, 1, 0, 0, 0),
        data_fine=datetime(2026, 4, 30, 0, 0, 0),
        stato="bozza",
    )
    db.add(piano)
    db.commit()

    original_emit = crud._emit_piano_budget_threshold_event
    original_get_piano_finanziario = crud.get_piano_finanziario
    crud.get_piano_finanziario = lambda db_arg, piano_id: db_arg.query(models.PianoFinanziario).filter(models.PianoFinanziario.id == piano_id).first()
    crud._emit_piano_budget_threshold_event = lambda db_arg, piano_obj: (_ for _ in ()).throw(RuntimeError("webhook down"))
    try:
        updated = crud.update_piano_finanziario(
            db,
            piano.id,
            schemas.PianoFinanziarioUpdate(
                nome="Dopo",
                budget_utilizzato=250.0,
                note="audit test",
            ),
        )
    finally:
        crud._emit_piano_budget_threshold_event = original_emit
        crud.get_piano_finanziario = original_get_piano_finanziario

    assert updated is not None
    assert updated.nome == "Dopo"
    assert float(updated.budget_utilizzato) == 250.0
    audit_logs = db.query(models.AuditLog).filter(models.AuditLog.entity == "piano_finanziario").all()
    assert len(audit_logs) == 1
    assert audit_logs[0].action == "update"
