# IMPORTAZIONI - tutte le librerie che useremo
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import List
from datetime import datetime
import os
import logging

# IMPORTAZIONI DEI NOSTRI MODULI
import models
import schemas
import crud
from database import SessionLocal, engine, get_db

# Setup logging avanzato
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
    ErrorHandler, GestionaleException,
    error_monitor
)

# Importazioni opzionali per sistemi avanzati
try:
    from backup_manager import get_backup_manager
    BACKUP_AVAILABLE = True
except ImportError:
    logger.warning("backup_manager non disponibile")
    BACKUP_AVAILABLE = False

try:
    from performance_monitor import get_performance_monitor
    PERFORMANCE_MONITOR_AVAILABLE = True
except ImportError:
    logger.warning("performance_monitor non disponibile")
    PERFORMANCE_MONITOR_AVAILABLE = False

from request_middleware import setup_middleware

# IMPORTAZIONI SICUREZZA E AUTENTICAZIONE
from auth import User, UserRole, create_user

# IMPORTAZIONI ROUTERS MODULARI
from routers import (
    collaborators,
    projects,
    attendances,
    assignments,
    implementing_entities,
    progetto_mansione_ente,
    contract_templates,
    admin,
    system,
    reporting
)

# CREIAMO LE TABELLE NEL DATABASE
models.Base.metadata.create_all(bind=engine)

# CREAZIONE DELL'APPLICAZIONE FASTAPI
app = FastAPI(
    title="Gestionale Collaboratori e Progetti",
    description="Sistema per gestire collaboratori, progetti formativi e presenze",
    version="2.0.0"
)

# ========================================
# GESTORI DI ERRORE CENTRALIZZATI
# ========================================

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


# ========================================
# CONFIGURAZIONE CORS E MIDDLEWARE
# ========================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

setup_middleware(app)


# ========================================
# REGISTRAZIONE ROUTERS MODULARI
# ========================================

# Router per risorse principali
app.include_router(system.router)
app.include_router(collaborators.router)
app.include_router(projects.router)
app.include_router(attendances.router)
app.include_router(assignments.router)

# Router per enti e associazioni
app.include_router(implementing_entities.router)
app.include_router(progetto_mansione_ente.router)

# Router per template e generazione contratti
app.include_router(contract_templates.router)

# Router per reporting e statistiche
app.include_router(reporting.router)

# Router amministrazione
app.include_router(admin.router)


# ========================================
# ENDPOINTS CROSS-RESOURCE
# Questi endpoint collegano più risorse e rimangono nel main
# ========================================

@app.post("/test-post")
def test_post_endpoint(data: dict):
    """TEST ENDPOINT - verifica che POST funzioni"""
    return {"received": data, "status": "OK"}


@app.get("/collaborators-with-projects/", response_model=List[schemas.CollaboratorWithProjects], response_model_by_alias=False)
def read_collaborators_with_projects(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    OTTIENI COLLABORATORI CON I LORO PROGETTI ASSEGNATI
    Endpoint cross-resource che unisce collaboratori e progetti
    """
    collaborators_with_projects = crud.get_collaborators_with_projects(db, skip=skip, limit=limit)
    return collaborators_with_projects


@app.post("/collaborators/{collaborator_id}/projects/{project_id}")
def assign_collaborator_to_project(
    collaborator_id: int,
    project_id: int,
    db: Session = Depends(get_db)
):
    """ASSEGNA UN COLLABORATORE AD UN PROGETTO"""
    collaborator = crud.assign_collaborator_to_project(db, collaborator_id, project_id)
    if collaborator is None:
        raise HTTPException(status_code=404, detail="Collaboratore o progetto non trovato")
    return {"message": "Collaboratore assegnato al progetto con successo"}


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


@app.get("/collaborators/{collaborator_id}/assignments/", response_model=List[schemas.Assignment], response_model_by_alias=False)
def read_collaborator_assignments(
    collaborator_id: int,
    db: Session = Depends(get_db)
):
    """OTTIENI TUTTE LE ASSEGNAZIONI DI UN COLLABORATORE"""
    assignments = crud.get_assignments_by_collaborator(db, collaborator_id)
    return assignments


@app.get("/projects/{project_id}/assignments/", response_model=List[schemas.Assignment], response_model_by_alias=False)
def read_project_assignments(
    project_id: int,
    db: Session = Depends(get_db)
):
    """OTTIENI TUTTE LE ASSEGNAZIONI DI UN PROGETTO"""
    assignments = crud.get_assignments_by_project(db, project_id)
    return assignments


@app.get("/projects/{project_id}/mansioni-enti", response_model=List[schemas.ProgettoMansioneEnteWithDetails], response_model_by_alias=False)
def get_project_mansioni_enti(
    project_id: int,
    db: Session = Depends(get_db)
):
    """RECUPERA TUTTE LE ASSOCIAZIONI (MANSIONI-ENTI) DI UN PROGETTO"""
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Progetto non trovato"
        )

    associazioni = crud.get_progetto_mansione_ente_by_project(db, project_id)
    return associazioni


@app.get("/implementing-entities/{entity_id}/mansioni-progetti", response_model=List[schemas.ProgettoMansioneEnteWithDetails], response_model_by_alias=False)
def get_entity_mansioni_progetti(
    entity_id: int,
    db: Session = Depends(get_db)
):
    """RECUPERA TUTTE LE ASSOCIAZIONI (MANSIONI-PROGETTI) DI UN ENTE ATTUATORE"""
    entity = crud.get_implementing_entity(db, entity_id)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ente attuatore non trovato"
        )

    associazioni = crud.get_progetto_mansione_ente_by_entity(db, entity_id)
    return associazioni


# ========================================
# STARTUP E SHUTDOWN EVENTS
# ========================================

@app.on_event("startup")
async def startup_event():
    """Inizializzazione app al startup"""
    logger.info("🚀 Gestionale Collaboratori v2.0 - Starting up")
    logger.info("✅ Error handling system enabled")
    logger.info("✅ Modular routers architecture enabled")
    logger.info("✅ Security middleware enabled")
    logger.info("✅ Database connection pool configured")

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
    logger.info("🛑 Gestionale Collaboratori v2.0 - Shutting down")

    # Ferma sistemi di monitoraggio (se disponibile)
    if PERFORMANCE_MONITOR_AVAILABLE:
        try:
            perf_monitor = get_performance_monitor()
            perf_monitor.stop_monitoring()
            logger.info("✅ Performance monitoring stopped")
        except Exception as e:
            logger.error(f"Error stopping performance monitoring: {e}")

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

    logger.info("✅ Gestionale shutdown completed safely")


# DOCUMENTAZIONE API
# - Sviluppo: http://localhost:8000/docs
# - Produzione: Documentazione disabilitata per sicurezza
