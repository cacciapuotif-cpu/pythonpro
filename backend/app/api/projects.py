"""
Router Progetti - Implementazione In-Memory
"""
from fastapi import APIRouter, HTTPException
from typing import List, Optional
from datetime import datetime
from app.schemas.projects import Project, ProjectCreate, ProjectUpdate

router = APIRouter(prefix="/api/v1/projects", tags=["Projects"])

# Storage in-memory
projects_db = []
next_id = 1


@router.post("/", response_model=Project, status_code=201)
def create_project(project: ProjectCreate):
    """Crea un nuovo progetto"""
    global next_id

    new_project = {
        "id": next_id,
        **project.dict(),
        "created_at": datetime.now()
    }
    projects_db.append(new_project)
    next_id += 1
    return new_project


@router.get("/", response_model=List[Project])
def get_projects(status: Optional[str] = None):
    """Lista tutti i progetti con filtro status opzionale"""
    if status:
        return [p for p in projects_db if p["status"] == status]
    return projects_db


@router.get("/{project_id}", response_model=Project)
def get_project(project_id: int):
    """Ottieni un progetto specifico"""
    project = next((p for p in projects_db if p["id"] == project_id), None)
    if not project:
        raise HTTPException(status_code=404, detail="Progetto non trovato")
    return project


@router.put("/{project_id}", response_model=Project)
def update_project(project_id: int, project: ProjectUpdate):
    """Aggiorna un progetto"""
    proj = next((p for p in projects_db if p["id"] == project_id), None)
    if not proj:
        raise HTTPException(status_code=404, detail="Progetto non trovato")

    update_data = project.dict(exclude_unset=True)
    proj.update(update_data)
    return proj


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: int):
    """Elimina un progetto"""
    global projects_db
    initial_len = len(projects_db)
    projects_db = [p for p in projects_db if p["id"] != project_id]
    if len(projects_db) == initial_len:
        raise HTTPException(status_code=404, detail="Progetto non trovato")
    return None
