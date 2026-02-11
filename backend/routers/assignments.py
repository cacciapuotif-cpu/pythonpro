"""
Router per gestione assegnazioni dettagliate
Gestisce mansioni, contratti e generazione PDF
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List
import logging
import tempfile

import crud
import schemas
from database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/assignments", tags=["Assignments"])

# Verifica disponibilità generatore contratti
try:
    from contract_generator import ContractGenerator
    CONTRACT_GENERATOR_AVAILABLE = True
except ImportError:
    logger.warning("contract_generator non disponibile")
    CONTRACT_GENERATOR_AVAILABLE = False
    ContractGenerator = None


@router.post("/", response_model=schemas.Assignment)
def create_assignment(
    assignment: schemas.AssignmentCreate,
    db: Session = Depends(get_db)
):
    """CREA UNA NUOVA ASSEGNAZIONE"""
    try:
        logger.info(f"Ricevuta richiesta creazione assegnazione: {assignment.dict()}")

        collaborator = crud.get_collaborator(db, assignment.collaborator_id)
        if not collaborator:
            raise HTTPException(status_code=404, detail="Collaboratore non trovato")

        project = crud.get_project(db, assignment.project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Progetto non trovato")

        result = crud.create_assignment(db=db, assignment=assignment)
        db.commit()
        db.refresh(result)

        logger.info(f"Assegnazione creata con successo: ID {result.id}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Errore creazione assegnazione: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[schemas.Assignment])
def read_assignments(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """OTTIENI LISTA DELLE ASSEGNAZIONI"""
    assignments = crud.get_assignments(db, skip=skip, limit=limit)
    return assignments


@router.get("/{assignment_id}", response_model=schemas.Assignment)
def read_assignment(
    assignment_id: int,
    db: Session = Depends(get_db)
):
    """OTTIENI UNA ASSEGNAZIONE SPECIFICA"""
    db_assignment = crud.get_assignment(db, assignment_id=assignment_id)
    if db_assignment is None:
        raise HTTPException(status_code=404, detail="Assegnazione non trovata")
    return db_assignment


@router.put("/{assignment_id}", response_model=schemas.Assignment)
def update_assignment(
    assignment_id: int,
    assignment: schemas.AssignmentUpdate,
    db: Session = Depends(get_db)
):
    """AGGIORNA UNA ASSEGNAZIONE"""
    db_assignment = crud.update_assignment(db, assignment_id, assignment)
    if db_assignment is None:
        raise HTTPException(status_code=404, detail="Assegnazione non trovata")
    return db_assignment


@router.delete("/{assignment_id}")
def delete_assignment(
    assignment_id: int,
    db: Session = Depends(get_db)
):
    """ELIMINA UNA ASSEGNAZIONE"""
    db_assignment = crud.delete_assignment(db, assignment_id)
    if db_assignment is None:
        raise HTTPException(status_code=404, detail="Assegnazione non trovata")
    return {"message": "Assegnazione eliminata con successo"}


@router.get("/{assignment_id}/generate-contract")
def generate_contract_pdf(
    assignment_id: int,
    db: Session = Depends(get_db)
):
    """
    GENERA UN CONTRATTO PDF PER UNA ASSEGNAZIONE

    Compila automaticamente un contratto con i dati del collaboratore,
    progetto, mansione, ore e importo.
    """
    if not CONTRACT_GENERATOR_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sistema di generazione contratti non disponibile"
        )

    try:
        assignment = crud.get_assignment(db, assignment_id=assignment_id)
        if not assignment:
            raise HTTPException(status_code=404, detail="Assegnazione non trovata")

        collaborator = crud.get_collaborator(db, assignment.collaborator_id)
        project = crud.get_project(db, assignment.project_id)

        if not collaborator or not project:
            raise HTTPException(status_code=404, detail="Dati incompleti per generare il contratto")

        assignment_data = {
            'id': assignment.id,
            'role': assignment.role,
            'assigned_hours': assignment.assigned_hours,
            'hourly_rate': assignment.hourly_rate,
            'start_date': assignment.start_date.isoformat() if assignment.start_date else None,
            'end_date': assignment.end_date.isoformat() if assignment.end_date else None,
            'contract_type': assignment.contract_type,
            'collaborator': {
                'first_name': collaborator.first_name,
                'last_name': collaborator.last_name,
                'email': collaborator.email,
                'fiscal_code': collaborator.fiscal_code,
                'birthplace': collaborator.birthplace,
                'birth_date': collaborator.birth_date.isoformat() if collaborator.birth_date else None,
                'address': collaborator.address,
                'city': collaborator.city
            },
            'project': {
                'name': project.name,
                'description': project.description
            }
        }

        generator = ContractGenerator()
        pdf_buffer = generator.generate_contract(assignment_data)

        filename = f"contratto_{collaborator.last_name}_{project.name.replace(' ', '_')}.pdf"

        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            tmp.write(pdf_buffer.read())
            tmp_path = tmp.name

        logger.info(f"Contratto generato per assignment {assignment_id}")

        return FileResponse(
            tmp_path,
            media_type='application/pdf',
            filename=filename,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Errore generazione contratto: {e}")
        raise HTTPException(status_code=500, detail=f"Errore nella generazione del contratto: {str(e)}")
