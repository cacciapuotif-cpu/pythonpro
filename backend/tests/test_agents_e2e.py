"""A6 — Test end-to-end dei 6 flussi canonici della piattaforma agenti.

Flusso canonico: trigger → AgentRun → AgentSuggestion → [Draft] → revisione
umana → AgentReviewAction + audit → stato. Zero side effect senza
approvazione umana.

1. mail_recovery: proposta → bozza → approvazione umana → invio (mock SMTP)
2. intake email documento valido: IMAP → proposta field_diff → apply-fix reale con audit
3. intake email documento invalido: reply come bozza, nessun invio
4. validazione umana documento → contract_agent via workflow → contract_ready
5. certification via workflow: attestato_pronto proposto, nessuna scrittura su allievo
6. kill switch globale: nessun run, nessun side effect

Mock: smtplib.SMTP (mai rete), IMAP (fixture messaggi), LLM
(monkeypatch ai_agents.llm.call_ollama_json).
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from email.message import EmailMessage
from unittest.mock import MagicMock, patch

import pytest
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
        models.Project.__table__,
        models.Assignment.__table__,
        models.Allievo.__table__,
        models.AllievoProject.__table__,
        models.DocumentoRichiesto.__table__,
        models.EmailInboxItem.__table__,
        models.AgentRun.__table__,
        models.AgentSuggestion.__table__,
        models.AgentCommunicationDraft.__table__,
        models.AgentReviewAction.__table__,
        models.AuditLog.__table__,
        models.SecurityAuditLog.__table__,
    ])
    return Session(engine)


def add_collaborator(db, **overrides) -> models.Collaborator:
    values = {
        "first_name": "Mario",
        "last_name": "Rossi",
        "email": "mario@example.com",
        "fiscal_code": "RSSMRA80A01H501U",
        "is_active": True,
        "consenso_email_agenti": True,
    }
    values.update(overrides)
    collaborator = models.Collaborator(**values)
    db.add(collaborator)
    db.commit()
    return collaborator


def pdf_message(message_id: str = "<e2e-1@example.com>") -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = "Mario Rossi <mario@example.com>"
    msg["Subject"] = "Documento identita"
    msg["Message-ID"] = message_id
    msg.set_content("In allegato il documento.")
    msg.add_attachment(b"%PDF-1.4 fake", maintype="application", subtype="pdf", filename="carta_identita.pdf")
    return msg


def fake_imap_for(msg: EmailMessage):
    imap = MagicMock()
    imap.fetch.return_value = ("OK", [(b"1 (RFC822)", msg.as_bytes())])
    return imap


def run_inbox_worker(msg: EmailMessage, db, tmp_path):
    from services.email_inbox_worker import EmailInboxWorker

    worker = EmailInboxWorker(
        imap_user="inbox@example.com",
        imap_password="x",
        upload_base_dir=tmp_path,
    )
    worker._process_single_message(fake_imap_for(msg), b"1", db)


# --- Flusso 1: mail_recovery, bozza -> approvazione umana -> invio -----------


def test_flow_mail_recovery_draft_then_human_approval_sends(monkeypatch):
    from agent_workflows import apply_workflow_action, run_agent_workflow

    monkeypatch.setenv("ENABLE_EMAIL", "true")
    monkeypatch.setenv("SMTP_HOST", "smtp.test.local")
    monkeypatch.setenv("SMTP_PORT", "25")
    monkeypatch.delenv("AI_AGENT_LLM_PROVIDER", raising=False)

    db = make_db()
    collaborator = add_collaborator(db)

    smtp_instance = MagicMock()
    with patch("agent_workflows.smtplib.SMTP") as smtp_cls:
        smtp_cls.return_value.__enter__.return_value = smtp_instance

        run = run_agent_workflow(
            db,
            agent_type="mail_recovery",
            entity_type="collaborator",
            entity_id=collaborator.id,
        )

        # Nessun invio in fase di proposta.
        smtp_cls.assert_not_called()

        draft = db.query(models.AgentCommunicationDraft).filter(
            models.AgentCommunicationDraft.channel == "email"
        ).first()
        assert draft is not None and draft.status == "draft"
        suggestion = db.query(models.AgentSuggestion).filter_by(id=draft.suggestion_id).one()
        assert suggestion.status == "pending"

        # Approvazione umana: ora (e solo ora) parte l'invio.
        apply_workflow_action(
            db,
            suggestion_id=suggestion.id,
            action="approve_email",
            reviewed_by_user_id=None,
        )

        assert smtp_instance.send_message.called

    db.refresh(draft)
    db.refresh(suggestion)
    assert draft.status == "sent"
    assert draft.sent_at is not None
    assert suggestion.status == "sent"
    review_actions = db.query(models.AgentReviewAction).filter_by(suggestion_id=suggestion.id).all()
    assert any(action.action == "approve_email" for action in review_actions)
    audit_rows = db.query(models.AuditLog).all()
    assert audit_rows, "atteso audit log sul flusso di approvazione"
    assert run.status == "completed"


# --- Flusso 2: intake documento valido -> proposta -> apply-fix con audit ----


def test_flow_intake_valid_document_proposal_then_real_apply(monkeypatch, tmp_path):
    from services.agent_apply_service import apply_field_update_suggestion

    monkeypatch.setenv("AI_AGENT_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("AI_AGENT_LLM_MODEL", "qwen-test")

    db = make_db()
    collaborator = add_collaborator(db, phone=None)

    llm_payload = {
        "valid": True,
        "doc_type": "documento_identita",
        "confidence": 0.9,
        "issues": [],
        "extracted_data": {"phone": "3331112233"},
    }
    with patch("ai_agents.llm.call_ollama_json", return_value=llm_payload):
        run_inbox_worker(pdf_message(), db, tmp_path)

    # Documento mai auto-validato: resta caricato per revisione umana.
    documento = db.query(models.DocumentoRichiesto).one()
    assert documento.stato == "caricato"

    # Collaboratore NON toccato: solo proposta con diff.
    db.refresh(collaborator)
    assert collaborator.phone is None
    suggestion = db.query(models.AgentSuggestion).filter_by(
        suggestion_type="document_field_updates"
    ).one()
    assert suggestion.status == "pending"
    payload = json.loads(suggestion.auto_fix_payload)
    proposed_fields = {change["field"] for change in payload["changes"]}
    assert "phone" in proposed_fields

    # Revisione umana: apply-fix reale con audit per campo.
    result = apply_field_update_suggestion(db, suggestion, user_id=None)

    assert "phone" in result["applied"]
    db.refresh(collaborator)
    assert collaborator.phone == "3331112233"
    audit_rows = db.query(models.AuditLog).all()
    assert audit_rows, "atteso audit log per campo applicato"


# --- Flusso 3: intake documento invalido -> reply bozza, zero invii ----------


def test_flow_intake_invalid_document_reply_stays_draft(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_AGENT_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("AI_AGENT_LLM_MODEL", "qwen-test")

    db = make_db()
    add_collaborator(db)

    llm_payload = {
        "valid": False,
        "doc_type": "documento_identita",
        "confidence": 0.9,
        "issues": ["Documento illeggibile"],
        "extracted_data": {},
    }
    with patch("ai_agents.llm.call_ollama_json", return_value=llm_payload), \
         patch("agent_workflows.smtplib.SMTP") as smtp_cls, \
         patch("services.inbox_reply_composer.InboxReplyComposer.send_reply") as send_reply_mock:
        run_inbox_worker(pdf_message("<e2e-3@example.com>"), db, tmp_path)

    smtp_cls.assert_not_called()
    send_reply_mock.assert_not_called()

    draft = db.query(models.AgentCommunicationDraft).one()
    assert draft.status == "draft"
    assert draft.sent_at is None
    assert "Documento illeggibile" in draft.body
    item = db.query(models.EmailInboxItem).one()
    assert item.reply_sent is False


# --- Flusso 4: validazione umana documento -> contract_agent via workflow ----


def test_flow_human_validation_triggers_contract_agent_workflow():
    from routers.documenti_richiesti import DocumentoReviewPayload, valida_documento

    db = make_db()
    collaborator = add_collaborator(db)
    project = models.Project(name="Progetto E2E", status="active")
    db.add(project)
    db.flush()
    assignment = models.Assignment(
        collaborator_id=collaborator.id,
        project_id=project.id,
        role="Docente",
        assigned_hours=40.0,
        start_date=datetime(2026, 1, 1),
        end_date=datetime(2026, 12, 31),
        hourly_rate=50.0,
        is_active=True,
    )
    db.add(assignment)
    documento_ok = models.DocumentoRichiesto(
        collaboratore_id=collaborator.id,
        tipo_documento="curriculum",
        obbligatorio=True,
        stato="validato",
    )
    documento_da_validare = models.DocumentoRichiesto(
        collaboratore_id=collaborator.id,
        tipo_documento="documento_identita",
        obbligatorio=True,
        stato="caricato",
    )
    db.add_all([documento_ok, documento_da_validare])
    db.commit()

    valida_documento(
        documento_da_validare.id,
        DocumentoReviewPayload(validato_da="operatore"),
        db,
    )

    db.refresh(documento_da_validare)
    assert documento_da_validare.stato == "validato"

    contract_runs = db.query(models.AgentRun).filter(
        models.AgentRun.agent_type == "contract_agent"
    ).all()
    assert len(contract_runs) == 1
    assert contract_runs[0].status == "completed"
    payload = json.loads(contract_runs[0].input_payload or "{}")
    assert payload.get("trigger_mode") == "automatic"

    suggestion = db.query(models.AgentSuggestion).filter_by(
        suggestion_type="contract_ready"
    ).one()
    assert suggestion.status == "pending"
    assert suggestion.entity_id == assignment.id


# --- Flusso 5: certification via workflow, nessuna scrittura sull'allievo ----


def test_flow_certification_proposes_without_touching_allievo():
    from agent_workflows import run_agent_workflow

    db = make_db()
    collaborator = add_collaborator(db)
    project = models.Project(name="Corso E2E", status="active")
    allievo = models.Allievo(nome="Anna", cognome="Verdi")
    db.add_all([project, allievo])
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
    link = models.AllievoProject(
        allievo_id=allievo.id,
        project_id=project.id,
        ore_frequentate=80.0,
    )
    db.add(link)
    db.commit()

    run = run_agent_workflow(db, agent_type="certification", auto_mode=True)

    assert run.status == "completed"
    suggestion = db.query(models.AgentSuggestion).filter_by(
        suggestion_type="attestato_pronto"
    ).one()
    assert suggestion.status == "pending"
    # Nessun side effect: l'attestato NON risulta emesso finche' un umano non agisce.
    db.refresh(link)
    assert bool(link.attestato_emesso) is False


# --- Flusso 6: kill switch globale, zero run e zero side effect --------------


def test_flow_global_kill_switch_blocks_everything(monkeypatch):
    import arq_worker
    from agent_workflows import run_agent_workflow

    monkeypatch.setenv("AGENTS_ENABLED", "false")

    db = make_db()
    collaborator = add_collaborator(db)

    with patch("agent_workflows.smtplib.SMTP") as smtp_cls:
        with pytest.raises(ValueError):
            run_agent_workflow(
                db,
                agent_type="mail_recovery",
                entity_type="collaborator",
                entity_id=collaborator.id,
            )
        for cron_name in (
            "run_mail_recovery_cron",
            "run_contract_agent_cron",
            "run_certification_agent_cron",
            "poll_email_inbox",
            "data_retention_cleanup",
        ):
            result = asyncio.run(getattr(arq_worker, cron_name)({}))
            assert result["status"] == "skipped", cron_name

    smtp_cls.assert_not_called()
    assert db.query(models.AgentRun).count() == 0
    assert db.query(models.AgentSuggestion).count() == 0
    assert db.query(models.AgentCommunicationDraft).count() == 0
