"""CRUD transazionale per l'Archivio Avvisi V1.

Le query operative espongono esclusivamente regole/scadenze validate. Le
transizioni di revisione ricevono l'identità dell'utente dal chiamante
autenticato, mai dal payload client.
"""

from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import models
import schemas_avvisi as avvisi_schemas


AVVISO_STATE_TRANSITIONS = {
    "bozza": {"attivo", "archiviato"},
    "attivo": {"in_scadenza", "scaduto", "archiviato"},
    "in_scadenza": {"attivo", "scaduto", "archiviato"},
    "scaduto": {"archiviato"},
    "archiviato": set(),
}


def _storage_key(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = value.strip().replace("\\", "/")
    path = PurePosixPath(normalized)
    if not normalized or path.is_absolute() or ".." in path.parts:
        raise ValueError("Storage key non valida")
    return str(path)


def _flush_integrity(db: Session, message: str) -> None:
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError(message) from exc


def get_avviso(db: Session, avviso_id: int) -> Optional[models.Avviso]:
    return db.query(models.Avviso).filter(models.Avviso.id == avviso_id).first()


def list_avvisi(
    db: Session,
    *,
    fondo: Optional[str] = None,
    stato: Optional[str] = None,
    anno: Optional[int] = None,
    include_archiviati: bool = False,
):
    query = db.query(models.Avviso)
    if fondo:
        query = query.filter(models.Avviso.fondo == fondo)
    if stato:
        query = query.filter(models.Avviso.stato == stato)
    if anno is not None:
        query = query.filter(models.Avviso.anno == anno)
    if not include_archiviati:
        query = query.filter(models.Avviso.stato != "archiviato")
    return query.order_by(models.Avviso.anno.desc(), models.Avviso.fondo, models.Avviso.numero).all()


def create_avviso(db: Session, payload: avvisi_schemas.AvvisoCreate) -> models.Avviso:
    data = payload.model_dump(mode="python")
    data["codice"] = data.get("codice") or f"{data['numero']}/{data['anno']}"
    data["descrizione"] = data.get("descrizione_breve")
    data["is_active"] = data["stato"] != "archiviato"
    avviso = models.Avviso(**data)
    db.add(avviso)
    _flush_integrity(db, "Esiste già un avviso con la stessa identità")
    db.commit()
    db.refresh(avviso)
    return avviso


def update_avviso(
    db: Session, avviso_id: int, payload: avvisi_schemas.AvvisoUpdate
) -> Optional[models.Avviso]:
    avviso = db.query(models.Avviso).filter(models.Avviso.id == avviso_id).with_for_update().first()
    if not avviso:
        return None
    changes = payload.model_dump(exclude_unset=True, mode="python")
    target_state = changes.get("stato")
    if target_state and target_state != avviso.stato:
        if target_state not in AVVISO_STATE_TRANSITIONS.get(avviso.stato, set()):
            raise ValueError(f"Transizione stato non consentita: {avviso.stato} -> {target_state}")
        avviso.is_active = target_state != "archiviato"
    for key, value in changes.items():
        setattr(avviso, key, value)
    if "descrizione_breve" in changes:
        avviso.descrizione = changes["descrizione_breve"]
    db.commit()
    db.refresh(avviso)
    return avviso


def create_next_revision(
    db: Session,
    avviso_id: int,
    payload: avvisi_schemas.AvvisoRevisioneCreate,
    *,
    created_by_user_id: Optional[int],
) -> models.AvvisoRevisione:
    avviso = db.query(models.Avviso).filter(models.Avviso.id == avviso_id).with_for_update().first()
    if not avviso:
        raise ValueError("Avviso non trovato")
    last_revision = (
        db.query(models.AvvisoRevisione)
        .filter(models.AvvisoRevisione.avviso_id == avviso_id)
        .order_by(models.AvvisoRevisione.numero_revisione.desc())
        .first()
    )
    data = payload.model_dump(mode="python")
    data["source_md_path"] = _storage_key(data["source_md_path"])
    data["cleaned_md_path"] = _storage_key(data.get("cleaned_md_path"))
    data["source_pdf_path"] = _storage_key(data.get("source_pdf_path"))
    revision = models.AvvisoRevisione(
        **data,
        avviso_id=avviso_id,
        numero_revisione=(last_revision.numero_revisione + 1 if last_revision else 1),
        revisione_precedente_id=(last_revision.id if last_revision else None),
        created_by_user_id=created_by_user_id,
    )
    try:
        db.add(revision)
        db.flush()
        avviso.revisione_corrente_id = revision.id
        avviso.titolo = revision.titolo
        avviso.descrizione_breve = revision.descrizione_breve
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("Revisione o documento sorgente già presente") from exc
    db.refresh(revision)
    return revision


def create_rule_proposal(
    db: Session,
    revision_id: int,
    payload: avvisi_schemas.AvvisoRegolaProposal,
    *,
    commit: bool = True,
) -> models.AvvisoRegola:
    if not db.query(models.AvvisoRevisione.id).filter(models.AvvisoRevisione.id == revision_id).first():
        raise ValueError("Revisione avviso non trovata")
    data = payload.model_dump(mode="python")
    data["valore"] = payload.valore.model_dump(mode="json")
    rule = models.AvvisoRegola(avviso_revisione_id=revision_id, stato="proposta", **data)
    db.add(rule)
    db.flush()
    if commit:
        db.commit()
        db.refresh(rule)
    return rule


def review_rule(
    db: Session,
    rule_id: int,
    *,
    action: str,
    reviewer_user_id: int,
    corrected_value: Optional[dict] = None,
    note: Optional[str] = None,
) -> Optional[models.AvvisoRegola]:
    rule = db.query(models.AvvisoRegola).filter(models.AvvisoRegola.id == rule_id).with_for_update().first()
    if not rule:
        return None
    if rule.stato != "proposta":
        raise ValueError("La regola non è più in revisione")
    if action not in {"approva", "rifiuta"}:
        raise ValueError("Azione di revisione non valida")
    if action == "rifiuta" and not (note or "").strip():
        raise ValueError("La motivazione del rifiuto è obbligatoria")
    if corrected_value is not None:
        rule.valore = corrected_value
    rule.nota_revisione = note
    if action == "approva":
        rule.stato = "validata"
        rule.validata_da_user_id = reviewer_user_id
        rule.validata_il = datetime.now(timezone.utc)
    else:
        rule.stato = "rifiutata"
    db.commit()
    db.refresh(rule)
    return rule


def get_validated_rules(db: Session, avviso_id: int, revision_id: Optional[int] = None):
    if revision_id is None:
        revision_id = db.query(models.Avviso.revisione_corrente_id).filter(models.Avviso.id == avviso_id).scalar()
    if revision_id is None:
        return []
    return (
        db.query(models.AvvisoRegola)
        .join(models.AvvisoRevisione)
        .filter(
            models.AvvisoRevisione.avviso_id == avviso_id,
            models.AvvisoRegola.avviso_revisione_id == revision_id,
            models.AvvisoRegola.stato == "validata",
        )
        .order_by(models.AvvisoRegola.categoria, models.AvvisoRegola.chiave)
        .all()
    )


def create_deadline_proposal(
    db: Session, revision_id: int, payload: avvisi_schemas.AvvisoScadenzaProposal
) -> models.AvvisoScadenza:
    if not db.query(models.AvvisoRevisione.id).filter(models.AvvisoRevisione.id == revision_id).first():
        raise ValueError("Revisione avviso non trovata")
    deadline = models.AvvisoScadenza(
        avviso_revisione_id=revision_id,
        stato="proposta",
        **payload.model_dump(mode="python"),
    )
    db.add(deadline)
    _flush_integrity(db, "Scadenza duplicata")
    db.commit()
    db.refresh(deadline)
    return deadline


def review_deadline(
    db: Session, deadline_id: int, *, action: str, reviewer_user_id: int
) -> Optional[models.AvvisoScadenza]:
    deadline = (
        db.query(models.AvvisoScadenza)
        .filter(models.AvvisoScadenza.id == deadline_id)
        .with_for_update()
        .first()
    )
    if not deadline:
        return None
    if deadline.stato != "proposta" or action not in {"approva", "rifiuta"}:
        raise ValueError("Revisione scadenza non consentita")
    deadline.stato = "validata" if action == "approva" else "rifiutata"
    if action == "approva":
        deadline.validata_da_user_id = reviewer_user_id
        deadline.validata_il = datetime.now(timezone.utc)
    db.commit()
    db.refresh(deadline)
    return deadline


def create_document(
    db: Session,
    avviso_id: int,
    payload: avvisi_schemas.AvvisoDocumentoCreate,
    *,
    uploaded_by_user_id: Optional[int],
) -> models.AvvisoDocumento:
    if payload.avviso_revisione_id is not None:
        revision = db.query(models.AvvisoRevisione).filter(
            models.AvvisoRevisione.id == payload.avviso_revisione_id,
            models.AvvisoRevisione.avviso_id == avviso_id,
        ).first()
        if not revision:
            raise ValueError("La revisione non appartiene all'avviso")
    data = payload.model_dump(mode="python")
    data["file_path"] = _storage_key(data["file_path"])
    document = models.AvvisoDocumento(
        avviso_id=avviso_id, uploaded_by_user_id=uploaded_by_user_id, **data
    )
    db.add(document)
    _flush_integrity(db, "Documento già presente nell'avviso")
    db.commit()
    db.refresh(document)
    return document


def create_knowledge(
    db: Session,
    avviso_id: int,
    payload: avvisi_schemas.AvvisoConoscenzaCreate,
    *,
    author_user_id: int,
) -> models.AvvisoConoscenza:
    if payload.avviso_revisione_id is not None:
        belongs = db.query(models.AvvisoRevisione.id).filter(
            models.AvvisoRevisione.id == payload.avviso_revisione_id,
            models.AvvisoRevisione.avviso_id == avviso_id,
        ).first()
        if not belongs:
            raise ValueError("La revisione non appartiene all'avviso")
    knowledge = models.AvvisoConoscenza(
        avviso_id=avviso_id,
        autore_user_id=author_user_id,
        **payload.model_dump(mode="python"),
    )
    db.add(knowledge)
    db.commit()
    db.refresh(knowledge)
    return knowledge


def create_project_outcome(
    db: Session,
    avviso_id: int,
    payload: avvisi_schemas.AvvisoEsitoProgettoCreate,
    *,
    created_by_user_id: int,
) -> models.AvvisoEsitoProgetto:
    project = db.query(models.Project).filter(models.Project.id == payload.project_id).first()
    if not project or project.avviso_id != avviso_id:
        raise ValueError("Il progetto non appartiene all'avviso")
    if payload.avviso_revisione_id is not None:
        if project.avviso_revisione_id != payload.avviso_revisione_id:
            raise ValueError("La revisione non coincide con quella del progetto")
    if payload.piano_finanziario_id is not None:
        plan = db.query(models.PianoFinanziario).filter(
            models.PianoFinanziario.id == payload.piano_finanziario_id,
            models.PianoFinanziario.progetto_id == project.id,
        ).first()
        if not plan or plan.avviso_pf_id != avviso_id:
            raise ValueError("Il piano non appartiene allo stesso avviso")
    outcome = models.AvvisoEsitoProgetto(
        avviso_id=avviso_id,
        created_by_user_id=created_by_user_id,
        **payload.model_dump(mode="python"),
    )
    db.add(outcome)
    db.commit()
    db.refresh(outcome)
    return outcome


def link_project_to_revision(db: Session, project_id: int, revision_id: int) -> models.Project:
    project = db.query(models.Project).filter(models.Project.id == project_id).with_for_update().first()
    revision = db.query(models.AvvisoRevisione).filter(models.AvvisoRevisione.id == revision_id).first()
    if not project or not revision:
        raise ValueError("Progetto o revisione non trovati")
    if project.avviso_id is not None and project.avviso_id != revision.avviso_id:
        raise ValueError("La revisione appartiene a un altro avviso")
    project.avviso_id = revision.avviso_id
    project.avviso_revisione_id = revision.id
    db.commit()
    db.refresh(project)
    return project
