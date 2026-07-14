from __future__ import annotations

import os
import re

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def _env_bool(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    normalized = raw.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    return default


def agent_env_name(agent_name: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", (agent_name or "").strip()).strip("_").upper()
    return f"AGENT_{normalized}_ENABLED" if normalized else "AGENT_ENABLED"


def agents_enabled() -> bool:
    return _env_bool("AGENTS_ENABLED", True)


def agent_enabled(agent_name: str) -> bool:
    return agents_enabled() and _env_bool(agent_env_name(agent_name), True)


def disabled_reason(agent_name: str) -> str:
    if not agents_enabled():
        return "Piattaforma agenti disabilitata da AGENTS_ENABLED=false"
    return f"Agente {agent_name} disabilitato da {agent_env_name(agent_name)}=false"
