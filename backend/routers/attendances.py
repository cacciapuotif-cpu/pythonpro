"""
Router per gestione presenze
Gestisce registrazione ore lavorate con validazioni avanzate
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import logging

import crud
import models
import schemas
from database import get_db
from error_handler import BusinessLogicError, SafeTransaction, retry_on_db_error
from validators import EnhancedAttendanceCreate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/attendances", tags=["Attendances"])


def _validate_ore_voce(db: Session, *, assignment_id: int | None, hours: float, exclude_attendance_id: int | None = None) -> None:
    if not assignment_id:
        return
    voce = db.query(models.VocePianoFinanziario).filter(
        models.VocePianoFinanziario.assignment_id == assignment_id
    ).first()
    if not voce:
        return
    query = db.query(func.coalesce(func.sum(models.Attendance.hours), 0.0)).filter(
        models.Attendance.assignment_id == assignment_id
    )
    if exclude_attendance_id is not None:
        query = query.filter(models.Attendance.id != exclude_attendance_id)
    total = float(query.scalar() or 0.0) + float(hours or 0.0)
    limit = float(voce.ore_previste or voce.ore or 0.0)
    if limit and total > limit:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Ore presenze ({total:g}h) superano ore previste dalla voce ({limit:g}h)",
        )


def _warn_if_budget_superato(db: Session, response: Response, project_id: int) -> None:
    """DOM-10 (GATE W1.4): consuntivo oltre budget alla registrazione presenza =
    WARNING, mai blocco — la presenza registra un fatto avvenuto; il taglio si
    gestisce in rendicontazione. Alert danger anche nel riepilogo piano."""
    piano = crud.get_piano_by_progetto(db, project_id)
    if not piano:
        return
    budget = float(piano.budget_totale or 0)
    utilizzato = float(piano.budget_utilizzato or 0)
    if budget > 0 and utilizzato > budget:
        msg = (
            f"Budget piano {piano.id} superato: consuntivo {utilizzato:.2f} EUR "
            f"su budget {budget:.2f} EUR"
        )
        response.headers["X-Budget-Warning"] = msg
        logger.warning(msg)


def _warn_if_activity_dates_missing(response: Response, project: models.Project) -> None:
    """UX-5: warning machine-readable senza bloccare la registrazione del fatto."""
    if (
        project.data_avvio_attivita_formative is not None
        and project.data_fine_attivita_formative is not None
    ):
        return
    message = "Registri presenze su progetto senza avvio attività dichiarato"
    header_message = "Registri presenze su progetto senza avvio attivita dichiarato"
    response.headers["X-Project-Date-Warning"] = "project_activity_dates_missing"
    response.headers["Warning"] = f'299 pythonpro "{header_message}"'
    logger.warning("%s (project_id=%s)", message, project.id)


@router.post("/", response_model=schemas.Attendance, response_model_by_alias=False)
@retry_on_db_error(max_retries=3)
def create_attendance(
    attendance: EnhancedAttendanceCreate,
    response: Response,
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

            _validate_ore_voce(db, assignment_id=attendance.assignment_id, hours=attendance.hours)
            attendance_data = schemas.AttendanceCreate(**attendance.dict())
            result = crud.create_attendance(db=db, attendance=attendance_data)
            transaction.commit()

            _warn_if_budget_superato(db, response, result.project_id)
            _warn_if_activity_dates_missing(response, project)
            logger.info(f"Presenza registrata con successo: ID {result.id}")
            return result

    except BusinessLogicError:
        raise
    except crud.PianoCongelatoError as e:
        # DOM-08: piano congelato → 409, non 400 (conflitto di stato, non input invalido)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
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
    response: Response,
    db: Session = Depends(get_db)
):
    """AGGIORNA UNA PRESENZA ESISTENTE"""
    try:
        existing = crud.get_attendance(db, attendance_id=attendance_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="Presenza non trovata")
        assignment_id = attendance.assignment_id if attendance.assignment_id is not None else existing.assignment_id
        hours = attendance.hours if attendance.hours is not None else existing.hours
        _validate_ore_voce(db, assignment_id=assignment_id, hours=hours, exclude_attendance_id=attendance_id)
        db_attendance = crud.update_attendance(db, attendance_id, attendance)
        if db_attendance is None:
            raise HTTPException(status_code=404, detail="Presenza non trovata")
        _warn_if_budget_superato(db, response, db_attendance.project_id)
        project = crud.get_project(db, db_attendance.project_id)
        if project is not None:
            _warn_if_activity_dates_missing(response, project)
        return db_attendance
    except HTTPException:
        raise
    except crud.PianoCongelatoError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValueError as e:
        logger.warning(f"Validazione aggiornamento presenza fallita: {e}")
        raise BusinessLogicError(str(e))


@router.delete("/{attendance_id}")
def delete_attendance(
    attendance_id: int,
    db: Session = Depends(get_db)
):
    """ELIMINA UNA PRESENZA"""
    try:
        db_attendance = crud.delete_attendance(db, attendance_id)
    except crud.PianoCongelatoError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    if db_attendance is None:
        raise HTTPException(status_code=404, detail="Presenza non trovata")
    return {"message": "Presenza eliminata con successo"}
