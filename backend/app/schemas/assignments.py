"""
Schemi Pydantic per Assegnazioni
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date


class AssignmentBase(BaseModel):
    collaborator_id: int
    project_id: int
    entity_id: int
    role: str
    start_date: date
    end_date: Optional[date] = None


class AssignmentCreate(AssignmentBase):
    pass


class Assignment(AssignmentBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
