"""Eliminazione/archiviazione versionata dei documenti progetto."""
from __future__ import annotations

from pathlib import Path
from sqlalchemy.orm import Session

import models
from services.audit_log import write_audit_log

ARCHIVIABILI = {"inviato", "rendicontato", "chiuso", "completed"}


def _project_state(db: Session, project_id: int) -> tuple[models.Project | None, list[str]]:
    project = db.query(models.Project).filter_by(id=project_id).first()
    if project is None:
        return None, []
    plans = db.query(models.PianoFinanziario).filter_by(progetto_id=project_id).all()
    states = [p.stato_rendicontazione for p in plans if p.stato_rendicontazione]
    return project, states


def build_document_deletion_impact(db: Session, project_id: int, documento_id: int) -> dict | None:
    doc = db.query(models.ProjectDocumento).filter_by(id=documento_id, project_id=project_id).first()
    if doc is None:
        return None
    project, plan_states = _project_state(db, project_id)
    blocked = bool(set(plan_states) & ARCHIVIABILI) or project.status in {"completed", "cancelled"}
    return {
        "documento_id": doc.id, "project_id": project_id, "file_name": doc.file_name,
        "tipo_documento": doc.tipo_documento, "versione": doc.versione,
        "blocked": blocked, "project_status": project.status,
        "piano_states": plan_states,
        "derived_data": {"convenzione_file_path": project.convenzione_file_path},
    }


def permanently_delete_document(db: Session, project_id: int, documento_id: int, *, user_id: int, reason: str) -> dict | None:
    impact = build_document_deletion_impact(db, project_id, documento_id)
    if impact is None:
        return None
    if impact["blocked"]:
        return {"blocked": True, **impact}
    doc = db.query(models.ProjectDocumento).filter_by(id=documento_id, project_id=project_id).one()
    path = Path(doc.file_path) if doc.file_path else None
    try:
        if doc.file_path and db.query(models.Project).filter_by(id=project_id).one().convenzione_file_path == doc.file_path:
            db.query(models.Project).filter_by(id=project_id).update({models.Project.convenzione_file_path: None})
        write_audit_log(db, user_id=user_id, azione="project_document_hard_delete", risorsa_tipo="project_document", risorsa_id=doc.id, dati_prima=impact, dati_dopo={"deleted": True, "reason": reason})
        db.delete(doc)
        db.commit()
    except Exception:
        db.rollback()
        raise
    if path:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
    return {"message": "Documento eliminato definitivamente", **impact}


def archive_document(db: Session, project_id: int, documento_id: int, *, user_id: int, reason: str) -> dict | None:
    doc = db.query(models.ProjectDocumento).filter_by(id=documento_id, project_id=project_id).first()
    if doc is None:
        return None
    doc.stato = "annullato"
    doc.annullato_motivo = reason
    doc.source_removed = False
    write_audit_log(db, user_id=user_id, azione="project_document_archived", risorsa_tipo="project_document", risorsa_id=doc.id, dati_dopo={"reason": reason})
    db.commit()
    return {"message": "Documento archiviato", "id": doc.id}
