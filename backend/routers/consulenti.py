"""Router per gestione consulenti / agenti commerciali."""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

import crud
import schemas
from database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/consulenti", tags=["Consulenti"])


@router.post("/", response_model=schemas.Consulente, status_code=status.HTTP_201_CREATED)
def create_consulente(consulente: schemas.ConsulenteCreate, db: Session = Depends(get_db)):
    """Crea un nuovo consulente."""
    try:
        # Verifica unicità email
        if consulente.email:
            existing = db.query(__import__('models').Consulente).filter(
                __import__('models').Consulente.email == consulente.email
            ).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Esiste già un consulente con email {consulente.email}"
                )
        db_obj = crud.create_consulente(db, consulente)
        logger.info(f"Consulente creato: {db_obj.cognome} {db_obj.nome} (ID: {db_obj.id})")
        return db_obj
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Errore creazione consulente: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Errore nella creazione del consulente")


@router.get("/", response_model=schemas.PaginatedResponse[schemas.Consulente])
def get_consulenti(
    search: Optional[str] = Query(None, description="Ricerca su nome, cognome, email"),
    attivo: Optional[bool] = Query(None),
    agenzia_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Lista consulenti paginata con filtri."""
    items, total, pages = crud.get_consulenti(
        db, search=search, attivo=attivo, agenzia_id=agenzia_id, page=page, limit=limit
    )
    return schemas.PaginatedResponse(
        items=items,
        total=total,
        page=page,
        pages=pages,
        has_next=page < pages
    )


@router.get("/{consulente_id}", response_model=schemas.ConsulenteWithAgenzia)
def get_consulente(consulente_id: int, db: Session = Depends(get_db)):
    db_obj = crud.get_consulente(db, consulente_id)
    if not db_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consulente non trovato")
    return db_obj


@router.get("/{consulente_id}/aziende", response_model=List[schemas.AziendaCliente])
def get_aziende_consulente(consulente_id: int, db: Session = Depends(get_db)):
    """Lista aziende clienti gestite da questo consulente."""
    if not crud.get_consulente(db, consulente_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consulente non trovato")
    return crud.get_aziende_by_consulente(db, consulente_id)


@router.put("/{consulente_id}", response_model=schemas.Consulente)
def update_consulente(consulente_id: int, consulente: schemas.ConsulenteUpdate,
                      db: Session = Depends(get_db)):
    try:
        db_obj = crud.update_consulente(db, consulente_id, consulente)
        if not db_obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consulente non trovato")
        return db_obj
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{consulente_id}", response_model=schemas.Consulente)
def delete_consulente(consulente_id: int, db: Session = Depends(get_db)):
    """Soft delete: imposta attivo=False."""
    db_obj = crud.delete_consulente(db, consulente_id)
    if not db_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consulente non trovato")
    return db_obj
