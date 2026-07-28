"""UX-10 — un ruolo valido sul cockpit non deve essere scambiato per 401."""

import pytest

from auth import rbac_decision_for


@pytest.mark.parametrize("role", ["admin", "operatore", "consultazione"])
def test_cockpit_get_ammesso_ai_tre_ruoli(role):
    decision = rbac_decision_for("GET", "/api/v1/cockpit/decisioni", role)
    assert decision["allowed"] is True
    assert decision["would_status"] == 200
