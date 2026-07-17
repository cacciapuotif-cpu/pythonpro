"""Registry unico dichiarativo degli agenti AI.

Ogni agente e' descritto da una definizione con: name, description,
supported_entity_types, triggers, kill_switch_env, allowed_roles, version
e runner. Il runner e' un collector puro: riceve (db, entity_type,
entity_id, input_payload) e ritorna {"summary", "suggestions"} SENZA
scrivere su DB. La persistenza (AgentRun + AgentSuggestion + draft) avviene
solo in `agent_workflows.run_agent_workflow`.

Guida completa: backend/AGENTS_PLATFORM.md
"""
from __future__ import annotations

from typing import Any, Optional

from .certification_agent import collect_certification_suggestions
from .contract_agent import collect_contract_suggestions
from .control import agent_env_name
from .data_quality import DataQualityAgent
from .data_retention import collect_data_retention_suggestions
from .mail_recovery import run_mail_recovery_agent


def _run_data_quality(
    db,
    *,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    input_payload: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
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


def _run_mail_recovery(
    db,
    *,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    input_payload: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    limit = int((input_payload or {}).get("limit", 25))
    return run_mail_recovery_agent(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        limit=limit,
    )


def _run_contract_agent(
    db,
    *,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    input_payload: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    if entity_type == "assignment" and entity_id:
        kwargs["assignment_id"] = entity_id
    elif entity_type == "project" and entity_id:
        kwargs["project_id"] = entity_id
    elif entity_type == "collaborator" and entity_id:
        kwargs["collaborator_id"] = entity_id
    return collect_contract_suggestions(db, **kwargs)


def _run_certification(
    db,
    *,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    input_payload: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    if entity_type == "project" and entity_id:
        kwargs["project_id"] = entity_id
    return collect_certification_suggestions(db, **kwargs)


def _run_data_retention(db, *, entity_type=None, entity_id=None, input_payload=None):
    return collect_data_retention_suggestions(db, collaborator_id=entity_id if entity_type == "collaborator" else None)

_AGENT_DEFINITIONS: dict[str, dict[str, Any]] = {
    "data_quality": {
        "name": "data_quality",
        "description": "Verifica completezza e coerenza dati anagrafici",
        "supported_entity_types": ["collaborator", "assignment", "attendance"],
        "triggers": ["manual", "event:collaborator_update"],
        "kill_switch_env": agent_env_name("data_quality"),
        "allowed_roles": ["admin", "manager"],
        "version": "1.0",
        "runner": _run_data_quality,
    },
    "mail_recovery": {
        "name": "mail_recovery",
        "description": "Recupera dati mancanti tramite comunicazioni ai collaboratori",
        "supported_entity_types": ["collaborator"],
        "triggers": ["manual", "cron:0,6,12,18h @:10"],
        "kill_switch_env": agent_env_name("mail_recovery"),
        "allowed_roles": ["admin", "manager"],
        "version": "1.0",
        "runner": _run_mail_recovery,
    },
    "contract_agent": {
        "name": "contract_agent",
        "description": "Monitora pratiche documentali complete e propone bozze contratto",
        "supported_entity_types": ["assignment", "project", "collaborator"],
        "triggers": ["manual", "cron:ogni 2h @:20", "event:document_validated"],
        "kill_switch_env": agent_env_name("contract_agent"),
        "allowed_roles": ["admin", "manager"],
        "version": "1.0",
        "runner": _run_contract_agent,
    },
    "certification": {
        "name": "certification",
        "description": "Verifica frequenza allievi e propone emissione attestato",
        "supported_entity_types": ["project"],
        "triggers": ["manual", "cron:09:00 daily"],
        "kill_switch_env": agent_env_name("certification"),
        "allowed_roles": ["admin", "manager"],
        "version": "1.0",
        "runner": _run_certification,
    },
    "data_retention": {
        "name": "data_retention",
        "description": "Propone anonimizzazioni GDPR oltre il periodo di retention",
        "supported_entity_types": ["collaborator"],
        "triggers": ["manual", "cron:domenica 03:00"],
        "kill_switch_env": agent_env_name("data_retention"),
        "allowed_roles": ["admin", "manager"],
        "version": "1.0",
        "runner": _run_data_retention,
    },
}


def _public_definition(definition: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in definition.items() if key != "runner"}


def get_agent_definition(agent_name: str) -> Optional[dict[str, Any]]:
    definition = _AGENT_DEFINITIONS.get(agent_name)
    return _public_definition(definition) if definition else None


def list_agent_definitions() -> list[dict[str, Any]]:
    return [_public_definition(item) for item in _AGENT_DEFINITIONS.values()]


def run_registered_agent(
    db,
    *,
    agent_name: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    input_payload: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    definition = _AGENT_DEFINITIONS.get(agent_name)
    if not definition:
        raise ValueError(f"Agente non registrato: {agent_name}")
    runner = definition["runner"]
    return runner(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        input_payload=input_payload,
    )


__all__ = [
    "DataQualityAgent",
    "collect_certification_suggestions",
    "collect_contract_suggestions",
    "collect_data_retention_suggestions",
    "get_agent_definition",
    "list_agent_definitions",
    "run_registered_agent",
]
