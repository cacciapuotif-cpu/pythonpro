"""AGENT-11: robustezza layer LLM.

- retry max 2 con backoff breve su timeout/5xx/output malformato
- output validato con schema Pydantic (MailCopySchema, DocumentResultSchema)
- fallback: mail -> None (testo deterministico del chiamante); documenti ->
  manual_review (valid=None), mai persi
- prompt versionati e registrati (DocumentResult.prompt_version)
- log strutturato per chiamata senza PII/contenuto documenti
"""
from __future__ import annotations

import json
import logging
from unittest.mock import patch

import httpx
import pytest

from ai_agents import llm as llm_module
from ai_agents.llm import call_llm_with_retry
from ai_agents.llm_schemas import DocumentResultSchema, MailCopySchema


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(llm_module.time, "sleep", lambda seconds: None)


# --- Schemi ---------------------------------------------------------------


def test_mail_copy_schema_rejects_missing_fields():
    with pytest.raises(Exception):
        MailCopySchema.model_validate({"subject": "solo oggetto"})
    with pytest.raises(Exception):
        MailCopySchema.model_validate({"subject": "", "body": "testo"})
    ok = MailCopySchema.model_validate({"subject": " Oggetto ", "body": "Testo"})
    assert ok.subject == "Oggetto"


def test_document_result_schema_clamps_confidence():
    ok = DocumentResultSchema.model_validate({"valid": True, "doc_type": "durc", "confidence": 3.5})
    assert ok.confidence == 1.0
    with pytest.raises(Exception):
        DocumentResultSchema.model_validate({"confidence": "alta"})
    with pytest.raises(Exception):
        DocumentResultSchema.model_validate({"issues": "non una lista"})


# --- Retry ----------------------------------------------------------------


def test_retry_then_success_on_timeout():
    calls = {"count": 0}

    def flaky():
        calls["count"] += 1
        if calls["count"] < 3:
            raise httpx.ConnectTimeout("timeout")
        return {"ok": True}

    result = call_llm_with_retry(flaky, agent="test_agent", prompt_version="v1")
    assert result == {"ok": True}
    assert calls["count"] == 3  # 1 tentativo + 2 retry


def test_retry_exhausted_raises():
    calls = {"count": 0}

    def always_timeout():
        calls["count"] += 1
        raise httpx.ConnectTimeout("timeout")

    with pytest.raises(httpx.ConnectTimeout):
        call_llm_with_retry(always_timeout, agent="test_agent")
    assert calls["count"] == 3


def test_no_retry_on_4xx():
    calls = {"count": 0}
    request = httpx.Request("POST", "http://llm.local")
    response = httpx.Response(status_code=401, request=request)

    def unauthorized():
        calls["count"] += 1
        raise httpx.HTTPStatusError("401", request=request, response=response)

    with pytest.raises(httpx.HTTPStatusError):
        call_llm_with_retry(unauthorized, agent="test_agent")
    assert calls["count"] == 1


def test_retry_on_malformed_output():
    calls = {"count": 0}

    def malformed_then_ok():
        calls["count"] += 1
        if calls["count"] == 1:
            raise ValueError("Output LLM non conforme")
        return {"ok": True}

    result = call_llm_with_retry(malformed_then_ok, agent="test_agent")
    assert result == {"ok": True}
    assert calls["count"] == 2


# --- Fallback mail ----------------------------------------------------------


def test_mail_fallback_when_retry_exhausted(monkeypatch):
    from ai_agents.llm import generate_mail_recovery_copy

    monkeypatch.setenv("AI_AGENT_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("AI_AGENT_LLM_MODEL", "qwen-test")

    with patch.object(llm_module, "_call_ollama", side_effect=httpx.ConnectTimeout("timeout")) as mock_call:
        result = generate_mail_recovery_copy(
            collaborator_name="Mario Rossi",
            collaborator_email="mario@example.com",
            context_label="missing_collaborator_data",
            requested_tone="formale",
            fallback_subject="Richiesta dati",
            fallback_body="Corpo deterministico",
            missing_fields=["codice fiscale"],
        )

    assert result is None  # il chiamante usa il testo deterministico
    assert mock_call.call_count == 3


def test_mail_result_has_prompt_version(monkeypatch):
    from ai_agents.llm import AgentLlmResult, generate_mail_recovery_copy

    monkeypatch.setenv("AI_AGENT_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("AI_AGENT_LLM_MODEL", "qwen-test")

    fake = AgentLlmResult(
        subject="Dati mancanti",
        body="Gentile Mario Rossi, manca il codice fiscale. Risponda inviando il dato.",
        provider="ollama",
    )
    with patch.object(llm_module, "_call_ollama", return_value=fake):
        result = generate_mail_recovery_copy(
            collaborator_name="Mario Rossi",
            collaborator_email="mario@example.com",
            context_label="missing_collaborator_data",
            requested_tone="formale",
            fallback_subject="s",
            fallback_body="b",
            missing_fields=["codice fiscale"],
        )

    assert result is not None
    assert result.prompt_version == "mail_recovery_v1"


# --- Fallback documenti ------------------------------------------------------


def test_document_malformed_output_goes_to_manual_review(monkeypatch):
    from ai_agents.document_processor import DocumentProcessor

    monkeypatch.setenv("AI_AGENT_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("AI_AGENT_LLM_MODEL", "qwen-test")

    calls = {"count": 0}

    def malformed(**kwargs):
        calls["count"] += 1
        return {"confidence": "altissima", "issues": "non lista"}

    with patch("ai_agents.llm.call_ollama_json", side_effect=malformed):
        result = DocumentProcessor().process(
            "/tmp/finto.pdf",
            entity_name="Mario Rossi",
            expected_doc_type="documento_identita",
        )

    assert calls["count"] == 3  # retry esauriti
    assert result.valid is None  # manual review, documento mai perso
    assert result.doc_type == "documento_identita"
    assert result.prompt_version == "document_processor_v1"


def test_document_prompt_version_recorded_on_success(monkeypatch):
    from ai_agents.document_processor import DocumentProcessor

    monkeypatch.setenv("AI_AGENT_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("AI_AGENT_LLM_MODEL", "qwen-test")

    good = {
        "valid": True,
        "doc_type": "documento_identita",
        "confidence": 0.9,
        "issues": [],
        "extracted_data": {"codice_fiscale": "RSSMRA80A01H501U"},
    }
    with patch("ai_agents.llm.call_ollama_json", return_value=good):
        result = DocumentProcessor().process(
            "/tmp/finto.pdf",
            entity_name="Mario Rossi",
            expected_doc_type="documento_identita",
        )

    assert result.prompt_version == "document_processor_v1"
    assert result.valid is True
    assert result.confidence == 0.9


# --- Log senza PII -----------------------------------------------------------


def test_llm_call_log_has_no_content(monkeypatch, caplog):
    from ai_agents.document_processor import DocumentProcessor

    monkeypatch.setenv("AI_AGENT_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("AI_AGENT_LLM_MODEL", "qwen-test")

    secret_cf = "RSSMRA80A01H501U"
    good = {
        "valid": True,
        "doc_type": "documento_identita",
        "confidence": 0.9,
        "issues": [],
        "extracted_data": {"codice_fiscale": secret_cf},
    }
    with caplog.at_level(logging.INFO, logger="ai_agents.llm"):
        with patch("ai_agents.llm.call_ollama_json", return_value=good):
            DocumentProcessor().process(
                "/tmp/finto.pdf",
                entity_name="Mario Rossi",
                expected_doc_type="documento_identita",
            )

    llm_logs = [record.getMessage() for record in caplog.records if "agent_llm_call" in record.getMessage()]
    assert llm_logs, "atteso almeno un log strutturato agent_llm_call"
    for message in llm_logs:
        assert secret_cf not in message
        assert "Mario Rossi" not in message
        payload = json.loads(message.split("agent_llm_call ", 1)[1])
        assert payload["agent"] == "document_processor"
        assert payload["prompt_version"] == "document_processor_v1"
        assert payload["outcome"] in ("ok", "retry", "failed")


# --- needs_careful_review -----------------------------------------------------


def test_low_confidence_suggestion_flagged_high_priority():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    import models
    from database import Base
    from services.agent_apply_service import build_change, create_field_update_suggestion

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        models.AgentRun.__table__,
        models.AgentSuggestion.__table__,
    ])
    db = Session(engine)

    suggestion = create_field_update_suggestion(
        db,
        entity_type="collaborator",
        entity_id=1,
        entity_name="Mario Rossi",
        changes=[build_change("phone", None, "3331112233", 0.4)],
        confidence=0.4,
    )

    assert suggestion.priority == "high"
    payload = json.loads(suggestion.auto_fix_payload)
    assert payload["needs_careful_review"] is True


def test_normal_confidence_suggestion_stays_medium():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    import models
    from database import Base
    from services.agent_apply_service import build_change, create_field_update_suggestion

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        models.AgentRun.__table__,
        models.AgentSuggestion.__table__,
    ])
    db = Session(engine)

    suggestion = create_field_update_suggestion(
        db,
        entity_type="collaborator",
        entity_id=1,
        entity_name="Mario Rossi",
        changes=[build_change("phone", None, "3331112233", 0.9)],
        confidence=0.9,
    )

    assert suggestion.priority == "medium"
    payload = json.loads(suggestion.auto_fix_payload)
    assert payload["needs_careful_review"] is False
