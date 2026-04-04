"""
Pacchetto routers per API modulari
Organizza endpoints in moduli separati per tipo
"""

from . import (
    auth,
    collaborators,
    projects,
    attendances,
    assignments,
    implementing_entities,
    progetto_mansione_ente,
    contract_templates,
    admin,
    system,
    reporting,
    agenzie,
    consulenti,
    aziende_clienti,
    catalogo,
    listini,
    preventivi,
    ordini,
    piani_finanziari,
    piani_fondimpresa,
    avvisi,
    agents,
)

__all__ = [
    "auth",
    "collaborators",
    "projects",
    "attendances",
    "assignments",
    "implementing_entities",
    "progetto_mansione_ente",
    "contract_templates",
    "admin",
    "system",
    "reporting",
    "agenzie",
    "consulenti",
    "aziende_clienti",
    "catalogo",
    "listini",
    "preventivi",
    "ordini",
    "piani_finanziari",
    "piani_fondimpresa",
    "avvisi",
    "agents",
]
