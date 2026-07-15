"""A5a (GATE confermato 2026-07-15): matrice RBAC piattaforma agenti.

- GET (catalogo, runs, suggestions, status, system-health): tutti i ruoli
- review/approve/reject/send/apply-fix + azioni inbox: OPERATORE e ADMIN
- run manuale agenti, trigger-poll, imap/test: solo ADMIN
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from auth import UserRole, User, rbac_decision_for

MATRIX_CASES = [
    # (nome, metodo, path, {ruolo: status atteso})
    ("agents-catalog-read", "GET", "/api/v1/agents/", {"admin": 200, "operatore": 200, "consultazione": 200}),
    ("agents-runs-read", "GET", "/api/v1/agents/runs/", {"admin": 200, "operatore": 200, "consultazione": 200}),
    ("agents-system-health-read", "GET", "/api/v1/agents/system-health", {"admin": 200, "operatore": 200, "consultazione": 200}),
    ("inbox-items-read", "GET", "/api/v1/email-inbox/items", {"admin": 200, "operatore": 200, "consultazione": 200}),
    ("inbox-status-read", "GET", "/api/v1/email-inbox/status", {"admin": 200, "operatore": 200, "consultazione": 200}),
    ("suggestion-review", "POST", "/api/v1/agents/suggestions/1/review", {"admin": 200, "operatore": 200, "consultazione": 403}),
    ("suggestion-apply-fix", "POST", "/api/v1/agents/suggestions/1/apply-fix", {"admin": 200, "operatore": 200, "consultazione": 403}),
    ("suggestion-send-email", "POST", "/api/v1/agent-suggestions/1/send-email", {"admin": 200, "operatore": 200, "consultazione": 403}),
    ("inbox-assign", "POST", "/api/v1/email-inbox/items/1/assign", {"admin": 200, "operatore": 200, "consultazione": 403}),
    ("inbox-followup", "POST", "/api/v1/email-inbox/1/send-followup", {"admin": 200, "operatore": 200, "consultazione": 403}),
    ("inbox-archive", "POST", "/api/v1/email-inbox/1/archive", {"admin": 200, "operatore": 200, "consultazione": 403}),
    ("agents-manual-run", "POST", "/api/v1/agents/run", {"admin": 200, "operatore": 403, "consultazione": 403}),
    ("agents-manual-run-typed", "POST", "/api/v1/agents/mail_recovery/run", {"admin": 200, "operatore": 403, "consultazione": 403}),
    ("sprint7-contract-run", "POST", "/api/v1/agents/contract-generator/run", {"admin": 200, "operatore": 403, "consultazione": 403}),
    ("sprint7-certification-run", "POST", "/api/v1/agents/certification/run", {"admin": 200, "operatore": 403, "consultazione": 403}),
    ("inbox-trigger-poll", "POST", "/api/v1/email-inbox/trigger-poll", {"admin": 200, "operatore": 403, "consultazione": 403}),
    ("inbox-imap-test", "POST", "/api/v1/email-inbox/imap/test", {"admin": 200, "operatore": 403, "consultazione": 403}),
]


@pytest.mark.parametrize("case_name,method,path,expected_by_role", MATRIX_CASES)
@pytest.mark.parametrize("role", [UserRole.ADMIN.value, UserRole.OPERATORE.value, UserRole.CONSULTAZIONE.value])
def test_agent_platform_rbac_matrix(case_name, method, path, expected_by_role, role):
    decision = rbac_decision_for(method, path, role)
    assert decision["would_status"] == expected_by_role[role], case_name


def _user(role: str) -> User:
    user = User(username=f"u-{role}", email=f"{role}@example.com", role=role)
    user.id = 1
    return user


def test_require_agents_execute_admin_only():
    from routers.agents import require_agents_execute

    assert require_agents_execute(_user("admin")).role == "admin"
    for role in ("operatore", "consultazione", "manager"):
        with pytest.raises(HTTPException) as excinfo:
            require_agents_execute(_user(role))
        assert excinfo.value.status_code == 403, role


def test_require_agents_write_operatore_and_admin():
    from routers.agents import require_agents_write

    assert require_agents_write(_user("admin")).role == "admin"
    assert require_agents_write(_user("operatore")).role == "operatore"
    # manager legacy normalizza a operatore: puo' revisionare, non eseguire.
    assert require_agents_write(_user("manager")).role == "manager"
    with pytest.raises(HTTPException) as excinfo:
        require_agents_write(_user("consultazione"))
    assert excinfo.value.status_code == 403
