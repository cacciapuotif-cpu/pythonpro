"""AGENT-04: documenti e anagrafiche solo per proposta.

L'intake documenti non valida piu' i documenti e non scrive campi
collaboratore/azienda: produce un AgentSuggestion "document_field_updates"
con diff campo per campo. L'applicazione reale avviene solo via apply-fix
(agent_apply_service) con whitelist, ricontrollo valori attuali e audit.
Il contract_agent parte solo dalla validazione umana del documento.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

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
        models.AziendaCliente.__table__,
        models.AgentRun.__table__,
        models.AgentSuggestion.__table__,
        models.AgentReviewAction.__table__,
        models.AuditLog.__table__,
    ])
    return Session(engine)


def make_collaborator(db, **overrides):
    data = dict(
        id=1,
        first_name="Mario",
        last_name="Rossi",
        email="mario@example.com",
        fiscal_code="RSSMRA80A01H501Z",
    )
    data.update(overrides)
    collab = models.Collaborator(**data)
    db.add(collab)
    db.commit()
    return collab


def intake_result(**overrides):
    from ai_agents.document_processor import DocumentResult

    data = dict(
        valid=True,
        doc_type="curriculum",
        issues=[],
        extracted_data={
            "profilo_professionale": "Project manager digitale",
            "skills": ["Python", "Gestione progetti"],
            "fiscal_code": "RSSMRA80A01H501Z",
            "phone": "3331234567",
        },
        confidence=0.9,
    )
    data.update(overrides)
    return DocumentResult(**data)


def run_intake(db, result, *, entity_type="collaborator", entity_id=1, expected="curriculum"):
    from services.document_intake_agent import DocumentIntakeAgent

    return DocumentIntakeAgent().apply_document_result(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        attachment_path="/tmp/doc.pdf",
        attachment_name="doc.pdf",
        result=result,
        expected_doc_type=expected,
    )


class TestIntakeProposalOnly:

    def test_llm_valid_result_does_not_touch_collaborator(self):
        db = make_db()
        make_collaborator(db)

        outcome = run_intake(db, intake_result())

        collab = db.query(models.Collaborator).filter_by(id=1).first()
        assert collab.fiscal_code == "RSSMRA80A01H501Z"
        assert collab.phone is None
        assert collab.profilo_professionale is None
        assert collab.curriculum_path is None
        assert collab.competenze_principali is None

        assert outcome.suggestion_id is not None
        suggestion = db.query(models.AgentSuggestion).filter_by(id=outcome.suggestion_id).first()
        assert suggestion.suggestion_type == "document_field_updates"
        assert suggestion.status == "pending"
        assert suggestion.auto_fix_available is True
        assert "phone" in outcome.proposed_fields
        assert "profilo_professionale" in outcome.proposed_fields
        # fiscal_code estratto identico al valore attuale: nessuna proposta
        assert "fiscal_code" not in outcome.proposed_fields

    def test_company_document_does_not_touch_azienda(self):
        db = make_db()
        db.add(models.AziendaCliente(
            id=55,
            ragione_sociale="Azienda Demo",
            partita_iva="12345678901",
            attivo=True,
        ))
        db.commit()

        result = intake_result(
            doc_type="visura_camerale",
            extracted_data={
                "ragione_sociale": "Azienda Demo SRL",
                "codice_fiscale": "12345678901",
                "indirizzo": "Via Roma 1",
                "provincia": "mi",
                "pec": "pec@aziendademo.it",
            },
        )
        outcome = run_intake(db, result, entity_type="azienda_cliente", entity_id=55, expected="visura_camerale")

        refreshed = db.query(models.AziendaCliente).filter_by(id=55).first()
        assert refreshed.ragione_sociale == "Azienda Demo"
        assert refreshed.indirizzo is None
        assert refreshed.pec is None

        assert outcome.suggestion_id is not None
        payload = json.loads(
            db.query(models.AgentSuggestion).filter_by(id=outcome.suggestion_id).first().auto_fix_payload
        )
        proposed = {change["field"]: change["proposed"] for change in payload["changes"]}
        assert proposed["ragione_sociale"] == "Azienda Demo SRL"
        assert proposed["provincia"] == "MI"

    def test_confidence_override_removed(self):
        from ai_agents.document_processor import _apply_confidence_decision, _parse_llm_result_dict

        # valid=False con confidence alta e zero issues: resta False (niente override False->True)
        parsed = _parse_llm_result_dict(
            {"valid": False, "confidence": 0.9, "issues": [], "extracted_data": {}},
            "curriculum",
        )
        assert parsed.valid is False
        decided = _apply_confidence_decision(parsed)
        assert decided.valid is False

        # valid=None con confidence alta: nessuna auto-validazione
        undecided = _parse_llm_result_dict(
            {"valid": None, "confidence": 0.95, "issues": [], "extracted_data": {}},
            "curriculum",
        )
        assert _apply_confidence_decision(undecided).valid is None

    def test_diff_payload_structure(self):
        db = make_db()
        make_collaborator(db)

        outcome = run_intake(db, intake_result())

        suggestion = db.query(models.AgentSuggestion).filter_by(id=outcome.suggestion_id).first()
        payload = json.loads(suggestion.auto_fix_payload)
        assert payload["kind"] == "field_diff"
        assert payload["entity_type"] == "collaborator"
        assert payload["entity_id"] == 1
        assert payload["changes"]
        for change in payload["changes"]:
            assert set(change.keys()) == {"field", "current", "proposed", "confidence"}
            assert change["confidence"] == 0.9

        by_field = {change["field"]: change for change in payload["changes"]}
        assert by_field["phone"]["current"] is None
        assert by_field["phone"]["proposed"] == "3331234567"

    def test_document_stays_caricato_until_human_validation(self):
        db = make_db()
        make_collaborator(db)

        outcome = run_intake(db, intake_result(valid=True))

        documento = db.query(models.DocumentoRichiesto).filter_by(id=outcome.documento_richiesto_id).first()
        assert documento.stato == "caricato"
        assert documento.validato_da is None
        assert documento.validato_il is None

        # anche con classificazione LLM "non valido" il documento resta caricato per revisione umana
        db2 = make_db()
        make_collaborator(db2)
        outcome2 = run_intake(db2, intake_result(valid=False, issues=["documento scaduto"]))
        documento2 = db2.query(models.DocumentoRichiesto).filter_by(id=outcome2.documento_richiesto_id).first()
        assert documento2.stato == "caricato"
        assert "scaduto" in documento2.note_operatore

    def test_contract_trigger_on_human_validation_only(self):
        db = make_db()
        make_collaborator(db)

        with patch("agent_workflows.run_agent_workflow") as mock_workflow:
            outcome = run_intake(db, intake_result(valid=True))
            mock_workflow.assert_not_called()

        from routers.documenti_richiesti import DocumentoReviewPayload, valida_documento

        with patch("agent_workflows.run_agent_workflow", return_value=MagicMock(id=1, status="completed")) as mock_workflow:
            valida_documento(
                outcome.documento_richiesto_id,
                DocumentoReviewPayload(validato_da="operatore"),
                db,
            )
            mock_workflow.assert_called_once()
            assert mock_workflow.call_args.kwargs["agent_type"] == "contract_agent"

        documento = db.query(models.DocumentoRichiesto).filter_by(id=outcome.documento_richiesto_id).first()
        assert documento.stato == "validato"
        assert documento.validato_da == "operatore"


class TestApplyFixReal:

    def _make_suggestion(self, db, changes, *, entity_type="collaborator", entity_id=1):
        from services.agent_apply_service import create_field_update_suggestion

        return create_field_update_suggestion(
            db,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name="Mario Rossi",
            changes=changes,
            source={"doc_type": "curriculum"},
            confidence=0.9,
        )

    def test_apply_fix_applies_diff_with_audit(self):
        from services.agent_apply_service import apply_field_update_suggestion, build_change

        db = make_db()
        make_collaborator(db)
        suggestion = self._make_suggestion(db, [
            build_change("profilo_professionale", None, "Project manager digitale", 0.9),
            build_change("phone", None, "3331234567", 0.9),
        ])

        result = apply_field_update_suggestion(db, suggestion, user_id=7)

        assert sorted(result["applied"]) == ["phone", "profilo_professionale"]
        assert result["skipped"] == []

        collab = db.query(models.Collaborator).filter_by(id=1).first()
        assert collab.profilo_professionale == "Project manager digitale"
        assert collab.phone == "3331234567"

        audit_rows = db.query(models.AuditLog).filter_by(action="agent_apply_fix").all()
        assert len(audit_rows) == 2
        assert all(row.user_id == 7 for row in audit_rows)
        audited_fields = {list(json.loads(row.new_value).keys())[0] for row in audit_rows}
        assert audited_fields == {"profilo_professionale", "phone"}

    def test_apply_fix_skips_stale_values(self):
        from services.agent_apply_service import apply_field_update_suggestion, build_change

        db = make_db()
        collab = make_collaborator(db)
        suggestion = self._make_suggestion(db, [
            build_change("profilo_professionale", None, "Project manager digitale", 0.9),
            build_change("phone", None, "3331234567", 0.9),
        ])

        # il valore attuale cambia dopo la proposta -> campo saltato e segnalato
        collab.profilo_professionale = "Sviluppatore backend"
        db.commit()

        result = apply_field_update_suggestion(db, suggestion, user_id=None)

        assert result["applied"] == ["phone"]
        assert len(result["skipped"]) == 1
        skipped = result["skipped"][0]
        assert skipped["field"] == "profilo_professionale"
        assert "cambiato" in skipped["reason"]
        assert skipped["actual_current"] == "Sviluppatore backend"

        collab = db.query(models.Collaborator).filter_by(id=1).first()
        assert collab.profilo_professionale == "Sviluppatore backend"
        assert collab.phone == "3331234567"

    def test_apply_fix_rejects_non_whitelisted_fields(self):
        from services.agent_apply_service import apply_field_update_suggestion, build_change

        db = make_db()
        make_collaborator(db)
        suggestion = self._make_suggestion(db, [
            build_change("email", "mario@example.com", "attacker@evil.com", 0.9),
            build_change("is_active", "True", "False", 0.9),
        ])

        result = apply_field_update_suggestion(db, suggestion, user_id=None)

        assert result["applied"] == []
        assert {item["field"] for item in result["skipped"]} == {"email", "is_active"}
        collab = db.query(models.Collaborator).filter_by(id=1).first()
        assert collab.email == "mario@example.com"

    def test_apply_fix_requires_structured_payload(self):
        import pytest
        from services.agent_apply_service import apply_field_update_suggestion

        db = make_db()
        make_collaborator(db)
        run = models.AgentRun(agent_type="email_intake", status="completed")
        db.add(run)
        db.flush()
        suggestion = models.AgentSuggestion(
            run_id=run.id,
            suggestion_type="generic",
            status="pending",
            entity_type="collaborator",
            entity_id=1,
            title="Suggerimento legacy",
            auto_fix_available=True,
            auto_fix_payload=json.dumps({"hint": "not a field diff"}),
        )
        db.add(suggestion)
        db.commit()

        with pytest.raises(ValueError):
            apply_field_update_suggestion(db, suggestion, user_id=None)

    def test_apply_fix_resolves_pending_data_requests(self):
        from services.agent_apply_service import apply_field_update_suggestion, build_change

        db = make_db()
        make_collaborator(db)
        run = models.AgentRun(agent_type="data_quality", status="completed")
        db.add(run)
        db.flush()
        pending_request = models.AgentSuggestion(
            run_id=run.id,
            suggestion_type="request_missing_collaborator_data",
            status="pending",
            entity_type="collaborator",
            entity_id=1,
            title="Dati mancanti",
        )
        db.add(pending_request)
        db.commit()

        suggestion = self._make_suggestion(db, [
            build_change("phone", None, "3331234567", 0.9),
        ])
        apply_field_update_suggestion(db, suggestion, user_id=None)

        db.refresh(pending_request)
        assert pending_request.status == "resolved"
