"""
Router Reporting & Timesheet - Implementazione In-Memory
"""
from fastapi import APIRouter, Query
from typing import Optional
from datetime import date
from app.api.attendances import attendances_db
from app.api.collaborators import collaborators_db
from app.api.projects import projects_db

router = APIRouter(prefix="/api/v1/reporting", tags=["Reporting"])


@router.get("/timesheet")
def get_timesheet(
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to")
):
    """Report timesheet presenze"""
    results = attendances_db

    if from_date:
        results = [a for a in results if a["date"] >= from_date]
    if to_date:
        results = [a for a in results if a["date"] <= to_date]

    total_hours = sum(a["hours"] for a in results)

    return {
        "period": {
            "from": from_date.isoformat() if from_date else None,
            "to": to_date.isoformat() if to_date else None
        },
        "attendances": results,
        "total_hours": total_hours,
        "count": len(results)
    }


@router.get("/summary")
def get_summary(
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to")
):
    """Report riepilogativo KPI"""
    results = attendances_db

    if from_date:
        results = [a for a in results if a["date"] >= from_date]
    if to_date:
        results = [a for a in results if a["date"] <= to_date]

    total_hours = sum(a["hours"] for a in results)

    return {
        "period": {
            "from": from_date.isoformat() if from_date else None,
            "to": to_date.isoformat() if to_date else None
        },
        "kpi": {
            "total_collaborators": len(collaborators_db),
            "total_projects": len(projects_db),
            "total_hours": total_hours,
            "total_attendances": len(results)
        }
    }
