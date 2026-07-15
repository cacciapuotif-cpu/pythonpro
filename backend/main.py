# IMPORTAZIONI - tutte le librerie che useremo
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import Any, List
from datetime import datetime
import json
import os
import logging
import re

# IMPORTAZIONI DEI NOSTRI MODULI
import models
import schemas
import crud
from database import SessionLocal, engine, get_db

# Setup logging avanzato
_log_dir = os.getenv('LOG_DIR', 'logs')
os.makedirs(_log_dir, exist_ok=True)
_log_handlers = [logging.StreamHandler()]
try:
    _log_handlers.insert(0, logging.FileHandler(os.path.join(_log_dir, 'gestionale.log')))
except (OSError, PermissionError):
    pass  # Se logs non è scrivibile usa solo stdout

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=_log_handlers
)
logger = logging.getLogger(__name__)

ADMIN_DEFAULT_PASSWORD = os.getenv("ADMIN_DEFAULT_PASSWORD", "").strip()
OPERATOR_DEFAULT_PASSWORD = os.getenv("OPERATOR_DEFAULT_PASSWORD", "").strip()

CAMPI_SENSIBILI = {
    "password", "token", "access_token", "refresh_token", "secret", "codice_fiscale", "iban",
    "documento_identita", "documento_identita_path", "curriculum_path",
    "email", "phone", "telefono", "partita_iva", "first_name",
    "last_name", "data_nascita",
}


def valida_password_bootstrap(password: str, ruolo: str) -> None:
    if not password:
        raise ValueError(f"[AVVIO] {ruolo}: BOOTSTRAP_PASSWORD non configurata")
    if len(password) < 12:
        raise ValueError(f"[AVVIO] {ruolo}: password troppo corta (min 12 char)")
    if not re.search(r"[A-Z]", password):
        raise ValueError(f"[AVVIO] {ruolo}: password deve contenere maiuscole")
    if not re.search(r"[0-9]", password):
        raise ValueError(f"[AVVIO] {ruolo}: password deve contenere cifre")
    if not re.search(r"[^A-Za-z0-9]", password):
        raise ValueError(f"[AVVIO] {ruolo}: password deve contenere caratteri speciali")


def sanitize_body_for_log(body: Any) -> Any:
    if isinstance(body, dict):
        sanitized = {}
        for key, value in body.items():
            normalized = str(key).lower()
            if any(sensitive in normalized for sensitive in CAMPI_SENSIBILI):
                sanitized[key] = "***REDACTED***"
            else:
                sanitized[key] = sanitize_body_for_log(value)
        return sanitized
    if isinstance(body, list):
        return [sanitize_body_for_log(item) for item in body]
    return body

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
from auth import User, UserRole, create_user, get_current_user, require_role

# IMPORTAZIONI ROUTERS MODULARI
from routers.timesheet import router as timesheet_router
from routers.cockpit import router as cockpit_router
from routers.sprint7 import router as sprint7_router
from routers.portale_allievi import router as portale_allievi_router
from routers.convenzione_upload import router as convenzione_upload_router
from routers.formulario_upload import router as formulario_upload_router
from routers.piano_finanziario_upload import router as piano_finanziario_upload_router
from routers.fondimpresa_upload import router as fondimpresa_upload_router
from routers import (
    auth,
    collaborators,
    projects,
    attendances,
    assignments,
    implementing_entities,
    progetto_mansione_ente,
    contract_templates,
    admin,
    system,
    reporting,
    agenzie,
    consulenti,
    aziende_clienti,
    allievi,
    catalogo,
    listini,
    preventivi,
    ordini,
    piani_finanziari,
    documenti_richiesti,
    avvisi,
    agents,
    email_inbox,
    whatsapp,
    gdpr,
)

# Lo schema database e' gestito esclusivamente da Alembic.
# L'entrypoint esegue `alembic upgrade head` prima dell'avvio applicativo.

# CREAZIONE DELL'APPLICAZIONE FASTAPI
app = FastAPI(
    title="Gestionale Collaboratori e Progetti",
    description="Sistema per gestire collaboratori, progetti formativi e presenze",
    version="2.0.0",
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
    logger.error("Validation error on %s: %s", request.url.path, ErrorHandler.redact_text(exc.errors()))
    if request.method == "POST" and request.url.path.startswith("/api/v1/auth/"):
        safe_body = "<auth body redatto>"
    else:
        body = await request.body()
        if body:
            try:
                parsed_body = json.loads(body.decode())
                safe_body = sanitize_body_for_log(parsed_body)
            except Exception:
                safe_body = "<non-json body redatto>"
        else:
            safe_body = "empty"
    safe_body_text = json.dumps(safe_body, ensure_ascii=False, default=str) if not isinstance(safe_body, str) else safe_body
    if len(safe_body_text) > 500:
        safe_body_text = safe_body_text[:500] + "...<truncated>"
    logger.error("Request body: %s", safe_body_text)
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
    logger.critical("Unhandled exception: %s", ErrorHandler.redact_text(exc))
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

setup_middleware(app)

_cors_origins_raw = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3001")
_cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin", "X-Requested-With", "X-Request-ID"],
)


# ========================================
# REGISTRAZIONE ROUTERS MODULARI
# ========================================

_protected_dependencies = [Depends(require_role)]


def include_protected_router(router):
    app.include_router(router, dependencies=_protected_dependencies)


# Router autenticazione
app.include_router(auth.router)

# Router pubblici per health/root
app.include_router(system.router)

# Portale allievi: pubblico by design, autenticato dal magic token
# a scadenza (vedi routers/portale_allievi.py), non dal JWT applicativo.
app.include_router(portale_allievi_router)

# Router per risorse principali
include_protected_router(collaborators.router)
include_protected_router(projects.router)
include_protected_router(attendances.router)
include_protected_router(assignments.router)
include_protected_router(timesheet_router)
include_protected_router(cockpit_router)
include_protected_router(sprint7_router)

# Router per enti e associazioni
include_protected_router(implementing_entities.router)
include_protected_router(progetto_mansione_ente.router)

# Router per template e generazione contratti
include_protected_router(contract_templates.router)

# Router per reporting e statistiche
include_protected_router(reporting.router)

# Router amministrazione
include_protected_router(admin.router)

# Router Blocco 1 — Anagrafica espansa
include_protected_router(agenzie.router)
include_protected_router(consulenti.router)
include_protected_router(aziende_clienti.router)
include_protected_router(allievi.router)

# Router Blocco 3 — Catalogo + Listini
include_protected_router(catalogo.router)
include_protected_router(listini.router)

# Router Blocco 4 — Preventivi + Ordini
include_protected_router(preventivi.router)
include_protected_router(ordini.router)

# Router Piano Finanziario Formazienda
include_protected_router(piani_finanziari.router)
include_protected_router(documenti_richiesti.router)
include_protected_router(avvisi.router)
include_protected_router(agents.router)
include_protected_router(agents.suggestion_actions_router)
include_protected_router(email_inbox.router)
include_protected_router(gdpr.router)

# Router FAPI — upload documenti
include_protected_router(convenzione_upload_router)
include_protected_router(formulario_upload_router)
include_protected_router(piano_finanziario_upload_router)
include_protected_router(fondimpresa_upload_router)

# Webhook WhatsApp Meta deve restare raggiungibile dal provider esterno.
app.include_router(whatsapp.router)


# ========================================
# ENDPOINTS CROSS-RESOURCE
# Questi endpoint collegano più risorse e rimangono nel main
# ========================================

@app.get("/collaborators-with-projects/", response_model=List[schemas.CollaboratorWithProjects], response_model_by_alias=False)
def read_collaborators_with_projects(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """OTTIENI TUTTE LE ASSEGNAZIONI DI UN COLLABORATORE"""
    assignments = crud.get_assignments_by_collaborator(db, collaborator_id)
    return assignments


@app.get("/projects/{project_id}/assignments/", response_model=List[schemas.Assignment], response_model_by_alias=False)
def read_project_assignments(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """OTTIENI TUTTE LE ASSEGNAZIONI DI UN PROGETTO"""
    assignments = crud.get_assignments_by_project(db, project_id)
    return assignments


@app.get("/projects/{project_id}/mansioni-enti", response_model=List[schemas.ProgettoMansioneEnteWithDetails], response_model_by_alias=False)
def get_project_mansioni_enti(
    project_id: int,
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
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

    auto_backup_enabled = os.getenv("AUTO_BACKUP_ENABLED", "false").lower() == "true"

    # Inizializza sistema backup (se disponibile)
    if BACKUP_AVAILABLE and auto_backup_enabled:
        try:
            backup_mgr = get_backup_manager()
            backup_mgr.schedule_automatic_backups()
            logger.info("✅ Automatic backup system started")
        except Exception as e:
            logger.error(f"Error starting backup system: {e}")
    elif BACKUP_AVAILABLE:
        logger.info("ℹ️ Automatic backup scheduler disabled for web process")
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

    # Crea utenti di accesso iniziali solo se le password bootstrap sono configurate.
    try:
        db = SessionLocal()
        admin_exists = db.query(User).filter(User.username == "admin").first()
        if not admin_exists:
            valida_password_bootstrap(ADMIN_DEFAULT_PASSWORD, "admin")
            create_user(
                db=db,
                username="admin",
                email="admin@gestionale.local",
                password=ADMIN_DEFAULT_PASSWORD,
                full_name="Amministratore Sistema",
                role=UserRole.ADMIN
            )
            logger.info("👤 Created default admin user from environment bootstrap password")


        operator_exists = db.query(User).filter(User.username == "operatore").first()
        if not operator_exists:
            valida_password_bootstrap(OPERATOR_DEFAULT_PASSWORD, "operatore")
            create_user(
                db=db,
                username="operatore",
                email="operatore@gestionale.local",
                password=OPERATOR_DEFAULT_PASSWORD,
                full_name="Operatore Gestionale",
                role=UserRole.OPERATORE
            )
            logger.info("👤 Created default operator user from environment bootstrap password")
        db.close()
    except Exception as e:
        logger.error(f"Error creating bootstrap users: {e}")
        raise

    # Verifica salute database
    try:
        from database import check_db_health
        if check_db_health():
            logger.info("✅ Database health check passed")
        else:
            logger.warning("⚠️ Database health check failed")
    except Exception as e:
        logger.error(f"Database health check error: {e}")

    # NOTA: EmailInboxWorker (IMAP polling) è stato spostato in arq_worker.py
    # come cron job (poll_email_inbox ogni 5 min). Avviarlo qui causerebbe
    # un thread per ogni processo uvicorn → elaborazione duplicata delle email.


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

    auto_backup_enabled = os.getenv("AUTO_BACKUP_ENABLED", "false").lower() == "true"

    # Crea backup di emergenza allo shutdown (se disponibile)
    if BACKUP_AVAILABLE and auto_backup_enabled:
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
