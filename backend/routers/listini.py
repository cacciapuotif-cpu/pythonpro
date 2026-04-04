"""Router per gestione listini prezzi e relative voci."""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

import crud
import schemas
from database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/listini", tags=["Listini"])

TIPI_CLIENTE = ['standard', 'apprendistato', 'finanziato', 'gratis']


# ── Listini ──────────────────────────────────────────────────────────────────

@router.post("/", response_model=schemas.Listino, status_code=status.HTTP_201_CREATED)
def create_listino(listino: schemas.ListinoCreate, db: Session = Depends(get_db)):
    """Crea un nuovo listino."""
    try:
        db_obj = crud.create_listino(db, listino)
        logger.info(f"Listino creato: {db_obj.nome} (ID: {db_obj.id})")
        return db_obj
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Errore creazione listino: {e}")
        raise HTTPException(status_code=500, detail="Errore nella creazione del listino")


@router.get("/", response_model=List[schemas.Listino])
def get_listini(
    search: Optional[str] = Query(None),
    tipo_cliente: Optional[str] = Query(None),
    attivo: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Lista listini con filtri."""
    if tipo_cliente and tipo_cliente not in TIPI_CLIENTE:
        raise HTTPException(status_code=400, detail=f"tipo_cliente non valido: {TIPI_CLIENTE}")
    items, _ = crud.get_listini(db, search=search, tipo_cliente=tipo_cliente, attivo=attivo, skip=skip, limit=limit)
    return items


@router.get("/tipi-cliente", response_model=List[str])
def get_tipi_cliente():
    """Restituisce i tipi cliente disponibili per i listini."""
    return TIPI_CLIENTE


@router.get("/{listino_id}", response_model=schemas.ListinoWithVoci)
def get_listino(listino_id: int, db: Session = Depends(get_db)):
    """Dettaglio listino con tutte le voci e prodotti embedded."""
    db_obj = crud.get_listino(db, listino_id)
    if not db_obj:
        raise HTTPException(status_code=404, detail="Listino non trovato")
    return db_obj


@router.put("/{listino_id}", response_model=schemas.Listino)
def update_listino(listino_id: int, listino: schemas.ListinoUpdate, db: Session = Depends(get_db)):
    try:
        db_obj = crud.update_listino(db, listino_id, listino)
        if not db_obj:
            raise HTTPException(status_code=404, detail="Listino non trovato")
        return db_obj
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{listino_id}", response_model=schemas.Listino)
def delete_listino(listino_id: int, db: Session = Depends(get_db)):
    """Soft delete: attivo=False."""
    db_obj = crud.delete_listino(db, listino_id)
    if not db_obj:
        raise HTTPException(status_code=404, detail="Listino non trovato")
    return db_obj


# ── Voci del listino ─────────────────────────────────────────────────────────

@router.get("/{listino_id}/voci", response_model=List[schemas.ListinoVoceWithProdotto])
def get_voci(listino_id: int, db: Session = Depends(get_db)):
    """Lista voci di un listino con prodotto embedded e prezzo calcolato."""
    if not crud.get_listino(db, listino_id):
        raise HTTPException(status_code=404, detail="Listino non trovato")
    voci = crud.get_voci_listino(db, listino_id)
    # Arricchisce ogni voce con prezzo_finale calcolato
    result = []
    for v in voci:
        data = schemas.ListinoVoceWithProdotto.model_validate(v)
        prezzo_base = v.prodotto.prezzo_base if v.prodotto else 0.0
        data.prezzo_finale = crud.calcola_prezzo_finale(prezzo_base, v.prezzo_override, v.sconto_percentuale)
        result.append(data)
    return result


@router.post("/{listino_id}/voci", response_model=schemas.ListinoVoceWithProdotto, status_code=201)
def add_voce(listino_id: int, voce: schemas.ListinoVoceCreate, db: Session = Depends(get_db)):
    """Aggiunge un prodotto al listino con prezzo/sconto specifico."""
    if not crud.get_listino(db, listino_id):
        raise HTTPException(status_code=404, detail="Listino non trovato")
    if voce.listino_id != listino_id:
        voce = voce.model_copy(update={"listino_id": listino_id})
    try:
        # Verifica unicità listino+prodotto
        import models as m
        existing = (db.query(m.ListinoVoce)
                    .filter(m.ListinoVoce.listino_id == listino_id,
                            m.ListinoVoce.prodotto_id == voce.prodotto_id).first())
        if existing:
            raise HTTPException(status_code=400, detail="Prodotto già presente in questo listino")
        db_obj = crud.create_voce(db, voce)
        prezzo_base = db_obj.prodotto.prezzo_base if db_obj.prodotto else 0.0
        result = schemas.ListinoVoceWithProdotto.model_validate(db_obj)
        result.prezzo_finale = crud.calcola_prezzo_finale(prezzo_base, db_obj.prezzo_override, db_obj.sconto_percentuale)
        return result
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{listino_id}/voci/{voce_id}", response_model=schemas.ListinoVoceWithProdotto)
def update_voce(listino_id: int, voce_id: int, voce: schemas.ListinoVoceUpdate, db: Session = Depends(get_db)):
    """Aggiorna prezzo/sconto di una voce."""
    try:
        db_obj = crud.update_voce(db, voce_id, voce)
        if not db_obj or db_obj.listino_id != listino_id:
            raise HTTPException(status_code=404, detail="Voce non trovata")
        prezzo_base = db_obj.prodotto.prezzo_base if db_obj.prodotto else 0.0
        result = schemas.ListinoVoceWithProdotto.model_validate(db_obj)
        result.prezzo_finale = crud.calcola_prezzo_finale(prezzo_base, db_obj.prezzo_override, db_obj.sconto_percentuale)
        return result
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{listino_id}/voci/{voce_id}")
def delete_voce(listino_id: int, voce_id: int, db: Session = Depends(get_db)):
    """Rimuove una voce dal listino (hard delete)."""
    voce = crud.get_voce(db, voce_id)
    if not voce or voce.listino_id != listino_id:
        raise HTTPException(status_code=404, detail="Voce non trovata")
    crud.delete_voce(db, voce_id)
    return {"message": "Voce rimossa"}


# ── Prezzo calcolato ─────────────────────────────────────────────────────────

@router.get("/{listino_id}/prezzo/{prodotto_id}", response_model=schemas.PrezzoCalcolatoResponse)
def get_prezzo(listino_id: int, prodotto_id: int, db: Session = Depends(get_db)):
    """Calcola il prezzo finale di un prodotto in un listino specifico."""
    result = crud.get_prezzo_prodotto_in_listino(db, prodotto_id, listino_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Prodotto non presente in questo listino")
    return result
