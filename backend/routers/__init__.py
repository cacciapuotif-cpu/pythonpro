"""
Pacchetto routers per API modulari
Organizza endpoints in moduli separati per tipo
"""

from . import (
    collaborators,
    projects,
    attendances,
    assignments,
    implementing_entities,
    progetto_mansione_ente,
    contract_templates,
    admin,
    system
)

__all__ = [
    "collaborators",
    "projects",
    "attendances",
    "assignments",
    "implementing_entities",
    "progetto_mansione_ente",
    "contract_templates",
    "admin",
    "system"
]
