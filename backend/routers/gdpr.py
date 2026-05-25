from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

import models
import schemas
from auth import Permission, User, get_current_user, require_permission
from database import get_db
from services.audit_log import hash_ip, write_audit_log
from services.gdpr_service import anonymize_collaborator, export_collaborator_data

router = APIRouter(prefix="/api/v1/gdpr", tags=["GDPR"])


def _get_collaborator(db: Session, collaboratore_id: int) -> models.Collaborator:
    collaboratore = db.query(models.Collaborator).filter(models.Collaborator.id == collaboratore_id).first()
    if not collaboratore:
        raise HTTPException(status_code=404, detail="Collaboratore non trovato")
    return collaboratore


@router.get("/consensi/{collaboratore_id}")
@require_permission(Permission.MANAGE_GDPR)
def list_consensi(collaboratore_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _get_collaborator(db, collaboratore_id)
    return db.query(models.GDPRConsenso).filter(models.GDPRConsenso.collaboratore_id == collaboratore_id).all()


@router.post("/consensi/{collaboratore_id}")
@require_permission(Permission.MANAGE_GDPR)
def create_consenso(collaboratore_id: int, payload: dict[str, Any], request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _get_collaborator(db, collaboratore_id)
    tipo = str(payload.get("tipo_consenso") or "").strip()
    if not tipo:
        raise HTTPException(status_code=422, detail="tipo_consenso obbligatorio")
    consenso = models.GDPRConsenso(
        collaboratore_id=collaboratore_id,
        tipo_consenso=tipo,
        ip_address_hash=hash_ip(request.client.host if request.client else None),
    )
    db.add(consenso)
    write_audit_log(db, user_id=current_user.id, azione="gdpr_consenso_create", risorsa_tipo="collaborator", risorsa_id=collaboratore_id, dati_dopo={"tipo_consenso": tipo}, ip_address=request.client.host if request.client else None)
    db.commit()
    db.refresh(consenso)
    return consenso


@router.delete("/consensi/{collaboratore_id}/{tipo}")
@require_permission(Permission.MANAGE_GDPR)
def revoke_consenso(collaboratore_id: int, tipo: str, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _get_collaborator(db, collaboratore_id)
    consenso = db.query(models.GDPRConsenso).filter(
        models.GDPRConsenso.collaboratore_id == collaboratore_id,
        models.GDPRConsenso.tipo_consenso == tipo,
        models.GDPRConsenso.revocato.is_(False),
    ).order_by(models.GDPRConsenso.data_consenso.desc()).first()
    if not consenso:
        raise HTTPException(status_code=404, detail="Consenso attivo non trovato")
    consenso.revocato = True
    consenso.data_revoca = datetime.now(timezone.utc)
    write_audit_log(db, user_id=current_user.id, azione="gdpr_consenso_revoke", risorsa_tipo="collaborator", risorsa_id=collaboratore_id, dati_dopo={"tipo_consenso": tipo, "revocato": True}, ip_address=request.client.host if request.client else None)
    db.commit()
    return {"status": "revoked", "tipo_consenso": tipo}


@router.get("/export/{collaboratore_id}")
@require_permission(Permission.MANAGE_GDPR)
def export_data(collaboratore_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    collaboratore = _get_collaborator(db, collaboratore_id)
    write_audit_log(db, user_id=current_user.id, azione="gdpr_export", risorsa_tipo="collaborator", risorsa_id=collaboratore_id, ip_address=request.client.host if request.client else None)
    db.commit()
    return export_collaborator_data(db, collaboratore)


@router.delete("/anonimizza/{collaboratore_id}")
@require_permission(Permission.MANAGE_GDPR)
def anonymize(collaboratore_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    collaboratore = _get_collaborator(db, collaboratore_id)
    anonymize_collaborator(db, collaboratore, user_id=current_user.id, ip_address=request.client.host if request.client else None)
    db.commit()
    return {"status": "anonimized", "collaboratore_id": collaboratore_id}


@router.get("/audit/{collaboratore_id}")
@require_permission(Permission.MANAGE_GDPR)
def audit(collaboratore_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _get_collaborator(db, collaboratore_id)
    return db.query(models.SecurityAuditLog).filter(
        models.SecurityAuditLog.risorsa_tipo == "collaborator",
        models.SecurityAuditLog.risorsa_id == str(collaboratore_id),
    ).order_by(models.SecurityAuditLog.timestamp.desc()).all()
