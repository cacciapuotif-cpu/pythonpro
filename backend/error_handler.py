# Sistema centralizzato di gestione errori per il gestionale
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, HTTPException
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError
from pydantic import ValidationError
import logging
import traceback
from datetime import datetime
import os

# Setup logging avanzato
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.getenv('LOG_DIR', 'logs'), 'gestionale_errors.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class GestionaleException(Exception):
    """Eccezione base del gestionale"""
    def __init__(self, message: str, error_code: str = "GESTIONALE_ERROR", details: dict = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

class DatabaseConnectionError(GestionaleException):
    """Errore di connessione database"""
    def __init__(self, message: str = "Errore di connessione al database"):
        super().__init__(message, "DB_CONNECTION_ERROR")

class ValidationError(GestionaleException):
    """Errore di validazione dati"""
    def __init__(self, message: str, field: str = None):
        details = {"field": field} if field else {}
        super().__init__(message, "VALIDATION_ERROR", details)

class BusinessLogicError(GestionaleException):
    """Errore di logica business"""
    def __init__(self, message: str, operation: str = None):
        details = {"operation": operation} if operation else {}
        super().__init__(message, "BUSINESS_LOGIC_ERROR", details)

class ErrorHandler:
    """Gestore centralizzato degli errori"""

    @staticmethod
    def log_error(error: Exception, request: Request = None, user_id: int = None):
        """Logga l'errore con contesto completo"""
        error_info = {
            "timestamp": datetime.now().isoformat(),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
            "user_id": user_id,
            "request_url": request.url if request else None,
            "request_method": request.method if request else None,
            "request_headers": dict(request.headers) if request else None
        }

        logger.error(f"Errore applicazione: {error_info}")
        return error_info

    @staticmethod
    def handle_database_error(error: SQLAlchemyError) -> JSONResponse:
        """Gestisce errori database con retry logic"""
        if isinstance(error, OperationalError):
            logger.error(f"Database operational error: {error}")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "error": "Servizio temporaneamente non disponibile",
                    "error_code": "DB_UNAVAILABLE",
                    "retry_after": 30
                }
            )
        elif isinstance(error, IntegrityError):
            logger.error(f"Database integrity error: {error}")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "error": "Violazione vincoli dati",
                    "error_code": "DATA_INTEGRITY_ERROR",
                    "details": "I dati forniti violano i vincoli del database"
                }
            )
        else:
            logger.error(f"Generic database error: {error}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "Errore interno database",
                    "error_code": "DB_ERROR"
                }
            )

    @staticmethod
    def handle_validation_error(error: RequestValidationError) -> JSONResponse:
        """Gestisce errori di validazione Pydantic"""
        validation_errors = []
        for err in error.errors():
            validation_errors.append({
                "field": ".".join(str(x) for x in err["loc"]),
                "message": err["msg"],
                "type": err["type"]
            })

        logger.warning(f"Validation error: {validation_errors}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "Errori di validazione",
                "error_code": "VALIDATION_ERROR",
                "details": validation_errors
            }
        )

    @staticmethod
    def handle_http_exception(error: HTTPException) -> JSONResponse:
        """Gestisce eccezioni HTTP"""
        logger.warning(f"HTTP exception: {error.status_code} - {error.detail}")
        return JSONResponse(
            status_code=error.status_code,
            content={
                "error": error.detail,
                "error_code": f"HTTP_{error.status_code}"
            }
        )

# Decorator per retry automatico
def retry_on_db_error(max_retries: int = 3, delay: float = 1.0):
    """Decorator per retry automatico su errori database"""
    from functools import wraps

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            import time
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except OperationalError as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(f"Database error on attempt {attempt + 1}, retrying in {delay}s: {e}")
                        time.sleep(delay * (2 ** attempt))  # Exponential backoff
                    else:
                        logger.error(f"Max retries reached for {func.__name__}")
                        raise
                except Exception as e:
                    # Per altri errori, non fare retry
                    raise

            raise last_exception
        return wrapper
    return decorator

# Context manager per transazioni sicure
class SafeTransaction:
    """Context manager per transazioni database sicure"""

    def __init__(self, db_session):
        self.db = db_session
        self.committed = False

    def __enter__(self):
        return self.db

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None and not self.committed:
            try:
                self.db.commit()
                self.committed = True
            except Exception as e:
                logger.error(f"Error committing transaction: {e}")
                self.db.rollback()
                raise
        elif exc_type is not None:
            logger.error(f"Transaction rolled back due to: {exc_type.__name__}: {exc_val}")
            self.db.rollback()

    def commit(self):
        """Commit manuale"""
        if not self.committed:
            self.db.commit()
            self.committed = True

# Middleware di monitoring errori
class ErrorMonitoringMiddleware:
    """Middleware per monitorare errori in tempo reale"""

    def __init__(self):
        self.error_count = {}
        self.last_reset = datetime.now()

    def record_error(self, error_type: str):
        """Registra un errore per monitoring"""
        current_time = datetime.now()

        # Reset contatori ogni ora
        if (current_time - self.last_reset).seconds > 3600:
            self.error_count = {}
            self.last_reset = current_time

        self.error_count[error_type] = self.error_count.get(error_type, 0) + 1

        # Alert se troppi errori
        if self.error_count[error_type] > 10:
            logger.critical(f"Molti errori di tipo {error_type}: {self.error_count[error_type]} nell'ultima ora")

    def get_error_stats(self):
        """Ottieni statistiche errori"""
        return {
            "error_counts": self.error_count,
            "last_reset": self.last_reset.isoformat(),
            "total_errors": sum(self.error_count.values())
        }

# Singleton per il monitoraggio
error_monitor = ErrorMonitoringMiddleware()