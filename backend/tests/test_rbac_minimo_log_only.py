import pytest

from auth import UserRole, rbac_decision_for, normalize_role


CORE_ROUTER_CASES = [
    ("collaborators-read", "GET", "/api/v1/collaborators/", {"admin": 200, "operatore": 200, "consultazione": 200}),
    ("collaborators-write", "POST", "/api/v1/collaborators/", {"admin": 200, "operatore": 200, "consultazione": 403}),
    ("projects-read", "GET", "/api/v1/projects/", {"admin": 200, "operatore": 200, "consultazione": 200}),
    ("projects-write", "PUT", "/api/v1/projects/1", {"admin": 200, "operatore": 200, "consultazione": 403}),
    ("attendances-read", "GET", "/api/v1/attendances/", {"admin": 200, "operatore": 200, "consultazione": 200}),
    ("attendances-write", "DELETE", "/api/v1/attendances/1", {"admin": 200, "operatore": 200, "consultazione": 403}),
    ("aziende-read", "GET", "/api/v1/aziende-clienti/", {"admin": 200, "operatore": 200, "consultazione": 200}),
    ("aziende-write", "POST", "/api/v1/aziende-clienti/", {"admin": 200, "operatore": 200, "consultazione": 403}),
    ("allievi-read", "GET", "/api/v1/allievi/", {"admin": 200, "operatore": 200, "consultazione": 200}),
    ("allievi-write", "POST", "/api/v1/allievi/", {"admin": 200, "operatore": 200, "consultazione": 403}),
    ("preventivi-read", "GET", "/api/v1/preventivi/", {"admin": 200, "operatore": 200, "consultazione": 200}),
    ("preventivi-write", "PUT", "/api/v1/preventivi/1", {"admin": 200, "operatore": 200, "consultazione": 403}),
    ("ordini-read", "GET", "/api/v1/ordini/", {"admin": 200, "operatore": 200, "consultazione": 200}),
    ("ordini-write", "DELETE", "/api/v1/ordini/1", {"admin": 200, "operatore": 200, "consultazione": 403}),
    ("report-summary-read", "GET", "/api/v1/reporting/summary", {"admin": 200, "operatore": 200, "consultazione": 200}),
    ("report-timesheet-sensitive", "GET", "/api/v1/reporting/timesheet", {"admin": 200, "operatore": 200, "consultazione": 403}),
    ("rendicontazione-generate", "POST", "/api/v1/reporting/projects/1/rendicontazione", {"admin": 200, "operatore": 200, "consultazione": 403}),
    ("piano-finanziario-read", "GET", "/api/v1/piani-finanziari/", {"admin": 200, "operatore": 200, "consultazione": 200}),
    ("piano-finanziario-write", "POST", "/api/v1/piani-finanziari/", {"admin": 200, "operatore": 200, "consultazione": 403}),
    ("piano-finanziario-export-sensitive", "GET", "/api/v1/piani-finanziari/1/export-excel", {"admin": 200, "operatore": 200, "consultazione": 403}),
    ("admin-users", "GET", "/api/v1/admin/security-logs", {"admin": 200, "operatore": 403, "consultazione": 403}),
    ("gdpr-export", "GET", "/api/v1/gdpr/export/1", {"admin": 200, "operatore": 403, "consultazione": 403}),
    ("agents", "POST", "/api/v1/agents/run", {"admin": 200, "operatore": 403, "consultazione": 403}),
]


@pytest.mark.parametrize("case_name,method,path,expected_by_role", CORE_ROUTER_CASES)
@pytest.mark.parametrize("role", [UserRole.ADMIN.value, UserRole.OPERATORE.value, UserRole.CONSULTAZIONE.value])
def test_rbac_matrix_would_status(case_name, method, path, expected_by_role, role):
    decision = rbac_decision_for(method, path, role)
    assert decision["would_status"] == expected_by_role[role], case_name


@pytest.mark.parametrize(
    "legacy_role,normalized",
    [
        ("user", "operatore"),
        ("manager", "operatore"),
        ("readonly", "consultazione"),
        ("dpo", "admin"),
        (None, "consultazione"),
    ],
)
def test_legacy_roles_are_normalized(legacy_role, normalized):
    assert normalize_role(legacy_role) == normalized
