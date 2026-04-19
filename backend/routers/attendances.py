"""
Router per gestione presenze
Gestisce registrazione ore lavorate con validazioni avanzate
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import logging

import crud
import schemas
from database import get_db
from error_handler import BusinessLogicError, SafeTransaction, retry_on_db_error
from validators import EnhancedAttendanceCreate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/attendances", tags=["Attendances"])


@router.post("/", response_model=schemas.Attendance, response_model_by_alias=False)
@retry_on_db_error(max_retries=3)
def create_attendance(
    attendance: EnhancedAttendanceCreate,
    db: Session = Depends(get_db)
):
    """
    REGISTRA UNA NUOVA PRESENZA CON VALIDAZIONE AVANZATA
    - Validazione orari e sovrapposizioni
    - Calcolo automatico ore se non fornite
    - Controllo business logic avanzato
    """
    try:
        with SafeTransaction(db) as transaction:
            collaborator = crud.get_collaborator(db, attendance.collaborator_id)
            if not collaborator:
                raise BusinessLogicError("Collaboratore non trovato")

            project = crud.get_project(db, attendance.project_id)
            if not project:
                raise BusinessLogicError("Progetto non trovato")

            attendance_data = schemas.AttendanceCreate(**attendance.dict())
            result = crud.create_attendance(db=db, attendance=attendance_data)
            transaction.commit()

            logger.info(f"Presenza registrata con successo: ID {result.id}")
            return result

    except BusinessLogicError:
        raise
    except ValueError as e:
        logger.warning(f"Validazione presenza fallita: {e}")
        raise BusinessLogicError(str(e))
    except Exception as e:
        logger.error(f"Errore registrazione presenza: {e}")
        raise


@router.get("/", response_model=List[schemas.Attendance], response_model_by_alias=False)
def read_attendances(
    skip: int = 0,
    limit: int = 100,
    collaborator_id: Optional[int] = None,
    project_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db)
):
    """OTTIENI LISTA DELLE PRESENZE CON FILTRI OPZIONALI"""
    attendances = crud.get_attendances(
        db, skip=skip, limit=limit,
        collaborator_id=collaborator_id,
        project_id=project_id,
        start_date=start_date,
        end_date=end_date
    )
    return attendances


@router.get("/summary")
def read_attendances_summary(
    from_date: datetime = Query(..., alias="from"),
    to_date: datetime = Query(..., alias="to"),
    db: Session = Depends(get_db)
):
    """OTTIENI STATISTICHE AGGREGATE DELLE PRESENZE PER COLLABORATORE/PROGETTO."""
    summary = crud.get_attendances_summary(db, start_date=from_date, end_date=to_date)
    items = [
        {
            "collaborator_id": row.collaborator_id,
            "project_id": row.project_id,
            "total_hours": float(row.total_hours or 0.0),
            "total_sessions": int(row.total_sessions or 0),
            "avg_hours_per_session": float(row.avg_hours_per_session or 0.0),
        }
        for row in summary
    ]
    return {
        "from": from_date.isoformat(),
        "to": to_date.isoformat(),
        "items": items,
        "total": len(items),
    }


@router.get("/{attendance_id}", response_model=schemas.Attendance, response_model_by_alias=False)
def read_attendance(
    attendance_id: int,
    db: Session = Depends(get_db)
):
    """OTTIENI UNA PRESENZA SPECIFICA"""
    db_attendance = crud.get_attendance(db, attendance_id=attendance_id)
    if db_attendance is None:
        raise HTTPException(status_code=404, detail="Presenza non trovata")
    return db_attendance


@router.put("/{attendance_id}", response_model=schemas.Attendance, response_model_by_alias=False)
def update_attendance(
    attendance_id: int,
    attendance: schemas.AttendanceUpdate,
    db: Session = Depends(get_db)
):
    """AGGIORNA UNA PRESENZA ESISTENTE"""
    try:
        db_attendance = crud.update_attendance(db, attendance_id, attendance)
        if db_attendance is None:
            raise HTTPException(status_code=404, detail="Presenza non trovata")
        return db_attendance
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Validazione aggiornamento presenza fallita: {e}")
        raise BusinessLogicError(str(e))


@router.delete("/{attendance_id}")
def delete_attendance(
    attendance_id: int,
    db: Session = Depends(get_db)
):
    """ELIMINA UNA PRESENZA"""
    db_attendance = crud.delete_attendance(db, attendance_id)
    if db_attendance is None:
        raise HTTPException(status_code=404, detail="Presenza non trovata")
    return {"message": "Presenza eliminata con successo"}
