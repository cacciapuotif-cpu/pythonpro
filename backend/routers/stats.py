"""Router statistiche aggregate."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

import crud
from database import get_db

router = APIRouter(prefix="/api/v1/stats", tags=["Stats"])


@router.get("/monthly")
def get_monthly_stats(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db)
):
    """Restituisce statistiche giornaliere aggregate per il mese richiesto."""
    try:
        datetime(year, month, 1)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    rows = crud.get_monthly_stats(db, year=year, month=month)
    items = [
        {
            "day": int(row.day),
            "total_hours": float(row.total_hours or 0.0),
            "total_attendances": int(row.total_attendances or 0),
        }
        for row in rows
    ]
    return {
        "year": year,
        "month": month,
        "items": items,
        "total_days": len(items),
    }
