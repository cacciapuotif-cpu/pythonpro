# Middleware avanzato per gestione richieste e performance
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
import time
import logging
import uuid
from typing import Callable
import json
from datetime import datetime

# Import opzionale del performance monitor
try:
    from performance_monitor import get_performance_monitor
    PERFORMANCE_MONITOR_AVAILABLE = True
except ImportError:
    PERFORMANCE_MONITOR_AVAILABLE = False
    get_performance_monitor = None

logger = logging.getLogger(__name__)

class RequestTrackingMiddleware(BaseHTTPMiddleware):
    """Middleware per tracking avanzato delle richieste"""

    def __init__(self, app, enable_detailed_logging: bool = True):
        super().__init__(app)
        self.enable_detailed_logging = enable_detailed_logging
        self.performance_monitor = get_performance_monitor() if PERFORMANCE_MONITOR_AVAILABLE else None

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Genera ID unico per la richiesta
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        # Timestamp inizio
        start_time = time.time()

        # Log richiesta in arrivo
        if self.enable_detailed_logging:
            logger.info(
                f"[{request_id}] {request.method} {request.url.path} "
                f"from {request.client.host if request.client else 'unknown'}"
            )

        try:
            # Processa richiesta
            response = await call_next(request)

            # Calcola tempo di risposta
            process_time = time.time() - start_time
            response_time_ms = process_time * 1000

            # Aggiungi headers di debug
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{response_time_ms:.2f}ms"

            # Registra metriche (se disponibile)
            if self.performance_monitor:
                self.performance_monitor.record_request(
                    endpoint=request.url.path,
                    method=request.method,
                    response_time=response_time_ms,
                    status_code=response.status_code
                )

            # Log risposta
            if self.enable_detailed_logging:
                logger.info(
                    f"[{request_id}] Response: {response.status_code} "
                    f"in {response_time_ms:.2f}ms"
                )

            # Log richieste lente
            if response_time_ms > 1000:  # > 1 secondo
                logger.warning(
                    f"[{request_id}] SLOW REQUEST: {request.method} {request.url.path} "
                    f"took {response_time_ms:.2f}ms"
                )

            return response

        except Exception as e:
            # Calcola tempo anche per errori
            process_time = time.time() - start_time
            response_time_ms = process_time * 1000

            # Registra errore (se disponibile)
            if self.performance_monitor:
                self.performance_monitor.record_request(
                    endpoint=request.url.path,
                    method=request.method,
                    response_time=response_time_ms,
                    status_code=500
                )

            logger.error(
                f"[{request_id}] ERROR: {request.method} {request.url.path} "
                f"failed after {response_time_ms:.2f}ms: {str(e)}"
            )

            raise

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware per aggiungere header di sicurezza"""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        # Header di sicurezza
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # CSP per prevenire XSS
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "connect-src 'self'"
        )

        return response

class RateLimitingMiddleware(BaseHTTPMiddleware):
    """Middleware per rate limiting semplice"""

    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.client_requests = {}  # IP -> [timestamps]

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        current_time = datetime.now()

        # Inizializza tracking per nuovo IP
        if client_ip not in self.client_requests:
            self.client_requests[client_ip] = []

        # Pulisci richieste vecchie (oltre 1 minuto)
        cutoff_time = current_time.timestamp() - 60
        self.client_requests[client_ip] = [
            req_time for req_time in self.client_requests[client_ip]
            if req_time > cutoff_time
        ]

        # Controlla rate limit
        if len(self.client_requests[client_ip]) >= self.requests_per_minute:
            logger.warning(f"Rate limit exceeded for {client_ip}")
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "retry_after": 60
                },
                headers={"Retry-After": "60"}
            )

        # Aggiungi timestamp richiesta corrente
        self.client_requests[client_ip].append(current_time.timestamp())

        return await call_next(request)

class RequestValidationMiddleware(BaseHTTPMiddleware):
    """Middleware per validazione richieste"""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Controlla dimensione body usando Content-Length header invece di leggere il body
        # (leggere il body consuma lo stream e causa problemi con FastAPI)
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > 10 * 1024 * 1024:  # 10MB limit
                    logger.warning(f"Request body too large: {content_length} bytes")
                    from fastapi.responses import JSONResponse
                    return JSONResponse(
                        status_code=413,
                        content={"error": "Request body too large"}
                    )
            except ValueError:
                pass  # Invalid content-length, ignore

        # Controlla Content-Type per richieste POST/PUT
        if request.method in ["POST", "PUT", "PATCH"]:
            content_type = request.headers.get("content-type", "")
            if not content_type.startswith("application/json") and \
               not content_type.startswith("multipart/form-data") and \
               not content_type.startswith("application/x-www-form-urlencoded"):
                logger.warning(f"Invalid Content-Type: {content_type}")

        return await call_next(request)

class DatabaseHealthMiddleware(BaseHTTPMiddleware):
    """Middleware per controllo salute database"""

    def __init__(self, app, check_interval: int = 30):
        super().__init__(app)
        self.check_interval = check_interval
        self.last_check = 0
        self.db_healthy = True

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        current_time = time.time()

        # Controlla salute database periodicamente
        if current_time - self.last_check > self.check_interval:
            self.db_healthy = await self._check_database_health()
            self.last_check = current_time

        # Se database non disponibile, ritorna errore per alcune operazioni
        if not self.db_healthy and request.method in ["POST", "PUT", "DELETE"]:
            logger.error("Database unhealthy, blocking write operations")
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Service temporarily unavailable",
                    "reason": "Database connection issues"
                }
            )

        return await call_next(request)

    async def _check_database_health(self) -> bool:
        """Controlla salute database"""
        try:
            from database import check_db_health
            return check_db_health()
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

class ResponseCompressionMiddleware(BaseHTTPMiddleware):
    """Middleware per compressione response"""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        # Aggiungi header per compressione se supportata
        accept_encoding = request.headers.get("accept-encoding", "")
        if "gzip" in accept_encoding:
            response.headers["Content-Encoding"] = "gzip"

        return response

# Funzione per configurare tutti i middleware
def setup_middleware(app):
    """Configura tutti i middleware dell'applicazione"""

    # Middleware in ordine di esecuzione (ultimo aggiunto = primo eseguito)

    # TUTTI I MIDDLEWARE DISABILITATI TEMPORANEAMENTE PER DEBUG
    # Uno di questi sta causando il timeout delle POST requests

    # Compressione disabilitata - causa problemi con ERR_CONTENT_DECODING_FAILED
    # app.add_middleware(ResponseCompressionMiddleware)

    # 1. Headers di sicurezza
    # app.add_middleware(SecurityHeadersMiddleware)

    # 2. Controllo salute database
    # app.add_middleware(DatabaseHealthMiddleware, check_interval=30)

    # 3. Validazione richieste
    # app.add_middleware(RequestValidationMiddleware)

    # 4. Rate limiting - disabilitato in development per evitare blocchi
    # app.add_middleware(RateLimitingMiddleware, requests_per_minute=120)

    # 5. Tracking richieste (primo)
    # app.add_middleware(RequestTrackingMiddleware, enable_detailed_logging=True)

    logger.info("All middleware DISABLED for debugging")