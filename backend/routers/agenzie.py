"""Router per gestione agenzie."""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

import crud
import schemas
from database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/agenzie", tags=["Agenzie"])


@router.post("/", response_model=schemas.Agenzia, status_code=status.HTTP_201_CREATED)
def create_agenzia(agenzia: schemas.AgenziaCreate, db: Session = Depends(get_db)):
    """Crea una nuova agenzia."""
    try:
        db_obj = crud.create_agenzia(db, agenzia)
        logger.info(f"Agenzia creata: {db_obj.nome} (ID: {db_obj.id})")
        return db_obj
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Errore creazione agenzia: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Errore nella creazione dell'agenzia")


@router.get("/", response_model=List[schemas.Agenzia])
def get_agenzie(
    search: Optional[str] = Query(None, description="Ricerca per nome"),
    attivo: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Lista agenzie con ricerca e filtri."""
    items, total = crud.get_agenzie(db, search=search, attivo=attivo, skip=skip, limit=limit)
    return items


@router.get("/{agenzia_id}", response_model=schemas.Agenzia)
def get_agenzia(agenzia_id: int, db: Session = Depends(get_db)):
    db_obj = crud.get_agenzia(db, agenzia_id)
    if not db_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agenzia non trovata")
    return db_obj


@router.put("/{agenzia_id}", response_model=schemas.Agenzia)
def update_agenzia(agenzia_id: int, agenzia: schemas.AgenziaUpdate, db: Session = Depends(get_db)):
    try:
        db_obj = crud.update_agenzia(db, agenzia_id, agenzia)
        if not db_obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agenzia non trovata")
        return db_obj
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{agenzia_id}", response_model=schemas.Agenzia)
def delete_agenzia(agenzia_id: int, db: Session = Depends(get_db)):
    """Soft delete: imposta attivo=False."""
    db_obj = crud.delete_agenzia(db, agenzia_id)
    if not db_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agenzia non trovata")
    return db_obj
