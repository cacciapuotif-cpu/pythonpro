"""S2: redazione snapshot e retention revisionabile del security audit log."""

import json
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import auth
import models
from database import Base
from services.audit_log import safe_json, write_audit_log
from services.security_audit_retention import (
    apply_security_audit_retention_suggestion,
    collect_security_audit_retention_suggestions,
    get_retention_months,
    retention_cutoff,
)


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[
            auth.User.__table__,
            models.SecurityAuditLog.__table__,
            models.Collaborator.__table__,
            models.Project.__table__,
            models.Assignment.__table__,
            models.AgentRun.__table__,
            models.AgentSuggestion.__table__,
            models.AgentReviewAction.__table__,
            models.AuditLog.__table__,
        ],
    )
    return Session(engine)


def add_audit(db, *, timestamp, user_id=None, dati_dopo=None):
    entry = models.SecurityAuditLog(
        timestamp=timestamp,
        user_id=user_id,
        azione="test",
        risorsa_tipo="collaborator",
        risorsa_id="1",
        dati_dopo=json.dumps(dati_dopo or {}),
        esito="success",
    )
    db.add(entry)
    db.commit()
    return entry


def test_snapshot_redacts_cf_composti_e_retribuzioni():
    raw = {
        "collaborator_fiscal_code": "RSSMRA80A01H501U",
        "dati": [{"ral_annua": 45_000, "hourly_rate": 35, "importo_progetto": 900}],
    }

    serialized = safe_json(raw)
    parsed = json.loads(serialized)

    assert "RSSMRA80A01H501U" not in serialized
    assert "45000" not in serialized
    assert "35" not in serialized
    assert parsed["collaborator_fiscal_code"] == "***REDACTED***"
    assert parsed["dati"][0]["ral_annua"] == "***REDACTED***"
    assert parsed["dati"][0]["hourly_rate"] == "***REDACTED***"
    assert parsed["dati"][0]["importo_progetto"] == 900


def test_snapshot_redacts_full_name_from_profile_events():
    serialized = safe_json({"full_name": "Mario Rossi", "changed_fields": ["full_name"]})

    assert "Mario Rossi" not in serialized
    assert json.loads(serialized)["full_name"] == "***REDACTED***"


def test_write_audit_log_preserves_actor_and_change_shape():
    db = make_db()
    write_audit_log(
        db,
        user_id=17,
        azione="update",
        risorsa_tipo="collaborator",
        risorsa_id=4,
        dati_prima={"codice_fiscale": "RSSMRA80A01H501U", "status": "old"},
        dati_dopo={"codice_fiscale": "VRDLGI80A01H501U", "status": "new"},
    )
    db.commit()

    entry = db.query(models.SecurityAuditLog).one()
    assert entry.user_id == 17
    assert entry.azione == "update"
    assert entry.risorsa_tipo == "collaborator"
    assert entry.risorsa_id == "4"
    assert json.loads(entry.dati_prima) == {
        "codice_fiscale": "***REDACTED***",
        "status": "old",
    }
    assert json.loads(entry.dati_dopo)["status"] == "new"


def test_retention_default_override_e_config_invalida(monkeypatch):
    monkeypatch.delenv("AUDIT_LOG_RETENTION_MONTHS", raising=False)
    assert get_retention_months() == 24
    monkeypatch.setenv("AUDIT_LOG_RETENTION_MONTHS", "36")
    assert get_retention_months() == 36
    monkeypatch.setenv("AUDIT_LOG_RETENTION_MONTHS", "0")
    with pytest.raises(ValueError, match="almeno 1"):
        get_retention_months()
    monkeypatch.setenv("AUDIT_LOG_RETENTION_MONTHS", "mai")
    with pytest.raises(ValueError, match="intero positivo"):
        get_retention_months()


def test_cutoff_usa_mesi_di_calendario():
    assert retention_cutoff(now=datetime(2024, 2, 29, 12), months=12) == datetime(2023, 2, 28, 12)


def test_collector_propone_senza_cancellare(monkeypatch):
    monkeypatch.setenv("AUDIT_LOG_RETENTION_MONTHS", "24")
    db = make_db()
    old = add_audit(db, timestamp=datetime(2020, 1, 1))
    recent = add_audit(db, timestamp=datetime(2026, 1, 1))

    result = collect_security_audit_retention_suggestions(db)

    assert result["summary"]["candidates"] == 1
    assert result["suggestions"][0]["entity_id"] == old.id
    assert db.get(models.SecurityAuditLog, old.id) is not None
    assert db.get(models.SecurityAuditLog, recent.id) is not None


def test_workflow_crea_una_sola_proposta_pendente(monkeypatch):
    from agent_workflows import run_agent_workflow

    monkeypatch.setenv("AGENTS_ENABLED", "true")
    monkeypatch.setenv("AGENT_DATA_RETENTION_ENABLED", "true")
    monkeypatch.setenv("AUDIT_LOG_RETENTION_MONTHS", "24")
    db = make_db()
    old = add_audit(db, timestamp=datetime(2020, 1, 1))

    run_agent_workflow(db, agent_type="data_retention", entity_type="security_audit_log")
    run_agent_workflow(db, agent_type="data_retention", entity_type="security_audit_log")

    suggestion = db.query(models.AgentSuggestion).one()
    assert suggestion.status == "pending"
    assert suggestion.entity_type == "security_audit_log"
    assert suggestion.entity_id == old.id
    assert suggestion.suggestion_type == "security_audit_log_retention_cleanup"
    assert db.get(models.SecurityAuditLog, old.id) is not None


def test_apply_richiede_revisore_umano(monkeypatch):
    monkeypatch.setenv("AUDIT_LOG_RETENTION_MONTHS", "24")
    db = make_db()
    add_audit(db, timestamp=datetime(2020, 1, 1))
    suggestion = models.AgentSuggestion(id=99)

    with pytest.raises(ValueError, match="Revisore umano"):
        apply_security_audit_retention_suggestion(db, suggestion, user_id=None)


def test_apply_cancella_solo_scaduti_e_scrive_audit_sintesi(monkeypatch):
    monkeypatch.setenv("AUDIT_LOG_RETENTION_MONTHS", "24")
    db = make_db()
    user = auth.User(username="reviewer", email="reviewer@example.com", hashed_password="x", role="admin")
    db.add(user)
    db.commit()
    old = add_audit(db, timestamp=datetime(2020, 1, 1))
    recent = add_audit(db, timestamp=datetime(2026, 1, 1))
    old_id = old.id
    recent_id = recent.id
    suggestion = models.AgentSuggestion(id=99)

    result = apply_security_audit_retention_suggestion(db, suggestion, user_id=user.id)

    assert result["applied"] == ["audit_logs_deleted:1"]
    assert db.get(models.SecurityAuditLog, old_id) is None
    assert db.get(models.SecurityAuditLog, recent_id) is not None
    summary = db.query(models.SecurityAuditLog).filter_by(
        azione="security_audit_log_retention_cleanup"
    ).one()
    assert summary.user_id == user.id
    assert json.loads(summary.dati_dopo)["deleted_count"] == 1
