"""
Router Presenze (Calendario) - Implementazione In-Memory
"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import datetime, date
from app.schemas.attendances import Attendance, AttendanceCreate, AttendanceUpdate

router = APIRouter(prefix="/api/v1/attendances", tags=["Attendances"])

# Storage in-memory
attendances_db = []
next_id = 1


@router.post("/", response_model=Attendance, status_code=201)
def create_attendance(attendance: AttendanceCreate):
    """Registra una nuova presenza"""
    global next_id

    new_attendance = {
        "id": next_id,
        **attendance.dict(),
        "created_at": datetime.now()
    }
    attendances_db.append(new_attendance)
    next_id += 1
    return new_attendance


@router.get("/", response_model=List[Attendance])
def get_attendances(
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to")
):
    """Lista presenze con filtro intervallo date"""
    results = attendances_db

    if from_date:
        results = [a for a in results if a["date"] >= from_date]
    if to_date:
        results = [a for a in results if a["date"] <= to_date]

    return results


@router.get("/{attendance_id}", response_model=Attendance)
def get_attendance(attendance_id: int):
    """Ottieni una presenza specifica"""
    attendance = next((a for a in attendances_db if a["id"] == attendance_id), None)
    if not attendance:
        raise HTTPException(status_code=404, detail="Presenza non trovata")
    return attendance


@router.put("/{attendance_id}", response_model=Attendance)
def update_attendance(attendance_id: int, attendance: AttendanceUpdate):
    """Aggiorna una presenza"""
    att = next((a for a in attendances_db if a["id"] == attendance_id), None)
    if not att:
        raise HTTPException(status_code=404, detail="Presenza non trovata")

    update_data = attendance.dict(exclude_unset=True)
    att.update(update_data)
    return att


@router.delete("/{attendance_id}", status_code=204)
def delete_attendance(attendance_id: int):
    """Elimina una presenza"""
    global attendances_db
    initial_len = len(attendances_db)
    attendances_db = [a for a in attendances_db if a["id"] != attendance_id]
    if len(attendances_db) == initial_len:
        raise HTTPException(status_code=404, detail="Presenza non trovata")
    return None
