"""
Router Collaboratori - Implementazione In-Memory
"""
from fastapi import APIRouter, HTTPException
from typing import List, Optional
from datetime import datetime
from app.schemas.collaborators import Collaborator, CollaboratorCreate, CollaboratorUpdate

router = APIRouter(prefix="/api/v1/collaborators", tags=["Collaborators"])

# Storage in-memory
collaborators_db = []
next_id = 1


@router.post("/", response_model=Collaborator, status_code=201)
def create_collaborator(collaborator: CollaboratorCreate):
    """Crea un nuovo collaboratore"""
    global next_id

    # Verifica email duplicata
    if any(c["email"] == collaborator.email for c in collaborators_db):
        raise HTTPException(status_code=400, detail=f"Email già esistente: {collaborator.email}")

    new_collaborator = {
        "id": next_id,
        **collaborator.dict(),
        "created_at": datetime.now()
    }
    collaborators_db.append(new_collaborator)
    next_id += 1
    return new_collaborator


@router.get("/", response_model=List[Collaborator])
def get_collaborators(search: Optional[str] = None):
    """Lista tutti i collaboratori con ricerca opzionale"""
    if search:
        return [c for c in collaborators_db
                if search.lower() in c["first_name"].lower()
                or search.lower() in c["last_name"].lower()
                or search.lower() in c["email"].lower()]
    return collaborators_db


@router.get("/{collaborator_id}", response_model=Collaborator)
def get_collaborator(collaborator_id: int):
    """Ottieni un collaboratore specifico"""
    collab = next((c for c in collaborators_db if c["id"] == collaborator_id), None)
    if not collab:
        raise HTTPException(status_code=404, detail="Collaboratore non trovato")
    return collab


@router.put("/{collaborator_id}", response_model=Collaborator)
def update_collaborator(collaborator_id: int, collaborator: CollaboratorUpdate):
    """Aggiorna un collaboratore"""
    collab = next((c for c in collaborators_db if c["id"] == collaborator_id), None)
    if not collab:
        raise HTTPException(status_code=404, detail="Collaboratore non trovato")

    update_data = collaborator.dict(exclude_unset=True)
    collab.update(update_data)
    return collab


@router.delete("/{collaborator_id}", status_code=204)
def delete_collaborator(collaborator_id: int):
    """Elimina un collaboratore"""
    global collaborators_db
    initial_len = len(collaborators_db)
    collaborators_db = [c for c in collaborators_db if c["id"] != collaborator_id]
    if len(collaborators_db) == initial_len:
        raise HTTPException(status_code=404, detail="Collaboratore non trovato")
    return None
