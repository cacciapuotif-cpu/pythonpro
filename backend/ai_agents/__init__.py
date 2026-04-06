from __future__ import annotations

from typing import Any, Optional

from .data_quality import DataQualityAgent
from .mail_recovery import run_mail_recovery_agent
from .registry import AgentRegistry, BaseAgent, AgentRunResult, agent_registry

_AGENT_DEFINITIONS: dict[str, dict[str, Any]] = {
    "data_quality": {
        "name": "data_quality",
        "description": "Verifica completezza e coerenza dati anagrafici",
        "supported_entity_types": ["collaborator", "assignment", "attendance"],
    },
    "mail_recovery": {
        "name": "mail_recovery",
        "description": "Recupera dati mancanti tramite comunicazioni ai collaboratori",
        "supported_entity_types": ["collaborator"],
    },
}


def get_agent_definition(agent_name: str) -> Optional[dict[str, Any]]:
    return _AGENT_DEFINITIONS.get(agent_name)


def list_agent_definitions() -> list[dict[str, Any]]:
    return list(_AGENT_DEFINITIONS.values())


def run_registered_agent(
    db,
    *,
    agent_name: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    input_payload: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    if agent_name == "mail_recovery":
        limit = int((input_payload or {}).get("limit", 25))
        return run_mail_recovery_agent(
            db,
            entity_type=entity_type,
            entity_id=entity_id,
            limit=limit,
        )

    if agent_name == "data_quality":
        agent = DataQualityAgent()
        result = agent.run(db)
        suggestions = []
        for item in result.suggestions:
            suggestions.append({
                **item,
                "severity": item.get("priority", "medium"),
            })
        summary = {
            "items_processed": result.items_processed,
            "items_with_issues": result.items_with_issues,
        }
        return {"summary": summary, "suggestions": suggestions}

    raise ValueError(f"Agente non registrato: {agent_name}")


__all__ = [
    "AgentRegistry",
    "BaseAgent",
    "AgentRunResult",
    "agent_registry",
    "DataQualityAgent",
    "get_agent_definition",
    "list_agent_definitions",
    "run_registered_agent",
]
