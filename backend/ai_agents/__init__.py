"""Registry e runner per agenti verticali della piattaforma."""

from .registry import get_agent_definition, list_agent_definitions, run_registered_agent

__all__ = ["get_agent_definition", "list_agent_definitions", "run_registered_agent"]
