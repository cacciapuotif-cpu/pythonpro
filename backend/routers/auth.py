"""
Router per autenticazione e autorizzazione
Gestisce login, refresh token e info utente corrente
"""

from fastapi import APIRouter, Depends, HTTPException, Form, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from datetime import timedelta
import logging

from auth import (
    authenticate_user, SecurityUtils, get_current_user, User,
    ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS,
    is_token_revoked, rate_limit, revoke_token, security,
)
from database import get_db
from services.audit_log import write_audit_log

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post("/login")
@rate_limit(max_requests=5, window_seconds=300)
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Login con credenziali → JWT access token e refresh token"""
    ip_address = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")

    user = authenticate_user(db, username, password, ip_address, user_agent)
    if not user:
        write_audit_log(
            db,
            user_id=None,
            azione="auth_login_failed",
            risorsa_tipo="auth",
            dati_dopo={"status": "failed"},
            ip_address=ip_address,
            esito="failure",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username o password non validi"
        )

    access_token = SecurityUtils.generate_token(
        data={"sub": user.username, "role": user.role},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    refresh_token = SecurityUtils.generate_token(
        data={"sub": user.username, "type": "refresh"},
        expires_delta=timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    )

    write_audit_log(
        db,
        user_id=user.id,
        azione="auth_login_success",
        risorsa_tipo="auth",
        risorsa_id=user.id,
        dati_dopo={"status": "success", "role": user.role},
        ip_address=ip_address,
        esito="success",
    )
    logger.info(f"Login riuscito per utente: {user.username}")
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "username": user.username,
        "role": user.role,
        "full_name": user.full_name
    }


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    """Restituisce info sull'utente corrente autenticato"""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "is_active": current_user.is_active,
        "last_login": current_user.last_login
    }


@router.post("/refresh")
@rate_limit(max_requests=20, window_seconds=300)
def refresh_token(
    request: Request,
    refresh_token: str = Form(...),
    db: Session = Depends(get_db)
):
    """Scambia un refresh token con un nuovo access token"""
    try:
        payload = SecurityUtils.verify_token(refresh_token)
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token non valido o scaduto"
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token non è un refresh token"
        )

    jti = payload.get("jti")
    if is_token_revoked(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token revocato"
        )

    username = payload.get("sub")
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utente non trovato o disattivato"
        )

    new_access_token = SecurityUtils.generate_token(
        data={"sub": user.username, "role": user.role},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    write_audit_log(
        db,
        user_id=user.id,
        azione="auth_token_refresh",
        risorsa_tipo="auth",
        risorsa_id=user.id,
        dati_dopo={"status": "success"},
        ip_address=request.client.host if request.client else None,
    )

    return {
        "access_token": new_access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }


@router.post("/logout")
def logout(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """Revoca il token corrente fino alla sua naturale scadenza."""
    payload = SecurityUtils.verify_token(credentials.credentials)
    revoke_token(payload.get("jti"), payload.get("exp"))
    username = payload.get("sub")
    user = db.query(User).filter(User.username == username).first() if username else None
    write_audit_log(
        db,
        user_id=user.id if user else None,
        azione="auth_logout",
        risorsa_tipo="auth",
        risorsa_id=user.id if user else None,
        dati_dopo={"status": "logged_out"},
        ip_address=request.client.host if request.client else None,
    )
    return {"status": "logged_out"}
