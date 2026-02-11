"""
Schemi Pydantic per Collaboratori
"""
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, date


class CollaboratorBase(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    fiscal_code: str
    birthplace: Optional[str] = None
    birth_date: Optional[date] = None


class CollaboratorCreate(CollaboratorBase):
    pass


class CollaboratorUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    fiscal_code: Optional[str] = None
    birthplace: Optional[str] = None
    birth_date: Optional[date] = None


class Collaborator(CollaboratorBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
