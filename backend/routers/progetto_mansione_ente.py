"""
Router per gestione associazioni progetto-mansione-ente
Gestisce collegamenti tra progetti, enti attuatori e mansioni
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

import crud
import schemas
from database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/project-assignments", tags=["Progetto-Mansione-Ente"])


@router.post("/", response_model=schemas.ProgettoMansioneEnte)
def create_progetto_mansione_ente(
    associazione: schemas.ProgettoMansioneEnteCreate,
    db: Session = Depends(get_db)
):
    """
    CREA UNA NUOVA ASSOCIAZIONE PROGETTO-MANSIONE-ENTE

    Collega un progetto a un ente attuatore specificando:
    - La mansione/ruolo da svolgere
    - Il periodo di attività (data_inizio, data_fine)
    - Le ore previste ed effettive
    - La tariffa oraria e il budget
    - Il tipo di contratto

    Validazioni:
    - Progetto ed ente devono esistere
    - Data fine > data inizio
    - Univocità: progetto + ente + mansione + data_inizio
    """
    try:
        db_associazione = crud.create_progetto_mansione_ente(db, associazione)
        logger.info(
            f"Created association: Project {associazione.progetto_id}, "
            f"Entity {associazione.ente_attuatore_id}, Role {associazione.mansione}"
        )
        return db_associazione

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating progetto-mansione-ente: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Errore nella creazione dell'associazione"
        )


@router.get("/", response_model=List[schemas.ProgettoMansioneEnteWithDetails])
def get_progetto_mansione_ente_list(
    skip: int = 0,
    limit: int = 100,
    progetto_id: Optional[int] = None,
    ente_attuatore_id: Optional[int] = None,
    mansione: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """
    RECUPERA LISTA ASSOCIAZIONI PROGETTO-MANSIONE-ENTE

    Parametri query:
    - skip: Salta N record (paginazione)
    - limit: Massimo record da restituire
    - progetto_id: Filtra per progetto specifico
    - ente_attuatore_id: Filtra per ente attuatore specifico
    - mansione: Cerca nella descrizione della mansione
    - is_active: Filtra per stato attivo (true/false)

    Restituisce le associazioni con i dettagli completi di progetto ed ente.
    """
    associazioni = crud.get_progetto_mansione_ente_list(
        db,
        skip=skip,
        limit=limit,
        progetto_id=progetto_id,
        ente_attuatore_id=ente_attuatore_id,
        mansione=mansione,
        is_active=is_active
    )
    return associazioni


@router.get("/count")
def get_progetto_mansione_ente_count(
    progetto_id: Optional[int] = None,
    ente_attuatore_id: Optional[int] = None,
    mansione: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """CONTA IL NUMERO TOTALE DI ASSOCIAZIONI (per paginazione frontend)"""
    count = crud.get_progetto_mansione_ente_count(
        db,
        progetto_id=progetto_id,
        ente_attuatore_id=ente_attuatore_id,
        mansione=mansione,
        is_active=is_active
    )
    return {"count": count}


@router.get("/{associazione_id}", response_model=schemas.ProgettoMansioneEnteWithDetails)
def get_progetto_mansione_ente(
    associazione_id: int,
    db: Session = Depends(get_db)
):
    """RECUPERA UNA SINGOLA ASSOCIAZIONE CON DETTAGLI COMPLETI"""
    associazione = crud.get_progetto_mansione_ente(db, associazione_id)
    if not associazione:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associazione non trovata"
        )
    return associazione


@router.put("/{associazione_id}", response_model=schemas.ProgettoMansioneEnte)
def update_progetto_mansione_ente(
    associazione_id: int,
    associazione: schemas.ProgettoMansioneEnteUpdate,
    db: Session = Depends(get_db)
):
    """
    AGGIORNA UN'ASSOCIAZIONE ESISTENTE

    Tutti i campi sono opzionali. Vengono aggiornati solo i campi forniti.

    Validazioni:
    - Se si modificano progetto/ente, devono esistere
    - Le date devono rimanere coerenti (fine > inizio)
    """
    try:
        updated_associazione = crud.update_progetto_mansione_ente(db, associazione_id, associazione)
        logger.info(f"Updated association ID {associazione_id}")
        return updated_associazione

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error updating progetto-mansione-ente {associazione_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Errore nell'aggiornamento dell'associazione"
        )


@router.delete("/{associazione_id}")
def delete_progetto_mansione_ente(
    associazione_id: int,
    soft_delete: bool = True,
    db: Session = Depends(get_db)
):
    """
    ELIMINA O DISATTIVA UN'ASSOCIAZIONE

    Parametri:
    - soft_delete=true (default): Disattiva l'associazione (is_active=False) mantenendo lo storico
    - soft_delete=false: Eliminazione fisica definitiva
    """
    try:
        if soft_delete:
            deleted_associazione = crud.soft_delete_progetto_mansione_ente(db, associazione_id)
            logger.info(f"Soft-deleted association ID {associazione_id}")
            return {
                "message": "Associazione disattivata con successo",
                "associazione_id": associazione_id,
                "soft_delete": True
            }
        else:
            result = crud.delete_progetto_mansione_ente(db, associazione_id)
            logger.info(f"Deleted association ID {associazione_id}")
            return {
                "message": "Associazione eliminata con successo",
                "associazione_id": associazione_id,
                "soft_delete": False
            }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error deleting progetto-mansione-ente {associazione_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Errore nell'eliminazione dell'associazione"
        )
