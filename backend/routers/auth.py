"""
Router per autenticazione e autorizzazione
Gestisce login, refresh token e info utente corrente
"""

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from datetime import timedelta
import hmac
import logging
import os
from pathlib import Path
import re
import uuid

from auth import (
    authenticate_user, SecurityUtils, get_current_user, User,
    ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS,
    is_token_revoked, rate_limit, revoke_token, security,
)
from database import get_db
from services.audit_log import write_audit_log
from services.password_reset import (
    PASSWORD_RESET_EXPIRE_MINUTES,
    PasswordResetTokenError,
    build_password_reset_url,
    issue_password_reset_token,
    replace_password_atomically,
    send_password_reset_email,
    validate_password_reset_token,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

AVATAR_DIR = Path(os.getenv("USER_AVATAR_DIR", "/app/uploads/user_avatars"))
MAX_AVATAR_BYTES = 2 * 1024 * 1024


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=100)
    first_name: str | None = Field(default=None, min_length=1, max_length=50)
    last_name: str | None = Field(default=None, min_length=1, max_length=50)
    phone: str | None = Field(default=None, max_length=30)
    email: EmailStr = Field(max_length=100)
    current_password: str | None = Field(default=None, min_length=1, max_length=128)

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        if len(normalized) < 2:
            raise ValueError("Il nome completo deve contenere almeno 2 caratteri")
        return normalized

    @field_validator("first_name", "last_name")
    @classmethod
    def normalize_name_part(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Nome e cognome non possono essere vuoti")
        return normalized

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str | None) -> str | None:
        normalized = " ".join(value.split()) if value else ""
        if not normalized:
            return None
        if not re.fullmatch(r"[0-9+(). /-]{5,30}", normalized):
            raise ValueError("Numero di telefono non valido")
        return normalized

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()

    @model_validator(mode="after")
    def validate_name(self):
        has_first = self.first_name is not None
        has_last = self.last_name is not None
        if has_first != has_last:
            raise ValueError("Nome e cognome devono essere indicati insieme")
        if not has_first and self.full_name is None:
            raise ValueError("Indica nome e cognome")
        return self


def _split_full_name(value: str | None) -> tuple[str, str]:
    parts = (value or "").strip().split(maxsplit=1)
    return (
        parts[0] if parts else "",
        parts[1] if len(parts) > 1 else "",
    )


def _serialize_user_profile(user: User) -> dict:
    fallback_first_name, fallback_last_name = _split_full_name(user.full_name)
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "first_name": user.first_name or fallback_first_name,
        "last_name": user.last_name or fallback_last_name,
        "phone": user.phone,
        "has_avatar": bool(user.avatar_path),
        "role": user.role,
        "is_active": user.is_active,
        "last_login": user.last_login,
    }


def _avatar_format(content: bytes) -> tuple[str, str] | None:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png", "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return ".jpg", "image/jpeg"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return ".webp", "image/webp"
    return None


def _safe_avatar_path(raw_path: str | None) -> Path | None:
    if not raw_path:
        return None
    root = AVATAR_DIR.resolve()
    candidate = Path(raw_path).resolve()
    if candidate.parent != root:
        return None
    return candidate


def _validate_new_password(new_password: str, confirm_password: str) -> None:
    if new_password != confirm_password:
        raise ValueError("La conferma non coincide con la nuova password")
    if len(new_password.encode("utf-8")) > 72:
        raise ValueError("La nuova password non può superare 72 byte")
    requirements = (
        (r"[a-z]", "una lettera minuscola"),
        (r"[A-Z]", "una lettera maiuscola"),
        (r"\d", "una cifra"),
        (r"[^A-Za-z0-9]", "un carattere speciale"),
    )
    missing = [label for pattern, label in requirements if not re.search(pattern, new_password)]
    if missing:
        raise ValueError(f"La nuova password deve contenere {', '.join(missing)}")


class PasswordFields(BaseModel):
    new_password: str = Field(min_length=12, max_length=128)
    confirm_password: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_password_fields(self):
        _validate_new_password(self.new_password, self.confirm_password)
        return self


class PasswordChange(PasswordFields):
    current_password: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_password_change(self):
        if self.current_password == self.new_password:
            raise ValueError("La nuova password deve essere diversa da quella attuale")
        return self


class ForgotPasswordRequest(BaseModel):
    email: EmailStr = Field(max_length=100)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class PasswordResetConfirm(PasswordFields):
    token: str = Field(min_length=20, max_length=4096)


def _token_data(user: User, **extra) -> dict:
    return {
        "sub": user.username,
        "credential_marker": SecurityUtils.credential_marker(user.hashed_password),
        **extra,
    }


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
        data=_token_data(user, type="access", role=user.role),
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    refresh_token = SecurityUtils.generate_token(
        data=_token_data(user, type="refresh"),
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
    return _serialize_user_profile(current_user)


@router.patch("/me")
def update_me(
    payload: ProfileUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Aggiorna i dati personali del solo account autenticato."""
    requested_updates = {}
    if payload.first_name is not None and payload.last_name is not None:
        requested_updates.update({
            "first_name": payload.first_name,
            "last_name": payload.last_name,
            "full_name": f"{payload.first_name} {payload.last_name}".strip(),
        })
    elif payload.full_name is not None:
        requested_updates["full_name"] = payload.full_name
    if "phone" in payload.model_fields_set:
        requested_updates["phone"] = payload.phone
    requested_updates["email"] = payload.email

    changed_fields = [
        field
        for field, new_value in requested_updates.items()
        if getattr(current_user, field) != new_value
    ]
    if "email" in changed_fields:
        if not payload.current_password or not SecurityUtils.verify_password(
            payload.current_password,
            current_user.hashed_password,
        ):
            write_audit_log(
                db,
                user_id=current_user.id,
                azione="auth_profile_update_failed",
                risorsa_tipo="user_profile",
                risorsa_id=current_user.id,
                dati_dopo={"reason": "current_password_required_for_email_change"},
                ip_address=request.client.host if request.client else None,
                esito="failure",
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inserisci la password attuale per modificare l'email",
            )

        duplicate = db.query(User.id).filter(
            func.lower(User.email) == payload.email.lower(),
            User.id != current_user.id,
        ).first()
        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Questa email è già associata a un altro account",
            )

    if changed_fields:
        for field, new_value in requested_updates.items():
            setattr(current_user, field, new_value)
        write_audit_log(
            db,
            user_id=current_user.id,
            azione="auth_profile_updated",
            risorsa_tipo="user_profile",
            risorsa_id=current_user.id,
            dati_dopo={"changed_fields": changed_fields},
            ip_address=request.client.host if request.client else None,
        )
        try:
            db.commit()
            db.refresh(current_user)
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Questa email è già associata a un altro account",
            )

    return _serialize_user_profile(current_user)


@router.post("/me/avatar")
async def upload_my_avatar(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Carica una foto profilo raster, massimo 2 MB."""
    content = await file.read(MAX_AVATAR_BYTES + 1)
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Il file della foto è vuoto",
        )
    if len(content) > MAX_AVATAR_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="La foto non può superare 2 MB",
        )
    detected = _avatar_format(content)
    if detected is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato foto non valido. Usa JPG, PNG o WebP",
        )

    extension, _media_type = detected
    AVATAR_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    final_path = AVATAR_DIR / f"user-{current_user.id}-{uuid.uuid4().hex}{extension}"
    temporary_path = AVATAR_DIR / f".user-{current_user.id}-{uuid.uuid4().hex}.tmp"
    old_path = _safe_avatar_path(current_user.avatar_path)
    try:
        temporary_path.write_bytes(content)
        os.replace(temporary_path, final_path)
        current_user.avatar_path = str(final_path)
        write_audit_log(
            db,
            user_id=current_user.id,
            azione="auth_avatar_updated",
            risorsa_tipo="user_profile",
            risorsa_id=current_user.id,
            dati_dopo={"changed_fields": ["avatar"]},
            ip_address=request.client.host if request.client else None,
        )
        db.commit()
        db.refresh(current_user)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        final_path.unlink(missing_ok=True)
        db.rollback()
        raise

    if old_path and old_path != final_path:
        old_path.unlink(missing_ok=True)
    return _serialize_user_profile(current_user)


@router.get("/me/avatar")
def get_my_avatar(current_user: User = Depends(get_current_user)):
    avatar_path = _safe_avatar_path(current_user.avatar_path)
    if not avatar_path or not avatar_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Foto profilo non presente",
        )
    detected = _avatar_format(avatar_path.read_bytes()[:16])
    if detected is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Foto profilo non disponibile",
        )
    return FileResponse(
        path=avatar_path,
        media_type=detected[1],
        filename=f"foto-profilo{detected[0]}",
    )


@router.delete("/me/avatar", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_avatar(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    avatar_path = _safe_avatar_path(current_user.avatar_path)
    current_user.avatar_path = None
    write_audit_log(
        db,
        user_id=current_user.id,
        azione="auth_avatar_deleted",
        risorsa_tipo="user_profile",
        risorsa_id=current_user.id,
        dati_dopo={"changed_fields": ["avatar"]},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    if avatar_path:
        avatar_path.unlink(missing_ok=True)


@router.post("/change-password")
@rate_limit(max_requests=5, window_seconds=300)
def change_password(
    payload: PasswordChange,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cambia password e rende inutilizzabili tutti i JWT emessi prima del cambio."""
    ip_address = request.client.host if request.client else None
    if not SecurityUtils.verify_password(payload.current_password, current_user.hashed_password):
        write_audit_log(
            db,
            user_id=current_user.id,
            azione="auth_password_change_failed",
            risorsa_tipo="user_profile",
            risorsa_id=current_user.id,
            dati_dopo={"reason": "current_password_mismatch"},
            ip_address=ip_address,
            esito="failure",
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La password attuale non è corretta",
        )

    current_user.hashed_password = SecurityUtils.hash_password(payload.new_password)
    write_audit_log(
        db,
        user_id=current_user.id,
        azione="auth_password_changed",
        risorsa_tipo="user_profile",
        risorsa_id=current_user.id,
        dati_dopo={"all_previous_tokens_invalidated": True},
        ip_address=ip_address,
    )
    db.commit()
    return {
        "status": "password_changed",
        "message": "Password aggiornata. Effettua di nuovo l'accesso.",
    }


@router.post("/forgot-password")
@rate_limit(max_requests=5, window_seconds=900)
def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Invia un link di recupero senza rivelare se l'account esiste."""
    generic_message = (
        "Se l'indirizzo è associato a un account attivo, riceverai un link "
        f"valido per {PASSWORD_RESET_EXPIRE_MINUTES} minuti."
    )
    user = db.query(User).filter(func.lower(User.email) == payload.email.lower()).first()
    delivery_queued = False

    if user and user.is_active:
        try:
            reset_token = issue_password_reset_token(user)
            reset_url = build_password_reset_url(reset_token)
            background_tasks.add_task(
                send_password_reset_email,
                recipient=user.email,
                full_name=user.full_name or user.username,
                reset_url=reset_url,
            )
            delivery_queued = True
        except Exception:
            logger.exception("Impossibile predisporre il recupero password")

    write_audit_log(
        db,
        user_id=user.id if user else None,
        azione="auth_password_reset_requested",
        risorsa_tipo="auth",
        risorsa_id=user.id if user else None,
        dati_dopo={"delivery_queued": delivery_queued},
        ip_address=request.client.host if request.client else None,
        esito="success" if delivery_queued else "not_queued",
    )
    db.commit()
    return {"status": "accepted", "message": generic_message}


@router.post("/reset-password")
@rate_limit(max_requests=5, window_seconds=900)
def reset_password(
    payload: PasswordResetConfirm,
    request: Request,
    db: Session = Depends(get_db),
):
    """Consuma il link una volta e invalida tutte le sessioni precedenti."""
    try:
        token_payload, user = validate_password_reset_token(payload.token, db)
    except PasswordResetTokenError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Il link non è valido, è scaduto o è già stato utilizzato",
        )

    if not replace_password_atomically(
        db=db,
        user=user,
        new_password=payload.new_password,
    ):
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Il link non è valido, è scaduto o è già stato utilizzato",
        )

    write_audit_log(
        db,
        user_id=user.id,
        azione="auth_password_reset_completed",
        risorsa_tipo="user_profile",
        risorsa_id=user.id,
        dati_dopo={"all_previous_tokens_invalidated": True},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    revoke_token(token_payload.get("jti"), token_payload.get("exp"))
    return {
        "status": "password_reset",
        "message": "Password reimpostata. Ora puoi accedere con la nuova password.",
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

    if not hmac.compare_digest(
        str(payload.get("credential_marker") or ""),
        SecurityUtils.credential_marker(user.hashed_password),
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenziali aggiornate: effettua di nuovo l'accesso",
        )

    new_access_token = SecurityUtils.generate_token(
        data=_token_data(user, type="access", role=user.role),
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
