"""
Router Assegnazioni - Implementazione In-Memory
"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import datetime
from app.schemas.assignments import Assignment, AssignmentCreate

router = APIRouter(prefix="/api/v1/assignments", tags=["Assignments"])

# Storage in-memory
assignments_db = []
next_id = 1


@router.post("/", response_model=Assignment, status_code=201)
def create_assignment(assignment: AssignmentCreate):
    """Crea una nuova assegnazione progetto-ente-mansione-collaboratore"""
    global next_id

    new_assignment = {
        "id": next_id,
        **assignment.dict(),
        "created_at": datetime.now()
    }
    assignments_db.append(new_assignment)
    next_id += 1
    return new_assignment


@router.get("/", response_model=List[Assignment])
def get_assignments(
    project_id: Optional[int] = Query(None),
    entity_id: Optional[int] = Query(None),
    role: Optional[str] = Query(None)
):
    """Lista tutte le assegnazioni con filtri opzionali"""
    results = assignments_db

    if project_id:
        results = [a for a in results if a["project_id"] == project_id]
    if entity_id:
        results = [a for a in results if a["entity_id"] == entity_id]
    if role:
        results = [a for a in results if role.lower() in a["role"].lower()]

    return results


@router.delete("/{assignment_id}", status_code=204)
def delete_assignment(assignment_id: int):
    """Elimina un'assegnazione"""
    global assignments_db
    initial_len = len(assignments_db)
    assignments_db = [a for a in assignments_db if a["id"] != assignment_id]
    if len(assignments_db) == initial_len:
        raise HTTPException(status_code=404, detail="Assegnazione non trovata")
    return None
