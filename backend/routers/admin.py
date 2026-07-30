"""
Router per funzionalità amministrazione
Gestisce backup, monitoring, security logs, performance e cache
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
import logging
import re
import secrets
import unicodedata

import crud
from database import get_db
from auth import (
    User, UserRole, Permission, require_permission,
    get_current_user, get_admin_user, LoginAttempt, SecurityUtils,
)
from error_handler import error_monitor
from services.audit_log import write_audit_log
from services.password_reset import (
    build_password_reset_url,
    issue_password_reset_token,
    send_password_reset_email,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


def _serialize_dashboard_metrics(metrics):
    if not metrics:
        return {}
    if hasattr(metrics, "_mapping"):
        return dict(metrics._mapping)
    if hasattr(metrics, "_asdict"):
        return metrics._asdict()
    return dict(metrics)


def _serialize_performance_analysis(performance):
    overloaded = []
    for row in performance.get("overloaded_collaborators", []):
        if hasattr(row, "_mapping"):
            overloaded.append(dict(row._mapping))
        elif hasattr(row, "_asdict"):
            overloaded.append(row._asdict())
        else:
            overloaded.append({
                "id": row[0],
                "first_name": row[1],
                "last_name": row[2],
                "total_assigned_hours": row[3],
                "total_completed_hours": row[4],
            })

    return {
        "overloaded_collaborators": overloaded,
        "timestamp": performance.get("timestamp"),
    }

# Verifica disponibilità sistemi avanzati
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


# ========================================
# METRICS E DASHBOARD
# ========================================

@router.get("/metrics")
@require_permission(Permission.VIEW_DASHBOARD)
def get_system_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Metriche di sistema per dashboard admin"""
    try:
        metrics = crud.get_dashboard_metrics(db)
        performance = crud.get_performance_bottlenecks(db)

        return {
            "dashboard_metrics": _serialize_dashboard_metrics(metrics),
            "performance_analysis": _serialize_performance_analysis(performance),
            "timestamp": datetime.now()
        }
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Errore nel recupero metriche"
        )


@router.get("/error-stats")
@require_permission(Permission.VIEW_DASHBOARD)
def get_error_statistics(
    current_user: User = Depends(get_current_user)
):
    """Ottieni statistiche errori del sistema"""
    return error_monitor.get_error_stats()


# ========================================
# SECURITY LOGS
# ========================================

@router.get("/security-logs")
@require_permission(Permission.MANAGE_USERS)
def get_security_logs(
    skip: int = 0,
    limit: int = 100,
    success_only: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Visualizza log di sicurezza (solo admin)"""
    query = db.query(LoginAttempt)

    if success_only is not None:
        query = query.filter(LoginAttempt.success == success_only)

    logs = query.order_by(LoginAttempt.timestamp.desc()).offset(skip).limit(limit).all()

    return {
        "logs": [
            {
                "id": log.id,
                "username": log.username,
                "ip_address": log.ip_address,
                "success": log.success,
                "failure_reason": log.failure_reason,
                "timestamp": log.timestamp
            }
            for log in logs
        ],
        "total": query.count()
    }


# ========================================
# BACKUP MANAGEMENT
# ========================================

@router.get("/backup")
@require_permission(Permission.MANAGE_USERS)
def create_manual_backup(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """Crea backup manuale del database"""
    if not BACKUP_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sistema di backup non disponibile"
        )

    try:
        backup_mgr = get_backup_manager()
        backup_path = backup_mgr.create_backup("manual")

        if backup_path:
            return {
                "message": "Backup creato con successo",
                "backup_path": backup_path,
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Errore nella creazione del backup"
            )
    except Exception as e:
        logger.error(f"Errore backup manuale: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/backups")
@require_permission(Permission.MANAGE_USERS)
def list_backups(
    current_user: User = Depends(get_admin_user)
):
    """Lista tutti i backup disponibili"""
    if not BACKUP_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sistema di backup non disponibile"
        )

    backup_mgr = get_backup_manager()
    return {
        "backups": backup_mgr.list_backups(),
        "statistics": backup_mgr.get_backup_statistics()
    }


@router.post("/restore/{backup_filename}")
@require_permission(Permission.MANAGE_USERS)
def restore_backup(
    backup_filename: str,
    current_user: User = Depends(get_admin_user)
):
    """Ripristina un backup (ATTENZIONE: operazione irreversibile)"""
    if not BACKUP_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sistema di backup non disponibile"
        )

    try:
        backup_mgr = get_backup_manager()
        backup_path = backup_mgr.backup_dir / backup_filename

        if backup_mgr.restore_backup(str(backup_path)):
            return {
                "message": "Backup ripristinato con successo",
                "backup_file": backup_filename,
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Errore nel ripristino del backup"
            )
    except Exception as e:
        logger.error(f"Errore ripristino backup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ========================================
# PERFORMANCE MONITORING
# ========================================

@router.get("/performance")
@require_permission(Permission.VIEW_DASHBOARD)
def get_performance_metrics(
    current_user: User = Depends(get_current_user)
):
    """Ottieni metriche di performance del sistema"""
    if not PERFORMANCE_MONITOR_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sistema di monitoraggio performance non disponibile"
        )

    perf_monitor = get_performance_monitor()
    return {
        "current_metrics": perf_monitor.get_current_metrics(),
        "endpoint_metrics": perf_monitor.get_endpoint_metrics(),
        "performance_summary": perf_monitor.get_performance_summary()
    }


@router.get("/performance/history")
@require_permission(Permission.VIEW_DASHBOARD)
def get_performance_history(
    hours: int = 24,
    current_user: User = Depends(get_current_user)
):
    """Ottieni storico metriche performance"""
    if not PERFORMANCE_MONITOR_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sistema di monitoraggio performance non disponibile"
        )

    perf_monitor = get_performance_monitor()
    return perf_monitor.get_historical_metrics(hours)


@router.post("/performance/export")
@require_permission(Permission.MANAGE_USERS)
def export_performance_metrics(
    hours: int = 24,
    current_user: User = Depends(get_admin_user)
):
    """Esporta metriche performance in file JSON"""
    if not PERFORMANCE_MONITOR_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sistema di monitoraggio performance non disponibile"
        )

    try:
        perf_monitor = get_performance_monitor()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = f"./performance_export_{timestamp}.json"

        if perf_monitor.export_metrics(filepath, hours):
            return {
                "message": "Metriche esportate con successo",
                "filepath": filepath,
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Errore esportazione metriche"
            )
    except Exception as e:
        logger.error(f"Errore esportazione performance: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ========================================
# CACHE MANAGEMENT
# ========================================

@router.post("/cache/clear")
@require_permission(Permission.MANAGE_USERS)
def clear_application_cache(
    current_user: User = Depends(get_admin_user)
):
    """Endpoint legacy: non esiste piu cache applicativa in-process da pulire."""
    logger.info("Cache clear requested by admin, but in-process cache is disabled")
    return {
        "message": "Nessuna cache in-process attiva da pulire",
        "timestamp": datetime.now().isoformat()
    }


# ========================================
# GESTIONE UTENTI
# ========================================

CREATABLE_ROLES = {UserRole.ADMIN.value, UserRole.OPERATORE.value, UserRole.CONSULTAZIONE.value}


class UserCreateRequest(BaseModel):
    username: Optional[str] = Field(default=None, min_length=3, max_length=50)
    email: EmailStr = Field(max_length=100)
    first_name: Optional[str] = Field(default=None, min_length=1, max_length=50)
    last_name: Optional[str] = Field(default=None, min_length=1, max_length=50)
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    role: str

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        if len(normalized) < 3:
            raise ValueError("Lo username deve contenere almeno 3 caratteri")
        return normalized

    @field_validator("first_name", "last_name")
    @classmethod
    def normalize_name_part(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Nome e cognome non possono essere vuoti")
        return normalized

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: Optional[str]) -> Optional[str]:
        return " ".join(value.split()) if value is not None else None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        if value not in CREATABLE_ROLES:
            raise ValueError(
                f"Ruolo non valido. Valori ammessi: {', '.join(sorted(CREATABLE_ROLES))}"
            )
        return value

    @model_validator(mode="after")
    def validate_name(self):
        has_first = self.first_name is not None
        has_last = self.last_name is not None
        if has_first != has_last:
            raise ValueError("Nome e cognome devono essere indicati insieme")
        if not has_first and not self.full_name:
            raise ValueError("Indica nome e cognome")
        return self


def _name_parts(payload: UserCreateRequest) -> tuple[str, str, str]:
    if payload.first_name is not None and payload.last_name is not None:
        return (
            payload.first_name,
            payload.last_name,
            f"{payload.first_name} {payload.last_name}".strip(),
        )
    parts = (payload.full_name or "").split(maxsplit=1)
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else ""
    return first_name, last_name, payload.full_name or first_name


def _generate_available_username(db: Session, email: str) -> str:
    local_part = email.split("@", 1)[0]
    ascii_local = unicodedata.normalize("NFKD", local_part).encode("ascii", "ignore").decode()
    base = re.sub(r"[^a-zA-Z0-9._-]+", ".", ascii_local).strip("._-").lower()
    if len(base) < 3:
        base = f"{base or 'utente'}.utente"
    base = base[:50]
    candidate = base
    suffix = 2
    while db.query(User.id).filter(func.lower(User.username) == candidate.lower()).first():
        suffix_text = f"-{suffix}"
        candidate = f"{base[:50 - len(suffix_text)]}{suffix_text}"
        suffix += 1
    return candidate


@router.get("/users")
def list_user_accounts(
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """Elenco account per la schermata admin di creazione utenti."""
    users = db.query(User).order_by(User.username).all()
    return {
        "users": [
            {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": user.role,
                "is_active": user.is_active,
                "created_at": user.created_at,
            }
            for user in users
        ]
    }


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user_account(
    payload: UserCreateRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """Crea un utente con ruolo assegnato dall'amministratore.

    Nessuna password viene scelta o trasmessa dall'admin: l'account nasce con
    una password inutilizzabile e un link di impostazione (stesso circuito del
    recupero password) viene inviato subito via email.
    """
    duplicate = db.query(User.id).filter(
        func.lower(User.email) == payload.email
    ).first()
    if not duplicate and payload.username:
        duplicate = db.query(User.id).filter(
            func.lower(User.username) == payload.username.lower()
        ).first()
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username o email già in uso",
        )

    first_name, last_name, full_name = _name_parts(payload)
    username = payload.username or _generate_available_username(db, payload.email)
    new_user = User(
        username=username,
        email=payload.email,
        hashed_password=SecurityUtils.hash_password(secrets.token_urlsafe(32)),
        full_name=full_name,
        first_name=first_name,
        last_name=last_name or None,
        role=payload.role,
        is_active=True,
    )
    db.add(new_user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username o email già in uso",
        )
    db.refresh(new_user)

    invite_queued = False
    try:
        reset_token = issue_password_reset_token(new_user)
        reset_url = build_password_reset_url(reset_token)
        background_tasks.add_task(
            send_password_reset_email,
            recipient=new_user.email,
            full_name=new_user.full_name or new_user.username,
            reset_url=reset_url,
        )
        invite_queued = True
    except Exception:
        logger.exception("Impossibile predisporre l'invito per il nuovo utente")

    write_audit_log(
        db,
        user_id=current_user.id,
        azione="admin_user_created",
        risorsa_tipo="user_account",
        risorsa_id=new_user.id,
        dati_dopo={"username": new_user.username, "role": new_user.role, "invite_queued": invite_queued},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()

    return {
        "id": new_user.id,
        "username": new_user.username,
        "email": new_user.email,
        "full_name": new_user.full_name,
        "first_name": new_user.first_name,
        "last_name": new_user.last_name,
        "role": new_user.role,
        "is_active": new_user.is_active,
        "invite_queued": invite_queued,
    }


@router.post("/users/{user_id}/resend-invite")
def resend_user_invite(
    user_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """Rinvia il link per impostare la password (stesso circuito del recupero)."""
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utente non trovato")
    if not target.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Utente disattivato: riattivalo prima di reinviare le credenziali",
        )

    reset_token = issue_password_reset_token(target)
    reset_url = build_password_reset_url(reset_token)
    background_tasks.add_task(
        send_password_reset_email,
        recipient=target.email,
        full_name=target.full_name or target.username,
        reset_url=reset_url,
    )

    write_audit_log(
        db,
        user_id=current_user.id,
        azione="admin_user_invite_resent",
        risorsa_tipo="user_account",
        risorsa_id=target.id,
        dati_dopo={"username": target.username},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()

    return {"status": "invite_queued", "email": target.email}


class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: Optional[EmailStr]) -> Optional[str]:
        return str(value).strip().lower() if value is not None else None

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value not in CREATABLE_ROLES:
            raise ValueError(
                f"Ruolo non valido. Valori ammessi: {', '.join(sorted(CREATABLE_ROLES))}"
            )
        return value


def _get_user_or_404(db: Session, user_id: int) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utente non trovato")
    return user


def _other_active_admins_count(db: Session, exclude_user_id: int) -> int:
    return db.query(User).filter(
        User.role == UserRole.ADMIN.value,
        User.is_active.is_(True),
        User.id != exclude_user_id,
    ).count()


def _would_remove_last_active_admin(db: Session, target: User, next_role: str, next_is_active: bool) -> bool:
    was_active_admin = target.role == UserRole.ADMIN.value and target.is_active
    stays_active_admin = next_role == UserRole.ADMIN.value and next_is_active
    if not was_active_admin or stays_active_admin:
        return False
    return _other_active_admins_count(db, exclude_user_id=target.id) == 0


@router.patch("/users/{user_id}")
def update_user_account(
    user_id: int,
    payload: UserUpdateRequest,
    request: Request,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    target = _get_user_or_404(db, user_id)

    next_role = payload.role if payload.role is not None else target.role
    next_is_active = payload.is_active if payload.is_active is not None else target.is_active

    if target.id == current_user.id and (
        payload.is_active is False or (payload.role is not None and payload.role != UserRole.ADMIN.value)
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Non puoi disattivare o degradare te stesso.",
        )

    if (
        target.id == current_user.id
        and payload.email is not None
        and payload.email != target.email
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Per cambiare la tua email usa l'Area personale "
                "e conferma con la password attuale."
            ),
        )

    if _would_remove_last_active_admin(db, target, next_role, next_is_active):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="È l'unico amministratore attivo: non puoi disattivarlo o degradarlo.",
        )

    if payload.email is not None and payload.email != target.email:
        duplicate = db.query(User.id).filter(
            func.lower(User.email) == payload.email,
            User.id != target.id,
        ).first()
        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email già in uso da un altro account",
            )

    changed_fields = []
    if payload.full_name is not None and payload.full_name != target.full_name:
        target.full_name = payload.full_name
        name_parts = payload.full_name.split(maxsplit=1)
        target.first_name = name_parts[0]
        target.last_name = name_parts[1] if len(name_parts) > 1 else None
        changed_fields.append("full_name")
    if payload.email is not None and payload.email != target.email:
        target.email = payload.email
        changed_fields.append("email")
    if payload.role is not None and payload.role != target.role:
        target.role = payload.role
        changed_fields.append("role")
    if payload.is_active is not None and payload.is_active != target.is_active:
        target.is_active = payload.is_active
        changed_fields.append("is_active")

    if changed_fields:
        write_audit_log(
            db,
            user_id=current_user.id,
            azione="admin_user_updated",
            risorsa_tipo="user_account",
            risorsa_id=target.id,
            dati_dopo={"changed_fields": changed_fields, "role": target.role, "is_active": target.is_active},
            ip_address=request.client.host if request.client else None,
        )
    db.commit()
    db.refresh(target)

    return {
        "id": target.id,
        "username": target.username,
        "email": target.email,
        "full_name": target.full_name,
        "first_name": target.first_name,
        "last_name": target.last_name,
        "role": target.role,
        "is_active": target.is_active,
    }


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_account(
    user_id: int,
    request: Request,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    target = _get_user_or_404(db, user_id)

    if target.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Non puoi eliminare te stesso.",
        )

    if _would_remove_last_active_admin(db, target, next_role=UserRole.CONSULTAZIONE.value, next_is_active=False):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="È l'unico amministratore attivo: non puoi eliminarlo.",
        )

    write_audit_log(
        db,
        user_id=current_user.id,
        azione="admin_user_deleted",
        risorsa_tipo="user_account",
        risorsa_id=target.id,
        dati_dopo={"username": target.username, "role": target.role},
        ip_address=request.client.host if request.client else None,
    )
    db.delete(target)
    db.commit()
    return None
