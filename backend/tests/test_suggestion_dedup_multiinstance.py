"""Regressione: la deduplica delle AgentSuggestion non deve collassare le
proposte multi-istanza (una per regola / per scadenza) su una sola riga.

Bug: run_agent_workflow deduplicava solo su (entity_type, entity_id,
suggestion_type). Un'estrazione con N regole persisteva 1 sola suggestion
(l'ultima sovrascriveva le altre). Fix: per i tipi multi-istanza la deduplica
include anche il title (che codifica la chiave della proposta).
"""
from __future__ import annotations

import auth  # noqa: F401 — registra users nella Base
import models
from database import Base

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import agent_workflows


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        auth.User.__table__,
        models.AgentRun.__table__,
        models.AgentSuggestion.__table__,
        models.AgentCommunicationDraft.__table__,
        models.AuditLog.__table__,
    ])
    return Session(engine)


def _regola_item(chiave: str):
    return {
        "suggestion_type": "avviso_regola_proposta",
        "entity_type": "avviso_revisione",
        "entity_id": 7,
        "severity": "medium",
        "title": f"Regola proposta: {chiave}",
        "description": f"desc {chiave}",
        "payload": {"chiave": chiave},
        "confidence_score": 0.9,
        "auto_fix_available": True,
        "auto_fix_payload": {"kind": "avviso_estrazione", "target": "regola"},
    }


def _fake_result(chiavi):
    return {"summary": {"revision_id": 7}, "suggestions": [_regola_item(c) for c in chiavi]}


def test_multi_instance_suggestions_non_collassano(monkeypatch):
    db = make_db()
    chiavi = ["massimale_ora", "durata_max", "min_partecipanti", "cofinanziamento"]
    monkeypatch.setattr(agent_workflows, "run_registered_agent",
                         lambda *a, **k: _fake_result(chiavi))

    run = agent_workflows.run_agent_workflow(
        db, agent_type="avviso_extractor",
        entity_type="avviso_revisione", entity_id=7,
    )
    sugg = db.query(models.AgentSuggestion).filter_by(
        entity_type="avviso_revisione", entity_id=7).all()
    # 4 proposte distinte → 4 righe, non 1
    assert len(sugg) == len(chiavi)
    assert {s.title for s in sugg} == {f"Regola proposta: {c}" for c in chiavi}
    assert all(s.run_id == run.id for s in sugg)


def test_re_estrazione_e_idempotente(monkeypatch):
    """Ri-eseguire l'estrazione aggiorna in place le stesse proposte, non le duplica."""
    db = make_db()
    chiavi = ["massimale_ora", "durata_max", "min_partecipanti"]
    monkeypatch.setattr(agent_workflows, "run_registered_agent",
                         lambda *a, **k: _fake_result(chiavi))

    agent_workflows.run_agent_workflow(
        db, agent_type="avviso_extractor",
        entity_type="avviso_revisione", entity_id=7)
    run2 = agent_workflows.run_agent_workflow(
        db, agent_type="avviso_extractor",
        entity_type="avviso_revisione", entity_id=7)

    sugg = db.query(models.AgentSuggestion).filter_by(
        entity_type="avviso_revisione", entity_id=7).all()
    # stesso set di chiavi → ancora 3 righe (aggiornate), non 6
    assert len(sugg) == len(chiavi)
    assert all(s.run_id == run2.id for s in sugg)
