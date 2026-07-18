from types import SimpleNamespace
import pytest
from fastapi import HTTPException

from routers.attivita import require_attivita_admin, require_attivita_write, router


@pytest.mark.parametrize("role", ["admin", "manager", "operatore"])
def test_activity_write_roles(role):
    user = SimpleNamespace(role=role)
    assert require_attivita_write(user) is user


def test_consultazione_cannot_write_and_only_admin_can_manage_playbooks():
    with pytest.raises(HTTPException) as write_error:
        require_attivita_write(SimpleNamespace(role="consultazione"))
    assert write_error.value.status_code == 403
    with pytest.raises(HTTPException) as admin_error:
        require_attivita_admin(SimpleNamespace(role="manager"))
    assert admin_error.value.status_code == 403
    assert require_attivita_admin(SimpleNamespace(role="admin")).role == "admin"


def test_playbook_routes_precede_dynamic_activity_routes():
    paths = [route.path for route in router.routes]
    assert paths.index("/api/v1/attivita/playbooks") < paths.index("/api/v1/attivita/{attivita_id}/stato")
