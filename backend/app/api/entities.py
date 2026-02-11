"""
Router Enti Attuatori - Implementazione In-Memory
"""
from fastapi import APIRouter, HTTPException
from typing import List, Optional
from datetime import datetime
from app.schemas.entities import Entity, EntityCreate, EntityUpdate

router = APIRouter(prefix="/api/v1/entities", tags=["Entities"])

# Storage in-memory
entities_db = []
next_id = 1


@router.post("/", response_model=Entity, status_code=201)
def create_entity(entity: EntityCreate):
    """Crea un nuovo ente attuatore"""
    global next_id

    new_entity = {
        "id": next_id,
        **entity.dict(),
        "created_at": datetime.now()
    }
    entities_db.append(new_entity)
    next_id += 1
    return new_entity


@router.get("/", response_model=List[Entity])
def get_entities(search: Optional[str] = None):
    """Lista tutti gli enti attuatori con ricerca opzionale"""
    if search:
        return [e for e in entities_db
                if search.lower() in e["name"].lower()
                or (e.get("description") and search.lower() in e["description"].lower())]
    return entities_db


@router.get("/{entity_id}", response_model=Entity)
def get_entity(entity_id: int):
    """Ottieni un ente attuatore specifico"""
    entity = next((e for e in entities_db if e["id"] == entity_id), None)
    if not entity:
        raise HTTPException(status_code=404, detail="Ente attuatore non trovato")
    return entity


@router.put("/{entity_id}", response_model=Entity)
def update_entity(entity_id: int, entity: EntityUpdate):
    """Aggiorna un ente attuatore"""
    ent = next((e for e in entities_db if e["id"] == entity_id), None)
    if not ent:
        raise HTTPException(status_code=404, detail="Ente attuatore non trovato")

    update_data = entity.dict(exclude_unset=True)
    ent.update(update_data)
    return ent


@router.delete("/{entity_id}", status_code=204)
def delete_entity(entity_id: int):
    """Elimina un ente attuatore"""
    global entities_db
    initial_len = len(entities_db)
    entities_db = [e for e in entities_db if e["id"] != entity_id]
    if len(entities_db) == initial_len:
        raise HTTPException(status_code=404, detail="Ente attuatore non trovato")
    return None
