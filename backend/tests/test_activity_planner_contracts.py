from types import SimpleNamespace
import pytest

from ai_agents.activity_planner import collect_activity_planner_suggestions
from ai_agents import get_agent_definition


class EmptyDB:
    def __init__(self, project): self.project = project
    def get(self, model, value): return self.project


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
