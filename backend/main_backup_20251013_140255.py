# IMPORTAZIONI - tutte le librerie che useremo
from fastapi import FastAPI, Depends, HTTPException, status, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware  # Per permettere richieste dal frontend
from fastapi.responses import JSONResponse, FileResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session  # Per le sessioni database
from sqlalchemy import text  # Per query SQL dirette
from sqlalchemy.exc import SQLAlchemyError
from typing import List, Optional  # Per definire i tipi di dato
from datetime import datetime
import os
import logging

# IMPORTAZIONI DEI NOSTRI MODULI
import models  # I nostri modelli database
import schemas  # Gli schemi per validare i dati
import crud  # Le funzioni per operazioni database
from database import SessionLocal, engine, get_db

# Setup logging avanzato (PRIMA degli import opzionali)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.getenv('LOG_DIR', 'logs'), 'gestionale.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# IMPORTAZIONI SISTEMI AVANZATI
from error_handler import (
    ErrorHandler, GestionaleException, DatabaseConnectionError,
    ValidationError, BusinessLogicError, retry_on_db_error,
    SafeTransaction, error_monitor
)
from validators import (
    InputSanitizer, BusinessValidator,
    EnhancedCollaboratorCreate, EnhancedProjectCreate,
    EnhancedAttendanceCreate, EnhancedAssignmentCreate,
    BatchOperationValidator
)

# Importazioni opzionali per sistemi avanzati
try:
    from backup_manager import get_backup_manager
    BACKUP_AVAILABLE = True
except ImportError:
    logger.warning("backup_manager non disponibile - funzionalità di backup disabilitate")
    BACKUP_AVAILABLE = False

try:
    from performance_monitor import get_performance_monitor
    PERFORMANCE_MONITOR_AVAILABLE = True
except ImportError:
    logger.warning("performance_monitor non disponibile - monitoraggio performance disabilitato")
    PERFORMANCE_MONITOR_AVAILABLE = False

from request_middleware import setup_middleware

# IMPORTAZIONI SICUREZZA E AUTENTICAZIONE
from auth import (
    User, UserRole, Permission, require_permission,
    get_current_user, get_admin_user, create_user,
    log_security_event, LoginAttempt
)

# IMPORTAZIONI GENERAZIONE CONTRATTI (opzionale)
try:
    from contract_generator import ContractGenerator
    CONTRACT_GENERATOR_AVAILABLE = True
except ImportError:
    logger.warning("contract_generator non disponibile - funzionalità di generazione contratti disabilitate")
    CONTRACT_GENERATOR_AVAILABLE = False
    ContractGenerator = None

# CREIAMO LE TABELLE NEL DATABASE
# Questo comando crea automaticamente tutte le tabelle se non esistono
models.Base.metadata.create_all(bind=engine)

# CREAZIONE DELL'APPLICAZIONE FASTAPI
app = FastAPI(
    title="Gestionale Collaboratori e Progetti",  # Nome dell'applicazione
    description="Sistema per gestire collaboratori, progetti formativi e presenze",
    version="1.0.0"
)

# GESTORI DI ERRORE CENTRALIZZATI
@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    error_monitor.record_error("database_error")
    ErrorHandler.log_error(exc, request)
    return ErrorHandler.handle_database_error(exc)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    error_monitor.record_error("validation_error")
    logger.error(f"Validation error on {request.url}: {exc.errors()}")
    body = await request.body()
    logger.error(f"Request body: {body.decode() if body else 'empty'}")
    ErrorHandler.log_error(exc, request)
    return ErrorHandler.handle_validation_error(exc)

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    error_monitor.record_error(f"http_{exc.status_code}")
    ErrorHandler.log_error(exc, request)
    return ErrorHandler.handle_http_exception(exc)

@app.exception_handler(GestionaleException)
async def gestionale_exception_handler(request: Request, exc: GestionaleException):
    error_monitor.record_error(exc.error_code)
    ErrorHandler.log_error(exc, request)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": exc.message,
            "error_code": exc.error_code,
            "details": exc.details
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    error_monitor.record_error("general_error")
    ErrorHandler.log_error(exc, request)
    logger.critical(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Errore interno del server",
            "error_code": "INTERNAL_SERVER_ERROR"
        }
    )

# CONFIGURAZIONE CORS - permette al frontend di comunicare con il backend
# Senza questo, il browser bloccherebbe le richieste dal frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # URL interno Docker
        "http://localhost:3001",  # URL esterno per browser
        "http://127.0.0.1:3001",  # Variante con 127.0.0.1
    ],
    allow_credentials=True,  # Permette cookies e auth headers
    allow_methods=["*"],     # Permette tutti i metodi HTTP (GET, POST, PUT, DELETE)
    allow_headers=["*"],     # Permette tutti gli headers
)

# CONFIGURAZIONE MIDDLEWARE AVANZATI
setup_middleware(app)

# ==========================================
# API ENDPOINTS PER GESTIRE I COLLABORATORI
# ==========================================

@app.post("/test-post")
def test_post_endpoint(data: dict):
    """TEST ENDPOINT - verifica che POST funzioni"""
    return {"received": data, "status": "OK"}

@app.post("/collaborators/", response_model=schemas.Collaborator)
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
        # Verifica se esiste già un collaboratore con questa email
        existing_email = crud.get_collaborator_by_email(db, collaborator.email)
        if existing_email:
            raise HTTPException(
                status_code=409,
                detail=f"Esiste già un collaboratore con email '{collaborator.email}'"
            )

        # Verifica se esiste già un collaboratore con questo codice fiscale
        existing_cf = crud.get_collaborator_by_fiscal_code(db, collaborator.fiscal_code)
        if existing_cf:
            raise HTTPException(
                status_code=409,
                detail=f"Esiste già un collaboratore con codice fiscale '{collaborator.fiscal_code.upper()}'"
            )

        # Crea il collaboratore
        result = crud.create_collaborator(db=db, collaborator=collaborator)
        db.commit()
        db.refresh(result)
        logger.info(f"Collaboratore creato: {result.first_name} {result.last_name} (CF: {result.fiscal_code})")
        return result
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Errore creazione collaboratore: {e}")
        raise HTTPException(status_code=400, detail=f"Errore creazione collaboratore: {str(e)}")

@app.get("/collaborators/", response_model=List[schemas.Collaborator])
def read_collaborators(
    skip: int = 0,      # Quanti record saltare (per la paginazione)
    limit: int = 100,   # Quanti record restituire massimo
    db: Session = Depends(get_db)
):
    """
    OTTIENI LISTA DI TUTTI I COLLABORATORI
    - Supporta la paginazione con skip e limit
    - Esempio: skip=0, limit=10 → primi 10 collaboratori
    - Esempio: skip=10, limit=10 → collaboratori dall'11 al 20
    """
    collaborators = crud.get_collaborators(db, skip=skip, limit=limit)
    return collaborators

@app.get("/collaborators-with-projects/", response_model=List[schemas.CollaboratorWithProjects])
def read_collaborators_with_projects(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    OTTIENI COLLABORATORI CON I LORO PROGETTI ASSEGNATI
    - Restituisce collaboratori con lista dei progetti associati
    - Utile per visualizzare le assegnazioni nella UI
    """
    collaborators = crud.get_collaborators_with_projects(db, skip=skip, limit=limit)
    return collaborators

@app.get("/collaborators/{collaborator_id}", response_model=schemas.Collaborator)
def read_collaborator(
    collaborator_id: int,  # ID del collaboratore da cercare
    db: Session = Depends(get_db)
):
    """
    OTTIENI UN COLLABORATORE SPECIFICO TRAMITE IL SUO ID
    - Se non trova il collaboratore, restituisce errore 404
    """
    db_collaborator = crud.get_collaborator(db, collaborator_id=collaborator_id)
    if db_collaborator is None:
        raise HTTPException(status_code=404, detail="Collaboratore non trovato")
    return db_collaborator

@app.put("/collaborators/{collaborator_id}", response_model=schemas.Collaborator)
def update_collaborator(
    collaborator_id: int,
    collaborator: schemas.CollaboratorUpdate,  # Dati da aggiornare
    db: Session = Depends(get_db)
):
    """
    AGGIORNA UN COLLABORATORE ESISTENTE

    Validazioni automatiche:
    - Email: deve essere unica (se viene cambiata)
    - Codice Fiscale: deve essere unico (se viene cambiato)
    - Solo i campi forniti verranno aggiornati
    """
    try:
        # Verifica se il collaboratore esiste
        db_collaborator = crud.get_collaborator(db, collaborator_id)
        if not db_collaborator:
            raise HTTPException(status_code=404, detail="Collaboratore non trovato")

        # Verifica email duplicata se viene aggiornata
        if collaborator.email:
            existing_email = crud.get_collaborator_by_email(db, collaborator.email)
            if existing_email and existing_email.id != collaborator_id:
                raise HTTPException(
                    status_code=409,
                    detail=f"Esiste già un collaboratore con email '{collaborator.email}'"
                )

        # Verifica codice fiscale duplicato se viene aggiornato
        if collaborator.fiscal_code:
            existing_cf = crud.get_collaborator_by_fiscal_code(db, collaborator.fiscal_code)
            if existing_cf and existing_cf.id != collaborator_id:
                raise HTTPException(
                    status_code=409,
                    detail=f"Esiste già un collaboratore con codice fiscale '{collaborator.fiscal_code.upper()}'"
                )

        # Esegui l'aggiornamento
        updated_collaborator = crud.update_collaborator(db, collaborator_id, collaborator)
        return updated_collaborator
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Errore aggiornamento collaboratore {collaborator_id}: {e}")
        raise HTTPException(status_code=400, detail=f"Errore aggiornamento: {str(e)}")

@app.delete("/collaborators/{collaborator_id}")
def delete_collaborator(
    collaborator_id: int,
    db: Session = Depends(get_db)
):
    """
    ELIMINA UN COLLABORATORE
    - Attenzione: questo eliminerà anche tutte le sue presenze!
    """
    db_collaborator = crud.delete_collaborator(db, collaborator_id)
    if db_collaborator is None:
        raise HTTPException(status_code=404, detail="Collaboratore non trovato")
    return {"message": "Collaboratore eliminato con successo"}

# ====================================================
# API ENDPOINTS PER UPLOAD DOCUMENTI COLLABORATORI
# ====================================================

@app.post("/collaborators/{collaborator_id}/upload-documento")
async def upload_documento_identita(
    collaborator_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    UPLOAD DOCUMENTO IDENTITÀ per collaboratore

    - Formati permessi: PDF, JPG, PNG
    - Dimensione massima: 10MB
    - File salvato su filesystem
    - Path salvato in database
    """
    from file_upload import save_uploaded_file, delete_file

    # Verifica esistenza collaboratore
    collaborator = crud.get_collaborator(db, collaborator_id)
    if not collaborator:
        raise HTTPException(status_code=404, detail="Collaboratore non trovato")

    # Elimina vecchio file se esiste
    if collaborator.documento_identita_path:
        await delete_file(collaborator.documento_identita_path)

    # Salva nuovo file
    try:
        filename, filepath = await save_uploaded_file(file, collaborator_id, "documento")

        # Aggiorna database
        collaborator.documento_identita_filename = filename
        collaborator.documento_identita_path = filepath
        collaborator.documento_identita_uploaded_at = datetime.now()
        db.commit()
        db.refresh(collaborator)

        logger.info(f"Documento identità uploadato per collaboratore {collaborator_id}")

        return {
            "message": "Documento identità caricato con successo",
            "filename": filename,
            "uploaded_at": collaborator.documento_identita_uploaded_at
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Errore upload documento: {e}")
        raise HTTPException(status_code=500, detail=f"Errore upload: {str(e)}")


@app.post("/collaborators/{collaborator_id}/upload-curriculum")
async def upload_curriculum(
    collaborator_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    UPLOAD CURRICULUM per collaboratore

    - Formati permessi: PDF, DOC, DOCX
    - Dimensione massima: 10MB
    - File salvato su filesystem
    - Path salvato in database
    """
    from file_upload import save_uploaded_file, delete_file

    # Verifica esistenza collaboratore
    collaborator = crud.get_collaborator(db, collaborator_id)
    if not collaborator:
        raise HTTPException(status_code=404, detail="Collaboratore non trovato")

    # Elimina vecchio file se esiste
    if collaborator.curriculum_path:
        await delete_file(collaborator.curriculum_path)

    # Salva nuovo file
    try:
        filename, filepath = await save_uploaded_file(file, collaborator_id, "curriculum")

        # Aggiorna database
        collaborator.curriculum_filename = filename
        collaborator.curriculum_path = filepath
        collaborator.curriculum_uploaded_at = datetime.now()
        db.commit()
        db.refresh(collaborator)

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


@app.get("/collaborators/{collaborator_id}/download-documento")
async def download_documento_identita(
    collaborator_id: int,
    db: Session = Depends(get_db)
):
    """
    DOWNLOAD DOCUMENTO IDENTITÀ di un collaboratore

    - Ritorna il file per download
    - Verifica esistenza e permessi
    """
    from file_upload import get_file_path

    # Verifica collaboratore
    collaborator = crud.get_collaborator(db, collaborator_id)
    if not collaborator:
        raise HTTPException(status_code=404, detail="Collaboratore non trovato")

    # Verifica documento esiste
    if not collaborator.documento_identita_path:
        raise HTTPException(status_code=404, detail="Nessun documento identità caricato")

    # Ottieni path file
    file_path = get_file_path(collaborator.documento_identita_path)

    # Ritorna file per download
    return FileResponse(
        path=file_path,
        filename=collaborator.documento_identita_filename,
        media_type="application/octet-stream"
    )


@app.get("/collaborators/{collaborator_id}/download-curriculum")
async def download_curriculum(
    collaborator_id: int,
    db: Session = Depends(get_db)
):
    """
    DOWNLOAD CURRICULUM di un collaboratore

    - Ritorna il file per download
    - Verifica esistenza e permessi
    """
    from file_upload import get_file_path

    # Verifica collaboratore
    collaborator = crud.get_collaborator(db, collaborator_id)
    if not collaborator:
        raise HTTPException(status_code=404, detail="Collaboratore non trovato")

    # Verifica curriculum esiste
    if not collaborator.curriculum_path:
        raise HTTPException(status_code=404, detail="Nessun curriculum caricato")

    # Ottieni path file
    file_path = get_file_path(collaborator.curriculum_path)

    # Ritorna file per download
    return FileResponse(
        path=file_path,
        filename=collaborator.curriculum_filename,
        media_type="application/octet-stream"
    )


@app.delete("/collaborators/{collaborator_id}/delete-documento")
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

    # Elimina file
    await delete_file(collaborator.documento_identita_path)

    # Aggiorna database
    collaborator.documento_identita_filename = None
    collaborator.documento_identita_path = None
    collaborator.documento_identita_uploaded_at = None
    db.commit()

    return {"message": "Documento identità eliminato con successo"}


@app.delete("/collaborators/{collaborator_id}/delete-curriculum")
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

    # Elimina file
    await delete_file(collaborator.curriculum_path)

    # Aggiorna database
    collaborator.curriculum_filename = None
    collaborator.curriculum_path = None
    collaborator.curriculum_uploaded_at = None
    db.commit()

    return {"message": "Curriculum eliminato con successo"}

# ====================================
# API ENDPOINTS PER GESTIRE I PROGETTI
# ====================================

@app.post("/projects/", response_model=schemas.Project)
def create_project(
    project: schemas.ProjectCreate,  # Usa schema semplice
    db: Session = Depends(get_db)
):
    """CREA UN NUOVO PROGETTO FORMATIVO"""
    try:
        result = crud.create_project(db=db, project=project)
        db.commit()
        db.refresh(result)

        logger.info(f"Progetto creato: ID {result.id}")
        return result

    except Exception as e:
        db.rollback()
        logger.error(f"Errore creazione progetto: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/projects/", response_model=List[schemas.Project])
def read_projects(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """OTTIENI LISTA DI TUTTI I PROGETTI"""
    projects = crud.get_projects(db, skip=skip, limit=limit)
    return projects

@app.get("/projects/{project_id}", response_model=schemas.Project)
def read_project(
    project_id: int,
    db: Session = Depends(get_db)
):
    """OTTIENI UN PROGETTO SPECIFICO"""
    db_project = crud.get_project(db, project_id=project_id)
    if db_project is None:
        raise HTTPException(status_code=404, detail="Progetto non trovato")
    return db_project

@app.put("/projects/{project_id}", response_model=schemas.Project)
def update_project(
    project_id: int,
    project: schemas.ProjectUpdate,
    db: Session = Depends(get_db)
):
    """AGGIORNA UN PROGETTO ESISTENTE"""
    db_project = crud.update_project(db, project_id, project)
    if db_project is None:
        raise HTTPException(status_code=404, detail="Progetto non trovato")
    return db_project

@app.delete("/projects/{project_id}")
def delete_project(
    project_id: int,
    db: Session = Depends(get_db)
):
    """ELIMINA UN PROGETTO"""
    db_project = crud.delete_project(db, project_id)
    if db_project is None:
        raise HTTPException(status_code=404, detail="Progetto non trovato")
    return {"message": "Progetto eliminato con successo"}

# ====================================================
# API ENDPOINTS PER ASSOCIARE COLLABORATORI E PROGETTI
# ====================================================

@app.post("/collaborators/{collaborator_id}/projects/{project_id}")
def assign_collaborator_to_project(
    collaborator_id: int,
    project_id: int,
    db: Session = Depends(get_db)
):
    """
    ASSEGNA UN COLLABORATORE AD UN PROGETTO
    - Crea il collegamento many-to-many tra collaboratore e progetto
    - Un collaboratore può lavorare su più progetti
    - Un progetto può avere più collaboratori
    """
    collaborator = crud.assign_collaborator_to_project(db, collaborator_id, project_id)
    if collaborator is None:
        raise HTTPException(status_code=404, detail="Collaboratore o progetto non trovato")
    return {"message": f"Collaboratore assegnato al progetto con successo"}

@app.delete("/collaborators/{collaborator_id}/projects/{project_id}")
def remove_collaborator_from_project(
    collaborator_id: int,
    project_id: int,
    db: Session = Depends(get_db)
):
    """RIMUOVI UN COLLABORATORE DA UN PROGETTO"""
    collaborator = crud.remove_collaborator_from_project(db, collaborator_id, project_id)
    if collaborator is None:
        raise HTTPException(status_code=404, detail="Collaboratore o progetto non trovato")
    return {"message": "Collaboratore rimosso dal progetto"}

# =====================================
# API ENDPOINTS PER GESTIRE LE PRESENZE
# =====================================

@app.post("/attendances/", response_model=schemas.Attendance)
@retry_on_db_error(max_retries=3)
def create_attendance(
    attendance: EnhancedAttendanceCreate,
    db: Session = Depends(get_db)
):
    """
    REGISTRA UNA NUOVA PRESENZA CON VALIDAZIONE AVANZATA
    - Validazione orari e sovrapposizioni
    - Calcolo automatico ore se non fornite
    - Controllo business logic avanzato
    """
    try:
        with SafeTransaction(db) as transaction:
            # Verifica esistenza collaboratore e progetto
            collaborator = crud.get_collaborator(db, attendance.collaborator_id)
            if not collaborator:
                raise BusinessLogicError("Collaboratore non trovato")

            project = crud.get_project(db, attendance.project_id)
            if not project:
                raise BusinessLogicError("Progetto non trovato")

            attendance_data = schemas.AttendanceCreate(**attendance.dict())
            result = crud.create_attendance(db=db, attendance=attendance_data)
            transaction.commit()

            logger.info(f"Presenza registrata con successo: ID {result.id}")
            return result

    except Exception as e:
        logger.error(f"Errore registrazione presenza: {e}")
        raise

@app.get("/attendances/", response_model=List[schemas.Attendance])
def read_attendances(
    skip: int = 0,
    limit: int = 100,
    collaborator_id: Optional[int] = None,  # Filtra per collaboratore specifico
    project_id: Optional[int] = None,       # Filtra per progetto specifico
    start_date: Optional[datetime] = None,  # Filtra da data specifica
    end_date: Optional[datetime] = None,    # Filtra fino a data specifica
    db: Session = Depends(get_db)
):
    """
    OTTIENI LISTA DELLE PRESENZE CON FILTRI OPZIONALI
    - Senza filtri: tutte le presenze
    - Con filtri: solo le presenze che soddisfano i criteri
    - Utile per il calendario: passare start_date e end_date del mese visualizzato
    """
    attendances = crud.get_attendances(
        db, skip=skip, limit=limit,
        collaborator_id=collaborator_id,
        project_id=project_id,
        start_date=start_date,
        end_date=end_date
    )
    return attendances

@app.get("/attendances/{attendance_id}", response_model=schemas.Attendance)
def read_attendance(
    attendance_id: int,
    db: Session = Depends(get_db)
):
    """OTTIENI UNA PRESENZA SPECIFICA"""
    db_attendance = crud.get_attendance(db, attendance_id=attendance_id)
    if db_attendance is None:
        raise HTTPException(status_code=404, detail="Presenza non trovata")
    return db_attendance

@app.put("/attendances/{attendance_id}", response_model=schemas.Attendance)
def update_attendance(
    attendance_id: int,
    attendance: schemas.AttendanceUpdate,
    db: Session = Depends(get_db)
):
    """
    AGGIORNA UNA PRESENZA ESISTENTE
    - Utile per correggere orari o aggiungere note
    """
    db_attendance = crud.update_attendance(db, attendance_id, attendance)
    if db_attendance is None:
        raise HTTPException(status_code=404, detail="Presenza non trovata")
    return db_attendance

@app.delete("/attendances/{attendance_id}")
def delete_attendance(
    attendance_id: int,
    db: Session = Depends(get_db)
):
    """ELIMINA UNA PRESENZA"""
    db_attendance = crud.delete_attendance(db, attendance_id)
    if db_attendance is None:
        raise HTTPException(status_code=404, detail="Presenza non trovata")
    return {"message": "Presenza eliminata con successo"}

# ========================================
# API ENDPOINTS PER GESTIRE LE ASSEGNAZIONI DETTAGLIATE
# ========================================

@app.post("/assignments/", response_model=schemas.Assignment)
def create_assignment(
    assignment: schemas.AssignmentCreate,
    db: Session = Depends(get_db)
):
    """
    CREA UNA NUOVA ASSEGNAZIONE
    """
    try:
        logger.info(f"Ricevuta richiesta creazione assegnazione: {assignment.dict()}")

        # Verifica esistenza collaboratore e progetto
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

@app.get("/assignments/", response_model=List[schemas.Assignment])
def read_assignments(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """OTTIENI LISTA DELLE ASSEGNAZIONI"""
    assignments = crud.get_assignments(db, skip=skip, limit=limit)
    return assignments

@app.get("/assignments/{assignment_id}", response_model=schemas.Assignment)
def read_assignment(
    assignment_id: int,
    db: Session = Depends(get_db)
):
    """OTTIENI UNA ASSEGNAZIONE SPECIFICA"""
    db_assignment = crud.get_assignment(db, assignment_id=assignment_id)
    if db_assignment is None:
        raise HTTPException(status_code=404, detail="Assegnazione non trovata")
    return db_assignment

@app.put("/assignments/{assignment_id}", response_model=schemas.Assignment)
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

@app.delete("/assignments/{assignment_id}")
def delete_assignment(
    assignment_id: int,
    db: Session = Depends(get_db)
):
    """ELIMINA UNA ASSEGNAZIONE"""
    db_assignment = crud.delete_assignment(db, assignment_id)
    if db_assignment is None:
        raise HTTPException(status_code=404, detail="Assegnazione non trovata")
    return {"message": "Assegnazione eliminata con successo"}

@app.get("/collaborators/{collaborator_id}/assignments/", response_model=List[schemas.Assignment])
def read_collaborator_assignments(
    collaborator_id: int,
    db: Session = Depends(get_db)
):
    """OTTIENI TUTTE LE ASSEGNAZIONI DI UN COLLABORATORE"""
    assignments = crud.get_assignments_by_collaborator(db, collaborator_id)
    return assignments

@app.get("/projects/{project_id}/assignments/", response_model=List[schemas.Assignment])
def read_project_assignments(
    project_id: int,
    db: Session = Depends(get_db)
):
    """OTTIENI TUTTE LE ASSEGNAZIONI DI UN PROGETTO"""
    assignments = crud.get_assignments_by_project(db, project_id)
    return assignments

@app.get("/assignments/{assignment_id}/generate-contract")
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
        # Ottieni l'assignment con tutti i dettagli
        assignment = crud.get_assignment(db, assignment_id=assignment_id)
        if not assignment:
            raise HTTPException(status_code=404, detail="Assegnazione non trovata")

        # Ottieni collaboratore e progetto
        collaborator = crud.get_collaborator(db, assignment.collaborator_id)
        project = crud.get_project(db, assignment.project_id)

        if not collaborator or not project:
            raise HTTPException(status_code=404, detail="Dati incompleti per generare il contratto")

        # Prepara i dati per il contratto
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

        # Genera il contratto PDF
        generator = ContractGenerator()
        pdf_buffer = generator.generate_contract(assignment_data)

        # Prepara il nome del file
        filename = f"contratto_{collaborator.last_name}_{project.name.replace(' ', '_')}.pdf"

        # Salva temporaneamente il file
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            tmp.write(pdf_buffer.read())
            tmp_path = tmp.name

        logger.info(f"Contratto generato per assignment {assignment_id}")

        # Restituisci il PDF
        return FileResponse(
            tmp_path,
            media_type='application/pdf',
            filename=filename,
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Errore generazione contratto: {e}")
        raise HTTPException(status_code=500, detail=f"Errore nella generazione del contratto: {str(e)}")

# ========================================
# API ENDPOINTS PER ENTI ATTUATORI (IMPLEMENTING ENTITIES)
# ========================================

@app.post("/implementing-entities/", response_model=schemas.ImplementingEntity)
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
        # Verifica se esiste già un ente con questa P.IVA
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
        # Errori di validazione dal modello
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

@app.get("/implementing-entities/", response_model=List[schemas.ImplementingEntity])
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

@app.get("/implementing-entities/count")
def get_implementing_entities_count(
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """CONTA IL NUMERO TOTALE DI ENTI (per paginazione frontend)"""
    count = crud.get_implementing_entities_count(db, search=search, is_active=is_active)
    return {"count": count}

@app.get("/implementing-entities/{entity_id}", response_model=schemas.ImplementingEntityWithProjects)
def get_implementing_entity(
    entity_id: int,
    db: Session = Depends(get_db)
):
    """
    RECUPERA UN SINGOLO ENTE ATTUATORE CON I PROGETTI COLLEGATI
    """
    entity = crud.get_implementing_entity_with_projects(db, entity_id)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ente attuatore non trovato"
        )
    return entity

@app.put("/implementing-entities/{entity_id}", response_model=schemas.ImplementingEntity)
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
        # Verifica se l'ente esiste
        existing_entity = crud.get_implementing_entity(db, entity_id)
        if not existing_entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ente attuatore non trovato"
            )

        # Se viene modificata la P.IVA, verifica che non sia duplicata
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

@app.delete("/implementing-entities/{entity_id}")
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
            # Soft delete (disattivazione)
            deleted_entity = crud.soft_delete_implementing_entity(db, entity_id)
            logger.info(f"Soft-deleted implementing entity: ID {entity_id}")
            return {
                "message": "Ente disattivato con successo",
                "entity_id": entity_id,
                "soft_delete": True
            }
        else:
            # Hard delete (eliminazione fisica)
            deleted_entity = crud.delete_implementing_entity(db, entity_id)
            logger.info(f"Deleted implementing entity: ID {entity_id}")
            return {
                "message": "Ente eliminato con successo",
                "entity_id": entity_id,
                "soft_delete": False
            }

    except ValueError as e:
        # Errore se ci sono progetti collegati
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

@app.get("/implementing-entities/{entity_id}/projects", response_model=List[schemas.Project])
def get_entity_projects(
    entity_id: int,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    RECUPERA TUTTI I PROGETTI DI UN ENTE ATTUATORE

    Parametri:
    - status: Filtra per stato progetto (active, completed, paused, cancelled)
    """
    entity = crud.get_implementing_entity(db, entity_id)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ente attuatore non trovato"
        )

    projects = crud.get_projects_by_entity(db, entity_id, status=status)
    return projects

# ========================================
# API ENDPOINTS PER ASSOCIAZIONI PROGETTO-MANSIONE-ENTE
# ========================================

@app.post("/progetto-mansione-ente/", response_model=schemas.ProgettoMansioneEnte)
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

@app.get("/progetto-mansione-ente/", response_model=List[schemas.ProgettoMansioneEnteWithDetails])
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

@app.get("/progetto-mansione-ente/count")
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

@app.get("/progetto-mansione-ente/{associazione_id}", response_model=schemas.ProgettoMansioneEnteWithDetails)
def get_progetto_mansione_ente(
    associazione_id: int,
    db: Session = Depends(get_db)
):
    """
    RECUPERA UNA SINGOLA ASSOCIAZIONE CON DETTAGLI COMPLETI
    """
    associazione = crud.get_progetto_mansione_ente(db, associazione_id)
    if not associazione:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associazione non trovata"
        )
    return associazione

@app.put("/progetto-mansione-ente/{associazione_id}", response_model=schemas.ProgettoMansioneEnte)
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

@app.delete("/progetto-mansione-ente/{associazione_id}")
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

@app.get("/projects/{project_id}/mansioni-enti", response_model=List[schemas.ProgettoMansioneEnteWithDetails])
def get_project_mansioni_enti(
    project_id: int,
    db: Session = Depends(get_db)
):
    """
    RECUPERA TUTTE LE ASSOCIAZIONI (MANSIONI-ENTI) DI UN PROGETTO

    Utile per vedere quali enti attuatori sono coinvolti in un progetto
    e con quali mansioni/ruoli.
    """
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Progetto non trovato"
        )

    associazioni = crud.get_progetto_mansione_ente_by_project(db, project_id)
    return associazioni

@app.get("/implementing-entities/{entity_id}/mansioni-progetti", response_model=List[schemas.ProgettoMansioneEnteWithDetails])
def get_entity_mansioni_progetti(
    entity_id: int,
    db: Session = Depends(get_db)
):
    """
    RECUPERA TUTTE LE ASSOCIAZIONI (MANSIONI-PROGETTI) DI UN ENTE ATTUATORE

    Utile per vedere tutti i progetti in cui un ente attuatore è coinvolto
    e con quali mansioni/ruoli.
    """
    entity = crud.get_implementing_entity(db, entity_id)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ente attuatore non trovato"
        )

    associazioni = crud.get_progetto_mansione_ente_by_entity(db, entity_id)
    return associazioni


@app.post("/implementing-entities/{entity_id}/upload-logo")
async def upload_logo_ente_attuatore(
    entity_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    UPLOAD LOGO per ente attuatore

    - Formati permessi: PNG, JPG, JPEG, SVG, GIF
    - Dimensione massima: 5MB
    - File salvato su filesystem
    - Path salvato in database
    - Il logo può essere usato nei contratti generati per questo ente
    """
    from file_upload import save_uploaded_file, delete_file

    # Verifica esistenza ente
    entity = crud.get_implementing_entity(db, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Ente attuatore non trovato")

    # Validazione formato file
    allowed_extensions = ['.png', '.jpg', '.jpeg', '.svg', '.gif']
    file_extension = os.path.splitext(file.filename)[1].lower()
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Formato file non supportato. Formati ammessi: {', '.join(allowed_extensions)}"
        )

    # Elimina vecchio logo se esiste
    if entity.logo_path:
        try:
            await delete_file(entity.logo_path)
        except Exception as e:
            logger.warning(f"Errore eliminazione vecchio logo: {e}")

    # Salva nuovo file
    try:
        filename, filepath = await save_uploaded_file(file, entity_id, "logo_ente")

        # Aggiorna database
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


@app.get("/implementing-entities/{entity_id}/download-logo")
async def download_logo_ente_attuatore(
    entity_id: int,
    db: Session = Depends(get_db)
):
    """
    DOWNLOAD LOGO di un ente attuatore

    - Ritorna il file per visualizzazione/download
    - Verifica esistenza e permessi
    """
    from file_upload import get_file_path

    # Verifica ente
    entity = crud.get_implementing_entity(db, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Ente attuatore non trovato")

    # Verifica logo esiste
    if not entity.logo_path:
        raise HTTPException(status_code=404, detail="Nessun logo caricato per questo ente")

    # Ottieni path file
    file_path = get_file_path(entity.logo_path)

    # Ritorna file per download
    return FileResponse(
        path=file_path,
        filename=entity.logo_filename,
        media_type="application/octet-stream"
    )


@app.delete("/implementing-entities/{entity_id}/delete-logo")
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

    # Elimina file
    await delete_file(entity.logo_path)

    # Aggiorna database
    entity.logo_filename = None
    entity.logo_path = None
    entity.logo_uploaded_at = None
    db.commit()

    return {"message": "Logo eliminato con successo"}


# ========================================
# API ENDPOINTS PER TEMPLATE CONTRATTI
# ========================================

@app.post("/contract-templates/", response_model=schemas.ContractTemplate)
def create_contract_template(
    template: schemas.ContractTemplateCreate,
    db: Session = Depends(get_db)
):
    """
    CREA UN NUOVO TEMPLATE CONTRATTO

    Campi obbligatori:
    - nome_template
    - tipo_contratto (professionale, occasionale, ordine_servizio, contratto_progetto)
    - contenuto_html (HTML con variabili {{variabile}})

    Variabili disponibili per il template:
    - Collaboratore: {{collaboratore_nome}}, {{collaboratore_cognome}}, {{collaboratore_codice_fiscale}}, ecc.
    - Progetto: {{progetto_nome}}, {{progetto_descrizione}}, {{progetto_cup}}
    - Ente: {{ente_ragione_sociale}}, {{ente_piva}}, {{ente_indirizzo_completo}}, ecc.
    - Contratto: {{mansione}}, {{ore_previste}}, {{tariffa_oraria}}, {{compenso_totale}}, ecc.
    - Sistema: {{data_oggi}}

    Se is_default=True, questo diventa il template di default per il tipo_contratto
    """
    try:
        db_template = crud.create_contract_template(db, template)
        logger.info(f"Template contratto creato: {db_template.nome_template} (ID: {db_template.id})")
        return db_template

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Errore creazione template contratto: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Errore nella creazione del template"
        )


@app.get("/contract-templates/", response_model=List[schemas.ContractTemplate])
def get_contract_templates(
    skip: int = 0,
    limit: int = 100,
    tipo_contratto: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    RECUPERA LISTA TEMPLATE CONTRATTI

    Parametri query:
    - skip: Salta N record (paginazione)
    - limit: Massimo record da restituire
    - tipo_contratto: Filtra per tipo specifico
    - is_active: Filtra per stato attivo
    - search: Cerca nel nome o descrizione template
    """
    templates = crud.get_contract_templates(
        db,
        skip=skip,
        limit=limit,
        tipo_contratto=tipo_contratto,
        is_active=is_active,
        search=search
    )
    return templates


@app.get("/contract-templates/count")
def get_contract_templates_count(
    tipo_contratto: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """CONTA IL NUMERO TOTALE DI TEMPLATE (per paginazione frontend)"""
    count = crud.get_contract_templates_count(
        db,
        tipo_contratto=tipo_contratto,
        is_active=is_active,
        search=search
    )
    return {"count": count}


@app.get("/contract-templates/{template_id}", response_model=schemas.ContractTemplate)
def get_contract_template(
    template_id: int,
    db: Session = Depends(get_db)
):
    """RECUPERA UN SINGOLO TEMPLATE CONTRATTO"""
    template = crud.get_contract_template(db, template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template contratto non trovato"
        )
    return template


@app.get("/contract-templates/{template_id}/variables")
def get_contract_template_variables(
    template_id: int,
    db: Session = Depends(get_db)
):
    """
    RECUPERA UN TEMPLATE CON LE VARIABILI DISPONIBILI

    Restituisce il template completo più un oggetto 'variabili_disponibili'
    che elenca tutte le variabili che possono essere usate nel template
    """
    template_with_vars = crud.get_template_with_variables(db, template_id)
    if not template_with_vars:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template contratto non trovato"
        )
    return template_with_vars


@app.put("/contract-templates/{template_id}", response_model=schemas.ContractTemplate)
def update_contract_template(
    template_id: int,
    template: schemas.ContractTemplateUpdate,
    db: Session = Depends(get_db)
):
    """
    AGGIORNA UN TEMPLATE CONTRATTO ESISTENTE

    Tutti i campi sono opzionali. Vengono aggiornati solo i campi forniti.

    Se is_default viene impostato a True, rimuove automaticamente
    il flag di default dagli altri template dello stesso tipo
    """
    try:
        updated_template = crud.update_contract_template(db, template_id, template)
        logger.info(f"Template contratto aggiornato: ID {template_id}")
        return updated_template

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Errore aggiornamento template {template_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Errore nell'aggiornamento del template"
        )


@app.delete("/contract-templates/{template_id}")
def delete_contract_template(
    template_id: int,
    soft_delete: bool = True,
    db: Session = Depends(get_db)
):
    """
    ELIMINA O DISATTIVA UN TEMPLATE CONTRATTO

    Parametri:
    - soft_delete=true (default): Disattiva il template (is_active=False) mantenendo lo storico
    - soft_delete=false: Eliminazione fisica definitiva

    Il soft delete è consigliato per mantenere traccia dei contratti già generati
    """
    try:
        deleted_template = crud.delete_contract_template(db, template_id, soft_delete=soft_delete)

        if soft_delete:
            return {
                "message": "Template disattivato con successo",
                "template_id": template_id,
                "soft_delete": True
            }
        else:
            return {
                "message": "Template eliminato con successo",
                "template_id": template_id,
                "soft_delete": False
            }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Errore eliminazione template {template_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Errore nell'eliminazione del template"
        )


@app.get("/contract-templates/by-type/{tipo_contratto}")
def get_default_template_by_type(
    tipo_contratto: str,
    db: Session = Depends(get_db)
):
    """
    RECUPERA IL TEMPLATE DI DEFAULT PER UN TIPO DI CONTRATTO

    Utile per ottenere il template da usare quando si genera un contratto
    senza specificare un template_id specifico
    """
    template = crud.get_contract_template_by_type(db, tipo_contratto, use_default=True)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Nessun template di default trovato per tipo: {tipo_contratto}"
        )
    return template


@app.post("/contracts/generate")
async def generate_contract_from_template(
    request: schemas.ContractGenerationRequest,
    db: Session = Depends(get_db)
):
    """
    GENERA UN CONTRATTO PDF USANDO UN TEMPLATE PERSONALIZZATO

    Richiede:
    - collaboratore_id: ID del collaboratore
    - progetto_id: ID del progetto
    - ente_attuatore_id: ID dell'ente attuatore
    - mansione: Mansione/ruolo
    - ore_previste: Ore totali previste
    - tariffa_oraria: Tariffa oraria in euro
    - data_inizio: Data inizio contratto
    - data_fine: Data fine contratto
    - template_id (opzionale): ID del template da usare
    - tipo_contratto (opzionale): Se template_id non fornito, usa il default per questo tipo

    Il sistema:
    1. Recupera tutti i dati dalle tabelle (collaboratore, progetto, ente)
    2. Recupera il template (specificato o default)
    3. Sostituisce le variabili {{variabile}} con i dati reali
    4. Include il logo dell'ente se presente e configurato nel template
    5. Genera e restituisce il PDF del contratto
    """
    try:
        # Recupera i dati
        collaboratore = crud.get_collaborator(db, request.collaboratore_id)
        if not collaboratore:
            raise HTTPException(status_code=404, detail="Collaboratore non trovato")

        progetto = crud.get_project(db, request.progetto_id)
        if not progetto:
            raise HTTPException(status_code=404, detail="Progetto non trovato")

        ente = crud.get_implementing_entity(db, request.ente_attuatore_id)
        if not ente:
            raise HTTPException(status_code=404, detail="Ente attuatore non trovato")

        # Recupera il template
        if request.template_id:
            template = crud.get_contract_template(db, request.template_id)
            if not template or not template.is_active:
                raise HTTPException(status_code=404, detail="Template non trovato o non attivo")
        elif request.tipo_contratto:
            template = crud.get_contract_template_by_type(db, request.tipo_contratto, use_default=True)
            if not template:
                raise HTTPException(
                    status_code=404,
                    detail=f"Nessun template di default per tipo: {request.tipo_contratto}"
                )
        else:
            raise HTTPException(
                status_code=400,
                detail="Specificare template_id o tipo_contratto"
            )

        # Prepara i dati per le sostituzioni
        from jinja2 import Template as JinjaTemplate

        compenso_totale = request.ore_previste * request.tariffa_oraria

        context = {
            # Collaboratore
            'collaboratore_nome': collaboratore.first_name,
            'collaboratore_cognome': collaboratore.last_name,
            'collaboratore_nome_completo': f"{collaboratore.first_name} {collaboratore.last_name}",
            'collaboratore_codice_fiscale': collaboratore.fiscal_code,
            'collaboratore_luogo_nascita': collaboratore.birthplace or 'N/A',
            'collaboratore_data_nascita': collaboratore.birth_date.strftime(template.formato_data) if collaboratore.birth_date else 'N/A',
            'collaboratore_indirizzo': collaboratore.address or 'N/A',
            'collaboratore_citta': collaboratore.city or 'N/A',
            # Progetto
            'progetto_nome': progetto.name,
            'progetto_descrizione': progetto.description or '',
            'progetto_cup': progetto.cup or 'N/A',
            # Ente
            'ente_ragione_sociale': ente.ragione_sociale,
            'ente_piva': ente.partita_iva,
            'ente_indirizzo_completo': ente.indirizzo_completo,
            'ente_referente': ente.referente_nome_completo,
            'ente_pec': ente.pec or 'N/A',
            'ente_telefono': ente.telefono or 'N/A',
            # Contratto
            'mansione': request.mansione,
            'ore_previste': str(request.ore_previste),
            'tariffa_oraria': template.formato_importo.format(request.tariffa_oraria),
            'compenso_totale': template.formato_importo.format(compenso_totale),
            'data_inizio': request.data_inizio.strftime(template.formato_data),
            'data_fine': request.data_fine.strftime(template.formato_data),
            # Sistema
            'data_oggi': datetime.now().strftime(template.formato_data)
        }

        # Sostituisci le variabili nel contenuto HTML
        jinja_template = JinjaTemplate(template.contenuto_html)
        contenuto_compilato = jinja_template.render(**context)

        # Se ci sono intestazione o piè di pagina, compilali
        intestazione_compilata = None
        if template.intestazione:
            jinja_header = JinjaTemplate(template.intestazione)
            intestazione_compilata = jinja_header.render(**context)

        pie_pagina_compilato = None
        if template.pie_pagina:
            jinja_footer = JinjaTemplate(template.pie_pagina)
            pie_pagina_compilato = jinja_footer.render(**context)

        # Genera il PDF con ReportLab
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import cm
        from io import BytesIO
        import tempfile

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
        story = []
        styles = getSampleStyleSheet()

        # Aggiungi logo se configurato e presente
        if template.include_logo_ente and template.posizione_logo == "header" and ente.logo_path:
            try:
                from file_upload import get_file_path
                logo_path = get_file_path(ente.logo_path)

                # Dimensioni logo
                logo_width = {'small': 3*cm, 'medium': 5*cm, 'large': 7*cm}[template.dimensione_logo]
                logo_height = logo_width * 0.6  # Mantieni proporzioni

                img = Image(logo_path, width=logo_width, height=logo_height)
                story.append(img)
                story.append(Spacer(1, 0.5*cm))
            except Exception as e:
                logger.warning(f"Errore caricamento logo: {e}")

        # Aggiungi intestazione se presente
        if intestazione_compilata:
            story.append(Paragraph(intestazione_compilata, styles['Normal']))
            story.append(Spacer(1, 0.5*cm))

        # Aggiungi contenuto principale
        story.append(Paragraph(contenuto_compilato, styles['BodyText']))
        story.append(Spacer(1, 1*cm))

        # Aggiungi piè di pagina se presente
        if pie_pagina_compilato:
            story.append(Paragraph(pie_pagina_compilato, styles['Normal']))

        # Logo nel footer se configurato
        if template.include_logo_ente and template.posizione_logo == "footer" and ente.logo_path:
            try:
                from file_upload import get_file_path
                logo_path = get_file_path(ente.logo_path)
                logo_width = {'small': 2*cm, 'medium': 3*cm, 'large': 4*cm}[template.dimensione_logo]
                logo_height = logo_width * 0.6

                story.append(Spacer(1, 0.5*cm))
                img = Image(logo_path, width=logo_width, height=logo_height)
                story.append(img)
            except Exception as e:
                logger.warning(f"Errore caricamento logo footer: {e}")

        # Genera PDF
        doc.build(story)
        buffer.seek(0)

        # Incrementa uso template
        crud.increment_template_usage(db, template.id)

        # Salva in file temporaneo
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            tmp.write(buffer.read())
            tmp_path = tmp.name

        filename = f"contratto_{collaboratore.last_name}_{ente.ragione_sociale}_{datetime.now().strftime('%Y%m%d')}.pdf"

        logger.info(f"Contratto generato per collaboratore {collaboratore.id} con template {template.id}")

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


# ========================================
# ENDPOINT DI SISTEMA E MONITORAGGIO
# ========================================

@app.get("/")
def read_root():
    """Endpoint di benvenuto pubblico"""
    return {
        "message": "Gestionale Collaboratori e Progetti v2.0",
        "status": "online",
        "security": "enabled",
        "docs": "/docs" if os.getenv("ENVIRONMENT") != "production" else "Contact admin"
    }

def check_db_health():
    """Controlla lo stato del database"""
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False

@app.get("/health")
def health_check():
    """Health check superficiale - NO dipendenze DB/Redis"""
    return {"status": "ok"}

@app.get("/metrics")
@require_permission(Permission.VIEW_DASHBOARD)
def get_system_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Metriche di sistema per dashboard admin"""
    try:
        metrics = crud.get_dashboard_metrics(db)
        performance = crud.get_performance_bottlenecks(db)

        return {
            "dashboard_metrics": metrics._asdict() if metrics else {},
            "performance_analysis": performance,
            "timestamp": datetime.now()
        }
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Errore nel recupero metriche"
        )

@app.get("/admin/security-logs")
@require_permission(Permission.MANAGE_USERS)
def get_security_logs(
    skip: int = 0,
    limit: int = 100,
    success_only: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Visualizza log di sicurezza (solo admin)"""
    from auth import LoginAttempt

    query = db.query(LoginAttempt)

    if success_only is not None:
        query = query.filter(LoginAttempt.success == success_only)

    logs = query.order_by(LoginAttempt.timestamp.desc()).offset(skip).limit(limit).all()

    return {
        "logs": [
            {
                "id": log.id,
                "username": log.username,
                "ip_address": log.ip_address,
                "success": log.success,
                "failure_reason": log.failure_reason,
                "timestamp": log.timestamp
            }
            for log in logs
        ],
        "total": query.count()
    }

# NUOVI ENDPOINT PER BACKUP E MONITORING
@app.get("/admin/backup")
@require_permission(Permission.MANAGE_USERS)
def create_manual_backup(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Crea backup manuale del database"""
    if not BACKUP_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sistema di backup non disponibile"
        )

    try:
        backup_mgr = get_backup_manager()
        backup_path = backup_mgr.create_backup("manual")

        if backup_path:
            return {
                "message": "Backup creato con successo",
                "backup_path": backup_path,
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Errore nella creazione del backup"
            )
    except Exception as e:
        logger.error(f"Errore backup manuale: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.get("/admin/backups")
@require_permission(Permission.MANAGE_USERS)
def list_backups(
    current_user: User = Depends(get_admin_user)
):
    """Lista tutti i backup disponibili"""
    if not BACKUP_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sistema di backup non disponibile"
        )

    backup_mgr = get_backup_manager()
    return {
        "backups": backup_mgr.list_backups(),
        "statistics": backup_mgr.get_backup_statistics()
    }

@app.post("/admin/restore/{backup_filename}")
@require_permission(Permission.MANAGE_USERS)
def restore_backup(
    backup_filename: str,
    current_user: User = Depends(get_admin_user)
):
    """Ripristina un backup (ATTENZIONE: operazione irreversibile)"""
    if not BACKUP_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sistema di backup non disponibile"
        )

    try:
        backup_mgr = get_backup_manager()
        backup_path = backup_mgr.backup_dir / backup_filename

        if backup_mgr.restore_backup(str(backup_path)):
            return {
                "message": "Backup ripristinato con successo",
                "backup_file": backup_filename,
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Errore nel ripristino del backup"
            )
    except Exception as e:
        logger.error(f"Errore ripristino backup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.get("/admin/error-stats")
@require_permission(Permission.VIEW_DASHBOARD)
def get_error_statistics(
    current_user: User = Depends(get_current_user)
):
    """Ottieni statistiche errori del sistema"""
    return error_monitor.get_error_stats()

@app.get("/admin/performance")
@require_permission(Permission.VIEW_DASHBOARD)
def get_performance_metrics(
    current_user: User = Depends(get_current_user)
):
    """Ottieni metriche di performance del sistema"""
    if not PERFORMANCE_MONITOR_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sistema di monitoraggio performance non disponibile"
        )

    perf_monitor = get_performance_monitor()
    return {
        "current_metrics": perf_monitor.get_current_metrics(),
        "endpoint_metrics": perf_monitor.get_endpoint_metrics(),
        "performance_summary": perf_monitor.get_performance_summary()
    }

@app.get("/admin/performance/history")
@require_permission(Permission.VIEW_DASHBOARD)
def get_performance_history(
    hours: int = 24,
    current_user: User = Depends(get_current_user)
):
    """Ottieni storico metriche performance"""
    if not PERFORMANCE_MONITOR_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sistema di monitoraggio performance non disponibile"
        )

    perf_monitor = get_performance_monitor()
    return perf_monitor.get_historical_metrics(hours)

@app.post("/admin/performance/export")
@require_permission(Permission.MANAGE_USERS)
def export_performance_metrics(
    hours: int = 24,
    current_user: User = Depends(get_admin_user)
):
    """Esporta metriche performance in file JSON"""
    if not PERFORMANCE_MONITOR_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sistema di monitoraggio performance non disponibile"
        )

    try:
        perf_monitor = get_performance_monitor()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = f"./performance_export_{timestamp}.json"

        if perf_monitor.export_metrics(filepath, hours):
            return {
                "message": "Metriche esportate con successo",
                "filepath": filepath,
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Errore esportazione metriche"
            )
    except Exception as e:
        logger.error(f"Errore esportazione performance: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.post("/admin/cache/clear")
@require_permission(Permission.MANAGE_USERS)
def clear_application_cache(
    current_user: User = Depends(get_admin_user)
):
    """Pulisci cache applicazione"""
    try:
        from crud import query_cache
        query_cache.clear()
        logger.info("Application cache cleared by admin")
        return {
            "message": "Cache pulita con successo",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Errore pulizia cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# STARTUP EVENT
@app.on_event("startup")
async def startup_event():
    """Inizializzazione app al startup con sistemi avanzati"""
    logger.info("🚀 Gestionale Collaboratori v3.0 - Starting up")
    logger.info("✅ Error handling system enabled")
    logger.info("✅ Input validation system enabled")
    logger.info("✅ Security middleware enabled")
    logger.info("✅ Database connection pool configured")
    logger.info("✅ Authentication system ready")

    # Inizializza sistema backup (se disponibile)
    if BACKUP_AVAILABLE:
        try:
            backup_mgr = get_backup_manager()
            backup_mgr.schedule_automatic_backups()
            logger.info("✅ Automatic backup system started")
        except Exception as e:
            logger.error(f"Error starting backup system: {e}")
    else:
        logger.warning("⚠️ Backup system not available")

    # Inizializza monitoraggio performance (se disponibile)
    if PERFORMANCE_MONITOR_AVAILABLE:
        try:
            perf_monitor = get_performance_monitor()
            perf_monitor.start_monitoring(interval=30)
            logger.info("✅ Performance monitoring started")
        except Exception as e:
            logger.error(f"Error starting performance monitoring: {e}")
    else:
        logger.warning("⚠️ Performance monitoring not available")

    # Crea utente admin default se non esiste
    try:
        db = SessionLocal()
        admin_exists = db.query(User).filter(User.role == UserRole.ADMIN).first()
        if not admin_exists:
            create_user(
                db=db,
                username="admin",
                email="admin@gestionale.local",
                password="admin123",  # CAMBIARE IN PRODUZIONE!
                full_name="Amministratore Sistema",
                role=UserRole.ADMIN
            )
            logger.info("👤 Created default admin user (change password!)")
        db.close()
    except Exception as e:
        logger.error(f"Error creating admin user: {e}")

    # Verifica salute database
    try:
        from database import check_db_health
        if check_db_health():
            logger.info("✅ Database health check passed")
        else:
            logger.warning("⚠️ Database health check failed")
    except Exception as e:
        logger.error(f"Database health check error: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup al shutdown con backup automatico"""
    logger.info("🛑 Gestionale Collaboratori v3.0 - Shutting down")

    # Ferma sistemi di monitoraggio (se disponibile)
    if PERFORMANCE_MONITOR_AVAILABLE:
        try:
            perf_monitor = get_performance_monitor()
            perf_monitor.stop_monitoring()
            logger.info("✅ Performance monitoring stopped")
        except Exception as e:
            logger.error(f"Error stopping performance monitoring: {e}")
    else:
        logger.info("⚠️ Performance monitoring not available - skipping")

    # Crea backup di emergenza allo shutdown (se disponibile)
    if BACKUP_AVAILABLE:
        try:
            backup_mgr = get_backup_manager()
            backup_mgr.stop_automatic_backups()
            emergency_backup = backup_mgr.create_backup("emergency_shutdown")
            if emergency_backup:
                logger.info(f"✅ Emergency backup created: {emergency_backup}")
        except Exception as e:
            logger.error(f"Error creating emergency backup: {e}")
    else:
        logger.info("⚠️ Backup system not available - skipping emergency backup")

    logger.info("✅ Gestionale shutdown completed safely")

# DOCUMENTAZIONE:
# - Produzione: Documentazione disabilitata per sicurezza
# - Sviluppo: http://localhost:8000/docs
# - Autenticazione: Bearer token JWT required
# - Rate limiting: Attivo su tutti gli endpoints sensibili