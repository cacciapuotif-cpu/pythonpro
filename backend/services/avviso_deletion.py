"""Cancellazione definitiva e auditata degli avvisi, riservata agli amministratori."""
from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import or_
from sqlalchemy.orm import Session

import models
from file_upload import UPLOAD_DIR
from services.audit_log import write_audit_log

logger = logging.getLogger(__name__)


def _revision_ids(db: Session, avviso_id: int) -> list[int]:
    return [
        row[0]
        for row in db.query(models.AvvisoRevisione.id)
        .filter(models.AvvisoRevisione.avviso_id == avviso_id)
        .all()
    ]


def _linked_projects(db: Session, avviso_id: int, revision_ids: list[int]):
    conditions = [models.Project.avviso_id == avviso_id]
    if revision_ids:
        conditions.append(models.Project.avviso_revisione_id.in_(revision_ids))
    return db.query(models.Project).filter(or_(*conditions)).order_by(models.Project.id).all()


def _linked_plans(db: Session, avviso_id: int, revision_ids: list[int]):
    conditions = [models.PianoFinanziario.avviso_pf_id == avviso_id]
    if revision_ids:
        conditions.append(models.PianoFinanziario.avviso_revisione_id.in_(revision_ids))
    return (
        db.query(models.PianoFinanziario)
        .filter(or_(*conditions))
        .order_by(models.PianoFinanziario.id)
        .all()
    )


def _count_for_revisions(db: Session, model, revision_ids: list[int]) -> int:
    if not revision_ids:
        return 0
    return db.query(model).filter(model.avviso_revisione_id.in_(revision_ids)).count()


def build_deletion_impact(db: Session, avviso_id: int) -> dict | None:
    avviso = db.query(models.Avviso).filter(models.Avviso.id == avviso_id).first()
    if avviso is None:
        return None
    revision_ids = _revision_ids(db, avviso_id)
    revisions = (
        db.query(models.AvvisoRevisione)
        .filter(models.AvvisoRevisione.avviso_id == avviso_id)
        .order_by(models.AvvisoRevisione.numero_revisione)
        .all()
    )
    projects = _linked_projects(db, avviso_id, revision_ids)
    plans = _linked_plans(db, avviso_id, revision_ids)
    documents = db.query(models.AvvisoDocumento).filter(models.AvvisoDocumento.avviso_id == avviso_id)
    knowledge = db.query(models.AvvisoConoscenza).filter(models.AvvisoConoscenza.avviso_id == avviso_id)
    outcomes = db.query(models.AvvisoEsitoProgetto).filter(models.AvvisoEsitoProgetto.avviso_id == avviso_id)
    filenames = [
        revision.original_filename or Path(revision.source_md_path or "").name
        for revision in revisions
        if revision.original_filename or revision.source_md_path
    ]
    filenames.extend(row[0] for row in documents.with_entities(models.AvvisoDocumento.original_filename).all())
    phrase = f"ELIMINA {avviso.ente_erogatore.upper()} {avviso.codice}"
    return {
        "avviso_id": avviso.id,
        "codice": avviso.codice,
        "ente_erogatore": avviso.ente_erogatore,
        "titolo": avviso.titolo,
        "confirmation_phrase": phrase,
        "projects": [{"id": item.id, "label": item.name} for item in projects],
        "financial_plans": [
            {"id": item.id, "label": item.nome or item.codice_piano or f"Piano {item.id}"}
            for item in plans
        ],
        "revision_filenames": filenames,
        "counts": {
            "revisions": len(revisions),
            "rules": _count_for_revisions(db, models.AvvisoRegola, revision_ids),
            "deadlines": _count_for_revisions(db, models.AvvisoScadenza, revision_ids),
            "documents": documents.count(),
            "knowledge": knowledge.count(),
            "outcomes": outcomes.count(),
        },
    }


def _safe_source_paths(db: Session, avviso_id: int) -> list[Path]:
    keys: list[str] = []
    for revision in db.query(models.AvvisoRevisione).filter(models.AvvisoRevisione.avviso_id == avviso_id):
        keys.extend(
            key for key in (revision.source_md_path, revision.cleaned_md_path, revision.source_pdf_path) if key
        )
    keys.extend(
        row[0]
        for row in db.query(models.AvvisoDocumento.file_path)
        .filter(models.AvvisoDocumento.avviso_id == avviso_id)
        .all()
        if row[0]
    )
    root = UPLOAD_DIR.resolve()
    paths: list[Path] = []
    for key in keys:
        candidate = (UPLOAD_DIR / key).resolve()
        if candidate != root and root in candidate.parents:
            paths.append(candidate)
        else:
            logger.warning("Percorso sorgente avviso fuori upload root ignorato: %s", key)
    return list(dict.fromkeys(paths))


def permanently_delete_avviso(db: Session, avviso_id: int, *, user_id: int) -> dict | None:
    impact = build_deletion_impact(db, avviso_id)
    if impact is None:
        return None
    avviso = db.query(models.Avviso).filter(models.Avviso.id == avviso_id).one()
    revision_ids = _revision_ids(db, avviso_id)
    projects = _linked_projects(db, avviso_id, revision_ids)
    plans = _linked_plans(db, avviso_id, revision_ids)
    source_paths = _safe_source_paths(db, avviso_id)

    try:
        for project in projects:
            project.avviso_id = None
            project.avviso_revisione_id = None
        for plan in plans:
            plan.avviso_pf_id = None
            plan.avviso_revisione_id = None
        avviso.revisione_corrente_id = None
        db.flush()

        db.query(models.AvvisoEsitoProgetto).filter(
            models.AvvisoEsitoProgetto.avviso_id == avviso_id
        ).delete(synchronize_session=False)
        db.query(models.AvvisoDocumento).filter(models.AvvisoDocumento.avviso_id == avviso_id).delete(
            synchronize_session=False
        )
        db.query(models.AvvisoConoscenza).filter(models.AvvisoConoscenza.avviso_id == avviso_id).delete(
            synchronize_session=False
        )
        if revision_ids:
            db.query(models.AvvisoRegola).filter(
                models.AvvisoRegola.avviso_revisione_id.in_(revision_ids)
            ).delete(synchronize_session=False)
            db.query(models.AvvisoScadenza).filter(
                models.AvvisoScadenza.avviso_revisione_id.in_(revision_ids)
            ).delete(synchronize_session=False)
            db.query(models.AgentSuggestion).filter(
                models.AgentSuggestion.entity_type == "avviso_revisione",
                models.AgentSuggestion.entity_id.in_(revision_ids),
            ).update({models.AgentSuggestion.entity_id: None}, synchronize_session=False)
            db.query(models.AgentRun).filter(
                models.AgentRun.entity_type == "avviso_revisione",
                models.AgentRun.entity_id.in_(revision_ids),
            ).update({models.AgentRun.entity_id: None}, synchronize_session=False)
            db.query(models.AvvisoRevisione).filter(models.AvvisoRevisione.id.in_(revision_ids)).delete(
                synchronize_session=False
            )

        write_audit_log(
            db,
            user_id=user_id,
            azione="avviso_hard_delete",
            risorsa_tipo="avviso",
            risorsa_id=avviso_id,
            dati_prima=impact,
            dati_dopo={"deleted": True},
        )
        db.delete(avviso)
        db.commit()
    except Exception:
        db.rollback()
        raise

    deleted_files = 0
    file_delete_errors: list[str] = []
    for path in source_paths:
        try:
            if path.exists():
                path.unlink()
                deleted_files += 1
        except OSError:
            logger.exception("Impossibile eliminare sorgente avviso %s", path)
            file_delete_errors.append(path.name)

    return {
        "message": "Avviso eliminato definitivamente",
        "id": avviso_id,
        "detached_projects": len(projects),
        "detached_financial_plans": len(plans),
        "deleted_files": deleted_files,
        "file_delete_errors": file_delete_errors,
    }
