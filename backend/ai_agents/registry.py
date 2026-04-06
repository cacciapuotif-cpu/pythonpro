from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import crud


@dataclass
class AgentRunResult:
    items_processed: int
    items_with_issues: int
    suggestions: List[dict] = field(default_factory=list)
    error: Optional[str] = None


class BaseAgent(ABC):
    agent_type: str = ""
    version: str = "1.0"
    description: str = ""

    @abstractmethod
    def run(self, db) -> AgentRunResult:
        raise NotImplementedError

    def get_info(self) -> dict:
        return {
            "agent_type": self.agent_type,
            "version": self.version,
            "description": self.description,
        }


class AgentRegistry:
    _instance: Optional["AgentRegistry"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._agents = {}
        return cls._instance

    def register(self, agent: BaseAgent):
        if not agent.agent_type:
            raise ValueError("agent.agent_type obbligatorio")
        self._agents[agent.agent_type] = agent

    def get(self, agent_type: str) -> BaseAgent:
        agent = self._agents.get((agent_type or "").strip())
        if not agent:
            raise ValueError(f"Agente non registrato: {agent_type}")
        return agent

    def list_agents(self) -> List[dict]:
        return [agent.get_info() for agent in self._agents.values()]

    def run_agent(self, db, agent_type: str, triggered_by: str):
        run = crud.create_agent_run(
            db,
            agent_type=agent_type,
            triggered_by=triggered_by,
            trigger_details=None,
        )

        try:
            agent = self.get(agent_type)
            result = agent.run(db)

            created_suggestions = 0
            for suggestion in result.suggestions:
                crud.create_suggestion(
                    db=db,
                    run_id=run.id,
                    suggestion_type=suggestion["suggestion_type"],
                    priority=suggestion.get("priority", "medium"),
                    entity_type=suggestion["entity_type"],
                    entity_id=suggestion.get("entity_id"),
                    title=suggestion["title"],
                    description=suggestion.get("description"),
                    suggested_action=suggestion.get("suggested_action"),
                    confidence_score=suggestion.get("confidence_score"),
                    auto_fix_available=suggestion.get("auto_fix_available", False),
                    auto_fix_payload=suggestion.get("auto_fix_payload"),
                )
                created_suggestions += 1

            final_status = "failed" if result.error else "completed"
            return crud.complete_agent_run(
                db=db,
                run_id=run.id,
                status=final_status,
                items_processed=result.items_processed,
                items_with_issues=result.items_with_issues,
                suggestions_created=created_suggestions,
                error_message=result.error,
            )
        except Exception as exc:
            return crud.complete_agent_run(
                db=db,
                run_id=run.id,
                status="failed",
                items_processed=0,
                items_with_issues=0,
                suggestions_created=0,
                error_message=str(exc),
            )


agent_registry = AgentRegistry()
