"""
Schemi Pydantic per Contratti e Template
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ContractTemplateBase(BaseModel):
    name: str
    description: Optional[str] = None
    template_type: str
    content: str


class ContractTemplateCreate(ContractTemplateBase):
    pass


class ContractTemplate(ContractTemplateBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class ContractGenerateRequest(BaseModel):
    template_id: int
    collaborator_id: int
    project_id: int
    entity_id: int
