"""Router per gestione aziende clienti."""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional
import logging

import crud
import schemas
from database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/aziende-clienti", tags=["Aziende Clienti"])

SORT_FIELDS = {"ragione_sociale", "citta", "created_at", "partita_iva"}


@router.post("/", response_model=schemas.AziendaCliente, status_code=status.HTTP_201_CREATED)
def create_azienda_cliente(azienda: schemas.AziendaClienteCreate, db: Session = Depends(get_db)):
    """Crea una nuova azienda cliente."""
    try:
        if azienda.partita_iva:
            piva_conflict = crud.find_partita_iva_conflict(
                db,
                azienda.partita_iva,
                entity_type="azienda_cliente",
            )
            if piva_conflict:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=piva_conflict["message"]
                )
        db_obj = crud.create_azienda_cliente(db, azienda)
        logger.info(f"Azienda creata: {db_obj.ragione_sociale} (ID: {db_obj.id})")
        return db_obj
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Errore creazione azienda cliente: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Errore nella creazione dell'azienda cliente")


@router.get("/", response_model=schemas.PaginatedResponse[schemas.AziendaCliente])
def get_aziende_clienti(
    search: Optional[str] = Query(None, description="Ricerca su ragione sociale, PEC, P.IVA"),
    citta: Optional[str] = Query(None),
    agenzia_id: Optional[int] = Query(None),
    consulente_id: Optional[int] = Query(None),
    attivo: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort_by: str = Query("ragione_sociale"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db)
):
    """Lista aziende clienti paginata con filtri e ordinamento."""
    if sort_by not in SORT_FIELDS:
        sort_by = "ragione_sociale"
    items, total, pages = crud.get_aziende_clienti(
        db, search=search, citta=citta, agenzia_id=agenzia_id, consulente_id=consulente_id,
        attivo=attivo, page=page, limit=limit, sort_by=sort_by, order=order
    )
    return schemas.PaginatedResponse(
        items=items,
        total=total,
        page=page,
        pages=pages,
        has_next=page < pages
    )


@router.get("/search", response_model=List[schemas.AziendaCliente])
def search_aziende(
    q: str = Query(..., min_length=2, description="Testo di ricerca (min 2 caratteri)"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """Full-text search rapida su ragione_sociale (per autocomplete)."""
    items, _, _ = crud.get_aziende_clienti(db, search=q, attivo=True, page=1, limit=limit)
    return items


@router.get("/{azienda_id}", response_model=schemas.AziendaClienteWithConsulente)
def get_azienda_cliente(azienda_id: int, db: Session = Depends(get_db)):
    db_obj = crud.get_azienda_cliente(db, azienda_id)
    if not db_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Azienda cliente non trovata")
    return db_obj


@router.put("/{azienda_id}", response_model=schemas.AziendaCliente)
def update_azienda_cliente(azienda_id: int, azienda: schemas.AziendaClienteUpdate,
                            db: Session = Depends(get_db)):
    try:
        if azienda.partita_iva:
            piva_conflict = crud.find_partita_iva_conflict(
                db,
                azienda.partita_iva,
                entity_type="azienda_cliente",
                entity_id=azienda_id,
            )
            if piva_conflict:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=piva_conflict["message"]
                )
        db_obj = crud.update_azienda_cliente(db, azienda_id, azienda)
        if not db_obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="Azienda cliente non trovata")
        return db_obj
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{azienda_id}", response_model=schemas.AziendaCliente)
def delete_azienda_cliente(azienda_id: int, db: Session = Depends(get_db)):
    """Soft delete: imposta attivo=False."""
    try:
        db_obj = crud.delete_azienda_cliente(db, azienda_id)
        if not db_obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="Azienda cliente non trovata")
        return db_obj
    except HTTPException:
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossibile eliminare: esistono preventivi o ordini collegati a questa azienda. Eliminali prima."
        )


@router.post("/bulk-import")
def bulk_import_aziende_clienti(
    aziende: List[schemas.AziendaClienteCreate],
    db: Session = Depends(get_db),
):
    success_count = 0
    error_count = 0
    errors = []
    created_ids = []

    for index, azienda_data in enumerate(aziende):
        try:
            if azienda_data.partita_iva:
                piva_conflict = crud.find_partita_iva_conflict(
                    db,
                    azienda_data.partita_iva,
                    entity_type="azienda_cliente",
                )
                if piva_conflict:
                    error_count += 1
                    errors.append({
                        "index": index + 1,
                        "name": azienda_data.ragione_sociale,
                        "error": piva_conflict["message"],
                    })
                    continue

            result = crud.create_azienda_cliente(db, azienda_data)
            created_ids.append(result.id)
            success_count += 1
        except Exception as exc:
            db.rollback()
            error_count += 1
            errors.append({
                "index": index + 1,
                "name": azienda_data.ragione_sociale,
                "error": str(exc),
            })

    return {
        "success_count": success_count,
        "error_count": error_count,
        "total": len(aziende),
        "errors": errors,
        "created_ids": created_ids,
        "message": f"Importazione completata: {success_count} su {len(aziende)} aziende importate con successo",
    }
