"""
Schemi Pydantic per Presenze
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date


class AttendanceBase(BaseModel):
    collaborator_id: int
    project_id: int
    date: date
    hours: float
    notes: Optional[str] = None


class AttendanceCreate(AttendanceBase):
    pass


class AttendanceUpdate(BaseModel):
    hours: Optional[float] = None
    notes: Optional[str] = None


class Attendance(AttendanceBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
