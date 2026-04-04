from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import crud
import schemas
from database import get_db

router = APIRouter(prefix="/api/v1/avvisi", tags=["Avvisi"])


@router.get("/", response_model=List[schemas.Avviso], response_model_by_alias=False)
def read_avvisi(
    skip: int = 0,
    limit: int = 100,
    ente_erogatore: Optional[str] = None,
    active_only: bool = True,
    db: Session = Depends(get_db),
):
    return crud.get_avvisi(
        db,
        skip=skip,
        limit=limit,
        ente_erogatore=ente_erogatore,
        active_only=active_only,
    )


@router.post("/", response_model=schemas.Avviso, response_model_by_alias=False)
def create_avviso(avviso: schemas.AvvisoCreate, db: Session = Depends(get_db)):
    try:
        return crud.create_avviso(db, avviso)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Avviso duplicato per codice/ente erogatore")


@router.get("/{avviso_id}", response_model=schemas.Avviso, response_model_by_alias=False)
def read_avviso(avviso_id: int, db: Session = Depends(get_db)):
    db_avviso = crud.get_avviso(db, avviso_id)
    if db_avviso is None:
        raise HTTPException(status_code=404, detail="Avviso non trovato")
    return db_avviso


@router.put("/{avviso_id}", response_model=schemas.Avviso, response_model_by_alias=False)
def update_avviso(avviso_id: int, avviso: schemas.AvvisoUpdate, db: Session = Depends(get_db)):
    try:
        db_avviso = crud.update_avviso(db, avviso_id, avviso)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Avviso duplicato per codice/ente erogatore")
    if db_avviso is None:
        raise HTTPException(status_code=404, detail="Avviso non trovato")
    return db_avviso


@router.delete("/{avviso_id}")
def delete_avviso(avviso_id: int, db: Session = Depends(get_db)):
    db_avviso = crud.delete_avviso(db, avviso_id)
    if db_avviso is None:
        raise HTTPException(status_code=404, detail="Avviso non trovato")
    return {"message": "Avviso disattivato con successo", "id": avviso_id}
