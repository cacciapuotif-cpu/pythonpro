"""
Router per funzionalità amministrazione
Gestisce backup, monitoring, security logs, performance e cache
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
import logging

import crud
from database import get_db
from auth import (
    User, Permission, require_permission,
    get_current_user, get_admin_user, LoginAttempt
)
from error_handler import error_monitor

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
    """Pulisci cache applicazione"""
    try:
        from crud import query_cache
        query_cache.clear()
        logger.info("Application cache cleared by admin")
        return {
            "message": "Cache pulita con successo",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Errore pulizia cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
