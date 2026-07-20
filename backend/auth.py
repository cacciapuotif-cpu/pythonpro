"""
Sistema di autenticazione e autorizzazione avanzato
Implementa JWT, RBAC, rate limiting e security headers
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any, Iterable
from functools import wraps
import inspect
from jose import jwt  # python-jose library
import bcrypt
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, func
from sqlalchemy.orm import relationship
from database import Base, get_db
import os
import logging
from enum import Enum
import redis
import json
import uuid

logger = logging.getLogger(__name__)

# Configurazione JWT
_secret_key = os.getenv("SECRET_KEY") or os.getenv("JWT_SECRET_KEY")
_insecure_defaults = {"your-super-secret-key-change-in-production", "changeme_secret_key_super_sicura", ""}
if not _secret_key or _secret_key in _insecure_defaults:
    raise RuntimeError(
        "SECRET_KEY non configurata o usa un valore di default insicuro. "
        "Imposta SECRET_KEY nel file .env con una stringa casuale di almeno 32 caratteri."
    )
SECRET_KEY = _secret_key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Redis per session management e rate limiting
try:
    redis_client = redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        password=os.getenv("REDIS_PASSWORD") or None,
        db=0,
        decode_responses=True
    )
    redis_client.ping()  # Verifica connessione subito
except redis.RedisError as _redis_err:
    redis_client = None
    logger.warning("Redis non disponibile (%s) - usando fallback in memoria", _redis_err)

# Fallback in-memory per rate limiting se Redis non disponibile
_memory_store = {}
_memory_token_blacklist = {}

def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _current_timestamp() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def is_token_revoked(jti: Optional[str]) -> bool:
    if not jti:
        return False
    key = f"blacklist:jti:{jti}"
    if redis_client:
        try:
            return bool(redis_client.exists(key))
        except redis.RedisError:
            logger.warning("Redis non disponibile durante controllo blacklist token")
    expires_at = _memory_token_blacklist.get(jti)
    if expires_at is None:
        return False
    if expires_at <= _current_timestamp():
        _memory_token_blacklist.pop(jti, None)
        return False
    return True


def revoke_token(jti: Optional[str], exp: Optional[int]) -> None:
    if not jti or not exp:
        return
    ttl = int(exp) - _current_timestamp()
    if ttl <= 0:
        return
    key = f"blacklist:jti:{jti}"
    if redis_client:
        try:
            redis_client.setex(key, ttl, "revoked")
            return
        except redis.RedisError:
            logger.warning("Redis non disponibile durante revoca token; uso fallback memoria")
    _memory_token_blacklist[jti] = _current_timestamp() + ttl


class UserRole(str, Enum):
    ADMIN = "admin"
    OPERATORE = "operatore"
    CONSULTAZIONE = "consultazione"
    # Legacy values kept so old tokens/users can be normalized during rollout.
    MANAGER = "manager"
    USER = "user"
    READONLY = "readonly"
    DPO = "dpo"


LEGACY_ROLE_MAP = {
    UserRole.MANAGER.value: UserRole.OPERATORE.value,
    UserRole.USER.value: UserRole.OPERATORE.value,
    UserRole.READONLY.value: UserRole.CONSULTAZIONE.value,
    UserRole.DPO.value: UserRole.ADMIN.value,
}
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
RBAC_ENFORCE = os.getenv("RBAC_ENFORCE", "false").lower() == "true"
RBAC_LOG_ONLY_EVENTS: list[dict[str, Any]] = []

ADMIN_ONLY_PREFIXES = (
    "/api/v1/admin",
    "/api/v1/gdpr",
)
# Matrice A5a (GATE confermato 2026-07-15): GET consultabili da tutti i ruoli,
# review/approve/send/inbox = OPERATORE+, run manuale e strumenti tecnici = ADMIN.
AGENT_PLATFORM_PREFIXES = (
    "/api/v1/agents",
    "/api/v1/agent-suggestions",
    "/api/v1/email-inbox",
)
AGENT_PLATFORM_ADMIN_ONLY_PATHS = (
    "/api/v1/email-inbox/trigger-poll",
    "/api/v1/email-inbox/imap/test",
)
OPERATIONAL_PREFIXES = (
    "/api/v1/collaborators",
    "/api/v1/projects",
    "/api/v1/attendances",
    "/api/v1/assignments",
    "/api/v1/entities",
    "/api/v1/project-assignments",
    "/api/v1/contracts",
    "/api/v1/reporting",
    "/api/v1/agenzie",
    "/api/v1/consulenti",
    "/api/v1/aziende-clienti",
    "/api/v1/allievi",
    "/api/v1/catalogo",
    "/api/v1/listini",
    "/api/v1/preventivi",
    "/api/v1/ordini",
    "/api/v1/piani-finanziari",
    "/api/v1/documenti-richiesti",
    "/api/v1/avvisi",
    "/api/v1/attivita",
    "/api/v1/cockpit",
)
OPERATIONAL_EXACT_PREFIXES = (
    "/collaborators-with-projects",
    "/collaborators/",
)
ADMIN_ONLY_PATTERNS = (
    "/download-documento",
    "/download-curriculum",
    "/api/v1/reporting/timesheet/export",
)
OPERATORE_ALLOWED_SENSITIVE_GET_PATHS = (
    "/api/v1/reporting/timesheet",
)
OPERATORE_ALLOWED_SENSITIVE_GET_SUFFIXES = (
    "/export-excel",
    # NEW-022: il download del contratto firmato (PII: CF, indirizzo,
    # compenso) non deve essere raggiungibile dal ruolo consultazione, a
    # differenza delle GET generiche su /api/v1/assignments.
    "/contract",
    # NEW-024: il PDF del timesheet (GET /api/v1/assignments/{id}/timesheet)
    # contiene nome collaboratore, ore e righe presenze — dato lavorativo
    # individuale, matrice: solo admin+operatore. Nessun altro endpoint GET
    # termina con questo suffisso oltre a /api/v1/reporting/timesheet, che
    # ha gia' lo stesso insieme di ruoli via
    # OPERATORE_ALLOWED_SENSITIVE_GET_PATHS.
    "/timesheet",
)


def normalize_role(role: str | UserRole | None) -> str:
    if isinstance(role, UserRole):
        role = role.value
    if not role:
        return UserRole.CONSULTAZIONE.value
    normalized = LEGACY_ROLE_MAP.get(str(role), str(role))
    valid_roles = {item.value for item in UserRole}
    return normalized if normalized in valid_roles else UserRole.CONSULTAZIONE.value


def _path_matches(path: str, prefixes: Iterable[str]) -> bool:
    return any(path == prefix or path.startswith(prefix + "/") for prefix in prefixes)


def _path_starts_with_any(path: str, prefixes: Iterable[str]) -> bool:
    return any(path.startswith(prefix) for prefix in prefixes)


def _agent_platform_allowed_roles(method: str, path: str) -> set[str]:
    if method in SAFE_METHODS:
        # NEW-025: il download dell'allegato email
        # (GET /api/v1/email-inbox/items/{id}/attachment) serve un file dal
        # contenuto arbitrario (documenti identita', CV, contratti in arrivo
        # via email). La regola A5a "GET consultabili da tutti i ruoli" copre
        # i metadati inbox, non i file binari: stessa classe di NEW-022.
        if path.endswith("/attachment"):
            return {UserRole.ADMIN.value, UserRole.OPERATORE.value}
        return {UserRole.ADMIN.value, UserRole.OPERATORE.value, UserRole.CONSULTAZIONE.value}
    # Run manuale agenti: /api/v1/agents/run e /api/v1/agents/<tipo>/run
    # (copre anche gli endpoint sprint7 contract-generator/certification).
    if path == "/api/v1/agents/run" or (path.startswith("/api/v1/agents/") and path.endswith("/run")):
        return {UserRole.ADMIN.value}
    if path in AGENT_PLATFORM_ADMIN_ONLY_PATHS:
        return {UserRole.ADMIN.value}
    # Review/approve/reject/send/apply-fix e azioni inbox: operatori.
    return {UserRole.ADMIN.value, UserRole.OPERATORE.value}


def rbac_allowed_roles(method: str, path: str) -> set[str]:
    method = method.upper()
    if _path_matches(path, ADMIN_ONLY_PREFIXES):
        return {UserRole.ADMIN.value}
    if _path_matches(path, AGENT_PLATFORM_PREFIXES):
        return _agent_platform_allowed_roles(method, path)
    if method in SAFE_METHODS and (
        path in OPERATORE_ALLOWED_SENSITIVE_GET_PATHS
        or any(path.endswith(suffix) for suffix in OPERATORE_ALLOWED_SENSITIVE_GET_SUFFIXES)
    ):
        return {UserRole.ADMIN.value, UserRole.OPERATORE.value}
    if any(pattern in path for pattern in ADMIN_ONLY_PATTERNS):
        return {UserRole.ADMIN.value}
    if _path_matches(path, OPERATIONAL_PREFIXES) or _path_starts_with_any(path, OPERATIONAL_EXACT_PREFIXES):
        if method in SAFE_METHODS:
            return {UserRole.ADMIN.value, UserRole.OPERATORE.value, UserRole.CONSULTAZIONE.value}
        return {UserRole.ADMIN.value, UserRole.OPERATORE.value}
    return {UserRole.ADMIN.value}


def rbac_decision_for(method: str, path: str, role: str | UserRole | None) -> dict[str, Any]:
    normalized_role = normalize_role(role)
    allowed_roles = rbac_allowed_roles(method, path)
    allowed = normalized_role in allowed_roles
    return {
        "method": method.upper(),
        "path": path,
        "role": normalized_role,
        "allowed_roles": sorted(allowed_roles),
        "allowed": allowed,
        "would_status": 200 if allowed else 403,
    }


class Permission(str, Enum):
    READ_COLLABORATORS = "read:collaborators"
    WRITE_COLLABORATORS = "write:collaborators"
    DELETE_COLLABORATORS = "delete:collaborators"
    READ_PROJECTS = "read:projects"
    WRITE_PROJECTS = "write:projects"
    DELETE_PROJECTS = "delete:projects"
    READ_ATTENDANCES = "read:attendances"
    WRITE_ATTENDANCES = "write:attendances"
    DELETE_ATTENDANCES = "delete:attendances"
    READ_ASSIGNMENTS = "read:assignments"
    WRITE_ASSIGNMENTS = "write:assignments"
    DELETE_ASSIGNMENTS = "delete:assignments"
    VIEW_DASHBOARD = "view:dashboard"
    MANAGE_USERS = "manage:users"
    MANAGE_GDPR = "manage:gdpr"

# Mapping ruoli -> permessi
ROLE_PERMISSIONS: Dict[UserRole, List[Permission]] = {
    UserRole.ADMIN: [p for p in Permission],  # Tutti i permessi
    UserRole.OPERATORE: [
        Permission.READ_COLLABORATORS, Permission.WRITE_COLLABORATORS, Permission.DELETE_COLLABORATORS,
        Permission.READ_PROJECTS, Permission.WRITE_PROJECTS, Permission.DELETE_PROJECTS,
        Permission.READ_ATTENDANCES, Permission.WRITE_ATTENDANCES, Permission.DELETE_ATTENDANCES,
        Permission.READ_ASSIGNMENTS, Permission.WRITE_ASSIGNMENTS, Permission.DELETE_ASSIGNMENTS,
        Permission.VIEW_DASHBOARD,
    ],
    UserRole.CONSULTAZIONE: [
        Permission.READ_COLLABORATORS, Permission.READ_PROJECTS,
        Permission.READ_ATTENDANCES, Permission.READ_ASSIGNMENTS,
        Permission.VIEW_DASHBOARD,
    ],
    UserRole.DPO: [
        Permission.READ_COLLABORATORS, Permission.READ_PROJECTS, Permission.MANAGE_GDPR
    ],
    UserRole.MANAGER: [
        Permission.READ_COLLABORATORS, Permission.WRITE_COLLABORATORS,
        Permission.READ_PROJECTS, Permission.WRITE_PROJECTS,
        Permission.READ_ATTENDANCES, Permission.WRITE_ATTENDANCES,
        Permission.READ_ASSIGNMENTS, Permission.WRITE_ASSIGNMENTS,
        Permission.VIEW_DASHBOARD
    ],
    UserRole.USER: [
        Permission.READ_COLLABORATORS, Permission.READ_PROJECTS,
        Permission.READ_ATTENDANCES, Permission.WRITE_ATTENDANCES,
        Permission.READ_ASSIGNMENTS, Permission.VIEW_DASHBOARD
    ],
    UserRole.READONLY: [
        Permission.READ_COLLABORATORS, Permission.READ_PROJECTS,
        Permission.READ_ATTENDANCES, Permission.READ_ASSIGNMENTS,
        Permission.VIEW_DASHBOARD
    ]
}

class User(Base):
    """Modello utente per autenticazione"""
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(100), nullable=False)
    full_name = Column(String(100))
    role = Column(String(20), default=UserRole.CONSULTAZIONE.value, nullable=False, server_default=UserRole.CONSULTAZIONE.value, index=True)

    is_active = Column(Boolean, default=True, index=True)
    is_verified = Column(Boolean, default=False)
    last_login = Column(DateTime)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relazione con collaboratore (se applicabile)
    collaborator_id = Column(Integer, ForeignKey("collaborators.id"), nullable=True)
    collaborator = relationship("Collaborator")

class LoginAttempt(Base):
    """Log dei tentativi di login per sicurezza"""
    __tablename__ = "login_attempts"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), index=True)
    ip_address = Column(String(45))  # IPv6 support
    user_agent = Column(Text)
    success = Column(Boolean, index=True)
    failure_reason = Column(String(100))
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)

class SecurityUtils:
    """Utilità per operazioni di sicurezza"""

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password con bcrypt"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Verifica password"""
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

    @staticmethod
    def generate_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Genera JWT token"""
        to_encode = data.copy()
        now = datetime.now(timezone.utc)
        if expires_delta:
            expire = now + expires_delta
        else:
            expire = now + timedelta(minutes=15)

        to_encode.update({"exp": expire, "iat": now, "jti": str(uuid.uuid4())})
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    @staticmethod
    def verify_token(token: str) -> Dict[str, Any]:
        """Verifica JWT token"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token scaduto"
            )
        except jwt.JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token non valido"
            )

class RateLimiter:
    """Rate limiting per prevenire abusi"""

    def __init__(self, max_requests: int = 100, window_seconds: int = 3600):
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    def is_allowed(self, key: str) -> bool:
        """Controlla se la richiesta è permessa"""
        now = datetime.now().timestamp()
        window_start = now - self.window_seconds

        if redis_client:
            # Usa Redis per distributed rate limiting
            pipe = redis_client.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            pipe.zadd(key, {str(now): now})
            pipe.expire(key, self.window_seconds)
            results = pipe.execute()

            current_requests = results[1]
            return current_requests < self.max_requests
        else:
            # Fallback in-memory
            if key not in _memory_store:
                _memory_store[key] = []

            # Pulisci richieste vecchie
            _memory_store[key] = [
                timestamp for timestamp in _memory_store[key]
                if timestamp > window_start
            ]

            # Aggiungi richiesta corrente
            _memory_store[key].append(now)

            return len(_memory_store[key]) <= self.max_requests

# Security dependencies
security = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Dependency per ottenere l'utente corrente dal token"""
    try:
        payload = SecurityUtils.verify_token(credentials.credentials)
        jti: str = payload.get("jti")
        if is_token_revoked(jti):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token revocato"
            )
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token non valido"
            )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token non valido"
        )

    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utente non trovato"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utente disattivato"
        )

    return user

def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """Dependency per verificare che l'utente sia admin"""
    if normalize_role(current_user.role) != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permessi amministratore richiesti"
        )
    return current_user

async def require_role(request: Request, current_user: User = Depends(get_current_user)) -> User:
    """RBAC minimo. In fase (a) log-only: registra i 403 potenziali senza bloccare."""
    decision = rbac_decision_for(request.method, request.url.path, current_user.role)
    if not decision["allowed"]:
        event = {
            "user_id": current_user.id,
            "username": current_user.username,
            **decision,
            "enforced": RBAC_ENFORCE,
        }
        RBAC_LOG_ONLY_EVENTS.append(event)
        logger.warning(
            "RBAC %s: user_id=%s username=%s role=%s method=%s path=%s allowed_roles=%s",
            "DENY" if RBAC_ENFORCE else "WOULD_DENY",
            current_user.id,
            current_user.username,
            decision["role"],
            decision["method"],
            decision["path"],
            ",".join(decision["allowed_roles"]),
        )
        if RBAC_ENFORCE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permessi insufficienti",
            )
    return current_user

def require_permission(permission: Permission):
    """Decorator per richiedere un permesso specifico"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Estrai current_user dai kwargs o args
            current_user = None
            for arg in args:
                if isinstance(arg, User):
                    current_user = arg
                    break
            if not current_user:
                current_user = kwargs.get('current_user')

            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Autenticazione richiesta"
                )

            user_permissions = ROLE_PERMISSIONS.get(UserRole(normalize_role(current_user.role)), [])
            if permission not in user_permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permesso richiesto: {permission.value}"
                )

            return func(*args, **kwargs)
        return wrapper
    return decorator

def rate_limit(max_requests: int = 100, window_seconds: int = 3600):
    """Decorator per rate limiting"""
    limiter = RateLimiter(max_requests, window_seconds)

    def decorator(func):
        def check_request(args, kwargs) -> None:
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            if request is None:
                request = kwargs.get("request")

            if request:
                client_ip = request.client.host if request.client else "unknown"
                path = request.url.path if request.url else "unknown"
                key = f"rate_limit:{path}:{client_ip}"

                if not limiter.is_allowed(key):
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Troppe richieste. Riprova più tardi."
                    )

        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                check_request(args, kwargs)
                return await func(*args, **kwargs)

            return async_wrapper

        @wraps(func)
        def wrapper(*args, **kwargs):
            check_request(args, kwargs)
            return func(*args, **kwargs)

        return wrapper
    return decorator

def log_security_event(
    db: Session,
    username: str,
    ip_address: str,
    user_agent: str,
    success: bool,
    failure_reason: Optional[str] = None
):
    """Log eventi di sicurezza"""
    try:
        attempt = LoginAttempt(
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            failure_reason=failure_reason
        )
        db.add(attempt)
        db.commit()
    except Exception as e:
        logger.error(f"Errore nel logging di sicurezza: {e}")

def create_user(
    db: Session,
    username: str,
    email: str,
    password: str,
    full_name: str,
    role: UserRole = UserRole.CONSULTAZIONE
) -> User:
    """Crea nuovo utente con password hashata"""
    # Verifica se username o email esistono già
    existing = db.query(User).filter(
        (User.username == username) | (User.email == email)
    ).first()

    if existing:
        raise ValueError("Username o email già esistenti")

    hashed_password = SecurityUtils.hash_password(password)

    user = User(
        username=username,
        email=email,
        hashed_password=hashed_password,
        full_name=full_name,
        role=role.value
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info(f"Creato nuovo utente: {username}")
    return user

def authenticate_user(
    db: Session,
    username: str,
    password: str,
    ip_address: str,
    user_agent: str
) -> Optional[User]:
    """Autentica utente con controllo tentativi falliti"""
    user = db.query(User).filter(User.username == username).first()

    if not user:
        log_security_event(db, username, ip_address, user_agent, False, "User not found")
        return None

    # Controllo account bloccato
    if user.locked_until and user.locked_until > _utcnow_naive():
        log_security_event(db, username, ip_address, user_agent, False, "Account locked")
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Account bloccato fino a {user.locked_until}"
        )

    # Verifica password
    if not SecurityUtils.verify_password(password, user.hashed_password):
        # Incrementa tentativi falliti
        user.failed_login_attempts += 1

        # Blocca account dopo 5 tentativi
        if user.failed_login_attempts >= 5:
            user.locked_until = _utcnow_naive() + timedelta(hours=1)
            log_security_event(db, username, ip_address, user_agent, False, "Account locked after failed attempts")
        else:
            log_security_event(db, username, ip_address, user_agent, False, "Invalid password")

        db.commit()
        return None

    # Login riuscito
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = _utcnow_naive()
    db.commit()

    log_security_event(db, username, ip_address, user_agent, True)
    return user
