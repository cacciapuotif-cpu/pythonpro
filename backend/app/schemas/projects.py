"""
Schemi Pydantic per Progetti
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date


class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: str = "active"


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[str] = None


class Project(ProjectBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
