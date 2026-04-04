"""
Router per gestione progetti
Gestisce CRUD progetti e associazioni con collaboratori
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

import crud
import schemas
from database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/projects", tags=["Projects"])


@router.post("/", response_model=schemas.Project, response_model_by_alias=False)
def create_project(
    project: schemas.ProjectCreateExtended,
    db: Session = Depends(get_db)
):
    """CREA UN NUOVO PROGETTO FORMATIVO"""
    try:
        result = crud.create_project(db=db, project=project)
        db.commit()
        db.refresh(result)
        logger.info(f"Progetto creato: ID {result.id}")
        return result
    except Exception as e:
        db.rollback()
        logger.error(f"Errore creazione progetto: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[schemas.Project], response_model_by_alias=False)
def read_projects(
    skip: int = 0,
    limit: int = 100,
    is_active: Optional[bool] = True,
    db: Session = Depends(get_db)
):
    """OTTIENI LISTA DI TUTTI I PROGETTI"""
    projects = crud.get_projects(db, skip=skip, limit=limit, is_active=is_active)
    return projects


@router.get("/{project_id}", response_model=schemas.Project, response_model_by_alias=False)
def read_project(
    project_id: int,
    db: Session = Depends(get_db)
):
    """OTTIENI UN PROGETTO SPECIFICO"""
    db_project = crud.get_project(db, project_id=project_id)
    if db_project is None:
        raise HTTPException(status_code=404, detail="Progetto non trovato")
    return db_project


@router.get(
    "/{project_id}/full-context",
    response_model=schemas.ProjectFullContext,
    response_model_by_alias=False,
    summary="Super-Context Progetto per Agenti AI",
    description=(
        "Restituisce in una singola risposta il contesto operativo completo del progetto: "
        "anagrafica progetto, ente attuatore, piani finanziari attivi e stato ore collaboratori "
        "aggregato. Endpoint pensato per tool-use AI con payload semantico pronto."
    ),
)
def read_project_full_context(
    project_id: int,
    db: Session = Depends(get_db),
):
    full_context = crud.get_project_full_context(db, project_id=project_id)
    if full_context is None:
        raise HTTPException(status_code=404, detail="Progetto non trovato")
    return full_context


@router.put("/{project_id}", response_model=schemas.Project, response_model_by_alias=False)
def update_project(
    project_id: int,
    project: schemas.ProjectUpdateExtended,
    db: Session = Depends(get_db)
):
    """AGGIORNA UN PROGETTO ESISTENTE"""
    db_project = crud.update_project(db, project_id, project)
    if db_project is None:
        raise HTTPException(status_code=404, detail="Progetto non trovato")
    return db_project


@router.delete("/{project_id}")
def delete_project(
    project_id: int,
    db: Session = Depends(get_db)
):
    """ELIMINA UN PROGETTO"""
    db_project = crud.delete_project(db, project_id)
    if db_project is None:
        raise HTTPException(status_code=404, detail="Progetto non trovato")
    return {"message": "Progetto eliminato con successo"}
