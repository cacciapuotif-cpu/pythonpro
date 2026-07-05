# RBAC log-only report

Modalita': log-only. I 403 indicati sono blocchi potenziali, non enforcement reale.

| Caso | Metodo | Path | ADMIN | OPERATORE | CONSULTAZIONE |
| --- | --- | --- | --- | --- | --- |
| collaborators-read | GET | `/api/v1/collaborators/` | 200 | 200 | 200 |
| collaborators-write | POST | `/api/v1/collaborators/` | 200 | 200 | 403 |
| projects-read | GET | `/api/v1/projects/` | 200 | 200 | 200 |
| projects-write | PUT | `/api/v1/projects/1` | 200 | 200 | 403 |
| attendances-read | GET | `/api/v1/attendances/` | 200 | 200 | 200 |
| attendances-write | DELETE | `/api/v1/attendances/1` | 200 | 200 | 403 |
| aziende-read | GET | `/api/v1/aziende-clienti/` | 200 | 200 | 200 |
| aziende-write | POST | `/api/v1/aziende-clienti/` | 200 | 200 | 403 |
| allievi-read | GET | `/api/v1/allievi/` | 200 | 200 | 200 |
| allievi-write | POST | `/api/v1/allievi/` | 200 | 200 | 403 |
| preventivi-read | GET | `/api/v1/preventivi/` | 200 | 200 | 200 |
| preventivi-write | PUT | `/api/v1/preventivi/1` | 200 | 200 | 403 |
| ordini-read | GET | `/api/v1/ordini/` | 200 | 200 | 200 |
| ordini-write | DELETE | `/api/v1/ordini/1` | 200 | 200 | 403 |
| report-summary-read | GET | `/api/v1/reporting/summary` | 200 | 200 | 200 |
| report-timesheet-sensitive | GET | `/api/v1/reporting/timesheet` | 200 | 200 | 403 |
| piano-finanziario-read | GET | `/api/v1/piani-finanziari/` | 200 | 200 | 200 |
| piano-finanziario-write | POST | `/api/v1/piani-finanziari/` | 200 | 200 | 403 |
| piano-finanziario-export-sensitive | GET | `/api/v1/piani-finanziari/1/export-excel` | 200 | 200 | 403 |
| admin-users | GET | `/api/v1/admin/security-logs` | 200 | 403 | 403 |
| gdpr-export | GET | `/api/v1/gdpr/export/1` | 200 | 403 | 403 |
| agents | POST | `/api/v1/agents/run` | 200 | 403 | 403 |
