"""Router per la gestione degli ordini."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional, List
import logging

import crud
import schemas
from database import get_db

router = APIRouter(prefix="/api/v1/ordini", tags=["ordini"])
logger = logging.getLogger(__name__)


@router.get("/stati", response_model=List[str])
def get_stati():
    return ['in_lavorazione', 'completato', 'annullato']


@router.get("/", response_model=schemas.PaginatedResponse)
def list_ordini(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    stato: Optional[str] = Query(None),
    azienda_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    items, total = crud.get_ordini(db, skip=skip, limit=limit,
                                   stato=stato, azienda_id=azienda_id, search=search)
    page = skip // limit + 1 if limit else 1
    pages = (total + limit - 1) // limit if limit else 1
    serialized = [schemas.OrdineRead.model_validate(o) for o in items]
    return {"items": serialized, "total": total, "page": page, "pages": pages, "has_next": page < pages}


@router.get("/{ordine_id}", response_model=schemas.OrdineRead)
def get_ordine(ordine_id: int, db: Session = Depends(get_db)):
    obj = crud.get_ordine(db, ordine_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Ordine non trovato")
    return obj


@router.put("/{ordine_id}", response_model=schemas.OrdineRead)
def update_ordine(ordine_id: int, data: schemas.OrdineUpdate, db: Session = Depends(get_db)):
    obj = crud.update_ordine(db, ordine_id, data)
    if not obj:
        raise HTTPException(status_code=404, detail="Ordine non trovato")
    return obj


@router.delete("/{ordine_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ordine(ordine_id: int, db: Session = Depends(get_db)):
    """
    Elimina logicamente un ordine annullandolo.
    """
    ordine = crud.get_ordine(db, ordine_id)
    if not ordine:
        raise HTTPException(status_code=404, detail="Ordine non trovato")

    crud.update_ordine(db, ordine_id, schemas.OrdineUpdate(stato="annullato"))
    logger.info("Ordine %s annullato", ordine_id)
    return None


@router.delete("/{ordine_id}/hard", status_code=status.HTTP_204_NO_CONTENT)
def hard_delete_ordine(ordine_id: int, db: Session = Depends(get_db)):
    """
    Elimina fisicamente un ordine.
    """
    ordine = crud.get_ordine(db, ordine_id)
    if not ordine:
        raise HTTPException(status_code=404, detail="Ordine non trovato")

    crud.delete_ordine(db, ordine_id)
    logger.info("Ordine %s eliminato permanentemente", ordine_id)
    return None
