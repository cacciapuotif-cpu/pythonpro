"""
Router per gestione collaboratori
Gestisce tutte le operazioni CRUD su collaboratori e upload documenti
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import logging

import crud
import schemas
from agent_workflows import sync_collaborator_data_quality
from database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/collaborators", tags=["Collaborators"])


@router.post("/", response_model=schemas.Collaborator, response_model_by_alias=False)
def create_collaborator(
    collaborator: schemas.CollaboratorCreate,
    db: Session = Depends(get_db)
):
    """
    CREA UN NUOVO COLLABORATORE

    Validazioni automatiche:
    - Email: deve essere unica e valida
    - Codice Fiscale: deve essere unico, 16 caratteri, normalizzato uppercase
    """
    try:
        # Verifica email duplicata
        existing_email = crud.get_collaborator_by_email(db, collaborator.email)
        if existing_email:
            raise HTTPException(
                status_code=409,
                detail=f"Esiste già un collaboratore con email '{collaborator.email}'"
            )

        # Verifica codice fiscale duplicato
        existing_cf = crud.get_collaborator_by_fiscal_code(db, collaborator.fiscal_code)
        if existing_cf:
            raise HTTPException(
                status_code=409,
                detail=f"Esiste già un collaboratore con codice fiscale '{collaborator.fiscal_code.upper()}'"
            )

        if collaborator.partita_iva:
            piva_conflict = crud.find_partita_iva_conflict(db, collaborator.partita_iva, entity_type="collaborator")
            if piva_conflict:
                raise HTTPException(
                    status_code=409,
                    detail=piva_conflict["message"]
                )

        result = crud.create_collaborator(db=db, collaborator=collaborator)
        db.commit()
        db.refresh(result)
        try:
            sync_collaborator_data_quality(db, collaborator_id=result.id, trigger_source="collaborator_create")
        except Exception as workflow_exc:
            logger.warning("Auto data quality collaborator %s failed after create: %s", result.id, workflow_exc)
        logger.info(f"Collaboratore creato: {result.first_name} {result.last_name} (CF: {result.fiscal_code})")
        return result
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Errore creazione collaboratore: {e}")
        raise HTTPException(status_code=400, detail=f"Errore creazione collaboratore: {str(e)}")


@router.get("/", response_model=List[schemas.CollaboratorWithProjects], response_model_by_alias=False)
def read_collaborators(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = False,
    db: Session = Depends(get_db)
):
    """OTTIENI LISTA DI TUTTI I COLLABORATORI con paginazione"""
    collaborators = crud.get_collaborators(db, skip=skip, limit=limit, is_active=True if active_only else None)
    logger.info(f"Totale collaboratori restituiti: {len(collaborators)}")
    return collaborators


@router.get("/search", response_model_by_alias=False)
def search_collaborators(
    search: Optional[str] = Query(None, description="Ricerca su nome, cognome, email, CF, posizione"),
    competenza: Optional[str] = Query(None, description="Filtro parziale su posizione/competenza"),
    disponibile: Optional[bool] = Query(None, description="True=ha progetto attivo, False=nessun progetto attivo"),
    citta: Optional[str] = Query(None, description="Filtro parziale su città"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort_by: str = Query("last_name", description="Campo di ordinamento"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db)
):
    """
    SMART SEARCH COLLABORATORI — server-side con filtri, paginazione e ordinamento.

    Restituisce PaginatedResponse con items, total, page, pages, has_next.
    """
    VALID_SORT = {"last_name", "first_name", "email", "position", "city", "created_at"}
    if sort_by not in VALID_SORT:
        sort_by = "last_name"

    items, total, pages = crud.search_collaborators_paginated(
        db,
        search=search,
        competenza=competenza,
        disponibile=disponibile,
        citta=citta,
        page=page,
        limit=limit,
        sort_by=sort_by,
        order=order
    )

    # Serializzazione manuale per mantenere response_model_by_alias=False
    serialized = [schemas.CollaboratorWithProjects.model_validate(c) for c in items]

    return {
        "items": [s.model_dump() for s in serialized],
        "total": total,
        "page": page,
        "pages": pages,
        "has_next": page < pages,
    }


@router.get("/{collaborator_id}", response_model=schemas.CollaboratorWithProjects, response_model_by_alias=False)
def read_collaborator(
    collaborator_id: int,
    db: Session = Depends(get_db)
):
    """OTTIENI UN COLLABORATORE SPECIFICO TRAMITE IL SUO ID"""
    db_collaborator = crud.get_collaborator(db, collaborator_id=collaborator_id)
    if db_collaborator is None:
        raise HTTPException(status_code=404, detail="Collaboratore non trovato")
    return db_collaborator


@router.put("/{collaborator_id}", response_model=schemas.Collaborator, response_model_by_alias=False)
def update_collaborator(
    collaborator_id: int,
    collaborator: schemas.CollaboratorUpdate,
    db: Session = Depends(get_db)
):
    """
    AGGIORNA UN COLLABORATORE ESISTENTE

    Validazioni automatiche:
    - Email: deve essere unica (se viene cambiata)
    - Codice Fiscale: deve essere unico (se viene cambiato)
    """
    try:
        # Verifica esistenza collaboratore
        db_collaborator = crud.get_collaborator(db, collaborator_id)
        if not db_collaborator:
            raise HTTPException(status_code=404, detail="Collaboratore non trovato")

        # Verifica email duplicata
        if collaborator.email:
            existing_email = crud.get_collaborator_by_email(db, collaborator.email)
            if existing_email and existing_email.id != collaborator_id:
                raise HTTPException(
                    status_code=409,
                    detail=f"Esiste già un collaboratore con email '{collaborator.email}'"
                )

        # Verifica codice fiscale duplicato
        if collaborator.fiscal_code:
            existing_cf = crud.get_collaborator_by_fiscal_code(db, collaborator.fiscal_code)
            if existing_cf and existing_cf.id != collaborator_id:
                raise HTTPException(
                    status_code=409,
                    detail=f"Esiste già un collaboratore con codice fiscale '{collaborator.fiscal_code.upper()}'"
                )

        if collaborator.partita_iva:
            piva_conflict = crud.find_partita_iva_conflict(
                db,
                collaborator.partita_iva,
                entity_type="collaborator",
                entity_id=collaborator_id,
            )
            if piva_conflict:
                raise HTTPException(
                    status_code=409,
                    detail=piva_conflict["message"]
                )

        updated_collaborator = crud.update_collaborator(db, collaborator_id, collaborator)
        try:
            sync_collaborator_data_quality(db, collaborator_id=collaborator_id, trigger_source="collaborator_update")
        except Exception as workflow_exc:
            logger.warning("Auto data quality collaborator %s failed after update: %s", collaborator_id, workflow_exc)
        return updated_collaborator
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Errore aggiornamento collaboratore {collaborator_id}: {e}")
        raise HTTPException(status_code=400, detail=f"Errore aggiornamento: {str(e)}")


@router.delete("/{collaborator_id}")
def delete_collaborator(
    collaborator_id: int,
    db: Session = Depends(get_db)
):
    """ELIMINA UN COLLABORATORE - Attenzione: elimina anche tutte le presenze!"""
    db_collaborator = crud.delete_collaborator(db, collaborator_id)
    if db_collaborator is None:
        raise HTTPException(status_code=404, detail="Collaboratore non trovato")
    return {"message": "Collaboratore eliminato con successo"}


@router.post("/bulk-import")
def bulk_import_collaborators(
    collaborators: List[schemas.CollaboratorCreate],
    db: Session = Depends(get_db)
):
    """
    IMPORTAZIONE MASSIVA COLLABORATORI

    Importa una lista di collaboratori in modalità batch.
    Gestisce duplicati e validazioni per ogni collaboratore.

    Ritorna:
    - success_count: numero di collaboratori importati con successo
    - error_count: numero di errori
    - errors: lista dettagliata degli errori
    - created_ids: lista degli ID dei collaboratori creati
    """
    success_count = 0
    error_count = 0
    errors = []
    created_ids = []

    for index, collaborator_data in enumerate(collaborators):
        try:
            # Verifica email duplicata
            existing_email = crud.get_collaborator_by_email(db, collaborator_data.email)
            if existing_email:
                error_count += 1
                errors.append({
                    "index": index + 1,
                    "email": collaborator_data.email,
                    "name": f"{collaborator_data.first_name} {collaborator_data.last_name}",
                    "error": f"Email '{collaborator_data.email}' già esistente"
                })
                continue

            # Verifica codice fiscale duplicato (se fornito)
            if collaborator_data.fiscal_code:
                existing_cf = crud.get_collaborator_by_fiscal_code(db, collaborator_data.fiscal_code)
                if existing_cf:
                    error_count += 1
                    errors.append({
                        "index": index + 1,
                        "email": collaborator_data.email,
                        "name": f"{collaborator_data.first_name} {collaborator_data.last_name}",
                        "error": f"Codice fiscale '{collaborator_data.fiscal_code.upper()}' già esistente"
                    })
                    continue

            if collaborator_data.partita_iva:
                piva_conflict = crud.find_partita_iva_conflict(
                    db,
                    collaborator_data.partita_iva,
                    entity_type="collaborator",
                )
                if piva_conflict:
                    error_count += 1
                    errors.append({
                        "index": index + 1,
                        "email": collaborator_data.email,
                        "name": f"{collaborator_data.first_name} {collaborator_data.last_name}",
                        "error": piva_conflict["message"]
                    })
                    continue

            # Crea il collaboratore
            result = crud.create_collaborator(db=db, collaborator=collaborator_data)
            db.flush()  # Flush per ottenere l'ID senza committare

            created_ids.append(result.id)
            success_count += 1
            logger.info(f"Bulk import: Collaboratore creato - {result.first_name} {result.last_name}")

        except Exception as e:
            error_count += 1
            errors.append({
                "index": index + 1,
                "email": collaborator_data.email if hasattr(collaborator_data, 'email') else 'N/A',
                "name": f"{collaborator_data.first_name} {collaborator_data.last_name}" if hasattr(collaborator_data, 'first_name') else 'N/A',
                "error": str(e)
            })
            logger.error(f"Bulk import error at index {index + 1}: {e}")

    # Commit solo se almeno un collaboratore è stato creato
    if success_count > 0:
        try:
            db.commit()
            logger.info(f"Bulk import completato: {success_count} successi, {error_count} errori")
        except Exception as e:
            db.rollback()
            logger.error(f"Errore durante il commit dell'import massivo: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Errore durante il salvataggio: {str(e)}"
            )
    else:
        db.rollback()

    return {
        "success_count": success_count,
        "error_count": error_count,
        "total": len(collaborators),
        "errors": errors,
        "created_ids": created_ids,
        "message": f"Importazione completata: {success_count} su {len(collaborators)} collaboratori importati con successo"
    }


# ====================================================
# ENDPOINTS PER UPLOAD DOCUMENTI COLLABORATORI
# ====================================================

@router.post("/{collaborator_id}/upload-documento")
async def upload_documento_identita(
    collaborator_id: int,
    file: UploadFile = File(...),
    data_scadenza: str | None = Form(None),
    db: Session = Depends(get_db)
):
    """
    UPLOAD DOCUMENTO IDENTITÀ per collaboratore

    - Formati permessi: PDF, JPG, PNG
    - Dimensione massima: 10MB
    """
    from file_upload import save_uploaded_file, delete_file

    collaborator = crud.get_collaborator(db, collaborator_id)
    if not collaborator:
        raise HTTPException(status_code=404, detail="Collaboratore non trovato")

    if collaborator.documento_identita_path:
        await delete_file(collaborator.documento_identita_path)

    try:
        filename, filepath = await save_uploaded_file(file, collaborator_id, "documento")
        expiry_date = None
        if data_scadenza:
            try:
                expiry_date = datetime.fromisoformat(data_scadenza.replace("Z", "+00:00"))
            except ValueError as exc:
                raise HTTPException(
                    status_code=400,
                    detail="Data scadenza documento non valida"
                ) from exc

        collaborator.documento_identita_filename = filename
        collaborator.documento_identita_path = filepath
        collaborator.documento_identita_uploaded_at = datetime.now()
        collaborator.documento_identita_scadenza = expiry_date
        db.commit()
        db.refresh(collaborator)
        try:
            sync_collaborator_data_quality(db, collaborator_id=collaborator_id, trigger_source="document_upload")
        except Exception as workflow_exc:
            logger.warning("Auto data quality collaborator %s failed after document upload: %s", collaborator_id, workflow_exc)

        logger.info(f"Documento identità uploadato per collaboratore {collaborator_id}")

        return {
            "message": "Documento identità caricato con successo",
            "filename": filename,
            "uploaded_at": collaborator.documento_identita_uploaded_at,
            "documento_identita_scadenza": collaborator.documento_identita_scadenza
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Errore upload documento: {e}")
        raise HTTPException(status_code=500, detail=f"Errore upload: {str(e)}")


@router.post("/{collaborator_id}/upload-curriculum")
async def upload_curriculum(
    collaborator_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    UPLOAD CURRICULUM per collaboratore

    - Formati permessi: PDF, DOC, DOCX
    - Dimensione massima: 10MB
    """
    from file_upload import save_uploaded_file, delete_file

    collaborator = crud.get_collaborator(db, collaborator_id)
    if not collaborator:
        raise HTTPException(status_code=404, detail="Collaboratore non trovato")

    if collaborator.curriculum_path:
        await delete_file(collaborator.curriculum_path)

    try:
        filename, filepath = await save_uploaded_file(file, collaborator_id, "curriculum")

        collaborator.curriculum_filename = filename
        collaborator.curriculum_path = filepath
        collaborator.curriculum_uploaded_at = datetime.now()
        db.commit()
        db.refresh(collaborator)
        try:
            sync_collaborator_data_quality(db, collaborator_id=collaborator_id, trigger_source="curriculum_upload")
        except Exception as workflow_exc:
            logger.warning("Auto data quality collaborator %s failed after curriculum upload: %s", collaborator_id, workflow_exc)

        logger.info(f"Curriculum uploadato per collaboratore {collaborator_id}")

        return {
            "message": "Curriculum caricato con successo",
            "filename": filename,
            "uploaded_at": collaborator.curriculum_uploaded_at
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Errore upload curriculum: {e}")
        raise HTTPException(status_code=500, detail=f"Errore upload: {str(e)}")


@router.get("/{collaborator_id}/download-documento")
async def download_documento_identita(
    collaborator_id: int,
    db: Session = Depends(get_db)
):
    """DOWNLOAD DOCUMENTO IDENTITÀ di un collaboratore"""
    from file_upload import get_file_path

    collaborator = crud.get_collaborator(db, collaborator_id)
    if not collaborator:
        raise HTTPException(status_code=404, detail="Collaboratore non trovato")

    if not collaborator.documento_identita_path:
        raise HTTPException(status_code=404, detail="Nessun documento identità caricato")

    file_path = get_file_path(collaborator.documento_identita_path)

    return FileResponse(
        path=file_path,
        filename=collaborator.documento_identita_filename,
        media_type="application/octet-stream"
    )


@router.get("/{collaborator_id}/download-curriculum")
async def download_curriculum(
    collaborator_id: int,
    db: Session = Depends(get_db)
):
    """DOWNLOAD CURRICULUM di un collaboratore"""
    from file_upload import get_file_path

    collaborator = crud.get_collaborator(db, collaborator_id)
    if not collaborator:
        raise HTTPException(status_code=404, detail="Collaboratore non trovato")

    if not collaborator.curriculum_path:
        raise HTTPException(status_code=404, detail="Nessun curriculum caricato")

    file_path = get_file_path(collaborator.curriculum_path)

    return FileResponse(
        path=file_path,
        filename=collaborator.curriculum_filename,
        media_type="application/octet-stream"
    )


@router.delete("/{collaborator_id}/delete-documento")
async def delete_documento_identita(
    collaborator_id: int,
    db: Session = Depends(get_db)
):
    """ELIMINA DOCUMENTO IDENTITÀ di un collaboratore"""
    from file_upload import delete_file

    collaborator = crud.get_collaborator(db, collaborator_id)
    if not collaborator:
        raise HTTPException(status_code=404, detail="Collaboratore non trovato")

    if not collaborator.documento_identita_path:
        raise HTTPException(status_code=404, detail="Nessun documento da eliminare")

    await delete_file(collaborator.documento_identita_path)

    collaborator.documento_identita_filename = None
    collaborator.documento_identita_path = None
    collaborator.documento_identita_uploaded_at = None
    collaborator.documento_identita_scadenza = None
    db.commit()

    return {"message": "Documento identità eliminato con successo"}


@router.delete("/{collaborator_id}/delete-curriculum")
async def delete_curriculum(
    collaborator_id: int,
    db: Session = Depends(get_db)
):
    """ELIMINA CURRICULUM di un collaboratore"""
    from file_upload import delete_file

    collaborator = crud.get_collaborator(db, collaborator_id)
    if not collaborator:
        raise HTTPException(status_code=404, detail="Collaboratore non trovato")

    if not collaborator.curriculum_path:
        raise HTTPException(status_code=404, detail="Nessun curriculum da eliminare")

    await delete_file(collaborator.curriculum_path)

    collaborator.curriculum_filename = None
    collaborator.curriculum_path = None
    collaborator.curriculum_uploaded_at = None
    db.commit()

    return {"message": "Curriculum eliminato con successo"}
