"""
Sistema di autenticazione e autorizzazione avanzato
Implementa JWT, RBAC, rate limiting e security headers
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from functools import wraps
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
from datetime import timezone

logger = logging.getLogger(__name__)

# Configurazione JWT
SECRET_KEY = os.getenv("SECRET_KEY", "your-super-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Redis per session management e rate limiting
try:
    redis_client = redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        db=0,
        decode_responses=True
    )
except:
    redis_client = None
    logger.warning("Redis non disponibile - usando fallback in memoria")

# Fallback in-memory per rate limiting se Redis non disponibile
_memory_store = {}

class UserRole(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    USER = "user"
    READONLY = "readonly"

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

# Mapping ruoli -> permessi
ROLE_PERMISSIONS: Dict[UserRole, List[Permission]] = {
    UserRole.ADMIN: [p for p in Permission],  # Tutti i permessi
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

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(100), nullable=False)
    full_name = Column(String(100))
    role = Column(String(20), default=UserRole.USER, index=True)

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
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=15)

        to_encode.update({"exp": expire, "iat": datetime.utcnow()})
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
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permessi amministratore richiesti"
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

            user_permissions = ROLE_PERMISSIONS.get(UserRole(current_user.role), [])
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
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Estrai l'indirizzo IP dalla richiesta
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break

            if request:
                client_ip = request.client.host
                key = f"rate_limit:{client_ip}"

                if not limiter.is_allowed(key):
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Troppe richieste. Riprova più tardi."
                    )

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
    role: UserRole = UserRole.USER
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
    if user.locked_until and user.locked_until > datetime.utcnow():
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
            user.locked_until = datetime.utcnow() + timedelta(hours=1)
            log_security_event(db, username, ip_address, user_agent, False, "Account locked after failed attempts")
        else:
            log_security_event(db, username, ip_address, user_agent, False, "Invalid password")

        db.commit()
        return None

    # Login riuscito
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = datetime.utcnow()
    db.commit()

    log_security_event(db, username, ip_address, user_agent, True)
    return user