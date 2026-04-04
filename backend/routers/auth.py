"""
Router per autenticazione e autorizzazione
Gestisce login, refresh token e info utente corrente
"""

from fastapi import APIRouter, Depends, HTTPException, Form, Request, status
from sqlalchemy.orm import Session
from datetime import timedelta
import logging

from auth import (
    authenticate_user, SecurityUtils, get_current_user, User,
    ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS
)
from database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post("/login")
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
def refresh_token(
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

    return {
        "access_token": new_access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }
