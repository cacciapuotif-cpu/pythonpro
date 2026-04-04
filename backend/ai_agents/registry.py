from __future__ import annotations

from typing import Any, Optional

from .data_quality import run_data_quality_agent
from .mail_recovery import run_mail_recovery_agent


AGENT_REGISTRY = {
    "data_quality": {
        "name": "data_quality",
        "label": "Data Quality Agent",
        "description": (
            "Analizza progetti, collaboratori e aziende per trovare buchi di dato, "
            "incoerenze operative e prerequisiti mancanti."
        ),
        "supported_entity_types": ["project", "collaborator", "azienda_cliente", "global"],
        "runner": run_data_quality_agent,
    },
    "mail_recovery": {
        "name": "mail_recovery",
        "label": "Mail Recovery Agent",
        "description": (
            "Genera bozze email verso collaboratori con dati mancanti o documenti "
            "identita mancanti/in scadenza, senza invio automatico."
        ),
        "supported_entity_types": ["collaborator"],
        "runner": run_mail_recovery_agent,
    },
}


def list_agent_definitions() -> list[dict[str, Any]]:
    return [
        {
            "name": item["name"],
            "label": item["label"],
            "description": item["description"],
            "supported_entity_types": item["supported_entity_types"],
        }
        for item in AGENT_REGISTRY.values()
    ]


def get_agent_definition(agent_name: str) -> Optional[dict[str, Any]]:
    return AGENT_REGISTRY.get((agent_name or "").strip().lower())


def run_registered_agent(db, *, agent_name: str, entity_type: Optional[str] = None, entity_id: Optional[int] = None, input_payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    definition = get_agent_definition(agent_name)
    if not definition:
        raise ValueError(f"Agente non supportato: {agent_name}")

    runner = definition["runner"]
    payload = input_payload or {}
    return runner(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        limit=int(payload.get("limit", 25)),
    )
