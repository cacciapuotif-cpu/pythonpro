"""Router per gestione allievi."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional

import crud
import schemas
from database import get_db

router = APIRouter(prefix="/api/v1/allievi", tags=["Allievi"])


@router.get("/", response_model=schemas.PaginatedResponse[schemas.Allievo])
def read_allievi(
    search: Optional[str] = Query(None),
    azienda_cliente_id: Optional[int] = Query(None),
    project_id: Optional[int] = Query(None),
    occupato: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    items, total, pages = crud.get_allievi(
        db,
        search=search,
        azienda_cliente_id=azienda_cliente_id,
        project_id=project_id,
        occupato=occupato,
        page=page,
        limit=limit,
    )
    return schemas.PaginatedResponse(
        items=items,
        total=total,
        page=page,
        pages=pages,
        has_next=page < pages,
    )


@router.get("/{allievo_id}", response_model=schemas.Allievo)
def read_allievo(allievo_id: int, db: Session = Depends(get_db)):
    db_obj = crud.get_allievo(db, allievo_id)
    if not db_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Allievo non trovato")
    return db_obj


@router.post("/", response_model=schemas.Allievo, status_code=status.HTTP_201_CREATED)
def create_allievo(allievo: schemas.AllievoCreate, db: Session = Depends(get_db)):
    try:
        return crud.create_allievo(db, allievo)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.put("/{allievo_id}", response_model=schemas.Allievo)
def update_allievo(allievo_id: int, allievo: schemas.AllievoUpdate, db: Session = Depends(get_db)):
    try:
        db_obj = crud.update_allievo(db, allievo_id, allievo)
        if not db_obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Allievo non trovato")
        return db_obj
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.delete("/{allievo_id}", response_model=schemas.Allievo)
def delete_allievo(allievo_id: int, db: Session = Depends(get_db)):
    db_obj = crud.delete_allievo(db, allievo_id)
    if not db_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Allievo non trovato")
    return db_obj


@router.post("/bulk-import")
def bulk_import_allievi(
    allievi: List[schemas.AllievoCreate],
    db: Session = Depends(get_db),
):
    success_count = 0
    error_count = 0
    errors = []
    created_ids = []

    for index, allievo_data in enumerate(allievi):
        try:
            if allievo_data.codice_fiscale:
                existing = crud.get_allievi(
                    db,
                    search=allievo_data.codice_fiscale,
                    page=1,
                    limit=1,
                )[0]
                if any((item.codice_fiscale or "").upper() == allievo_data.codice_fiscale.upper() for item in existing):
                    error_count += 1
                    errors.append({
                        "index": index + 1,
                        "name": f"{allievo_data.nome} {allievo_data.cognome}",
                        "error": f"Codice fiscale '{allievo_data.codice_fiscale.upper()}' già esistente",
                    })
                    continue

            result = crud.create_allievo(db=db, allievo=allievo_data)
            created_ids.append(result.id)
            success_count += 1
        except Exception as exc:
            db.rollback()
            error_count += 1
            errors.append({
                "index": index + 1,
                "name": f"{allievo_data.nome} {allievo_data.cognome}",
                "error": str(exc),
            })

    return {
        "success_count": success_count,
        "error_count": error_count,
        "total": len(allievi),
        "errors": errors,
        "created_ids": created_ids,
        "message": f"Importazione completata: {success_count} su {len(allievi)} allievi importati con successo",
    }
