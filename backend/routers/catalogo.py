"""Router per gestione catalogo prodotti/servizi."""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

import crud
import schemas
from database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/catalogo", tags=["Catalogo"])

TIPI_PRODOTTO = ['apprendistato', 'tirocinio', 'formazione', 'altro']


@router.post("/", response_model=schemas.Prodotto, status_code=status.HTTP_201_CREATED)
def create_prodotto(prodotto: schemas.ProdottoCreate, db: Session = Depends(get_db)):
    """Crea un nuovo prodotto/servizio nel catalogo."""
    try:
        if prodotto.codice:
            import models as m
            if db.query(m.Prodotto).filter(m.Prodotto.codice == prodotto.codice).first():
                raise HTTPException(status_code=400, detail=f"Codice '{prodotto.codice}' già in uso")
        db_obj = crud.create_prodotto(db, prodotto)
        logger.info(f"Prodotto creato: {db_obj.nome} (ID: {db_obj.id})")
        return db_obj
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Errore creazione prodotto: {e}")
        raise HTTPException(status_code=500, detail="Errore nella creazione del prodotto")


@router.get("/", response_model=List[schemas.Prodotto])
def get_prodotti(
    search: Optional[str] = Query(None),
    tipo: Optional[str] = Query(None),
    attivo: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Lista prodotti con filtri."""
    if tipo and tipo not in TIPI_PRODOTTO:
        raise HTTPException(status_code=400, detail=f"Tipo non valido. Valori ammessi: {TIPI_PRODOTTO}")
    items, _ = crud.get_prodotti(db, search=search, tipo=tipo, attivo=attivo, skip=skip, limit=limit)
    return items


@router.get("/tipi", response_model=List[str])
def get_tipi_prodotto():
    """Restituisce i tipi di prodotto disponibili."""
    return TIPI_PRODOTTO


@router.get("/{prodotto_id}", response_model=schemas.Prodotto)
def get_prodotto(prodotto_id: int, db: Session = Depends(get_db)):
    db_obj = crud.get_prodotto(db, prodotto_id)
    if not db_obj:
        raise HTTPException(status_code=404, detail="Prodotto non trovato")
    return db_obj


@router.put("/{prodotto_id}", response_model=schemas.Prodotto)
def update_prodotto(prodotto_id: int, prodotto: schemas.ProdottoUpdate, db: Session = Depends(get_db)):
    try:
        db_obj = crud.update_prodotto(db, prodotto_id, prodotto)
        if not db_obj:
            raise HTTPException(status_code=404, detail="Prodotto non trovato")
        return db_obj
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{prodotto_id}", response_model=schemas.Prodotto)
def delete_prodotto(prodotto_id: int, db: Session = Depends(get_db)):
    """Soft delete: attivo=False."""
    db_obj = crud.delete_prodotto(db, prodotto_id)
    if not db_obj:
        raise HTTPException(status_code=404, detail="Prodotto non trovato")
    return db_obj
