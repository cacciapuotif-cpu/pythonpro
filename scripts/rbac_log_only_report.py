#!/usr/bin/env python3
from pathlib import Path
import importlib.util
import sys
import os

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("SECRET_KEY", "rbac-report-dummy-secret-key-not-used-for-runtime")
sys.path.insert(0, str(ROOT / "backend"))

spec = importlib.util.spec_from_file_location(
    "test_rbac_minimo_log_only",
    ROOT / "backend" / "tests" / "test_rbac_minimo_log_only.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

from auth import UserRole, rbac_decision_for  # noqa: E402

roles = [UserRole.ADMIN.value, UserRole.OPERATORE.value, UserRole.CONSULTAZIONE.value]
lines = [
    "# RBAC log-only report",
    "",
    "Modalita': log-only. I 403 indicati sono blocchi potenziali, non enforcement reale.",
    "",
    "| Caso | Metodo | Path | ADMIN | OPERATORE | CONSULTAZIONE |",
    "| --- | --- | --- | --- | --- | --- |",
]
for case_name, method, path, _expected_by_role in module.CORE_ROUTER_CASES:
    statuses = []
    for role in roles:
        decision = rbac_decision_for(method, path, role)
        statuses.append(str(decision["would_status"]))
    lines.append(f"| {case_name} | {method} | `{path}` | {statuses[0]} | {statuses[1]} | {statuses[2]} |")

out = ROOT / "audit" / "RBAC_LOG_ONLY_REPORT.md"
out.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(out)
