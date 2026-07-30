# Sistema centralizzato di gestione errori per il gestionale
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, HTTPException
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError
from pydantic import ValidationError as PydanticValidationError
import logging
import traceback
from datetime import datetime
import os
import re

# Setup logging avanzato
_log_dir = os.getenv('LOG_DIR', 'logs')
os.makedirs(_log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(_log_dir, 'gestionale_errors.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

REDACTED = "[REDACTED]"
SAFE_HEADER_NAMES = {"content-type", "x-request-id", "x-correlation-id"}
SENSITIVE_HEADER_NAMES = {
    "authorization",
    "cookie",
    "set-cookie",
    "proxy-authorization",
    "x-api-key",
    "x-auth-token",
    "x-csrf-token",
    "x-forwarded-access-token",
}
SENSITIVE_TEXT_PATTERNS = (
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+"),
    re.compile(r"(?i)(basic\s+)[A-Za-z0-9._~+/=-]+"),
    re.compile(
        r"(?i)((?:password|passwd|pwd|token|secret|api[_-]?key|authorization|cookie|set-cookie)\s*[=:]\s*)[^\s,;&]+"
    ),
)


def redact_sensitive_text(value):
    """Redact common credentials before writing application logs."""
    if value is None:
        return None
    redacted = str(value)
    for pattern in SENSITIVE_TEXT_PATTERNS:
        redacted = pattern.sub(rf"\1{REDACTED}", redacted)
    return redacted


def sanitize_request_headers(headers):
    """Keep only diagnostic headers and redact known sensitive headers."""
    if not headers:
        return None

    sanitized = {}
    for name, value in headers.items():
        key = name.lower()
        if key in SENSITIVE_HEADER_NAMES:
            sanitized[key] = REDACTED
        elif key in SAFE_HEADER_NAMES:
            sanitized[key] = redact_sensitive_text(value)
    return sanitized


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
        """Logga l'errore con contesto diagnostico redatto."""
        if isinstance(error, (RequestValidationError, PydanticValidationError)):
            # Pydantic include il payload originale dentro ``errors()`` e nella
            # rappresentazione testuale dell'eccezione. Per gli endpoint auth
            # quel payload può contenere password o token, quindi nei log
            # conserviamo solo conteggio e struttura dei campi.
            safe_errors = ErrorHandler.validation_errors_for_log(error)
            error_message = f"{type(error).__name__}: {len(safe_errors)} validation error(s)"
            safe_traceback = None
        else:
            error_message = redact_sensitive_text(str(error))
            safe_traceback = redact_sensitive_text(traceback.format_exc())

        error_info = {
            "timestamp": datetime.now().isoformat(),
            "error_type": type(error).__name__,
            "error_message": error_message,
            "traceback": safe_traceback,
            "user_id": user_id,
            "request_path": request.url.path if request else None,
            "request_method": request.method if request else None,
            "request_headers": sanitize_request_headers(request.headers) if request else None,
        }

        logger.error("Errore applicazione: %s", error_info)
        return error_info

    @staticmethod
    def redact_text(value):
        """Expose log redaction for callers that log outside ErrorHandler."""
        return redact_sensitive_text(value)

    @staticmethod
    def validation_errors_for_log(error):
        """Restituisce solo metadati strutturali, mai input o contesto Pydantic."""
        return [
            {
                "field": ".".join(str(item) for item in validation_error.get("loc", ())),
                "type": validation_error.get("type", "validation_error"),
            }
            for validation_error in error.errors()
        ]

    @staticmethod
    def handle_database_error(error: SQLAlchemyError) -> JSONResponse:
        """Gestisce errori database con retry logic"""
        if isinstance(error, OperationalError):
            logger.error("Database operational error: %s", ErrorHandler.redact_text(error))
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "error": "Servizio temporaneamente non disponibile",
                    "error_code": "DB_UNAVAILABLE",
                    "retry_after": 30
                }
            )
        elif isinstance(error, IntegrityError):
            logger.error("Database integrity error: %s", ErrorHandler.redact_text(error))
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "error": "Violazione vincoli dati",
                    "error_code": "DATA_INTEGRITY_ERROR",
                    "details": "I dati forniti violano i vincoli del database"
                }
            )
        else:
            logger.error("Generic database error: %s", ErrorHandler.redact_text(error))
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

        logger.warning("Validation error: %s", ErrorHandler.redact_text(validation_errors))
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
        logger.warning("HTTP exception: %s - %s", error.status_code, ErrorHandler.redact_text(error.detail))
        return JSONResponse(
            status_code=error.status_code,
            content={"detail": error.detail},
            headers=getattr(error, "headers", None),
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
                        logger.warning("Database error on attempt %s, retrying in %ss: %s", attempt + 1, delay, ErrorHandler.redact_text(e))
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
                logger.error("Error committing transaction: %s", ErrorHandler.redact_text(e))
                self.db.rollback()
                raise
        elif exc_type is not None:
            logger.error("Transaction rolled back due to: %s: %s", exc_type.__name__, ErrorHandler.redact_text(exc_val))
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
