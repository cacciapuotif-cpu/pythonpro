"""
Router per gestione enti attuatori
Gestisce CRUD enti attuatori con upload logo
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import logging
import os

import crud
import schemas
from database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/entities", tags=["Implementing Entities"])


@router.post("/", response_model=schemas.ImplementingEntity)
def create_implementing_entity(
    entity: schemas.ImplementingEntityCreate,
    db: Session = Depends(get_db)
):
    """
    CREA UN NUOVO ENTE ATTUATORE

    Campi obbligatori:
    - ragione_sociale
    - partita_iva (deve essere unica)

    Validazioni automatiche:
    - P.IVA: 11 cifre numeriche
    - IBAN: 27 caratteri formato IT
    - PEC/Email: formato email valido
    - CAP: 5 cifre
    """
    try:
        existing = crud.get_implementing_entity_by_piva(db, entity.partita_iva)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Esiste già un ente con P.IVA {entity.partita_iva}"
            )

        db_entity = crud.create_implementing_entity(db, entity)
        logger.info(f"Created implementing entity: {db_entity.ragione_sociale} (ID: {db_entity.id})")
        return db_entity

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating implementing entity: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Errore nella creazione dell'ente attuatore"
        )


@router.get("/", response_model=List[schemas.ImplementingEntity])
def get_implementing_entities(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """
    RECUPERA LISTA ENTI ATTUATORI

    Parametri query:
    - skip: Salta N record (paginazione)
    - limit: Massimo record da restituire
    - search: Cerca per ragione_sociale, P.IVA, città o PEC
    - is_active: Filtra per stato attivo (true/false)
    """
    entities = crud.get_implementing_entities(
        db,
        skip=skip,
        limit=limit,
        search=search,
        is_active=is_active
    )
    return entities


@router.get("/count")
def get_implementing_entities_count(
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """CONTA IL NUMERO TOTALE DI ENTI (per paginazione frontend)"""
    count = crud.get_implementing_entities_count(db, search=search, is_active=is_active)
    return {"count": count}


@router.get("/{entity_id}", response_model=schemas.ImplementingEntityWithProjects)
def get_implementing_entity(
    entity_id: int,
    db: Session = Depends(get_db)
):
    """RECUPERA UN SINGOLO ENTE ATTUATORE CON I PROGETTI COLLEGATI"""
    entity = crud.get_implementing_entity_with_projects(db, entity_id)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ente attuatore non trovato"
        )
    return entity


@router.put("/{entity_id}", response_model=schemas.ImplementingEntity)
def update_implementing_entity(
    entity_id: int,
    entity: schemas.ImplementingEntityUpdate,
    db: Session = Depends(get_db)
):
    """
    AGGIORNA UN ENTE ATTUATORE ESISTENTE

    Tutti i campi sono opzionali. Vengono aggiornati solo i campi forniti.
    """
    try:
        existing_entity = crud.get_implementing_entity(db, entity_id)
        if not existing_entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ente attuatore non trovato"
            )

        if entity.partita_iva and entity.partita_iva != existing_entity.partita_iva:
            duplicate = crud.get_implementing_entity_by_piva(db, entity.partita_iva)
            if duplicate and duplicate.id != entity_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Esiste già un altro ente con P.IVA {entity.partita_iva}"
                )

        updated_entity = crud.update_implementing_entity(db, entity_id, entity)
        logger.info(f"Updated implementing entity: ID {entity_id}")
        return updated_entity

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating implementing entity {entity_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Errore nell'aggiornamento dell'ente"
        )


@router.delete("/{entity_id}")
def delete_implementing_entity(
    entity_id: int,
    soft_delete: bool = True,
    db: Session = Depends(get_db)
):
    """
    ELIMINA O DISATTIVA UN ENTE ATTUATORE

    Parametri:
    - soft_delete=true (default): Disattiva l'ente (is_active=False) mantenendo lo storico
    - soft_delete=false: Eliminazione fisica (fallisce se ci sono progetti collegati)
    """
    try:
        entity = crud.get_implementing_entity(db, entity_id)
        if not entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ente attuatore non trovato"
            )

        if soft_delete:
            deleted_entity = crud.soft_delete_implementing_entity(db, entity_id)
            logger.info(f"Soft-deleted implementing entity: ID {entity_id}")
            return {
                "message": "Ente disattivato con successo",
                "entity_id": entity_id,
                "soft_delete": True
            }
        else:
            deleted_entity = crud.delete_implementing_entity(db, entity_id)
            logger.info(f"Deleted implementing entity: ID {entity_id}")
            return {
                "message": "Ente eliminato con successo",
                "entity_id": entity_id,
                "soft_delete": False
            }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting implementing entity {entity_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Errore nell'eliminazione dell'ente"
        )


@router.get("/{entity_id}/projects", response_model=List[schemas.Project])
def get_entity_projects(
    entity_id: int,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    RECUPERA TUTTI I PROGETTI DI UN ENTE ATTUATORE

    Parametri:
    - status_filter: Filtra per stato progetto (active, completed, paused, cancelled)
    """
    entity = crud.get_implementing_entity(db, entity_id)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ente attuatore non trovato"
        )

    projects = crud.get_projects_by_entity(db, entity_id, status=status_filter)
    return projects


# ====================================================
# ENDPOINTS PER UPLOAD LOGO ENTE ATTUATORE
# ====================================================

@router.post("/{entity_id}/upload-logo")
async def upload_logo_ente_attuatore(
    entity_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    UPLOAD LOGO per ente attuatore

    - Formati permessi: PNG, JPG, JPEG, SVG, GIF
    - Dimensione massima: 5MB
    """
    from file_upload import save_uploaded_file, delete_file

    entity = crud.get_implementing_entity(db, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Ente attuatore non trovato")

    allowed_extensions = ['.png', '.jpg', '.jpeg', '.svg', '.gif']
    file_extension = os.path.splitext(file.filename)[1].lower()
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Formato file non supportato. Formati ammessi: {', '.join(allowed_extensions)}"
        )

    if entity.logo_path:
        try:
            await delete_file(entity.logo_path)
        except Exception as e:
            logger.warning(f"Errore eliminazione vecchio logo: {e}")

    try:
        filename, filepath = await save_uploaded_file(file, entity_id, "logo_ente")

        entity.logo_filename = filename
        entity.logo_path = filepath
        entity.logo_uploaded_at = datetime.now()
        db.commit()
        db.refresh(entity)

        logger.info(f"Logo uploadato per ente attuatore {entity_id}")

        return {
            "message": "Logo caricato con successo",
            "filename": filename,
            "uploaded_at": entity.logo_uploaded_at
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Errore upload logo: {e}")
        raise HTTPException(status_code=500, detail=f"Errore upload: {str(e)}")


@router.get("/{entity_id}/download-logo")
async def download_logo_ente_attuatore(
    entity_id: int,
    db: Session = Depends(get_db)
):
    """DOWNLOAD LOGO di un ente attuatore"""
    from file_upload import get_file_path

    entity = crud.get_implementing_entity(db, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Ente attuatore non trovato")

    if not entity.logo_path:
        raise HTTPException(status_code=404, detail="Nessun logo caricato per questo ente")

    file_path = get_file_path(entity.logo_path)

    return FileResponse(
        path=file_path,
        filename=entity.logo_filename,
        media_type="application/octet-stream"
    )


@router.delete("/{entity_id}/delete-logo")
async def delete_logo_ente_attuatore(
    entity_id: int,
    db: Session = Depends(get_db)
):
    """ELIMINA LOGO di un ente attuatore"""
    from file_upload import delete_file

    entity = crud.get_implementing_entity(db, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Ente attuatore non trovato")

    if not entity.logo_path:
        raise HTTPException(status_code=404, detail="Nessun logo da eliminare")

    await delete_file(entity.logo_path)

    entity.logo_filename = None
    entity.logo_path = None
    entity.logo_uploaded_at = None
    db.commit()

    return {"message": "Logo eliminato con successo"}
