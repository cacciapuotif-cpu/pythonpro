"""
Router Contratti & Template - Implementazione In-Memory
"""
from fastapi import APIRouter, HTTPException
from typing import List
from datetime import datetime
from app.schemas.contracts import ContractTemplate, ContractTemplateCreate, ContractGenerateRequest

router = APIRouter(prefix="/api/v1/contracts", tags=["Contracts"])

# Storage in-memory
templates_db = []
next_id = 1


@router.post("/templates", response_model=ContractTemplate, status_code=201)
def create_template(template: ContractTemplateCreate):
    """Crea un nuovo template contratto"""
    global next_id

    new_template = {
        "id": next_id,
        **template.dict(),
        "created_at": datetime.now()
    }
    templates_db.append(new_template)
    next_id += 1
    return new_template


@router.get("/templates", response_model=List[ContractTemplate])
def get_templates():
    """Lista tutti i template contratti"""
    return templates_db


@router.delete("/templates/{template_id}", status_code=204)
def delete_template(template_id: int):
    """Elimina un template"""
    global templates_db
    initial_len = len(templates_db)
    templates_db = [t for t in templates_db if t["id"] != template_id]
    if len(templates_db) == initial_len:
        raise HTTPException(status_code=404, detail="Template non trovato")
    return None


@router.post("/generate")
def generate_contract(request: ContractGenerateRequest):
    """Genera un contratto da template"""
    template = next((t for t in templates_db if t["id"] == request.template_id), None)
    if not template:
        raise HTTPException(status_code=404, detail="Template non trovato")

    # Simulazione generazione contratto
    return {
        "message": "Contratto generato con successo",
        "template_id": request.template_id,
        "collaborator_id": request.collaborator_id,
        "project_id": request.project_id,
        "entity_id": request.entity_id,
        "generated_at": datetime.now().isoformat()
    }
