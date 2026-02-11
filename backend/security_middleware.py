"""
Middleware di sicurezza per FastAPI
Implementa security headers, CORS avanzato, request validation
"""

from fastapi import Request, Response, HTTPException, status
from fastapi.middleware.base import BaseHTTPMiddleware
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
import time
import logging
import json
import hashlib
import os
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import re

logger = logging.getLogger(__name__)

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware per aggiungere security headers"""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Security headers essenziali
        security_headers = {
            # Previene clickjacking
            "X-Frame-Options": "DENY",

            # Previene MIME sniffing
            "X-Content-Type-Options": "nosniff",

            # Attiva XSS protection
            "X-XSS-Protection": "1; mode=block",

            # Strict Transport Security (HTTPS only)
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",

            # Content Security Policy
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "connect-src 'self'; "
                "font-src 'self'; "
                "frame-ancestors 'none';"
            ),

            # Referrer Policy
            "Referrer-Policy": "strict-origin-when-cross-origin",

            # Permissions Policy
            "Permissions-Policy": (
                "accelerometer=(), camera=(), geolocation=(), "
                "gyroscope=(), magnetometer=(), microphone=(), "
                "payment=(), usb=()"
            ),

            # Cache Control per API
            "Cache-Control": "no-store, no-cache, must-revalidate, private",
            "Pragma": "no-cache",
            "Expires": "0",

            # Server header nascosto
            "Server": "Unknown"
        }

        for header, value in security_headers.items():
            response.headers[header] = value

        return response

class RequestValidationMiddleware(BaseHTTPMiddleware):
    """Middleware per validazione richieste e protezione da attacchi"""

    def __init__(self, app, max_request_size: int = 10 * 1024 * 1024):  # 10MB
        super().__init__(app)
        self.max_request_size = max_request_size

        # Pattern per rilevare attacchi comuni
        self.attack_patterns = {
            'sql_injection': [
                r"(\bunion\b.*\bselect\b|\bselect\b.*\bunion\b)",
                r"(\bdrop\b.*\btable\b|\btable\b.*\bdrop\b)",
                r"(\binsert\b.*\binto\b|\binto\b.*\binsert\b)",
                r"(\bdelete\b.*\bfrom\b|\bfrom\b.*\bdelete\b)",
                r"(\bupdate\b.*\bset\b|\bset\b.*\bupdate\b)",
                r"('.*'|\".*\").*(\bor\b|\band\b).*('.*'|\".*\")",
                r";.*(--)|(\/\*.*\*\/)"
            ],
            'xss': [
                r"<script[^>]*>.*?</script>",
                r"javascript:",
                r"on\w+\s*=",
                r"<iframe[^>]*>.*?</iframe>",
                r"<object[^>]*>.*?</object>",
                r"<embed[^>]*>.*?</embed>"
            ],
            'path_traversal': [
                r"\.\./",
                r"\.\.\\\\",
                r"\/\.\.\/",
                r"\\\\\.\.\\\\",
                r"%2e%2e%2f",
                r"%2e%2e%5c"
            ],
            'command_injection': [
                r"[;&|`]",
                r"\$\(",
                r"<\(",
                r">\(",
                r"nc\s+-",
                r"wget\s+",
                r"curl\s+"
            ]
        }

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        try:
            # Validazione dimensione richiesta
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > self.max_request_size:
                logger.warning(f"Request too large: {content_length} bytes from {request.client.host}")
                return JSONResponse(
                    status_code=413,
                    content={"detail": "Request entity too large"}
                )

            # Validazione User-Agent
            user_agent = request.headers.get("user-agent", "")
            if self._is_suspicious_user_agent(user_agent):
                logger.warning(f"Suspicious user agent: {user_agent} from {request.client.host}")
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid user agent"}
                )

            # Validazione URL e parametri
            if self._contains_attack_patterns(str(request.url)):
                logger.warning(f"Attack pattern in URL: {request.url} from {request.client.host}")
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid request"}
                )

            # Validazione body per richieste POST/PUT/PATCH
            if request.method in ["POST", "PUT", "PATCH"]:
                body = await self._get_request_body(request)
                if body and self._contains_attack_patterns(body):
                    logger.warning(f"Attack pattern in body from {request.client.host}")
                    return JSONResponse(
                        status_code=400,
                        content={"detail": "Invalid request body"}
                    )

            response = await call_next(request)

            # Log richieste per monitoring
            process_time = time.time() - start_time
            self._log_request(request, response, process_time)

            return response

        except Exception as e:
            logger.error(f"Error in request validation: {e}")
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"}
            )

    def _is_suspicious_user_agent(self, user_agent: str) -> bool:
        """Controlla se lo user agent è sospetto"""
        if not user_agent or len(user_agent) < 10:
            return True

        suspicious_agents = [
            "bot", "crawler", "spider", "scraper", "wget", "curl",
            "python-requests", "libwww", "scanner", "nikto", "sqlmap"
        ]

        return any(agent in user_agent.lower() for agent in suspicious_agents)

    def _contains_attack_patterns(self, text: str) -> bool:
        """Controlla se il testo contiene pattern di attacco"""
        if not text:
            return False

        text_lower = text.lower()

        for attack_type, patterns in self.attack_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    logger.warning(f"Detected {attack_type} pattern: {pattern}")
                    return True

        return False

    async def _get_request_body(self, request: Request) -> Optional[str]:
        """Ottiene il body della richiesta in modo sicuro"""
        try:
            body = await request.body()
            return body.decode('utf-8') if body else None
        except Exception as e:
            logger.error(f"Error reading request body: {e}")
            return None

    def _log_request(self, request: Request, response: Response, process_time: float):
        """Log delle richieste per monitoring"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "method": request.method,
            "url": str(request.url),
            "client_ip": request.client.host,
            "user_agent": request.headers.get("user-agent", ""),
            "status_code": response.status_code,
            "process_time": round(process_time, 4),
            "content_length": response.headers.get("content-length", 0)
        }

        # Log solo richieste sospette o errori
        if response.status_code >= 400 or process_time > 2.0:
            logger.info(f"Request log: {json.dumps(log_data)}")

class IPWhitelistMiddleware(BaseHTTPMiddleware):
    """Middleware per whitelist IP (opzionale per ambienti produzione)"""

    def __init__(self, app, allowed_ips: Optional[List[str]] = None):
        super().__init__(app)
        self.allowed_ips = allowed_ips or []

    async def dispatch(self, request: Request, call_next):
        if self.allowed_ips:
            client_ip = request.client.host

            # Permetti localhost in sviluppo
            if client_ip in ["127.0.0.1", "::1", "localhost"]:
                return await call_next(request)

            if client_ip not in self.allowed_ips:
                logger.warning(f"IP not whitelisted: {client_ip}")
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Access denied"}
                )

        return await call_next(request)

class RequestIdMiddleware(BaseHTTPMiddleware):
    """Middleware per tracciare richieste con ID unico"""

    async def dispatch(self, request: Request, call_next):
        # Genera ID unico per la richiesta
        request_id = self._generate_request_id(request)
        request.state.request_id = request_id

        response = await call_next(request)

        # Aggiungi request ID agli headers di risposta
        response.headers["X-Request-ID"] = request_id

        return response

    def _generate_request_id(self, request: Request) -> str:
        """Genera ID unico per la richiesta"""
        timestamp = str(time.time())
        client_info = f"{request.client.host}:{request.method}:{request.url.path}"
        hash_input = f"{timestamp}:{client_info}".encode()
        return hashlib.sha256(hash_input).hexdigest()[:16]

def setup_cors_middleware(app, allowed_origins: List[str] = None):
    """Configura CORS in modo sicuro"""
    if not allowed_origins:
        # Default per sviluppo
        allowed_origins = ["http://localhost:3000", "http://localhost:3001"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=[
            "Accept",
            "Accept-Language",
            "Content-Language",
            "Content-Type",
            "Authorization",
            "X-Request-ID"
        ],
        expose_headers=["X-Request-ID"],
        max_age=600  # Cache preflight per 10 minuti
    )

def setup_security_middleware(app):
    """Configura tutti i middleware di sicurezza"""
    # Ordine importante: più specifico prima
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestValidationMiddleware)

    # IP Whitelist solo se configurato
    allowed_ips = os.getenv("ALLOWED_IPS")
    if allowed_ips:
        ip_list = [ip.strip() for ip in allowed_ips.split(",")]
        app.add_middleware(IPWhitelistMiddleware, allowed_ips=ip_list)

    logger.info("Security middleware configurato")