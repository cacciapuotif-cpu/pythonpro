from types import SimpleNamespace
import pytest

from ai_agents.activity_planner import collect_activity_planner_suggestions
import ai_agents.activity_planner as planner
import models
from ai_agents import get_agent_definition


class EmptyDB:
    def __init__(self, project): self.project = project
    def get(self, model, value): return self.project

class Query:
    def __init__(self, values): self.values = values
    def filter_by(self, **kwargs):
        self.values = [v for v in self.values if all(getattr(v, k, None) == x for k, x in kwargs.items())]; return self
    def all(self): return self.values

class PlannerDB:
    def __init__(self, project, revision, deadlines, existing=()):
        self.objects = {models.Project: project, models.AvvisoRevisione: revision}
        self.deadlines = deadlines; self.existing = list(existing); self.writes = 0
    def get(self, model, value): return self.objects.get(model)
    def query(self, model):
        if model is models.AvvisoScadenza: return Query(self.deadlines)
        if model is models.AttivitaOperativa: return Query(self.existing)
        raise AssertionError(model)
    def add(self, *_): self.writes += 1
    def commit(self): self.writes += 1
    def flush(self): self.writes += 1


def test_planner_without_notice_is_honest_and_pure():
    project = SimpleNamespace(id=7, avviso_id=None, avviso_revisione_id=None)
    result = collect_activity_planner_suggestions(EmptyDB(project), project_id=7)
    assert result["suggestions"] == []
    assert "avviso" in result["summary"]["reason"]


def test_planner_is_registered_manual_and_proposal_only():
    definition = get_agent_definition("activity_planner")
    assert definition["supported_entity_types"] == ["project"]
    assert definition["triggers"] == ["manual"]
    assert definition["allowed_roles"] == ["admin", "manager"]


def test_planner_uses_validated_deadlines_deduplicates_and_marks_missing_anchor(monkeypatch):
    avviso = SimpleNamespace(fondo="fapi", ente_erogatore="INPS")
    revision = SimpleNamespace(id=3, avviso=avviso)
    project = SimpleNamespace(id=7, avviso_id=1, avviso_revisione_id=3)
    valid = SimpleNamespace(id=1, avviso_revisione_id=3, tipo="avvio", data=__import__("datetime").datetime(2026, 1, 10),
                            descrizione="Avvio", tassativa=True, stato="validata")
    proposed = SimpleNamespace(id=2, avviso_revisione_id=3, tipo="chiusura", data=__import__("datetime").datetime(2026, 2, 10),
                               descrizione="Ignora", tassativa=False, stato="proposta")
    voce = SimpleNamespace(id=8, fase="gestione", ordine=1, titolo="Procedura", descrizione="x",
                           applicabilita=None, stato="validata", contenuto={"tipo":"scadenza_relativa", "ancora":"chiusura", "offset_giorni":-3})
    db = PlannerDB(project, revision, [valid, proposed])
    monkeypatch.setattr(planner, "get_playbook_operativo", lambda *args, **kwargs: [voce])
    result = collect_activity_planner_suggestions(db, project_id=7)
    assert len(result["suggestions"]) == 1
    items = result["suggestions"][0]["auto_fix_payload"]["attivita"]
    assert {x["titolo"] for x in items} == {"Avvio", "Procedura"}
    assert next(x for x in items if x["titolo"] == "Procedura")["needs_review"] is True
    assert db.writes == 0
