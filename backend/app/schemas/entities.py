"""
Schemi Pydantic per Enti Attuatori
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class EntityBase(BaseModel):
    name: str
    description: Optional[str] = None
    vat_number: Optional[str] = None
    address: Optional[str] = None


class EntityCreate(EntityBase):
    pass


class EntityUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    vat_number: Optional[str] = None
    address: Optional[str] = None


class Entity(EntityBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
