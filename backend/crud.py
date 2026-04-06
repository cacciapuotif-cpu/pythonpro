from sqlalchemy.orm import Session, joinedload, selectinload, contains_eager
from sqlalchemy import and_, or_, desc, asc, func, text, select
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timedelta, date
from functools import lru_cache
from collections import defaultdict
import json
import re
import uuid
import models
import schemas
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from piano_finanziario_config import (
    MACROVOCE_LIMITS,
    MACROVOCE_TITLES,
    build_default_voci,
    get_voice_template_map,
    is_dynamic_voice,
)
from piano_fondimpresa_config import (
    SEZIONE_LIMITS as FONDIMPRESA_LIMITS,
    SEZIONE_TITLES as FONDIMPRESA_TITLES,
    build_default_voci_fondimpresa,
    get_voice_template_map as get_fondimpresa_voice_template_map,
)
from async_events import enqueue_webhook_notification, track_entity_event

logger = logging.getLogger(__name__)

# Thread pool per operazioni asincrone
executor = ThreadPoolExecutor(max_workers=4)

# Cache avanzata per query frequenti
class QueryCache:
    def __init__(self, max_size: int = 256, ttl_seconds: int = 300):
        self.cache = {}
        self.timestamps = {}
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds

    def get(self, key: str):
        if key in self.cache:
            if (datetime.now() - self.timestamps[key]).seconds < self.ttl_seconds:
                return self.cache[key]
            else:
                del self.cache[key]
                del self.timestamps[key]
        return None

    def set(self, key: str, value):
        if len(self.cache) >= self.max_size:
            oldest_key = min(self.timestamps.keys(), key=lambda k: self.timestamps[k])
            del self.cache[oldest_key]
            del self.timestamps[oldest_key]

        self.cache[key] = value
        self.timestamps[key] = datetime.now()

    def clear(self):
        self.cache.clear()
        self.timestamps.clear()

query_cache = QueryCache()

# Cache avanzata per query frequenti
def get_collaborator_cached(db: Session, collaborator_id: int):
    cache_key = f"collaborator_{collaborator_id}"
    cached_result = query_cache.get(cache_key)

    if cached_result is not None:
        return cached_result

    result = db.query(models.Collaborator).filter(
        models.Collaborator.id == collaborator_id,
        models.Collaborator.is_active == True
    ).first()

    if result:
        query_cache.set(cache_key, result)

    return result

# Funzione per invalidare cache
def invalidate_collaborator_cache(collaborator_id: int):
    cache_key = f"collaborator_{collaborator_id}"
    if cache_key in query_cache.cache:
        del query_cache.cache[cache_key]
        del query_cache.timestamps[cache_key]

def get_collaborator(db: Session, collaborator_id: int):
    return db.query(models.Collaborator).filter(
        models.Collaborator.id == collaborator_id
    ).first()


def _documento_payload(documento: Any) -> dict[str, Any]:
    if hasattr(documento, "model_dump"):
        return documento.model_dump(exclude_unset=True)
    if hasattr(documento, "dict"):
        return documento.dict(exclude_unset=True)
    if isinstance(documento, dict):
        return dict(documento)
    raise ValueError("Payload documento non valido")


def get_documento_richiesto(db: Session, doc_id: int):
    return db.query(models.DocumentoRichiesto).options(
        joinedload(models.DocumentoRichiesto.collaboratore)
    ).filter(
        models.DocumentoRichiesto.id == doc_id
    ).first()


def get_documenti_collaboratore(
    db: Session,
    collaboratore_id: int,
    stato: Optional[str] = None,
):
    query = db.query(models.DocumentoRichiesto).options(
        joinedload(models.DocumentoRichiesto.collaboratore)
    ).filter(
        models.DocumentoRichiesto.collaboratore_id == collaboratore_id
    )
    if stato is not None:
        query = query.filter(models.DocumentoRichiesto.stato == stato)
    return query.order_by(
        asc(models.DocumentoRichiesto.stato),
        asc(models.DocumentoRichiesto.data_scadenza),
        desc(models.DocumentoRichiesto.data_richiesta),
        desc(models.DocumentoRichiesto.id),
    ).all()


def get_documenti_richiesti(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    collaboratore_id: Optional[int] = None,
    stato: Optional[str] = None,
):
    query = db.query(models.DocumentoRichiesto).options(
        joinedload(models.DocumentoRichiesto.collaboratore)
    )
    if collaboratore_id is not None:
        query = query.filter(models.DocumentoRichiesto.collaboratore_id == collaboratore_id)
    if stato is not None:
        query = query.filter(models.DocumentoRichiesto.stato == stato)
    return query.order_by(
        asc(models.DocumentoRichiesto.data_scadenza),
        desc(models.DocumentoRichiesto.data_richiesta),
        desc(models.DocumentoRichiesto.id),
    ).offset(skip).limit(limit).all()


def get_documenti_mancanti(db: Session, collaboratore_id: int):
    return db.query(models.DocumentoRichiesto).options(
        joinedload(models.DocumentoRichiesto.collaboratore)
    ).filter(
        models.DocumentoRichiesto.collaboratore_id == collaboratore_id,
        models.DocumentoRichiesto.stato.in_(("richiesto", "scaduto")),
    ).order_by(
        asc(models.DocumentoRichiesto.data_scadenza),
        desc(models.DocumentoRichiesto.data_richiesta),
    ).all()


def get_documenti_in_scadenza(db: Session, giorni: int = 7):
    now = datetime.now()
    soglia = now + timedelta(days=giorni)
    return db.query(models.DocumentoRichiesto).options(
        joinedload(models.DocumentoRichiesto.collaboratore)
    ).filter(
        models.DocumentoRichiesto.data_scadenza.isnot(None),
        models.DocumentoRichiesto.data_scadenza >= now,
        models.DocumentoRichiesto.data_scadenza <= soglia,
        models.DocumentoRichiesto.stato.in_(("richiesto", "caricato", "validato")),
    ).order_by(
        asc(models.DocumentoRichiesto.data_scadenza),
        asc(models.DocumentoRichiesto.collaboratore_id),
    ).all()


def create_documento_richiesto(db: Session, documento):
    payload = _documento_payload(documento)
    collaboratore_id = payload.get("collaboratore_id")
    if not collaboratore_id:
        raise ValueError("collaboratore_id obbligatorio")

    collaboratore = get_collaborator(db, int(collaboratore_id))
    if not collaboratore:
        raise ValueError("Collaboratore non trovato")

    payload.setdefault("obbligatorio", True)
    payload.setdefault("stato", "richiesto")
    payload.setdefault("data_richiesta", datetime.now())
    db_obj = models.DocumentoRichiesto(**payload)
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return get_documento_richiesto(db, db_obj.id)


def update_documento_richiesto(db: Session, doc_id: int, documento):
    db_obj = get_documento_richiesto(db, doc_id)
    if not db_obj:
        return None

    update_data = _documento_payload(documento)
    if "collaboratore_id" in update_data:
        collaboratore = get_collaborator(db, int(update_data["collaboratore_id"]))
        if not collaboratore:
            raise ValueError("Collaboratore non trovato")

    for key, value in update_data.items():
        setattr(db_obj, key, value)

    if update_data.get("file_path") and not db_obj.data_caricamento:
        db_obj.data_caricamento = datetime.now()
        if db_obj.stato == "richiesto":
            db_obj.stato = "caricato"

    db.commit()
    db.refresh(db_obj)
    return get_documento_richiesto(db, doc_id)


def valida_documento(db: Session, doc_id: int, validato_da: str):
    db_obj = get_documento_richiesto(db, doc_id)
    if not db_obj:
        return None

    db_obj.stato = "validato"
    db_obj.validato_da = validato_da
    db_obj.validato_il = datetime.now()
    if db_obj.data_caricamento is None:
        db_obj.data_caricamento = datetime.now()
    db.commit()
    db.refresh(db_obj)
    return get_documento_richiesto(db, doc_id)


def rifiuta_documento(db: Session, doc_id: int, note: Optional[str] = None):
    db_obj = get_documento_richiesto(db, doc_id)
    if not db_obj:
        return None

    db_obj.stato = "rifiutato"
    db_obj.note_operatore = note
    db_obj.validato_il = None
    db_obj.validato_da = None
    db.commit()
    db.refresh(db_obj)
    return get_documento_richiesto(db, doc_id)


def marca_scaduti(db: Session):
    now = datetime.now()
    query = db.query(models.DocumentoRichiesto).filter(
        models.DocumentoRichiesto.data_scadenza.isnot(None),
        models.DocumentoRichiesto.data_scadenza < now,
        models.DocumentoRichiesto.stato.notin_(("rifiutato", "scaduto")),
    )
    documenti = query.all()
    for documento in documenti:
        documento.stato = "scaduto"
    if documenti:
        db.commit()
    return documenti


def delete_documento_richiesto(db: Session, doc_id: int):
    db_obj = get_documento_richiesto(db, doc_id)
    if not db_obj:
        return None
    db.delete(db_obj)
    db.commit()
    return db_obj

def get_collaborator_by_email(db: Session, email: str):
    """Recupera un collaboratore tramite email (case-insensitive)"""
    return db.query(models.Collaborator).filter(
        func.lower(models.Collaborator.email) == email.lower()
    ).first()

def get_collaborator_by_fiscal_code(db: Session, fiscal_code: str):
    """Recupera un collaboratore tramite codice fiscale (normalizzato uppercase)"""
    return db.query(models.Collaborator).filter(
        models.Collaborator.fiscal_code == fiscal_code.upper()
    ).first()


def get_collaborator_by_partita_iva(db: Session, partita_iva: str):
    """Recupera un collaboratore tramite partita IVA normalizzata."""
    clean = partita_iva.replace(' ', '').replace('IT', '').replace('it', '')
    return db.query(models.Collaborator).filter(
        models.Collaborator.partita_iva == clean
    ).first()


def normalize_partita_iva(partita_iva: Optional[str]) -> Optional[str]:
    if partita_iva is None:
        return None
    return partita_iva.replace(' ', '').replace('IT', '').replace('it', '')


def get_azienda_cliente_by_partita_iva(db: Session, partita_iva: str):
    """Recupera un'azienda cliente tramite partita IVA normalizzata."""
    clean = normalize_partita_iva(partita_iva)
    return db.query(models.AziendaCliente).filter(
        models.AziendaCliente.partita_iva == clean
    ).first()


def find_partita_iva_conflict(
    db: Session,
    partita_iva: Optional[str],
    entity_type: str,
    entity_id: Optional[int] = None,
):
    """
    Cerca conflitti di partita IVA tra collaboratori e aziende clienti.

    entity_type:
    - "collaborator"
    - "azienda_cliente"
    """
    clean = normalize_partita_iva(partita_iva)
    if not clean:
        return None

    collaborator = get_collaborator_by_partita_iva(db, clean)
    if collaborator and not (entity_type == "collaborator" and collaborator.id == entity_id):
        return {
            "entity_type": "collaborator",
            "entity_id": collaborator.id,
            "message": f"Esiste già un collaboratore con partita IVA '{clean}'",
        }

    azienda = get_azienda_cliente_by_partita_iva(db, clean)
    if azienda and not (entity_type == "azienda_cliente" and azienda.id == entity_id):
        return {
            "entity_type": "azienda_cliente",
            "entity_id": azienda.id,
            "message": f"Esiste già un'azienda cliente con partita IVA '{clean}'",
        }

    return None

def get_collaborators(db: Session, skip: int = 0, limit: int = 100, search: Optional[str] = None, is_active: Optional[bool] = None):
    query = db.query(models.Collaborator)

    if search:
        search_term = f"%{search.lower()}%"
        query = query.filter(
            or_(
                func.lower(models.Collaborator.first_name).like(search_term),
                func.lower(models.Collaborator.last_name).like(search_term),
                func.lower(models.Collaborator.email).like(search_term),
                func.lower(models.Collaborator.position).like(search_term)
            )
        )

    if is_active is not None:
        query = query.filter(models.Collaborator.is_active == is_active)

    return query.order_by(models.Collaborator.last_name, models.Collaborator.first_name).offset(skip).limit(limit).all()

def get_collaborators_with_projects(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Collaborator).options(
        selectinload(models.Collaborator.projects),
        selectinload(models.Collaborator.assignments)
    ).filter(
        models.Collaborator.is_active == True
    ).offset(skip).limit(limit).all()

def get_collaborators_count(db: Session, search: Optional[str] = None, is_active: Optional[bool] = None):
    query = db.query(func.count(models.Collaborator.id))

    if search:
        search_term = f"%{search.lower()}%"
        query = query.filter(
            or_(
                func.lower(models.Collaborator.first_name).like(search_term),
                func.lower(models.Collaborator.last_name).like(search_term),
                func.lower(models.Collaborator.email).like(search_term)
            )
        )

    if is_active is not None:
        query = query.filter(models.Collaborator.is_active == is_active)

    return query.scalar()

def create_collaborator(db: Session, collaborator: schemas.CollaboratorCreate):
    # Versione MINIMALISTA - solo add, niente flush/commit
    db_collaborator = models.Collaborator(**collaborator.dict())
    db.add(db_collaborator)
    db.flush()
    _sync_agency_from_collaborator(db, db_collaborator)
    return db_collaborator

def update_collaborator(db: Session, collaborator_id: int, collaborator: schemas.CollaboratorUpdate):
    try:
        db_collaborator = db.query(models.Collaborator).filter(
            models.Collaborator.id == collaborator_id
        ).first()

        if not db_collaborator:
            logger.warning(f"Collaborator not found for update: {collaborator_id}")
            return None

        # Log modifiche
        update_data = collaborator.dict(exclude_unset=True)
        logger.info(f"Updating collaborator {collaborator_id}: {list(update_data.keys())}")

        # Verifica email duplicata se viene aggiornata
        if 'email' in update_data:
            existing = db.query(models.Collaborator).filter(
                func.lower(models.Collaborator.email) == update_data['email'].lower(),
                models.Collaborator.id != collaborator_id
            ).first()

            if existing:
                raise IntegrityError("Email già esistente", None, None)

        # Applica aggiornamenti
        for key, value in update_data.items():
            setattr(db_collaborator, key, value)

        db_collaborator.updated_at = func.now()
        _sync_agency_from_collaborator(db, db_collaborator)
        db.commit()
        db.refresh(db_collaborator)

        # Invalidate cache
        invalidate_collaborator_cache(collaborator_id)
        query_cache.clear()

        logger.info(f"Collaborator updated successfully: {collaborator_id}")
        return db_collaborator

    except IntegrityError as e:
        db.rollback()
        logger.warning(f"Integrity error updating collaborator {collaborator_id}: {e}")
        raise ValueError("Email già esistente")
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating collaborator {collaborator_id}: {e}")
        raise

def delete_collaborator(db: Session, collaborator_id: int):
    try:
        # Soft delete invece di hard delete
        db_collaborator = db.query(models.Collaborator).filter(
            models.Collaborator.id == collaborator_id
        ).first()

        if db_collaborator:
            db_collaborator.is_active = False
            _sync_agency_from_collaborator(db, db_collaborator)
            _sync_consultant_from_collaborator(db, db_collaborator)
            db_collaborator.updated_at = func.now()
            # Disattiva anche le assegnazioni attive del collaboratore
            db.query(models.Assignment).filter(
                models.Assignment.collaborator_id == collaborator_id,
                models.Assignment.is_active == True
            ).update({"is_active": False})
            db.commit()
            db.refresh(db_collaborator)
            logger.info(f"Soft deleted collaborator: {collaborator_id}")
        return db_collaborator
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting collaborator {collaborator_id}: {e}")
        raise


def _sync_agency_from_collaborator(db: Session, collaborator: models.Collaborator):
    linked_agency = (
        db.query(models.Agenzia)
        .filter(models.Agenzia.collaborator_id == collaborator.id)
        .first()
    )

    if collaborator.is_agency and collaborator.is_active:
        agency_name = " ".join(
            part for part in [collaborator.first_name, collaborator.last_name] if part
        ).strip() or collaborator.email

        if linked_agency is None:
            linked_agency = models.Agenzia(collaborator_id=collaborator.id)
            db.add(linked_agency)

        linked_agency.nome = agency_name
        linked_agency.partita_iva = collaborator.partita_iva
        linked_agency.email = collaborator.email
        linked_agency.telefono = collaborator.phone
        linked_agency.attivo = True

        note_parts = []
        if linked_agency.note:
            note_parts.append(linked_agency.note)
        else:
            note_parts.append("Auto-generata da collaboratore")
        if collaborator.position:
            note_parts.append(f"Ruolo: {collaborator.position}")
        if collaborator.city:
            note_parts.append(f"Citta: {collaborator.city}")
        linked_agency.note = " | ".join(dict.fromkeys(part for part in note_parts if part))
    elif linked_agency is not None:
        linked_agency.attivo = False


def _sync_consultant_from_collaborator(db: Session, collaborator: models.Collaborator):
    linked_consultant = (
        db.query(models.Consulente)
        .filter(models.Consulente.collaborator_id == collaborator.id)
        .first()
    )
    if linked_consultant is None:
        return
    if collaborator.is_consultant and collaborator.is_active:
        linked_consultant.attivo = True
    else:
        linked_consultant.attivo = False

def get_project(db: Session, project_id: int):
    return db.query(models.Project).options(
        joinedload(models.Project.avviso_rel)
    ).filter(models.Project.id == project_id).first()

def get_projects(db: Session, skip: int = 0, limit: int = 100, is_active: Optional[bool] = True):
    query = db.query(models.Project).options(joinedload(models.Project.avviso_rel))
    if is_active is not None:
        query = query.filter(models.Project.is_active == is_active)
    return query.offset(skip).limit(limit).all()


def get_project_full_context(db: Session, project_id: int) -> Optional[schemas.ProjectFullContext]:
    project = (
        db.query(models.Project)
        .options(
            joinedload(models.Project.ente_attuatore),
            selectinload(models.Project.piani_finanziari).selectinload(models.PianoFinanziario.voci),
        )
        .filter(models.Project.id == project_id)
        .first()
    )
    if not project:
        return None

    # Aggregazione ore collaboratori senza N+1:
    # 1) subquery assegnazioni aggregate
    # 2) subquery presenze aggregate
    assignment_hours_subq = (
        db.query(
            models.Assignment.collaborator_id.label("collaborator_id"),
            func.sum(models.Assignment.assigned_hours).label("assigned_hours"),
            func.sum(models.Assignment.completed_hours).label("completed_hours"),
        )
        .filter(
            models.Assignment.project_id == project_id,
            models.Assignment.is_active == True,
        )
        .group_by(models.Assignment.collaborator_id)
        .subquery()
    )

    attendance_hours_subq = (
        db.query(
            models.Assignment.collaborator_id.label("collaborator_id"),
            func.sum(models.Attendance.hours).label("attendance_hours"),
        )
        .join(models.Attendance, models.Attendance.assignment_id == models.Assignment.id)
        .filter(
            models.Assignment.project_id == project_id,
            models.Assignment.is_active == True,
        )
        .group_by(models.Assignment.collaborator_id)
        .subquery()
    )

    collaborator_rows = (
        db.query(
            models.Collaborator.id.label("collaborator_id"),
            models.Collaborator.first_name,
            models.Collaborator.last_name,
            func.coalesce(assignment_hours_subq.c.assigned_hours, 0.0).label("assigned_hours"),
            func.coalesce(assignment_hours_subq.c.completed_hours, 0.0).label("completed_hours"),
            func.coalesce(attendance_hours_subq.c.attendance_hours, 0.0).label("attendance_hours"),
        )
        .join(assignment_hours_subq, assignment_hours_subq.c.collaborator_id == models.Collaborator.id)
        .outerjoin(attendance_hours_subq, attendance_hours_subq.c.collaborator_id == models.Collaborator.id)
        .order_by(models.Collaborator.last_name, models.Collaborator.first_name)
        .all()
    )

    active_piani_context = []
    for piano in sorted(project.piani_finanziari, key=lambda x: (x.anno, x.id), reverse=True):
        riepilogo = build_piano_finanziario_riepilogo(piano, db=db)
        totale_preventivo = float(riepilogo.get("totale_preventivo") or 0.0)
        totale_consuntivo = float(riepilogo.get("totale_consuntivo") or 0.0)
        usage = (totale_consuntivo / totale_preventivo * 100.0) if totale_preventivo > 0 else 0.0
        active_piani_context.append(
            schemas.PianoFinanziarioContextItem(
                id=piano.id,
                anno=piano.anno,
                ente_erogatore=piano.ente_erogatore,
                avviso=(piano.avviso_rel.codice if getattr(piano, "avviso_rel", None) else piano.avviso),
                totale_consuntivo=round(totale_consuntivo, 2),
                totale_preventivo=round(totale_preventivo, 2),
                budget_usage_percentage=round(usage, 2),
                is_warning_90_budget=usage >= 90.0,
            )
        )

    collaborator_hours = [
        schemas.ProjectCollaboratorHoursContext(
            collaborator_id=row.collaborator_id,
            collaborator_name=f"{row.first_name} {row.last_name}".strip(),
            assigned_hours=float(row.assigned_hours or 0.0),
            completed_hours=float(row.completed_hours or 0.0),
            attendance_hours=float(row.attendance_hours or 0.0),
        )
        for row in collaborator_rows
    ]

    return schemas.ProjectFullContext(
        project=schemas.Project.model_validate(project),
        implementing_entity=schemas.ImplementingEntity.model_validate(project.ente_attuatore) if project.ente_attuatore else None,
        active_piani_finanziari=active_piani_context,
        collaborator_hours=collaborator_hours,
        generated_at=datetime.utcnow(),
    )

def _get_project_financial_template_or_raise(db: Session, template_id: int):
    template = db.query(models.ContractTemplate).filter(
        models.ContractTemplate.id == template_id
    ).first()
    if not template:
        raise ValueError("Template piano finanziario non trovato")
    if not template.is_active:
        raise ValueError("Il template piano finanziario selezionato è disattivato")
    if template.ambito_template != "piano_finanziario":
        raise ValueError("Il template selezionato non è un template piano finanziario")
    if not _normalize_optional_text(template.ente_erogatore):
        raise ValueError("Il template piano finanziario selezionato non ha ente erogatore valorizzato")
    return template


def _apply_project_financial_template(db: Session, payload: Dict[str, Any], template_id: Optional[int]):
    if template_id is None:
        payload["template_piano_finanziario_id"] = None
        return payload

    template = _get_project_financial_template_or_raise(db, template_id)
    ente_erogatore = _normalize_optional_text(template.ente_erogatore)
    selected_avviso = None
    requested_avviso_id = payload.get("avviso_id")
    requested_avviso_code = _normalize_optional_text(payload.get("avviso"))

    if requested_avviso_id is not None:
        selected_avviso = db.query(models.Avviso).filter(
            models.Avviso.id == requested_avviso_id,
            models.Avviso.template_id == template.id,
            models.Avviso.is_active == True,
        ).first()

    if selected_avviso is None and requested_avviso_code:
        selected_avviso = db.query(models.Avviso).filter(
            models.Avviso.codice == requested_avviso_code,
            models.Avviso.template_id == template.id,
            models.Avviso.is_active == True,
        ).order_by(models.Avviso.id.desc()).first()

    linked_avviso = selected_avviso or db.query(models.Avviso).filter(
        models.Avviso.template_id == template.id,
        models.Avviso.is_active == True,
    ).order_by(models.Avviso.id.desc()).first()
    avviso = _normalize_optional_text(linked_avviso.codice if linked_avviso else template.avviso)
    payload["template_piano_finanziario_id"] = template.id
    payload["ente_erogatore"] = ente_erogatore
    payload["avviso"] = avviso
    payload["avviso_id"] = linked_avviso.id if linked_avviso else payload.get("avviso_id")
    return payload

def create_project(db: Session, project: schemas.ProjectCreateExtended):
    payload = project.dict()
    avviso_pf_id = payload.get("avviso_pf_id")
    template_id = payload.get("template_piano_finanziario_id")
    payload = _apply_project_financial_template(db, payload, template_id)
    db_project = models.Project(**payload)
    db.add(db_project)
    db.flush()

    if avviso_pf_id:
        _auto_create_piano_from_avviso_pf(db, db_project, avviso_pf_id)

    return db_project


def _auto_create_piano_from_avviso_pf(db: Session, project: models.Project, avviso_pf_id: int) -> Optional[models.PianoFinanziario]:
    """Crea automaticamente un PianoFinanziario dal AvvisoPianoFinanziario collegato."""
    from piano_finanziario_config import build_default_voci

    avviso = db.query(models.AvvisoPianoFinanziario).filter(
        models.AvvisoPianoFinanziario.id == avviso_pf_id,
    ).first()
    if not avviso:
        return None

    template = avviso.template
    if not template:
        return None

    now = datetime.now()
    data_inizio = project.start_date or now
    data_fine = project.end_date or now.replace(year=now.year + 1)
    if data_fine <= data_inizio:
        data_fine = data_inizio.replace(year=data_inizio.year + 1)

    piano = models.PianoFinanziario(
        progetto_id=project.id,
        template_id=template.id,
        avviso_id=avviso.id,
        nome=f"Piano Finanziario - {avviso.titolo}",
        tipo_fondo=template.tipo_fondo,
        budget_totale=0.0,
        budget_approvato=0.0,
        budget_utilizzato=0.0,
        budget_rimanente=0.0,
        data_inizio=data_inizio,
        data_fine=data_fine,
        stato="bozza",
        ente_erogatore=project.ente_erogatore or template.tipo_fondo,
        anno=data_inizio.year,
    )
    db.add(piano)
    db.flush()

    for row in build_default_voci():
        db.add(models.VocePianoFinanziario(piano_id=piano.id, **row))

    return piano

def update_project(db: Session, project_id: int, project: schemas.ProjectUpdateExtended):
    db_project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if db_project:
        update_data = project.dict(exclude_unset=True)
        if "template_piano_finanziario_id" in update_data:
            update_data = _apply_project_financial_template(db, update_data, update_data.get("template_piano_finanziario_id"))
        elif db_project.template_piano_finanziario_id:
            update_data = _apply_project_financial_template(db, update_data, db_project.template_piano_finanziario_id)
        for key, value in update_data.items():
            setattr(db_project, key, value)
        db.commit()
        db.refresh(db_project)
    return db_project

def delete_project(db: Session, project_id: int):
    db_project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if db_project:
        db_project.is_active = False
        # Disattiva anche le mansioni ente collegate al progetto
        db.query(models.ProgettoMansioneEnte).filter(
            models.ProgettoMansioneEnte.progetto_id == project_id
        ).update({"is_active": False})
        db.commit()
        db.refresh(db_project)
    return db_project


def get_avviso(db: Session, avviso_id: int):
    return db.query(models.Avviso).filter(models.Avviso.id == avviso_id).first()


def get_avvisi(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    ente_erogatore: Optional[str] = None,
    active_only: bool = True,
):
    query = db.query(models.Avviso)
    if ente_erogatore:
        query = query.filter(models.Avviso.ente_erogatore == ente_erogatore)
    if active_only:
        query = query.filter(models.Avviso.is_active.is_(True))
    return query.order_by(models.Avviso.ente_erogatore.asc(), models.Avviso.codice.asc()).offset(skip).limit(limit).all()


def create_avviso(db: Session, avviso: schemas.AvvisoCreate):
    payload = avviso.model_dump()
    db_avviso = models.Avviso(**payload)
    db.add(db_avviso)
    db.commit()
    db.refresh(db_avviso)
    return db_avviso


def update_avviso(db: Session, avviso_id: int, avviso: schemas.AvvisoUpdate):
    db_avviso = get_avviso(db, avviso_id)
    if not db_avviso:
        return None
    update_data = avviso.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_avviso, key, value)
    db.commit()
    db.refresh(db_avviso)
    return db_avviso


def delete_avviso(db: Session, avviso_id: int):
    db_avviso = get_avviso(db, avviso_id)
    if not db_avviso:
        return None
    db_avviso.is_active = False
    db.commit()
    db.refresh(db_avviso)
    return db_avviso


def assign_collaborator_to_project(db: Session, collaborator_id: int, project_id: int):
    collaborator = get_collaborator(db, collaborator_id)
    project = get_project(db, project_id)
    if collaborator and project:
        if project not in collaborator.projects:
            collaborator.projects.append(project)
            db.commit()
            db.refresh(collaborator)
    return collaborator

def remove_collaborator_from_project(db: Session, collaborator_id: int, project_id: int):
    collaborator = get_collaborator(db, collaborator_id)
    project = get_project(db, project_id)
    if collaborator and project:
        if project in collaborator.projects:
            collaborator.projects.remove(project)
            db.commit()
            db.refresh(collaborator)
    return collaborator

def get_attendance(db: Session, attendance_id: int):
    return db.query(models.Attendance).filter(models.Attendance.id == attendance_id).first()

def get_attendances(db: Session, skip: int = 0, limit: int = 100,
                   collaborator_id: Optional[int] = None,
                   project_id: Optional[int] = None,
                   start_date: Optional[datetime] = None,
                   end_date: Optional[datetime] = None,
                   include_details: bool = False):

    query = db.query(models.Attendance)

    # Eager loading per evitare N+1 queries
    if include_details:
        query = query.options(
            joinedload(models.Attendance.collaborator),
            joinedload(models.Attendance.project)
        )

    # Filtri ottimizzati
    if collaborator_id:
        query = query.filter(models.Attendance.collaborator_id == collaborator_id)
    if project_id:
        query = query.filter(models.Attendance.project_id == project_id)

    # Filtri di data con indici
    if start_date and end_date:
        query = query.filter(
            models.Attendance.date.between(start_date, end_date)
        )
    elif start_date:
        query = query.filter(models.Attendance.date >= start_date)
    elif end_date:
        query = query.filter(models.Attendance.date <= end_date)

    # Ordinamento per performance
    query = query.order_by(desc(models.Attendance.date), desc(models.Attendance.start_time))

    return query.offset(skip).limit(limit).all()

def get_attendances_summary(db: Session, start_date: datetime, end_date: datetime):
    """Ottieni statistiche aggregate delle presenze"""
    return db.query(
        models.Attendance.collaborator_id,
        models.Attendance.project_id,
        func.sum(models.Attendance.hours).label('total_hours'),
        func.count(models.Attendance.id).label('total_sessions'),
        func.avg(models.Attendance.hours).label('avg_hours_per_session')
    ).filter(
        models.Attendance.date.between(start_date, end_date)
    ).group_by(
        models.Attendance.collaborator_id,
        models.Attendance.project_id
    ).all()

def get_monthly_stats(db: Session, year: int, month: int):
    """Ottieni statistiche mensili con una sola query"""
    start_date = datetime(year, month, 1)
    if month == 12:
        end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        end_date = datetime(year, month + 1, 1) - timedelta(days=1)

    return db.query(
        func.extract('day', models.Attendance.date).label('day'),
        func.sum(models.Attendance.hours).label('total_hours'),
        func.count(models.Attendance.id).label('total_attendances')
    ).filter(
        models.Attendance.date.between(start_date, end_date)
    ).group_by(
        func.extract('day', models.Attendance.date)
    ).order_by('day').all()


def _as_day(value: datetime | date) -> date:
    if isinstance(value, datetime):
        return value.date()
    return value


def _create_audit_log(
    db: Session,
    *,
    entity: str,
    action: str,
    old_value: Optional[dict[str, Any]],
    new_value: Optional[dict[str, Any]],
    user_id: Optional[int] = None,
) -> None:
    log = models.AuditLog(
        entity=entity,
        action=action,
        old_value=json.dumps(old_value, default=str) if old_value is not None else None,
        new_value=json.dumps(new_value, default=str) if new_value is not None else None,
        user_id=user_id,
    )
    db.add(log)


def _validate_assignment_date_overlap_by_ente(
    db: Session,
    *,
    collaborator_id: int,
    project_id: int,
    start_date: datetime,
    end_date: datetime,
    exclude_assignment_id: Optional[int] = None,
) -> None:
    current_project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not current_project:
        raise ValueError("Progetto non trovato")

    query = (
        db.query(models.Assignment, models.Project)
        .join(models.Project, models.Project.id == models.Assignment.project_id)
        .filter(
            models.Assignment.collaborator_id == collaborator_id,
            models.Assignment.is_active == True,
            models.Assignment.start_date <= end_date,
            models.Assignment.end_date >= start_date,
            models.Assignment.project_id != project_id,
        )
    )
    if exclude_assignment_id is not None:
        query = query.filter(models.Assignment.id != exclude_assignment_id)

    overlaps = query.all()
    for existing_assignment, existing_project in overlaps:
        if existing_project.ente_attuatore_id != current_project.ente_attuatore_id:
            raise ValueError(
                "Conflitto cross-progetto: il collaboratore ha già una assegnazione attiva "
                f"sovrapposta su ente diverso (assignment_id={existing_assignment.id}, "
                f"progetto_id={existing_assignment.project_id})."
            )


def _validate_attendance_assignment_date_range(
    db: Session,
    *,
    collaborator_id: int,
    project_id: int,
    assignment_id: Optional[int],
    attendance_day: date,
) -> None:
    if assignment_id is not None:
        assignment = db.query(models.Assignment).filter(
            models.Assignment.id == assignment_id,
            models.Assignment.is_active == True,
        ).first()
        if not assignment:
            raise ValueError("Assegnazione non trovata o non attiva")
        if assignment.collaborator_id != collaborator_id or assignment.project_id != project_id:
            raise ValueError("L'assegnazione indicata non appartiene al collaboratore/progetto selezionato")

        assignment_start = _as_day(assignment.start_date)
        assignment_end = _as_day(assignment.end_date)
        if attendance_day < assignment_start or attendance_day > assignment_end:
            raise ValueError(
                f"La data presenza ({attendance_day.strftime('%d/%m/%Y')}) è fuori dal range assegnazione "
                f"({assignment_start.strftime('%d/%m/%Y')} - {assignment_end.strftime('%d/%m/%Y')})"
            )


def check_attendance_overlap(
    db: Session,
    collaborator_id: int,
    start_time: datetime,
    end_time: datetime,
    exclude_attendance_id: Optional[int] = None,
    project_id: Optional[int] = None,
    assignment_id: Optional[int] = None,
) -> Optional[models.Attendance]:
    """
    Verifica se esiste una sovrapposizione oraria per un collaboratore.

    Un collaboratore NON può essere presente nello stesso orario:
    - Con due mansioni sullo stesso progetto
    - Con due progetti diversi

    Due intervalli temporali [A_start, A_end] e [B_start, B_end] si sovrappongono se:
    A_start < B_end AND A_end > B_start

    Args:
        db: Sessione database
        collaborator_id: ID del collaboratore
        start_time: Ora di inizio della nuova presenza
        end_time: Ora di fine della nuova presenza
        exclude_attendance_id: ID della presenza da escludere (per update)

    Returns:
        La presenza sovrapposta se trovata, altrimenti None
    """
    # Costruisci query per trovare sovrapposizioni su attendances
    query = db.query(models.Attendance).filter(
        models.Attendance.collaborator_id == collaborator_id,
        # Sovrapposizione: start_time < existing.end_time AND end_time > existing.start_time
        models.Attendance.start_time < end_time,
        models.Attendance.end_time > start_time
    )

    # Escludi la presenza stessa se stiamo facendo un update
    if exclude_attendance_id:
        query = query.filter(models.Attendance.id != exclude_attendance_id)

    overlapping = query.first()

    # Validazione aggiuntiva su ASSIGNMENTS:
    # intercetta conflitti cross-progetto/cross-ente nella stessa finestra temporale.
    if project_id is not None:
        current_project = db.query(models.Project).filter(models.Project.id == project_id).first()
        if not current_project:
            raise ValueError("Progetto non trovato")

        assignment_query = db.query(models.Assignment).filter(
            models.Assignment.collaborator_id == collaborator_id,
            models.Assignment.is_active == True,
            models.Assignment.start_date <= end_time,
            models.Assignment.end_date >= start_time,
        )
        overlapping_assignments = assignment_query.all()

        # Se viene dichiarata una assignment specifica, deve essere effettivamente attiva
        # nella finestra oraria richiesta.
        if assignment_id is not None:
            has_target_assignment = any(a.id == assignment_id for a in overlapping_assignments)
            if not has_target_assignment:
                raise ValueError(
                    "L'assegnazione indicata non è attiva nella finestra temporale della presenza"
                )

        project_ids = {a.project_id for a in overlapping_assignments if a.project_id is not None}
        if project_ids:
            projects_by_id = {
                project.id: project
                for project in db.query(models.Project).filter(models.Project.id.in_(project_ids)).all()
            }
            for existing_assignment in overlapping_assignments:
                existing_project = projects_by_id.get(existing_assignment.project_id)
                if not existing_project:
                    continue
                if existing_project.id == project_id:
                    continue
                if existing_project.ente_attuatore_id != current_project.ente_attuatore_id:
                    raise ValueError(
                        "Conflitto cross-progetto: il collaboratore ha già una assegnazione attiva "
                        f"sovrapposta su ente diverso (assignment_id={existing_assignment.id}, "
                        f"progetto_id={existing_assignment.project_id})."
                    )

        _validate_assignment_date_overlap_by_ente(
            db,
            collaborator_id=collaborator_id,
            project_id=project_id,
            start_date=start_time,
            end_date=end_time,
            exclude_assignment_id=assignment_id,
        )

    if overlapping:
        logger.warning(
            f"Sovrapposizione oraria rilevata per collaboratore {collaborator_id}: "
            f"Nuova presenza [{start_time} - {end_time}] sovrapposta con "
            f"presenza esistente ID {overlapping.id} [{overlapping.start_time} - {overlapping.end_time}]"
        )

    return overlapping


def check_assignment_overlap(
    db: Session,
    collaborator_id: int,
    start_date,
    end_date,
    project_id: int,
    exclude_assignment_id: Optional[int] = None,
) -> Optional[models.Assignment]:
    """
    Verifica se esiste una sovrapposizione di date per un collaboratore su progetti diversi.

    Un collaboratore PUÒ avere più assegnazioni sullo stesso progetto (ruoli diversi).
    NON PUÒ avere assegnazioni su progetti diversi che si sovrappongono nel tempo.

    Due intervalli [A_start, A_end] e [B_start, B_end] si sovrappongono se:
    A_start < B_end AND A_end > B_start

    Args:
        db: Sessione database
        collaborator_id: ID del collaboratore
        start_date: Data di inizio della nuova assegnazione
        end_date: Data di fine della nuova assegnazione
        project_id: ID del progetto della nuova assegnazione (escluso dal controllo)
        exclude_assignment_id: ID dell'assegnazione da escludere (per update)

    Returns:
        La prima assegnazione sovrapposta trovata su un progetto diverso, altrimenti None
    """
    query = db.query(models.Assignment).filter(
        models.Assignment.collaborator_id == collaborator_id,
        models.Assignment.is_active == True,
        # Escludi stesso progetto: ruoli diversi sullo stesso progetto sono permessi
        models.Assignment.project_id != project_id,
        # Sovrapposizione: start_date < existing.end_date AND end_date > existing.start_date
        models.Assignment.start_date < end_date,
        models.Assignment.end_date > start_date,
    )

    if exclude_assignment_id:
        query = query.filter(models.Assignment.id != exclude_assignment_id)

    overlapping = query.first()

    if overlapping:
        logger.warning(
            f"Sovrapposizione assegnazione rilevata per collaboratore {collaborator_id}: "
            f"Nuova assegnazione [{start_date} - {end_date}] su progetto {project_id} sovrapposta con "
            f"assegnazione esistente ID {overlapping.id} [{overlapping.start_date} - {overlapping.end_date}] "
            f"su progetto {overlapping.project_id}"
        )

    return overlapping


def validate_attendance_in_assignment_range(
    db: Session,
    attendance_date,
    assignment_id: int,
) -> bool:
    """
    Verifica che la data di una presenza rientri nel periodo dell'assegnazione collegata.

    Args:
        db: Sessione database
        attendance_date: Data della presenza (date o datetime)
        assignment_id: ID dell'assegnazione di riferimento

    Returns:
        True se la data è nel range dell'assegnazione

    Raises:
        ValueError: Se l'assegnazione non esiste, non è attiva, o la data è fuori range
    """
    assignment = get_assignment(db, assignment_id)
    if not assignment:
        raise ValueError(f"Assegnazione ID {assignment_id} non trovata.")
    if not assignment.is_active:
        raise ValueError(f"Assegnazione ID {assignment_id} non è attiva.")

    # Normalizza tutto a date per il confronto
    from datetime import date as date_type, datetime as datetime_type
    if isinstance(attendance_date, datetime_type):
        att_date = attendance_date.date()
    else:
        att_date = attendance_date

    start = assignment.start_date.date() if isinstance(assignment.start_date, datetime_type) else assignment.start_date
    end = assignment.end_date.date() if isinstance(assignment.end_date, datetime_type) else assignment.end_date

    if att_date < start or att_date > end:
        raise ValueError(
            f"La data della presenza ({att_date.strftime('%d/%m/%Y')}) non rientra nel periodo "
            f"dell'assegnazione ({start.strftime('%d/%m/%Y')} - {end.strftime('%d/%m/%Y')})"
        )

    return True


def create_attendance(db: Session, attendance: schemas.AttendanceCreate):
    try:
        # VALIDAZIONE SOVRAPPOSIZIONI ORARIE
        # Verifica che il collaboratore non sia già presente nello stesso orario
        overlapping = check_attendance_overlap(
            db,
            attendance.collaborator_id,
            attendance.start_time,
            attendance.end_time,
            project_id=attendance.project_id,
            assignment_id=attendance.assignment_id,
        )

        if overlapping:
            # Ottieni informazioni dettagliate per messaggio d'errore
            collaborator = db.query(models.Collaborator).filter(
                models.Collaborator.id == attendance.collaborator_id
            ).first()

            existing_project = db.query(models.Project).filter(
                models.Project.id == overlapping.project_id
            ).first()

            new_project = db.query(models.Project).filter(
                models.Project.id == attendance.project_id
            ).first()

            # Costruisci messaggio d'errore dettagliato
            if overlapping.project_id == attendance.project_id:
                # Stessa presenza, progetto diverso (o stessa mansione)
                error_msg = (
                    f"Il collaboratore {collaborator.first_name} {collaborator.last_name} "
                    f"è già presente sul progetto '{existing_project.name}' "
                    f"nell'orario [{overlapping.start_time.strftime('%H:%M')} - {overlapping.end_time.strftime('%H:%M')}]. "
                    f"Un collaboratore può essere presente una sola volta in un determinato orario."
                )
            else:
                # Progetti diversi
                error_msg = (
                    f"Il collaboratore {collaborator.first_name} {collaborator.last_name} "
                    f"è già impegnato sul progetto '{existing_project.name}' "
                    f"nell'orario [{overlapping.start_time.strftime('%H:%M')} - {overlapping.end_time.strftime('%H:%M')}]. "
                    f"Non può essere presente contemporaneamente su '{new_project.name}'. "
                    f"Un collaboratore può essere presente una sola volta in un determinato orario."
                )

            raise ValueError(error_msg)

        if attendance.assignment_id:
            validate_attendance_in_assignment_range(db, attendance.date, attendance.assignment_id)

        # Calcolo automatico delle ore se non fornito
        attendance_data = attendance.dict()
        if not attendance_data.get('hours'):
            start = attendance_data['start_time']
            end = attendance_data['end_time']
            attendance_data['hours'] = (end - start).total_seconds() / 3600

        # Ottieni e normalizza la data della presenza
        presenza_date = attendance_data['date']
        if isinstance(presenza_date, str):
            from datetime import datetime as dt
            presenza_date = dt.fromisoformat(presenza_date)
        presenza_day = presenza_date.date() if hasattr(presenza_date, 'date') else presenza_date

        # Validazione periodo di attività dell'assegnazione collegata
        if attendance_data.get('assignment_id'):
            _validate_attendance_assignment_date_range(
                db,
                collaborator_id=attendance_data['collaborator_id'],
                project_id=attendance_data['project_id'],
                assignment_id=attendance_data['assignment_id'],
                attendance_day=presenza_day,
            )
            assignment = db.query(models.Assignment).filter(
                models.Assignment.id == attendance_data['assignment_id']
            ).first()
            ore_completate = assignment.completed_hours or 0
            ore_assegnate = assignment.assigned_hours
            ore_rimanenti = ore_assegnate - ore_completate
            if attendance_data['hours'] > ore_rimanenti:
                raise ValueError(
                    f"Le ore inserite ({attendance_data['hours']}h) superano le ore rimanenti "
                    f"({ore_rimanenti}h) per questa mansione"
                )
        else:
            # Nessuna assegnazione selezionata: cerca se ne esistono per questo collaboratore/progetto
            active_assignments = db.query(models.Assignment).filter(
                models.Assignment.collaborator_id == attendance_data['collaborator_id'],
                models.Assignment.project_id == attendance_data['project_id'],
                models.Assignment.is_active == True
            ).all()

            if active_assignments:
                # La data deve rientrare in almeno una delle assegnazioni attive
                dentro = any(
                    (a.start_date.date() if hasattr(a.start_date, 'date') else a.start_date) <= presenza_day <=
                    (a.end_date.date() if hasattr(a.end_date, 'date') else a.end_date)
                    for a in active_assignments
                )
                if not dentro:
                    periodi = ', '.join(
                        f"dal {(a.start_date.date() if hasattr(a.start_date, 'date') else a.start_date).strftime('%d/%m/%Y')} "
                        f"al {(a.end_date.date() if hasattr(a.end_date, 'date') else a.end_date).strftime('%d/%m/%Y')}"
                        for a in active_assignments
                    )
                    raise ValueError(
                        f"La data della presenza ({presenza_day.strftime('%d/%m/%Y')}) è fuori dal periodo "
                        f"di attività dell'assegnazione ({periodi})"
                    )

        db_attendance = models.Attendance(**attendance_data)
        db.add(db_attendance)
        db.commit()
        db.refresh(db_attendance)

        # Aggiorna statistiche dell'assegnazione se presente
        if db_attendance.assignment_id:
            update_assignment_progress(db, db_attendance.assignment_id)
            try:
                voce = get_voce_by_assignment(db, db_attendance.assignment_id)
                if voce:
                    aggiorna_voce_da_presenze(db, voce.id)
            except Exception as exc:
                logger.warning(f"Impossibile aggiornare voce piano da presenza {db_attendance.id}: {exc}")

        logger.info(f"Created attendance: {db_attendance.id}")
        return db_attendance
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating attendance: {e}")
        raise

def update_assignment_progress(db: Session, assignment_id: int):
    """Aggiorna il progresso dell'assegnazione basato sulle ore effettivamente lavorate"""
    try:
        assignment = db.query(models.Assignment).filter(
            models.Assignment.id == assignment_id,
            models.Assignment.is_active == True
        ).first()

        if assignment:
            # Somma SOLO le ore delle presenze collegate a questa specifica assegnazione
            total_hours = db.query(func.sum(models.Attendance.hours)).filter(
                models.Attendance.assignment_id == assignment_id
            ).scalar() or 0

            assignment.completed_hours = total_hours
            assignment.progress_percentage = min(100, (total_hours / assignment.assigned_hours) * 100)
            db.commit()
            logger.info(f"Updated assignment {assignment_id}: {total_hours}h completed out of {assignment.assigned_hours}h")
    except Exception as e:
        logger.error(f"Error updating assignment progress: {e}")

def update_attendance(db: Session, attendance_id: int, attendance: schemas.AttendanceUpdate):
    db_attendance = db.query(models.Attendance).filter(models.Attendance.id == attendance_id).first()
    if db_attendance:
        old_assignment_id = db_attendance.assignment_id
        old_hours = db_attendance.hours
        update_data = attendance.dict(exclude_unset=True)

        # VALIDAZIONE SOVRAPPOSIZIONI ORARIE
        # Verifica sovrapposizioni se cambiano gli orari o il collaboratore
        new_start_time = update_data.get('start_time', db_attendance.start_time)
        new_end_time = update_data.get('end_time', db_attendance.end_time)
        new_collaborator_id = update_data.get('collaborator_id', db_attendance.collaborator_id)

        # Controlla solo se cambiano orari o collaboratore
        if (new_start_time != db_attendance.start_time or
            new_end_time != db_attendance.end_time or
            new_collaborator_id != db_attendance.collaborator_id):

            overlapping = check_attendance_overlap(
                db,
                new_collaborator_id,
                new_start_time,
                new_end_time,
                exclude_attendance_id=attendance_id,  # Escludi la presenza stessa
                project_id=update_data.get('project_id', db_attendance.project_id),
                assignment_id=update_data.get('assignment_id', db_attendance.assignment_id),
            )

            if overlapping:
                # Ottieni informazioni dettagliate per messaggio d'errore
                collaborator = db.query(models.Collaborator).filter(
                    models.Collaborator.id == new_collaborator_id
                ).first()

                existing_project = db.query(models.Project).filter(
                    models.Project.id == overlapping.project_id
                ).first()

                new_project_id = update_data.get('project_id', db_attendance.project_id)
                new_project = db.query(models.Project).filter(
                    models.Project.id == new_project_id
                ).first()

                # Costruisci messaggio d'errore dettagliato
                if overlapping.project_id == new_project_id:
                    # Stesso progetto
                    error_msg = (
                        f"Il collaboratore {collaborator.first_name} {collaborator.last_name} "
                        f"è già presente sul progetto '{existing_project.name}' "
                        f"nell'orario [{overlapping.start_time.strftime('%H:%M')} - {overlapping.end_time.strftime('%H:%M')}]. "
                        f"Un collaboratore può essere presente una sola volta in un determinato orario."
                    )
                else:
                    # Progetti diversi
                    error_msg = (
                        f"Il collaboratore {collaborator.first_name} {collaborator.last_name} "
                        f"è già impegnato sul progetto '{existing_project.name}' "
                        f"nell'orario [{overlapping.start_time.strftime('%H:%M')} - {overlapping.end_time.strftime('%H:%M')}]. "
                        f"Non può essere presente contemporaneamente su '{new_project.name}'. "
                        f"Un collaboratore può essere presente una sola volta in un determinato orario."
                    )

                raise ValueError(error_msg)

        # Validazione ore rimanenti e periodo di attività se cambiano le ore o l'assegnazione
        new_assignment_id = update_data.get('assignment_id', db_attendance.assignment_id)
        new_hours = update_data.get('hours', db_attendance.hours)
        new_date = update_data.get('date', db_attendance.date)

        # Normalizza la data
        if isinstance(new_date, str):
            from datetime import datetime as dt
            new_date = dt.fromisoformat(new_date)
        new_day = new_date.date() if hasattr(new_date, 'date') else new_date

        if new_assignment_id:
            _validate_attendance_assignment_date_range(
                db,
                collaborator_id=update_data.get('collaborator_id', db_attendance.collaborator_id),
                project_id=update_data.get('project_id', db_attendance.project_id),
                assignment_id=new_assignment_id,
                attendance_day=new_day,
            )
            assignment = db.query(models.Assignment).filter(
                models.Assignment.id == new_assignment_id
            ).first()
            ore_completate = assignment.completed_hours or 0
            ore_assegnate = assignment.assigned_hours

            # Se stiamo modificando la stessa assegnazione, sottrai le ore vecchie
            if new_assignment_id == old_assignment_id:
                ore_disponibili = ore_assegnate - ore_completate + old_hours
            else:
                ore_disponibili = ore_assegnate - ore_completate

            if new_hours > ore_disponibili:
                raise ValueError(
                    f"Le ore inserite ({new_hours}h) superano le ore disponibili "
                    f"({ore_disponibili}h) per questa mansione"
                )
        else:
            # Nessuna assegnazione: cerca se ne esistono per questo collaboratore/progetto
            new_collaborator_id = update_data.get('collaborator_id', db_attendance.collaborator_id)
            new_project_id = update_data.get('project_id', db_attendance.project_id)
            active_assignments = db.query(models.Assignment).filter(
                models.Assignment.collaborator_id == new_collaborator_id,
                models.Assignment.project_id == new_project_id,
                models.Assignment.is_active == True
            ).all()

            if active_assignments:
                dentro = any(
                    (a.start_date.date() if hasattr(a.start_date, 'date') else a.start_date) <= new_day <=
                    (a.end_date.date() if hasattr(a.end_date, 'date') else a.end_date)
                    for a in active_assignments
                )
                if not dentro:
                    periodi = ', '.join(
                        f"dal {(a.start_date.date() if hasattr(a.start_date, 'date') else a.start_date).strftime('%d/%m/%Y')} "
                        f"al {(a.end_date.date() if hasattr(a.end_date, 'date') else a.end_date).strftime('%d/%m/%Y')}"
                        for a in active_assignments
                    )
                    raise ValueError(
                        f"La data della presenza ({new_day.strftime('%d/%m/%Y')}) è fuori dal periodo "
                        f"di attività dell'assegnazione ({periodi})"
                    )

        for key, value in update_data.items():
            setattr(db_attendance, key, value)
        db.commit()
        db.refresh(db_attendance)

        # Aggiorna statistiche della vecchia assegnazione se è cambiata
        if old_assignment_id and old_assignment_id != db_attendance.assignment_id:
            update_assignment_progress(db, old_assignment_id)
            try:
                old_voce = get_voce_by_assignment(db, old_assignment_id)
                if old_voce:
                    aggiorna_voce_da_presenze(db, old_voce.id)
            except Exception as exc:
                logger.warning(f"Impossibile riallineare la vecchia voce piano dell'assegnazione {old_assignment_id}: {exc}")

        # Aggiorna statistiche della nuova assegnazione
        if db_attendance.assignment_id:
            update_assignment_progress(db, db_attendance.assignment_id)
            try:
                voce = get_voce_by_assignment(db, db_attendance.assignment_id)
                if voce:
                    aggiorna_voce_da_presenze(db, voce.id)
            except Exception as exc:
                logger.warning(f"Impossibile aggiornare la voce piano per l'assegnazione {db_attendance.assignment_id}: {exc}")

    return db_attendance

def delete_attendance(db: Session, attendance_id: int):
    db_attendance = db.query(models.Attendance).filter(models.Attendance.id == attendance_id).first()
    if db_attendance:
        assignment_id = db_attendance.assignment_id
        db.delete(db_attendance)
        db.commit()

        # Aggiorna statistiche dell'assegnazione dopo la cancellazione
        if assignment_id:
            update_assignment_progress(db, assignment_id)

    return db_attendance

# ==========================================
# FUNZIONI CRUD PER ASSIGNMENT (ASSEGNAZIONI DETTAGLIATE)
# ==========================================

def get_dashboard_metrics(db: Session, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None):
    """Ottieni metriche per dashboard con una sola query complessa"""
    if not start_date:
        start_date = datetime.now() - timedelta(days=30)
    if not end_date:
        end_date = datetime.now()

    # Query complessa per tutte le metriche
    base_query = db.query(
        func.count(func.distinct(models.Attendance.collaborator_id)).label('active_collaborators'),
        func.count(func.distinct(models.Attendance.project_id)).label('active_projects'),
        func.sum(models.Attendance.hours).label('total_hours'),
        func.avg(models.Attendance.hours).label('avg_hours_per_session'),
        func.count(models.Attendance.id).label('total_sessions')
    ).filter(
        models.Attendance.date.between(start_date, end_date)
    )

    return base_query.first()

def get_performance_bottlenecks(db: Session):
    """Identifica potenziali colli di bottiglia nelle performance"""
    # Query per identificare collaboratori sovraccarichi
    overloaded_collaborators = db.query(
        models.Collaborator.id,
        models.Collaborator.first_name,
        models.Collaborator.last_name,
        func.sum(models.Assignment.assigned_hours).label('total_assigned_hours'),
        func.sum(models.Assignment.completed_hours).label('total_completed_hours')
    ).join(
        models.Assignment
    ).filter(
        models.Assignment.is_active == True
    ).group_by(
        models.Collaborator.id
    ).having(
        func.sum(models.Assignment.assigned_hours) > 40  # Più di 40 ore a settimana
    ).all()

    return {
        'overloaded_collaborators': overloaded_collaborators,
        'timestamp': datetime.now()
    }

def get_assignment(db: Session, assignment_id: int):
    return db.query(models.Assignment).filter(models.Assignment.id == assignment_id).first()

def get_assignments(db: Session, skip: int = 0, limit: int = 100, is_active: Optional[bool] = True):
    query = db.query(models.Assignment)
    if is_active is not None:
        query = query.filter(models.Assignment.is_active == is_active)
    return query.offset(skip).limit(limit).all()

def get_assignments_by_collaborator(db: Session, collaborator_id: int, include_inactive: bool = False):
    query = db.query(models.Assignment).options(
        joinedload(models.Assignment.project)
    ).filter(models.Assignment.collaborator_id == collaborator_id)

    if not include_inactive:
        query = query.filter(models.Assignment.is_active == True)

    return query.order_by(desc(models.Assignment.start_date)).all()

def get_assignments_by_project(db: Session, project_id: int, include_inactive: bool = False):
    query = db.query(models.Assignment).options(
        joinedload(models.Assignment.collaborator)
    ).filter(models.Assignment.project_id == project_id)

    if not include_inactive:
        query = query.filter(models.Assignment.is_active == True)

    return query.order_by(models.Assignment.role, models.Assignment.start_date).all()

def get_active_assignments(db: Session, date: Optional[datetime] = None):
    """Ottieni tutte le assegnazioni attive per una data specifica"""
    if not date:
        date = datetime.now()

    return db.query(models.Assignment).options(
        joinedload(models.Assignment.collaborator),
        joinedload(models.Assignment.project)
    ).filter(
        models.Assignment.is_active == True,
        models.Assignment.start_date <= date,
        models.Assignment.end_date >= date
    ).all()

def bulk_update_assignments(db: Session, assignment_updates: List[Dict[str, Any]]):
    """Aggiornamento bulk per performance"""
    try:
        for update in assignment_updates:
            assignment_id = update.pop('id')
            db.query(models.Assignment).filter(
                models.Assignment.id == assignment_id
            ).update(update)

        db.commit()
        logger.info(f"Bulk updated {len(assignment_updates)} assignments")
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"Error in bulk update: {e}")
        raise

def get_assignment_by_collaborator_and_project(db: Session, collaborator_id: int, project_id: int):
    return db.query(models.Assignment).filter(
        models.Assignment.collaborator_id == collaborator_id,
        models.Assignment.project_id == project_id
    ).first()

def create_assignment(db: Session, assignment: schemas.AssignmentCreate):
    """
    Crea assegnazione senza commit (gestito dal chiamante)
    """
    try:
        overlapping = check_assignment_overlap(
            db,
            collaborator_id=assignment.collaborator_id,
            start_date=assignment.start_date,
            end_date=assignment.end_date,
            project_id=assignment.project_id,
        )
        if overlapping:
            collaborator = get_collaborator(db, assignment.collaborator_id)
            collab_name = f"{collaborator.first_name} {collaborator.last_name}" if collaborator else f"ID {assignment.collaborator_id}"
            existing_project = get_project(db, overlapping.project_id)
            existing_project_name = existing_project.name if existing_project else f"ID {overlapping.project_id}"
            new_project = get_project(db, assignment.project_id)
            new_project_name = new_project.name if new_project else f"ID {assignment.project_id}"
            raise ValueError(
                f"Il collaboratore {collab_name} ha già un'assegnazione attiva sul progetto "
                f"'{existing_project_name}' nel periodo [{overlapping.start_date} - {overlapping.end_date}]. "
                f"Non può essere assegnato contemporaneamente al progetto '{new_project_name}'."
            )

        _validate_assignment_date_overlap_by_ente(
            db,
            collaborator_id=assignment.collaborator_id,
            project_id=assignment.project_id,
            start_date=assignment.start_date,
            end_date=assignment.end_date,
        )

        # Crea oggetto con i campi iniziali impostati esplicitamente
        assignment_data = assignment.dict()
        assignment_data['completed_hours'] = 0.0
        assignment_data['progress_percentage'] = 0.0
        assignment_data['is_active'] = True

        db_assignment = models.Assignment(**assignment_data)
        db.add(db_assignment)
        db.flush()  # Ottieni l'ID prima del commit finale

        # Crea relazione many-to-many se non esiste
        collaborator = get_collaborator(db, assignment.collaborator_id)
        project = get_project(db, assignment.project_id)
        if collaborator and project and project not in collaborator.projects:
            collaborator.projects.append(project)

        db.commit()
        db.refresh(db_assignment)

        try:
            collega_assegnazione_a_piano(db, db_assignment.id)
        except Exception as exc:
            logger.warning(f"Impossibile collegare assegnazione {db_assignment.id} al piano finanziario: {exc}")

        logger.info(f"Created assignment: {db_assignment.id}")
        return db_assignment
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating assignment: {e}")
        raise

def update_assignment(db: Session, assignment_id: int, assignment: schemas.AssignmentUpdate):
    db_assignment = db.query(models.Assignment).filter(models.Assignment.id == assignment_id).first()
    if db_assignment:
        update_data = assignment.dict(exclude_unset=True)
        new_start_date = update_data.get("start_date", db_assignment.start_date)
        new_end_date = update_data.get("end_date", db_assignment.end_date)
        new_project_id = update_data.get("project_id", db_assignment.project_id)

        if "start_date" in update_data or "end_date" in update_data:
            overlapping = check_assignment_overlap(
                db,
                collaborator_id=db_assignment.collaborator_id,
                start_date=new_start_date,
                end_date=new_end_date,
                project_id=new_project_id,
                exclude_assignment_id=assignment_id,
            )
            if overlapping:
                collaborator = get_collaborator(db, db_assignment.collaborator_id)
                collab_name = f"{collaborator.first_name} {collaborator.last_name}" if collaborator else f"ID {db_assignment.collaborator_id}"
                existing_project = get_project(db, overlapping.project_id)
                existing_project_name = existing_project.name if existing_project else f"ID {overlapping.project_id}"
                current_project = get_project(db, new_project_id)
                current_project_name = current_project.name if current_project else f"ID {new_project_id}"
                raise ValueError(
                    f"Il collaboratore {collab_name} ha già un'assegnazione attiva sul progetto "
                    f"'{existing_project_name}' nel periodo [{overlapping.start_date} - {overlapping.end_date}]. "
                    f"Non può essere assegnato contemporaneamente al progetto '{current_project_name}'."
                )

        _validate_assignment_date_overlap_by_ente(
            db,
            collaborator_id=db_assignment.collaborator_id,
            project_id=new_project_id,
            start_date=new_start_date,
            end_date=new_end_date,
            exclude_assignment_id=assignment_id,
        )
        for key, value in update_data.items():
            setattr(db_assignment, key, value)
        db.commit()
        db.refresh(db_assignment)
        try:
            collega_assegnazione_a_piano(db, db_assignment.id)
        except Exception as exc:
            logger.warning(f"Impossibile riallineare assegnazione {db_assignment.id} con il piano finanziario: {exc}")
    return db_assignment

def delete_assignment(db: Session, assignment_id: int):
    db_assignment = db.query(models.Assignment).filter(models.Assignment.id == assignment_id).first()
    if db_assignment:
        attendance_count = db.query(models.Attendance).filter(
            models.Attendance.assignment_id == assignment_id
        ).count()
        if attendance_count > 0:
            raise ValueError(f"Impossibile eliminare: {attendance_count} presenze collegate a questa assegnazione.")
        db_assignment.is_active = False
        db.commit()
        db.refresh(db_assignment)
    return db_assignment

# ========================================
# CRUD OPERATIONS PER IMPLEMENTING ENTITIES (ENTI ATTUATORI)
# ========================================

def get_implementing_entity(db: Session, entity_id: int):
    """Recupera un singolo Ente Attuatore per ID"""
    return db.query(models.ImplementingEntity).filter(
        models.ImplementingEntity.id == entity_id
    ).first()

def get_implementing_entity_by_piva(db: Session, partita_iva: str):
    """Recupera un Ente Attuatore per Partita IVA (unique)"""
    # Normalizza P.IVA rimuovendo spazi e prefisso IT
    piva_clean = partita_iva.replace(' ', '').replace('IT', '').replace('it', '')
    return db.query(models.ImplementingEntity).filter(
        models.ImplementingEntity.partita_iva == piva_clean
    ).first()

def get_implementing_entities(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    is_active: Optional[bool] = None
):
    """
    Recupera lista di Enti Attuatori con filtri opzionali

    Args:
        skip: Numero di record da saltare (paginazione)
        limit: Numero massimo di record da restituire
        search: Termine di ricerca (ragione_sociale, partita_iva, citta)
        is_active: Filtra per stato attivo/non attivo
    """
    query = db.query(models.ImplementingEntity)

    # Filtro per stato attivo
    if is_active is not None:
        query = query.filter(models.ImplementingEntity.is_active == is_active)

    # Filtro di ricerca testuale
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (models.ImplementingEntity.ragione_sociale.ilike(search_term)) |
            (models.ImplementingEntity.partita_iva.ilike(search_term)) |
            (models.ImplementingEntity.citta.ilike(search_term)) |
            (models.ImplementingEntity.pec.ilike(search_term))
        )

    # Ordina per ragione sociale
    query = query.order_by(models.ImplementingEntity.ragione_sociale)

    return query.offset(skip).limit(limit).all()

def get_implementing_entities_count(
    db: Session,
    search: Optional[str] = None,
    is_active: Optional[bool] = None
):
    """Conta il numero totale di Enti Attuatori (per paginazione)"""
    query = db.query(models.ImplementingEntity)

    if is_active is not None:
        query = query.filter(models.ImplementingEntity.is_active == is_active)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (models.ImplementingEntity.ragione_sociale.ilike(search_term)) |
            (models.ImplementingEntity.partita_iva.ilike(search_term)) |
            (models.ImplementingEntity.citta.ilike(search_term)) |
            (models.ImplementingEntity.pec.ilike(search_term))
        )

    return query.count()

def create_implementing_entity(db: Session, entity: schemas.ImplementingEntityCreate):
    """
    Crea un nuovo Ente Attuatore

    Validazioni:
    - Partita IVA unique (gestito dal DB)
    - Validazioni formato gestite dal modello SQLAlchemy
    """
    # Crea nuovo oggetto senza dati logo (gestiti separatamente)
    db_entity = models.ImplementingEntity(**entity.dict())

    db.add(db_entity)
    db.commit()
    db.refresh(db_entity)

    logger.info(f"Created implementing entity: {db_entity.ragione_sociale} (ID: {db_entity.id})")
    return db_entity

def update_implementing_entity(
    db: Session,
    entity_id: int,
    entity: schemas.ImplementingEntityUpdate
):
    """
    Aggiorna un Ente Attuatore esistente

    Nota: Logo filename/path vengono aggiornati separatamente tramite upload endpoint
    """
    db_entity = db.query(models.ImplementingEntity).filter(
        models.ImplementingEntity.id == entity_id
    ).first()

    if db_entity:
        # Aggiorna solo i campi forniti (exclude_unset=True)
        update_data = entity.dict(exclude_unset=True)

        for key, value in update_data.items():
            setattr(db_entity, key, value)

        db.commit()
        db.refresh(db_entity)

        logger.info(f"Updated implementing entity: {db_entity.ragione_sociale} (ID: {entity_id})")

    return db_entity

def delete_implementing_entity(db: Session, entity_id: int):
    """
    Elimina un Ente Attuatore

    Attenzione: Fallisce se ci sono progetti collegati (FK constraint)
    Considera soft-delete (is_active=False) per mantenere storico
    """
    db_entity = db.query(models.ImplementingEntity).filter(
        models.ImplementingEntity.id == entity_id
    ).first()

    if db_entity:
        # Verifica se ci sono progetti collegati
        projects_count = db.query(models.Project).filter(
            models.Project.ente_attuatore_id == entity_id
        ).count()

        if projects_count > 0:
            raise ValueError(
                f"Impossibile eliminare l'ente: ci sono {projects_count} progetti collegati. "
                f"Considera di disattivarlo (is_active=False) invece di eliminarlo."
            )

        db.delete(db_entity)
        db.commit()

        logger.info(f"Deleted implementing entity: {db_entity.ragione_sociale} (ID: {entity_id})")

    return db_entity

def soft_delete_implementing_entity(db: Session, entity_id: int):
    """
    Disattiva un Ente Attuatore invece di eliminarlo (soft delete)

    Usa questo metodo se vuoi mantenere lo storico dei progetti collegati
    """
    db_entity = db.query(models.ImplementingEntity).filter(
        models.ImplementingEntity.id == entity_id
    ).first()

    if db_entity:
        db_entity.is_active = False
        db.commit()
        db.refresh(db_entity)

        logger.info(f"Soft-deleted implementing entity: {db_entity.ragione_sociale} (ID: {entity_id})")

    return db_entity

def get_implementing_entity_with_projects(db: Session, entity_id: int):
    """Recupera un Ente Attuatore con tutti i progetti collegati"""
    entity = db.query(models.ImplementingEntity).filter(
        models.ImplementingEntity.id == entity_id
    ).first()

    if entity:
        # Forza il caricamento della relazione projects
        # (eager loading per evitare query N+1)
        _ = entity.projects  # Accesso alla relationship per caricarla

    return entity

def get_projects_by_entity(db: Session, entity_id: int, status: Optional[str] = None):
    """Recupera tutti i progetti di un Ente Attuatore specifico"""
    query = db.query(models.Project).filter(
        models.Project.ente_attuatore_id == entity_id
    )

    if status:
        query = query.filter(models.Project.status == status)

    return query.order_by(models.Project.start_date.desc()).all()

def update_entity_logo(
    db: Session,
    entity_id: int,
    filename: str,
    storage_path: str
):
    """
    Aggiorna i dati del logo di un Ente Attuatore

    Args:
        entity_id: ID dell'ente
        filename: Nome file originale del logo
        storage_path: Path nel sistema di storage
    """
    db_entity = db.query(models.ImplementingEntity).filter(
        models.ImplementingEntity.id == entity_id
    ).first()

    if db_entity:
        from datetime import datetime

        db_entity.logo_filename = filename
        db_entity.logo_path = storage_path
        db_entity.logo_uploaded_at = datetime.utcnow()

        db.commit()
        db.refresh(db_entity)

        logger.info(f"Updated logo for entity: {db_entity.ragione_sociale} (ID: {entity_id})")

    return db_entity

# ========================================
# PROGETTO-MANSIONE-ENTE OPERATIONS
# ========================================

def get_progetto_mansione_ente(db: Session, associazione_id: int):
    """Recupera una singola associazione progetto-mansione-ente per ID"""
    return db.query(models.ProgettoMansioneEnte).filter(
        models.ProgettoMansioneEnte.id == associazione_id
    ).first()

def get_progetto_mansione_ente_list(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    progetto_id: Optional[int] = None,
    ente_attuatore_id: Optional[int] = None,
    mansione: Optional[str] = None,
    is_active: Optional[bool] = None
):
    """
    Recupera lista associazioni progetto-mansione-ente con filtri opzionali

    Args:
        skip: Record da saltare (paginazione)
        limit: Numero massimo di record
        progetto_id: Filtra per progetto specifico
        ente_attuatore_id: Filtra per ente attuatore specifico
        mansione: Filtra per mansione (search parziale)
        is_active: Filtra per stato attivo
    """
    query = db.query(models.ProgettoMansioneEnte)

    # Applicazione filtri
    if progetto_id is not None:
        query = query.filter(models.ProgettoMansioneEnte.progetto_id == progetto_id)

    if ente_attuatore_id is not None:
        query = query.filter(models.ProgettoMansioneEnte.ente_attuatore_id == ente_attuatore_id)

    if mansione:
        query = query.filter(models.ProgettoMansioneEnte.mansione.ilike(f"%{mansione}%"))

    if is_active is not None:
        query = query.filter(models.ProgettoMansioneEnte.is_active == is_active)

    # Ordinamento e paginazione
    return query.order_by(
        models.ProgettoMansioneEnte.data_inizio.desc()
    ).offset(skip).limit(limit).all()

def get_progetto_mansione_ente_count(
    db: Session,
    progetto_id: Optional[int] = None,
    ente_attuatore_id: Optional[int] = None,
    mansione: Optional[str] = None,
    is_active: Optional[bool] = None
):
    """Conta le associazioni con gli stessi filtri della lista"""
    query = db.query(models.ProgettoMansioneEnte)

    if progetto_id is not None:
        query = query.filter(models.ProgettoMansioneEnte.progetto_id == progetto_id)

    if ente_attuatore_id is not None:
        query = query.filter(models.ProgettoMansioneEnte.ente_attuatore_id == ente_attuatore_id)

    if mansione:
        query = query.filter(models.ProgettoMansioneEnte.mansione.ilike(f"%{mansione}%"))

    if is_active is not None:
        query = query.filter(models.ProgettoMansioneEnte.is_active == is_active)

    return query.count()

def get_progetto_mansione_ente_by_project(db: Session, progetto_id: int):
    """Recupera tutte le associazioni di un progetto specifico"""
    return db.query(models.ProgettoMansioneEnte).filter(
        models.ProgettoMansioneEnte.progetto_id == progetto_id
    ).order_by(models.ProgettoMansioneEnte.data_inizio.desc()).all()

def get_progetto_mansione_ente_by_entity(db: Session, ente_attuatore_id: int):
    """Recupera tutte le associazioni di un ente attuatore specifico"""
    return db.query(models.ProgettoMansioneEnte).filter(
        models.ProgettoMansioneEnte.ente_attuatore_id == ente_attuatore_id
    ).order_by(models.ProgettoMansioneEnte.data_inizio.desc()).all()

def get_progetto_mansione_ente_active_by_date(
    db: Session,
    progetto_id: int,
    reference_date: datetime
):
    """Recupera associazioni attive per un progetto a una data specifica"""
    return db.query(models.ProgettoMansioneEnte).filter(
        models.ProgettoMansioneEnte.progetto_id == progetto_id,
        models.ProgettoMansioneEnte.is_active == True,
        models.ProgettoMansioneEnte.data_inizio <= reference_date,
        models.ProgettoMansioneEnte.data_fine >= reference_date
    ).all()

def create_progetto_mansione_ente(
    db: Session,
    associazione: schemas.ProgettoMansioneEnteCreate
):
    """
    Crea una nuova associazione progetto-mansione-ente

    Validazioni:
    - Verifica esistenza progetto
    - Verifica esistenza ente attuatore
    - Verifica date coerenti
    - Verifica univocità (progetto + ente + mansione + data_inizio)
    """
    # Verifica esistenza progetto
    progetto = get_project(db, associazione.progetto_id)
    if not progetto:
        raise ValueError(f"Progetto con ID {associazione.progetto_id} non trovato")

    # Verifica esistenza ente attuatore
    ente = get_implementing_entity(db, associazione.ente_attuatore_id)
    if not ente:
        raise ValueError(f"Ente attuatore con ID {associazione.ente_attuatore_id} non trovato")

    # Verifica date coerenti
    if associazione.data_fine <= associazione.data_inizio:
        raise ValueError("La data di fine deve essere successiva alla data di inizio")

    # Verifica univocità (il vincolo unique nel DB bloccherà i duplicati)
    # Ma faccio un check esplicito per dare un messaggio migliore
    existing = db.query(models.ProgettoMansioneEnte).filter(
        models.ProgettoMansioneEnte.progetto_id == associazione.progetto_id,
        models.ProgettoMansioneEnte.ente_attuatore_id == associazione.ente_attuatore_id,
        models.ProgettoMansioneEnte.mansione == associazione.mansione,
        models.ProgettoMansioneEnte.data_inizio == associazione.data_inizio
    ).first()

    if existing:
        raise ValueError(
            f"Esiste già un'associazione per questo progetto, ente, mansione e data di inizio"
        )

    # Creazione
    db_associazione = models.ProgettoMansioneEnte(**associazione.model_dump())
    db.add(db_associazione)
    db.commit()
    db.refresh(db_associazione)

    logger.info(
        f"Created ProgettoMansioneEnte: Project {associazione.progetto_id}, "
        f"Entity {associazione.ente_attuatore_id}, Role {associazione.mansione}"
    )

    return db_associazione

def update_progetto_mansione_ente(
    db: Session,
    associazione_id: int,
    associazione: schemas.ProgettoMansioneEnteUpdate
):
    """
    Aggiorna un'associazione esistente

    Validazioni:
    - Verifica esistenza associazione
    - Se cambiano progetto/ente, verifica esistenza
    - Verifica coerenza date se modificate
    """
    db_associazione = get_progetto_mansione_ente(db, associazione_id)
    if not db_associazione:
        raise ValueError(f"Associazione con ID {associazione_id} non trovata")

    update_data = associazione.model_dump(exclude_unset=True)

    # Validazioni condizionali
    if "progetto_id" in update_data:
        progetto = get_project(db, update_data["progetto_id"])
        if not progetto:
            raise ValueError(f"Progetto con ID {update_data['progetto_id']} non trovato")

    if "ente_attuatore_id" in update_data:
        ente = get_implementing_entity(db, update_data["ente_attuatore_id"])
        if not ente:
            raise ValueError(f"Ente attuatore con ID {update_data['ente_attuatore_id']} non trovato")

    # Verifica coerenza date
    data_inizio = update_data.get("data_inizio", db_associazione.data_inizio)
    data_fine = update_data.get("data_fine", db_associazione.data_fine)

    if data_fine <= data_inizio:
        raise ValueError("La data di fine deve essere successiva alla data di inizio")

    # Applicazione aggiornamenti
    for field, value in update_data.items():
        setattr(db_associazione, field, value)

    db.commit()
    db.refresh(db_associazione)

    logger.info(f"Updated ProgettoMansioneEnte ID {associazione_id}")

    return db_associazione

def delete_progetto_mansione_ente(db: Session, associazione_id: int):
    """
    Elimina un'associazione progetto-mansione-ente

    Nota: La cancellazione è fisica. Per mantenere lo storico,
    considerare invece l'uso di is_active=False
    """
    db_associazione = get_progetto_mansione_ente(db, associazione_id)
    if not db_associazione:
        raise ValueError(f"Associazione con ID {associazione_id} non trovata")

    db.delete(db_associazione)
    db.commit()

    logger.info(f"Deleted ProgettoMansioneEnte ID {associazione_id}")

    return {"message": "Associazione eliminata con successo", "id": associazione_id}

def soft_delete_progetto_mansione_ente(db: Session, associazione_id: int):
    """Disattiva un'associazione invece di eliminarla (soft delete)"""
    db_associazione = get_progetto_mansione_ente(db, associazione_id)
    if not db_associazione:
        raise ValueError(f"Associazione con ID {associazione_id} non trovata")

    db_associazione.is_active = False
    db.commit()
    db.refresh(db_associazione)

    logger.info(f"Soft-deleted ProgettoMansioneEnte ID {associazione_id}")

    return db_associazione


# ========================================
# CRUD OPERATIONS PER CONTRACT TEMPLATES
# ========================================

def get_contract_template(db: Session, template_id: int):
    """Recupera un singolo template contratto per ID"""
    return db.query(models.ContractTemplate).filter(
        models.ContractTemplate.id == template_id
    ).first()


def resolve_document_template(
    db: Session,
    *,
    ambito_template: str,
    chiave_documento: Optional[str] = None,
    progetto_id: Optional[int] = None,
    ente_attuatore_id: Optional[int] = None,
    ente_erogatore: Optional[str] = None,
    avviso: Optional[str] = None,
) -> Optional[models.ContractTemplate]:
    ambito = (ambito_template or "").strip().lower()
    if not ambito:
        return None

    normalized_key = _normalize_optional_text(chiave_documento)
    if normalized_key:
        normalized_key = re.sub(r"[^a-z0-9]+", "_", normalized_key.strip().lower()).strip("_") or None
    normalized_ente = _normalize_optional_text(ente_erogatore)
    normalized_avviso = _normalize_optional_text(avviso)

    def _find_candidate(require_key: bool) -> Optional[models.ContractTemplate]:
        query = db.query(models.ContractTemplate).filter(
            models.ContractTemplate.is_active == True,
            models.ContractTemplate.ambito_template == ambito,
        )

        if require_key and normalized_key:
            query = query.filter(
                or_(
                    models.ContractTemplate.chiave_documento == normalized_key,
                    models.ContractTemplate.chiave_documento.is_(None),
                )
            )

        if progetto_id is not None:
            query = query.filter(
                or_(
                    models.ContractTemplate.progetto_id == progetto_id,
                    models.ContractTemplate.progetto_id.is_(None),
                )
            )

        if ente_attuatore_id is not None:
            query = query.filter(
                or_(
                    models.ContractTemplate.ente_attuatore_id == ente_attuatore_id,
                    models.ContractTemplate.ente_attuatore_id.is_(None),
                )
            )

        if normalized_ente is not None:
            query = query.filter(
                or_(
                    models.ContractTemplate.ente_erogatore == normalized_ente,
                    models.ContractTemplate.ente_erogatore.is_(None),
                )
            )

        if normalized_avviso is not None:
            query = query.filter(
                or_(
                    models.ContractTemplate.avviso == normalized_avviso,
                    models.ContractTemplate.avviso.is_(None),
                )
            )

        return query.order_by(
            (models.ContractTemplate.chiave_documento == normalized_key).desc() if normalized_key else models.ContractTemplate.chiave_documento.isnot(None).desc(),
            models.ContractTemplate.progetto_id.isnot(None).desc(),
            models.ContractTemplate.ente_attuatore_id.isnot(None).desc(),
            models.ContractTemplate.ente_erogatore.isnot(None).desc(),
            models.ContractTemplate.avviso.isnot(None).desc(),
            models.ContractTemplate.created_at.desc(),
        ).first()

    if normalized_key:
        candidate = _find_candidate(require_key=True)
        if candidate:
            return candidate

    return _find_candidate(require_key=False)


def get_contract_templates(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    ambito_template: Optional[str] = None,
    chiave_documento: Optional[str] = None,
    ente_attuatore_id: Optional[int] = None,
    progetto_id: Optional[int] = None,
    ente_erogatore: Optional[str] = None,
    avviso: Optional[str] = None,
    tipo_contratto: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None
):
    """
    Recupera lista template contratti con filtri opzionali

    Args:
        skip: Record da saltare (paginazione)
        limit: Numero massimo di record
        ambito_template: Filtra per famiglia documento
        chiave_documento: Filtra per chiave/uso specifico
        ente_attuatore_id: Filtra per ente specifico o template globali
        progetto_id: Filtra per progetto specifico o template globali
        ente_erogatore: Filtra per fondo/ente erogatore specifico o template globali
        avviso: Filtra per avviso specifico o template globali
        tipo_contratto: Filtra per tipo contratto specifico
        is_active: Filtra per stato attivo
        search: Cerca nel nome template o descrizione
    """
    query = db.query(models.ContractTemplate)

    # Filtri
    if ambito_template:
        query = query.filter(models.ContractTemplate.ambito_template == ambito_template)

    if chiave_documento:
        query = query.filter(models.ContractTemplate.chiave_documento == chiave_documento)

    if ente_attuatore_id is not None:
        query = query.filter(
            or_(
                models.ContractTemplate.ente_attuatore_id == ente_attuatore_id,
                models.ContractTemplate.ente_attuatore_id.is_(None)
            )
        )

    if progetto_id is not None:
        query = query.filter(
            or_(
                models.ContractTemplate.progetto_id == progetto_id,
                models.ContractTemplate.progetto_id.is_(None)
            )
        )

    if ente_erogatore is not None:
        query = query.filter(
            or_(
                models.ContractTemplate.ente_erogatore == ente_erogatore,
                models.ContractTemplate.ente_erogatore.is_(None)
            )
        )

    if avviso is not None:
        query = query.filter(
            or_(
                models.ContractTemplate.avviso == avviso,
                models.ContractTemplate.avviso.is_(None)
            )
        )

    if tipo_contratto:
        query = query.filter(models.ContractTemplate.tipo_contratto == tipo_contratto)

    if is_active is not None:
        query = query.filter(models.ContractTemplate.is_active == is_active)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (models.ContractTemplate.nome_template.ilike(search_term)) |
            (models.ContractTemplate.descrizione.ilike(search_term)) |
            (models.ContractTemplate.ente_erogatore.ilike(search_term)) |
            (models.ContractTemplate.avviso.ilike(search_term))
        )

    # Ordinamento: template di default per primi, poi per data creazione
    return query.order_by(
        models.ContractTemplate.progetto_id.isnot(None).desc(),
        models.ContractTemplate.ente_attuatore_id.isnot(None).desc(),
        models.ContractTemplate.is_default.desc(),
        models.ContractTemplate.created_at.desc()
    ).offset(skip).limit(limit).all()


def get_contract_template_by_type(
    db: Session,
    tipo_contratto: str,
    use_default: bool = True
):
    """
    Recupera il template per un tipo di contratto specifico

    Args:
        tipo_contratto: Tipo di contratto
        use_default: Se True, restituisce il template di default per quel tipo
    """
    query = db.query(models.ContractTemplate).filter(
        models.ContractTemplate.ambito_template == "contratto",
        models.ContractTemplate.tipo_contratto == tipo_contratto,
        models.ContractTemplate.is_active == True
    )

    if use_default:
        default_template = query.filter(models.ContractTemplate.is_default == True).first()
        if default_template:
            return default_template

        # Fallback operativo: se manca il default ma esiste un template attivo,
        # usa il più recente invece di bloccare la generazione del contratto.
        return query.order_by(models.ContractTemplate.created_at.desc()).first()

    return query.order_by(
        models.ContractTemplate.is_default.desc(),
        models.ContractTemplate.created_at.desc()
    ).first()


def _normalize_contract_template_payload(
    payload: Dict[str, Any],
    existing: Optional[models.ContractTemplate] = None
) -> Dict[str, Any]:
    normalized = dict(payload)
    if "ambito_template" in normalized and normalized["ambito_template"] is not None:
        normalized["ambito_template"] = str(normalized["ambito_template"]).strip().lower()
    ambito = normalized.get("ambito_template") or (existing.ambito_template if existing else "contratto")

    if "chiave_documento" in normalized:
        raw_key = _normalize_optional_text(normalized.get("chiave_documento"))
        if raw_key:
            normalized_key = re.sub(r"[^a-z0-9]+", "_", raw_key.strip().lower()).strip("_")
            normalized["chiave_documento"] = normalized_key or None
        else:
            normalized["chiave_documento"] = None
    if "ente_erogatore" in normalized:
        normalized["ente_erogatore"] = _normalize_optional_text(normalized.get("ente_erogatore"))
    if "avviso" in normalized:
        normalized["avviso"] = _normalize_optional_text(normalized.get("avviso"))

    chiave_documento = normalized.get("chiave_documento")
    ente_erogatore = normalized.get("ente_erogatore")
    avviso = normalized.get("avviso")
    tipo_contratto = normalized.get("tipo_contratto")

    if ambito != "contratto":
        normalized["tipo_contratto"] = "documento_generico"
        normalized["is_default"] = False

    if ambito == "contratto":
        effective_tipo = tipo_contratto or (existing.tipo_contratto if existing else None)
        if not effective_tipo or effective_tipo == "documento_generico":
            raise ValueError("Per l'ambito contratto è obbligatorio un tipo contratto specifico")
    else:
        if not chiave_documento:
            raise ValueError("Per template non contrattuali è obbligatoria la chiave documento")

    if ambito == "piano_finanziario":
        if not ente_erogatore:
            raise ValueError("Per i template piano finanziario è obbligatorio l'ente erogatore")
        if not avviso:
            raise ValueError("Per i template piano finanziario è obbligatorio l'avviso")

    if ambito == "timesheet" and not chiave_documento:
        raise ValueError("Per i template timesheet è obbligatoria la chiave documento")

    return normalized


def get_contract_templates_count(
    db: Session,
    ambito_template: Optional[str] = None,
    chiave_documento: Optional[str] = None,
    ente_attuatore_id: Optional[int] = None,
    progetto_id: Optional[int] = None,
    ente_erogatore: Optional[str] = None,
    avviso: Optional[str] = None,
    tipo_contratto: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None
):
    """Conta i template con gli stessi filtri della lista"""
    query = db.query(models.ContractTemplate)

    if ambito_template:
        query = query.filter(models.ContractTemplate.ambito_template == ambito_template)

    if chiave_documento:
        query = query.filter(models.ContractTemplate.chiave_documento == chiave_documento)

    if ente_attuatore_id is not None:
        query = query.filter(
            or_(
                models.ContractTemplate.ente_attuatore_id == ente_attuatore_id,
                models.ContractTemplate.ente_attuatore_id.is_(None)
            )
        )

    if progetto_id is not None:
        query = query.filter(
            or_(
                models.ContractTemplate.progetto_id == progetto_id,
                models.ContractTemplate.progetto_id.is_(None)
            )
        )

    if ente_erogatore is not None:
        query = query.filter(
            or_(
                models.ContractTemplate.ente_erogatore == ente_erogatore,
                models.ContractTemplate.ente_erogatore.is_(None)
            )
        )

    if avviso is not None:
        query = query.filter(
            or_(
                models.ContractTemplate.avviso == avviso,
                models.ContractTemplate.avviso.is_(None)
            )
        )

    if tipo_contratto:
        query = query.filter(models.ContractTemplate.tipo_contratto == tipo_contratto)

    if is_active is not None:
        query = query.filter(models.ContractTemplate.is_active == is_active)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (models.ContractTemplate.nome_template.ilike(search_term)) |
            (models.ContractTemplate.descrizione.ilike(search_term)) |
            (models.ContractTemplate.ente_erogatore.ilike(search_term)) |
            (models.ContractTemplate.avviso.ilike(search_term))
        )

    return query.count()


@track_entity_event("contract_template", "created")
def create_contract_template(
    db: Session,
    template: schemas.ContractTemplateCreate
):
    """
    Crea un nuovo template contratto

    Validazioni:
    - Tipo contratto valido
    - Se is_default=True, rimuove il default dagli altri template dello stesso tipo
    """
    template_data = _normalize_contract_template_payload(template.dict())

    # Se questo è il template di default, rimuovi il flag dagli altri
    if template_data.get('is_default', False):
        db.query(models.ContractTemplate).filter(
            models.ContractTemplate.ambito_template == "contratto",
            models.ContractTemplate.tipo_contratto == template_data['tipo_contratto'],
            models.ContractTemplate.is_default == True
        ).update({'is_default': False})

    db_template = models.ContractTemplate(**template_data)
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    _create_audit_log(
        db,
        entity="contract_template",
        action="create",
        old_value=None,
        new_value={
            "id": db_template.id,
            "nome_template": db_template.nome_template,
            "ambito_template": db_template.ambito_template,
            "tipo_contratto": db_template.tipo_contratto,
            "is_default": db_template.is_default,
        },
    )
    db.commit()

    logger.info(f"Created contract template: {db_template.nome_template} (ID: {db_template.id})")
    return db_template


@track_entity_event("contract_template", "updated")
def update_contract_template(
    db: Session,
    template_id: int,
    template: schemas.ContractTemplateUpdate
):
    """
    Aggiorna un template contratto esistente

    Validazioni:
    - Se is_default viene impostato a True, rimuove il flag dagli altri template dello stesso tipo
    """
    db_template = db.query(models.ContractTemplate).filter(
        models.ContractTemplate.id == template_id
    ).first()

    if not db_template:
        raise ValueError(f"Template con ID {template_id} non trovato")

    old_snapshot = {
        "id": db_template.id,
        "nome_template": db_template.nome_template,
        "ambito_template": db_template.ambito_template,
        "tipo_contratto": db_template.tipo_contratto,
        "is_default": db_template.is_default,
        "is_active": db_template.is_active,
        "versione": db_template.versione,
    }
    update_data = _normalize_contract_template_payload(template.dict(exclude_unset=True), existing=db_template)

    # Se cambia il flag default
    if update_data.get('is_default', False) and not db_template.is_default:
        # Rimuovi default dagli altri template dello stesso tipo
        tipo_contratto = update_data.get('tipo_contratto', db_template.tipo_contratto)
        ambito_template = update_data.get('ambito_template', db_template.ambito_template)
        db.query(models.ContractTemplate).filter(
            models.ContractTemplate.ambito_template == ambito_template,
            models.ContractTemplate.tipo_contratto == tipo_contratto,
            models.ContractTemplate.is_default == True,
            models.ContractTemplate.id != template_id
        ).update({'is_default': False})

    # Applica aggiornamenti
    for key, value in update_data.items():
        setattr(db_template, key, value)

    db.commit()
    db.refresh(db_template)
    _create_audit_log(
        db,
        entity="contract_template",
        action="update",
        old_value=old_snapshot,
        new_value={
            "id": db_template.id,
            "nome_template": db_template.nome_template,
            "ambito_template": db_template.ambito_template,
            "tipo_contratto": db_template.tipo_contratto,
            "is_default": db_template.is_default,
            "is_active": db_template.is_active,
            "versione": db_template.versione,
        },
    )
    db.commit()

    logger.info(f"Updated contract template: {db_template.nome_template} (ID: {template_id})")
    return db_template


@track_entity_event(
    "contract_template",
    "deleted",
    entity_id_getter=lambda result, args, kwargs: (
        getattr(result, "id", None)
        or kwargs.get("template_id")
        or (args[1] if len(args) > 1 else None)
    ),
)
def delete_contract_template(db: Session, template_id: int, soft_delete: bool = True):
    """
    Elimina o disattiva un template contratto

    Args:
        soft_delete: Se True, disattiva (is_active=False), altrimenti elimina
    """
    db_template = db.query(models.ContractTemplate).filter(
        models.ContractTemplate.id == template_id
    ).first()

    if not db_template:
        raise ValueError(f"Template con ID {template_id} non trovato")

    old_snapshot = {
        "id": db_template.id,
        "nome_template": db_template.nome_template,
        "ambito_template": db_template.ambito_template,
        "tipo_contratto": db_template.tipo_contratto,
        "is_default": db_template.is_default,
        "is_active": db_template.is_active,
    }

    if soft_delete:
        db_template.is_active = False
        db.commit()
        db.refresh(db_template)
        _create_audit_log(
            db,
            entity="contract_template",
            action="soft_delete",
            old_value=old_snapshot,
            new_value={
                **old_snapshot,
                "is_active": db_template.is_active,
            },
        )
        db.commit()
        enqueue_webhook_notification(
            event_type="contract_template_soft_deleted",
            payload={
                "template_id": db_template.id,
                "nome_template": db_template.nome_template,
                "ambito_template": db_template.ambito_template,
                "tipo_contratto": db_template.tipo_contratto,
            },
        )
        logger.info(f"Soft-deleted contract template ID {template_id}")
    else:
        db.delete(db_template)
        db.commit()
        _create_audit_log(
            db,
            entity="contract_template",
            action="delete",
            old_value=old_snapshot,
            new_value=None,
        )
        db.commit()
        enqueue_webhook_notification(
            event_type="contract_template_deleted",
            payload={
                "template_id": old_snapshot["id"],
                "nome_template": old_snapshot["nome_template"],
                "ambito_template": old_snapshot["ambito_template"],
                "tipo_contratto": old_snapshot["tipo_contratto"],
            },
        )
        logger.info(f"Deleted contract template ID {template_id}")

    return db_template


def increment_template_usage(db: Session, template_id: int):
    """
    Incrementa il contatore utilizzi di un template

    Chiamato automaticamente quando un template viene usato per generare un contratto
    """
    db_template = db.query(models.ContractTemplate).filter(
        models.ContractTemplate.id == template_id
    ).first()

    if db_template:
        db_template.increment_usage()  # Metodo del modello
        db.commit()
        db.refresh(db_template)
        logger.info(f"Incremented usage for template {template_id}: {db_template.numero_utilizzi}")

    return db_template


def get_template_with_variables(db: Session, template_id: int):
    """Recupera un template con la lista delle variabili disponibili"""
    db_template = get_contract_template(db, template_id)

    if db_template:
        # Aggiungi le variabili disponibili
        template_dict = schemas.ContractTemplate.from_orm(db_template).dict()
        template_dict['variabili_disponibili'] = db_template.get_available_variables()
        return template_dict

    return None


# ─────────────────────────────────────────────
# BLOCCO 1 — ANAGRAFICA ESPANSA
# ─────────────────────────────────────────────

# ── Agenzie ──────────────────────────────────

def get_agenzie(db: Session, search: str = None, attivo: bool = None,
                skip: int = 0, limit: int = 50):
    q = db.query(models.Agenzia)
    if attivo is not None:
        q = q.filter(models.Agenzia.attivo == attivo)
    if search:
        q = q.filter(models.Agenzia.nome.ilike(f"%{search}%"))
    total = q.count()
    items = q.order_by(models.Agenzia.nome).offset(skip).limit(limit).all()
    return items, total


def get_agenzia(db: Session, agenzia_id: int):
    return db.query(models.Agenzia).filter(models.Agenzia.id == agenzia_id).first()


def create_agenzia(db: Session, agenzia: schemas.AgenziaCreate):
    if agenzia.partita_iva:
        existing = db.query(models.Agenzia).filter(models.Agenzia.partita_iva == agenzia.partita_iva).first()
        if existing:
            raise ValueError("Esiste già un'agenzia con questa partita IVA")
    db_obj = models.Agenzia(**agenzia.model_dump())
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def update_agenzia(db: Session, agenzia_id: int, agenzia: schemas.AgenziaUpdate):
    db_obj = get_agenzia(db, agenzia_id)
    if not db_obj:
        return None
    data = agenzia.model_dump(exclude_unset=True)
    if data.get("partita_iva"):
        existing = (
            db.query(models.Agenzia)
            .filter(models.Agenzia.partita_iva == data["partita_iva"], models.Agenzia.id != agenzia_id)
            .first()
        )
        if existing:
            raise ValueError("Esiste già un'agenzia con questa partita IVA")
    for k, v in data.items():
        setattr(db_obj, k, v)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def delete_agenzia(db: Session, agenzia_id: int):
    db_obj = get_agenzia(db, agenzia_id)
    if db_obj:
        db_obj.attivo = False
        db.commit()
    return db_obj


# ── Consulenti ───────────────────────────────

def get_consulenti(db: Session, search: str = None, attivo: bool = None,
                   agenzia_id: int = None, page: int = 1, limit: int = 20):
    q = db.query(models.Consulente)
    if attivo is not None:
        q = q.filter(models.Consulente.attivo == attivo)
    if agenzia_id:
        q = q.filter(models.Consulente.agenzia_id == agenzia_id)
    if search:
        term = f"%{search}%"
        q = q.filter(
            models.Consulente.nome.ilike(term) |
            models.Consulente.cognome.ilike(term) |
            models.Consulente.email.ilike(term)
        )
    total = q.count()
    pages = max(1, -(-total // limit))
    items = (q.order_by(models.Consulente.cognome, models.Consulente.nome)
              .offset((page - 1) * limit).limit(limit).all())
    return items, total, pages


def get_consulente(db: Session, consulente_id: int):
    return db.query(models.Consulente).filter(models.Consulente.id == consulente_id).first()


def create_consulente(db: Session, consulente: schemas.ConsulenteCreate):
    db_obj = models.Consulente(**consulente.model_dump())
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def update_consulente(db: Session, consulente_id: int, consulente: schemas.ConsulenteUpdate):
    db_obj = get_consulente(db, consulente_id)
    if not db_obj:
        return None
    data = consulente.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(db_obj, k, v)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def delete_consulente(db: Session, consulente_id: int):
    db_obj = get_consulente(db, consulente_id)
    if db_obj:
        db_obj.attivo = False
        db.commit()
    return db_obj


def get_aziende_by_consulente(db: Session, consulente_id: int):
    return (db.query(models.AziendaCliente)
              .filter(models.AziendaCliente.consulente_id == consulente_id)
              .order_by(models.AziendaCliente.ragione_sociale).all())


# ── Aziende Clienti ──────────────────────────

def get_aziende_clienti(db: Session, search: str = None, citta: str = None,
                        consulente_id: int = None, agenzia_id: int = None, attivo: bool = None,
                        page: int = 1, limit: int = 20,
                        sort_by: str = "ragione_sociale", order: str = "asc"):
    q = db.query(models.AziendaCliente)
    if attivo is not None:
        q = q.filter(models.AziendaCliente.attivo == attivo)
    if agenzia_id:
        q = q.filter(models.AziendaCliente.agenzia_id == agenzia_id)
    if consulente_id:
        q = q.filter(models.AziendaCliente.consulente_id == consulente_id)
    if citta:
        q = q.filter(models.AziendaCliente.citta.ilike(f"%{citta}%"))
    if search:
        term = f"%{search}%"
        q = q.filter(
            models.AziendaCliente.ragione_sociale.ilike(term) |
            models.AziendaCliente.pec.ilike(term) |
            models.AziendaCliente.partita_iva.ilike(term)
        )
    total = q.count()
    pages = max(1, -(-total // limit))
    col = getattr(models.AziendaCliente, sort_by, models.AziendaCliente.ragione_sociale)
    col = col.desc() if order == "desc" else col.asc()
    items = q.order_by(col).offset((page - 1) * limit).limit(limit).all()
    return items, total, pages


def get_azienda_cliente(db: Session, azienda_id: int):
    return db.query(models.AziendaCliente).filter(models.AziendaCliente.id == azienda_id).first()


def create_azienda_cliente(db: Session, azienda: schemas.AziendaClienteCreate):
    db_obj = models.AziendaCliente(**azienda.model_dump())
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def update_azienda_cliente(db: Session, azienda_id: int, azienda: schemas.AziendaClienteUpdate):
    db_obj = get_azienda_cliente(db, azienda_id)
    if not db_obj:
        return None
    data = azienda.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(db_obj, k, v)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def delete_azienda_cliente(db: Session, azienda_id: int):
    db_obj = get_azienda_cliente(db, azienda_id)
    if db_obj:
        db_obj.attivo = False
        db.commit()
    return db_obj


# ─────────────────────────────────────────────
# BLOCCO 2 — SMART COLLABORATORS LIST
# ─────────────────────────────────────────────

def search_collaborators_paginated(
    db: Session,
    search: str = None,
    competenza: str = None,
    disponibile: bool = None,
    citta: str = None,
    page: int = 1,
    limit: int = 20,
    sort_by: str = "last_name",
    order: str = "asc"
):
    """
    Ricerca collaboratori con filtri server-side e paginazione.

    - search: full-text su nome, cognome, email, codice fiscale, posizione
    - competenza: filtro esatto/parziale su position
    - disponibile: True = ha almeno un progetto attivo, False = nessun progetto attivo
    - citta: filtro parziale su city
    - page/limit: paginazione
    - sort_by/order: ordinamento
    """
    from models import collaborator_project

    SORT_FIELDS = {
        "last_name": models.Collaborator.last_name,
        "first_name": models.Collaborator.first_name,
        "email": models.Collaborator.email,
        "position": models.Collaborator.position,
        "city": models.Collaborator.city,
        "created_at": models.Collaborator.created_at,
    }

    q = db.query(models.Collaborator).options(
        selectinload(models.Collaborator.projects),
        selectinload(models.Collaborator.assignments)
    ).filter(models.Collaborator.is_active == True)

    # Ricerca full-text
    if search:
        term = f"%{search.lower()}%"
        q = q.filter(
            or_(
                func.lower(models.Collaborator.first_name).like(term),
                func.lower(models.Collaborator.last_name).like(term),
                func.lower(models.Collaborator.email).like(term),
                func.lower(func.coalesce(models.Collaborator.fiscal_code, '')).like(term),
                func.lower(func.coalesce(models.Collaborator.position, '')).like(term),
            )
        )

    # Filtro competenza (position)
    if competenza:
        q = q.filter(func.lower(func.coalesce(models.Collaborator.position, '')).like(f"%{competenza.lower()}%"))

    # Filtro città
    if citta:
        q = q.filter(func.lower(func.coalesce(models.Collaborator.city, '')).like(f"%{citta.lower()}%"))

    # Filtro disponibilità (subquery su progetti attivi)
    if disponibile is not None:
        active_ids_subq = (
            db.query(collaborator_project.c.collaborator_id)
            .join(models.Project, models.Project.id == collaborator_project.c.project_id)
            .filter(models.Project.status == 'active')
            .subquery()
        )
        if disponibile:
            q = q.filter(models.Collaborator.id.in_(active_ids_subq))
        else:
            q = q.filter(~models.Collaborator.id.in_(active_ids_subq))

    total = q.count()
    pages = max(1, -(-total // limit))

    col = SORT_FIELDS.get(sort_by, models.Collaborator.last_name)
    col = col.desc() if order == "desc" else col.asc()

    items = q.order_by(col, models.Collaborator.first_name.asc()).offset((page - 1) * limit).limit(limit).all()

    return items, total, pages


# ─────────────────────────────────────────────
# BLOCCO 3 — CATALOGO + LISTINI
# ─────────────────────────────────────────────

def calcola_prezzo_finale(prezzo_base: float, prezzo_override, sconto_percentuale: float) -> float:
    """Funzione riutilizzabile: prezzo_override ?? (prezzo_base * (1 - sconto/100))."""
    if prezzo_override is not None:
        return prezzo_override
    sconto = sconto_percentuale or 0.0
    return round(prezzo_base * (1 - sconto / 100), 4)


# ── Prodotti ──────────────────────────────────

def get_prodotti(db: Session, search: str = None, tipo: str = None, attivo: bool = None,
                 skip: int = 0, limit: int = 50):
    q = db.query(models.Prodotto)
    if attivo is not None:
        q = q.filter(models.Prodotto.attivo == attivo)
    if tipo:
        q = q.filter(models.Prodotto.tipo == tipo)
    if search:
        term = f"%{search}%"
        q = q.filter(
            models.Prodotto.nome.ilike(term) |
            func.coalesce(models.Prodotto.codice, '').ilike(term) |
            func.coalesce(models.Prodotto.descrizione, '').ilike(term)
        )
    total = q.count()
    items = q.order_by(models.Prodotto.nome).offset(skip).limit(limit).all()
    return items, total


def get_prodotto(db: Session, prodotto_id: int):
    return db.query(models.Prodotto).filter(models.Prodotto.id == prodotto_id).first()


def create_prodotto(db: Session, prodotto: schemas.ProdottoCreate):
    db_obj = models.Prodotto(**prodotto.model_dump())
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def update_prodotto(db: Session, prodotto_id: int, prodotto: schemas.ProdottoUpdate):
    db_obj = get_prodotto(db, prodotto_id)
    if not db_obj:
        return None
    for k, v in prodotto.model_dump(exclude_unset=True).items():
        setattr(db_obj, k, v)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def delete_prodotto(db: Session, prodotto_id: int):
    db_obj = get_prodotto(db, prodotto_id)
    if db_obj:
        db_obj.attivo = False
        db.commit()
    return db_obj


# ── Piani Finanziari ─────────────────────────

def _normalize_optional_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _resolve_avviso_for_context(
    db: Session,
    *,
    avviso_id: Optional[int],
    avviso: Optional[str],
    ente_erogatore: Optional[str],
) -> Optional[models.Avviso]:
    if avviso_id is not None:
        return db.query(models.Avviso).filter(models.Avviso.id == avviso_id).first()
    normalized_avviso = _normalize_optional_text(avviso)
    normalized_ente = _normalize_optional_text(ente_erogatore)
    if not normalized_avviso:
        return None
    query = db.query(models.Avviso).filter(models.Avviso.codice == normalized_avviso)
    if normalized_ente:
        query = query.filter(models.Avviso.ente_erogatore == normalized_ente)
    return query.order_by(models.Avviso.id.desc()).first()


def _resolve_financial_template(
    db: Session,
    *,
    progetto: models.Project,
    ente_erogatore: str,
    avviso: Optional[str],
    avviso_id: Optional[int] = None,
    template_id: Optional[int] = None,
):
    normalized_fondo = _normalize_optional_text(ente_erogatore)
    normalized_avviso = _normalize_optional_text(avviso)
    project_ente_erogatore = _normalize_optional_text(getattr(progetto, "ente_erogatore", None))
    project_avviso = _normalize_optional_text(
        getattr(getattr(progetto, "avviso_rel", None), "codice", None) or getattr(progetto, "avviso", None)
    )

    if template_id is not None:
        template = db.query(models.ContractTemplate).filter(
            models.ContractTemplate.id == template_id,
            models.ContractTemplate.is_active == True,
        ).first()
        if not template:
            raise ValueError("Template piano finanziario non trovato")
        if template.ambito_template != "piano_finanziario":
            raise ValueError("Il template selezionato non è un template piano finanziario")
        if project_ente_erogatore and template.ente_erogatore and template.ente_erogatore != project_ente_erogatore:
            raise ValueError("Il template piano finanziario selezionato non coincide con l'ente erogatore del progetto")
        if project_avviso and template.avviso and template.avviso != project_avviso:
            raise ValueError("Il template piano finanziario selezionato non coincide con l'avviso del progetto")
        return template

    query = db.query(models.ContractTemplate).filter(
        models.ContractTemplate.is_active == True,
        models.ContractTemplate.ambito_template == "piano_finanziario",
    )

    if normalized_fondo:
        query = query.filter(
            or_(
                models.ContractTemplate.ente_erogatore == normalized_fondo,
                models.ContractTemplate.ente_erogatore.is_(None),
            )
        )

    if normalized_avviso:
        query = query.filter(
            or_(
                models.ContractTemplate.avviso == normalized_avviso,
                models.ContractTemplate.avviso.is_(None),
            )
        )
    elif avviso_id is not None:
        linked_avviso = db.query(models.Avviso).filter(models.Avviso.id == avviso_id).first()
        if linked_avviso:
            query = query.filter(
                or_(
                    models.ContractTemplate.id == linked_avviso.template_id,
                    models.ContractTemplate.avviso.is_(None),
                )
            )

    if progetto.id is not None:
        query = query.filter(
            or_(
                models.ContractTemplate.progetto_id == progetto.id,
                models.ContractTemplate.progetto_id.is_(None),
            )
        )

    if getattr(progetto, "ente_attuatore_id", None) is not None:
        query = query.filter(
            or_(
                models.ContractTemplate.ente_attuatore_id == progetto.ente_attuatore_id,
                models.ContractTemplate.ente_attuatore_id.is_(None),
            )
        )

    candidates = query.order_by(
        models.ContractTemplate.progetto_id.isnot(None).desc(),
        models.ContractTemplate.ente_attuatore_id.isnot(None).desc(),
        models.ContractTemplate.avviso.isnot(None).desc(),
        models.ContractTemplate.created_at.desc(),
    ).all()

    if not candidates:
        return None

    return candidates[0]

def _build_piani_finanziari_query(
    db: Session,
    *,
    progetto_id: Optional[int] = None,
    stato: Optional[str] = None,
):
    query = db.query(models.PianoFinanziario).options(
        joinedload(models.PianoFinanziario.progetto),
        joinedload(models.PianoFinanziario.template),
        joinedload(models.PianoFinanziario.avviso_piano),
        selectinload(models.PianoFinanziario.voci),
    )
    if progetto_id is not None:
        query = query.filter(models.PianoFinanziario.progetto_id == progetto_id)
    if stato is not None:
        query = query.filter(models.PianoFinanziario.stato == stato)
    return query


def get_template_piano(db: Session, template_id: int):
    return db.query(models.TemplatePianoFinanziario).filter(
        models.TemplatePianoFinanziario.id == template_id
    ).first()


def get_template_by_tipo_fondo(db: Session, tipo_fondo: str):
    return db.query(models.TemplatePianoFinanziario).filter(
        models.TemplatePianoFinanziario.tipo_fondo == tipo_fondo,
        models.TemplatePianoFinanziario.is_active == True,
    ).order_by(
        models.TemplatePianoFinanziario.created_at.desc(),
        models.TemplatePianoFinanziario.id.desc(),
    ).first()


def get_templates_piano(db: Session, skip: int = 0, limit: int = 100, solo_attivi: bool = True):
    query = db.query(models.TemplatePianoFinanziario)
    if solo_attivi:
        query = query.filter(models.TemplatePianoFinanziario.is_active == True)
    return query.order_by(
        models.TemplatePianoFinanziario.tipo_fondo.asc(),
        models.TemplatePianoFinanziario.nome.asc(),
    ).offset(skip).limit(limit).all()


def create_template_piano(db: Session, template: schemas.TemplatePianoFinanziarioCreate):
    payload = template.model_dump()
    db_template = models.TemplatePianoFinanziario(**payload)
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    logger.info(f"Creato template piano finanziario: {db_template.codice}")
    return db_template


def update_template_piano(db: Session, template_id: int, template: schemas.TemplatePianoFinanziarioUpdate):
    db_template = get_template_piano(db, template_id)
    if not db_template:
        return None
    for key, value in template.model_dump(exclude_unset=True).items():
        setattr(db_template, key, value)
    db.commit()
    db.refresh(db_template)
    return db_template


def delete_template_piano(db: Session, template_id: int, soft_delete: bool = True):
    db_template = get_template_piano(db, template_id)
    if not db_template:
        return None
    if soft_delete:
        db_template.is_active = False
        db.commit()
        db.refresh(db_template)
        return db_template
    db.delete(db_template)
    db.commit()
    return db_template


def get_avviso_piano(db: Session, avviso_id: int):
    return db.query(models.AvvisoPianoFinanziario).filter(
        models.AvvisoPianoFinanziario.id == avviso_id
    ).first()


def get_avvisi_piano(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    template_id: Optional[int] = None,
    solo_aperti: bool = False,
):
    query = db.query(models.AvvisoPianoFinanziario)
    if template_id is not None:
        query = query.filter(models.AvvisoPianoFinanziario.template_id == template_id)
    if solo_aperti:
        now = datetime.now()
        query = query.filter(
            models.AvvisoPianoFinanziario.data_apertura <= now,
            models.AvvisoPianoFinanziario.data_chiusura >= now,
            models.AvvisoPianoFinanziario.stato == "aperto",
            models.AvvisoPianoFinanziario.is_active == True,
        )
    return query.order_by(
        desc(models.AvvisoPianoFinanziario.data_apertura),
        desc(models.AvvisoPianoFinanziario.id),
    ).offset(skip).limit(limit).all()


def get_avvisi_by_template(db: Session, template_id: int, solo_aperti: bool = False):
    return get_avvisi_piano(db, skip=0, limit=1000, template_id=template_id, solo_aperti=solo_aperti)


def create_avviso_piano(db: Session, avviso: schemas.AvvisoPianoFinanziarioCreate):
    payload = avviso.model_dump()
    db_avviso = models.AvvisoPianoFinanziario(**payload)
    db.add(db_avviso)
    db.commit()
    db.refresh(db_avviso)
    logger.info(f"Creato avviso piano finanziario: {db_avviso.codice_avviso}")
    return db_avviso


def update_avviso_piano(db: Session, avviso_id: int, avviso: schemas.AvvisoPianoFinanziarioUpdate):
    db_avviso = get_avviso_piano(db, avviso_id)
    if not db_avviso:
        return None
    for key, value in avviso.model_dump(exclude_unset=True).items():
        setattr(db_avviso, key, value)
    db.commit()
    db.refresh(db_avviso)
    return db_avviso


def delete_avviso_piano(db: Session, avviso_id: int, soft_delete: bool = True):
    db_avviso = get_avviso_piano(db, avviso_id)
    if not db_avviso:
        return None
    if soft_delete:
        db_avviso.is_active = False
        if db_avviso.stato == "aperto":
            db_avviso.stato = "chiuso"
        db.commit()
        db.refresh(db_avviso)
        return db_avviso
    db.delete(db_avviso)
    db.commit()
    return db_avviso


def get_piani_finanziari(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    progetto_id: Optional[int] = None,
    stato: Optional[str] = None,
):
    return _build_piani_finanziari_query(
        db,
        progetto_id=progetto_id,
        stato=stato,
    ).order_by(
        desc(models.PianoFinanziario.anno),
        desc(models.PianoFinanziario.created_at),
        desc(models.PianoFinanziario.id),
    ).offset(skip).limit(limit).all()


def get_piani_finanziari_count(
    db: Session,
    progetto_id: Optional[int] = None,
    stato: Optional[str] = None,
):
    query = db.query(func.count(models.PianoFinanziario.id))
    if progetto_id is not None:
        query = query.filter(models.PianoFinanziario.progetto_id == progetto_id)
    if stato is not None:
        query = query.filter(models.PianoFinanziario.stato == stato)
    return query.scalar() or 0


def get_piano_finanziario(db: Session, piano_id: int):
    return _build_piani_finanziari_query(db).filter(
        models.PianoFinanziario.id == piano_id
    ).first()


def get_piano_by_progetto(db: Session, progetto_id: int):
    return db.query(models.PianoFinanziario).filter(
        models.PianoFinanziario.progetto_id == progetto_id
    ).order_by(
        desc(models.PianoFinanziario.created_at),
        desc(models.PianoFinanziario.id),
    ).first()


def get_piani_by_progetto(db: Session, progetto_id: int):
    return get_piani_finanziari(
        db,
        skip=0,
        limit=1000,
        progetto_id=progetto_id,
    )


def calcola_budget_utilizzato(db: Session, piano_id: int) -> float:
    totale = db.query(
        func.coalesce(func.sum(models.VocePianoFinanziario.importo_consuntivo), 0.0)
    ).filter(
        models.VocePianoFinanziario.piano_id == piano_id
    ).scalar()
    return float(totale or 0.0)


def _emit_piano_budget_threshold_event(db: Session, piano_obj: models.PianoFinanziario) -> None:
    riepilogo = build_piano_finanziario_riepilogo(piano_obj, db=db)
    totale_preventivo = float(riepilogo.get("totale_preventivo") or 0.0)
    totale_consuntivo = float(riepilogo.get("totale_consuntivo") or 0.0)
    if totale_preventivo <= 0:
        return

    usage = totale_consuntivo / totale_preventivo
    if usage < 0.9:
        return

    enqueue_webhook_notification(
        event_type="piano_finanziario_budget_threshold",
        payload={
            "piano_id": piano_obj.id,
            "progetto_id": piano_obj.progetto_id,
            "anno": piano_obj.anno,
            "ente_erogatore": piano_obj.ente_erogatore,
            "avviso": (piano_obj.avviso_piano.codice_avviso if getattr(piano_obj, "avviso_piano", None) else piano_obj.avviso),
            "totale_consuntivo": totale_consuntivo,
            "totale_preventivo": totale_preventivo,
            "usage_percentage": round(usage * 100, 2),
            "threshold_percentage": 90.0,
            "warning_code": "budget_90_reached",
        },
    )


@track_entity_event("piano_finanziario", "created")
def create_piano_finanziario(db: Session, piano: schemas.PianoFinanziarioCreate):
    progetto = get_project(db, piano.progetto_id)
    if not progetto:
        raise ValueError("Progetto non trovato")
    payload = piano.model_dump()
    normalized_ente = ((getattr(progetto, "ente_erogatore", None) or "Formazienda").strip() or "Formazienda")
    normalized_avviso = ((getattr(progetto, "avviso", None) or "").strip())
    derived_anno = (
        getattr(piano, "data_inizio", None).year
        if getattr(piano, "data_inizio", None) is not None
        else datetime.now().year
    )
    existing = db.query(models.PianoFinanziario).filter(
        models.PianoFinanziario.progetto_id == piano.progetto_id,
        models.PianoFinanziario.anno == derived_anno,
        models.PianoFinanziario.ente_erogatore == normalized_ente,
        models.PianoFinanziario.avviso == normalized_avviso,
    ).first()
    if existing:
        suffix = f" / avviso {normalized_avviso}" if normalized_avviso else ""
        raise ValueError(
            f"Esiste già un piano finanziario {normalized_ente}{suffix} per questo progetto e anno"
        )

    payload["anno"] = derived_anno
    payload["ente_erogatore"] = normalized_ente
    payload["avviso"] = normalized_avviso
    payload["codice_piano"] = payload.get("codice_piano") or f"PF-{piano.progetto_id}-{str(uuid.uuid4())[:8].upper()}"
    payload["budget_approvato"] = float(payload.get("budget_approvato") or 0.0)
    payload["budget_utilizzato"] = float(payload.get("budget_utilizzato") or 0.0)
    payload["budget_rimanente"] = float(payload.get("budget_totale") or 0.0) - payload["budget_utilizzato"]
    payload["legacy_avviso_id"] = getattr(progetto, "avviso_id", None)
    payload["legacy_template_id"] = getattr(progetto, "template_piano_finanziario_id", None)

    if payload.get("template_id") is None and payload.get("tipo_fondo"):
        template = get_template_by_tipo_fondo(db, payload["tipo_fondo"])
        if template:
            payload["template_id"] = template.id

    if payload.get("avviso_id") is not None:
        avviso = get_avviso_piano(db, payload["avviso_id"])
        if not avviso:
            raise ValueError("Avviso piano finanziario non trovato")
        if payload.get("template_id") and avviso.template_id != payload["template_id"]:
            raise ValueError("L'avviso selezionato non appartiene al template indicato")

    db_obj = models.PianoFinanziario(**payload)
    db.add(db_obj)
    db.flush()

    for row in build_default_voci():
        db.add(models.VocePianoFinanziario(piano_id=db_obj.id, **row))

    db.commit()
    created = get_piano_finanziario(db, db_obj.id)
    _create_audit_log(
        db,
        entity="piano_finanziario",
        action="create",
        old_value=None,
        new_value={
            "id": created.id,
            "progetto_id": created.progetto_id,
            "nome": created.nome,
            "tipo_fondo": created.tipo_fondo,
            "stato": created.stato,
            "budget_totale": created.budget_totale,
        },
    )
    db.commit()
    _emit_piano_budget_threshold_event(db, created)
    return created


@track_entity_event(
    "piano_finanziario",
    "updated",
    entity_id_getter=lambda result, args, kwargs: (
        getattr(result, "id", None)
        or kwargs.get("piano_id")
        or (args[1] if len(args) > 1 else None)
    ),
)
def update_piano_finanziario(
    db: Session,
    piano_id: int,
    piano: schemas.PianoFinanziarioUpdate,
):
    db_obj = get_piano_finanziario(db, piano_id)
    if not db_obj:
        return None

    update_data = piano.model_dump(exclude_unset=True)
    old_value = {
        "nome": db_obj.nome,
        "tipo_fondo": db_obj.tipo_fondo,
        "budget_totale": db_obj.budget_totale,
        "budget_utilizzato": db_obj.budget_utilizzato,
        "data_inizio": db_obj.data_inizio,
        "data_fine": db_obj.data_fine,
        "stato": db_obj.stato,
        "note": db_obj.note,
    }

    data_inizio = update_data.get("data_inizio", db_obj.data_inizio)
    data_fine = update_data.get("data_fine", db_obj.data_fine)
    if data_inizio and data_fine and data_fine < data_inizio:
        raise ValueError("data_fine deve essere successiva a data_inizio")

    for key, value in update_data.items():
        setattr(db_obj, key, value)

    if "data_inizio" in update_data and update_data["data_inizio"] is not None:
        db_obj.anno = update_data["data_inizio"].year

    if "budget_utilizzato" not in update_data:
        db_obj.aggiorna_budget_utilizzato(db)
    else:
        db_obj.budget_rimanente = float(db_obj.budget_totale or 0.0) - float(db_obj.budget_utilizzato or 0.0)

    db.commit()
    db.refresh(db_obj)
    updated = get_piano_finanziario(db, piano_id)
    _create_audit_log(
        db,
        entity="piano_finanziario",
        action="update",
        old_value=old_value,
        new_value={
            "id": updated.id,
            "nome": updated.nome,
            "tipo_fondo": updated.tipo_fondo,
            "budget_totale": updated.budget_totale,
            "budget_utilizzato": updated.budget_utilizzato,
            "data_inizio": updated.data_inizio,
            "data_fine": updated.data_fine,
            "stato": updated.stato,
            "note": updated.note,
        },
    )
    db.commit()
    _emit_piano_budget_threshold_event(db, updated)
    return updated


@track_entity_event(
    "piano_finanziario",
    "deleted",
    entity_id_getter=lambda result, args, kwargs: (
        getattr(result, "id", None)
        or kwargs.get("piano_id")
        or (args[1] if len(args) > 1 else None)
    ),
)
def delete_piano_finanziario(
    db: Session,
    piano_id: int,
    soft_delete: bool = True,
):
    db_obj = get_piano_finanziario(db, piano_id)
    if not db_obj:
        return None

    old_value = {
        "id": db_obj.id,
        "nome": db_obj.nome,
        "stato": db_obj.stato,
        "progetto_id": db_obj.progetto_id,
    }

    if soft_delete:
        db_obj.stato = "chiuso"
        db_obj.aggiorna_budget_utilizzato(db)
        db.commit()
        db.refresh(db_obj)
        result = get_piano_finanziario(db, piano_id)
        action = "soft_delete"
    else:
        result = db_obj
        db.delete(db_obj)
        db.commit()
        action = "delete"

    _create_audit_log(
        db,
        entity="piano_finanziario",
        action=action,
        old_value=old_value,
        new_value=None if not soft_delete else {
            "id": result.id,
            "stato": result.stato,
        },
    )
    db.commit()
    return result


def _sync_piano_budget_utilizzato(db: Session, piano_id: int) -> Optional[models.PianoFinanziario]:
    piano = db.query(models.PianoFinanziario).filter(
        models.PianoFinanziario.id == piano_id
    ).first()
    if not piano:
        return None
    piano.aggiorna_budget_utilizzato(db)
    return piano


def get_voce_piano(db: Session, voce_id: int):
    return db.query(models.VocePianoFinanziario).options(
        joinedload(models.VocePianoFinanziario.piano),
        joinedload(models.VocePianoFinanziario.collaborator),
        joinedload(models.VocePianoFinanziario.assignment),
    ).filter(
        models.VocePianoFinanziario.id == voce_id
    ).first()


def get_voci_piano(db: Session, piano_id: int):
    return db.query(models.VocePianoFinanziario).options(
        joinedload(models.VocePianoFinanziario.collaborator),
        joinedload(models.VocePianoFinanziario.assignment),
    ).filter(
        models.VocePianoFinanziario.piano_id == piano_id
    ).order_by(
        asc(models.VocePianoFinanziario.macrovoce),
        asc(models.VocePianoFinanziario.voce_codice),
        asc(models.VocePianoFinanziario.id),
    ).all()


def get_voce_by_mansione(db: Session, piano_id: int, mansione: str):
    return db.query(models.VocePianoFinanziario).filter(
        models.VocePianoFinanziario.piano_id == piano_id,
        models.VocePianoFinanziario.mansione_riferimento == mansione,
    ).order_by(models.VocePianoFinanziario.id.asc()).first()


def get_voce_by_assignment(db: Session, assignment_id: int):
    return db.query(models.VocePianoFinanziario).filter(
        models.VocePianoFinanziario.assignment_id == assignment_id
    ).order_by(models.VocePianoFinanziario.id.asc()).first()


def _derive_categoria_from_role(role: Optional[str]) -> str:
    normalized = (role or "").strip().lower()
    if not normalized:
        return "altro"
    if "docen" in normalized:
        return "docenza"
    if "tutor" in normalized:
        return "tutoraggio"
    if "coordin" in normalized:
        return "coordinamento"
    if "progett" in normalized:
        return "progettazione"
    if "material" in normalized:
        return "materiali"
    if "aula" in normalized:
        return "aula"
    if "viagg" in normalized:
        return "viaggi"
    return "altro"


def _build_voce_payload_from_assignment(
    piano: models.PianoFinanziario,
    assignment: models.Assignment,
    *,
    existing_voce: Optional[models.VocePianoFinanziario] = None,
) -> dict[str, Any]:
    voice_map = get_voice_template_map()
    voce_codice, mansione_label = _normalize_assignment_role_to_voce(assignment.role, set(voice_map.keys()))
    template = voice_map.get(voce_codice) if voce_codice else None
    categoria = _derive_categoria_from_role(assignment.role)
    assigned_hours = float(assignment.assigned_hours or 0.0)
    completed_hours = float(assignment.completed_hours or 0.0)
    hourly_rate = float(assignment.hourly_rate or 0.0)
    preventivo = round(assigned_hours * hourly_rate, 2)
    consuntivo = round(completed_hours * hourly_rate, 2)

    return {
        "piano_id": piano.id,
        "macrovoce": template["macrovoce"] if template else getattr(existing_voce, "macrovoce", None) or "D",
        "voce_codice": voce_codice or getattr(existing_voce, "voce_codice", None) or "AUTO",
        "categoria": categoria,
        "descrizione": getattr(existing_voce, "descrizione", None) or (template["descrizione"] if template else (assignment.role or "Voce automatica")),
        "mansione_riferimento": mansione_label or assignment.role,
        "assignment_id": assignment.id,
        "collaborator_id": assignment.collaborator_id,
        "progetto_label": getattr(existing_voce, "progetto_label", None) or (piano.progetto.name if getattr(piano, "progetto", None) else None),
        "edizione_label": assignment.edizione_label or getattr(existing_voce, "edizione_label", None),
        "ore": completed_hours,
        "ore_previste": assigned_hours,
        "ore_effettive": completed_hours,
        "tariffa_oraria": hourly_rate,
        "importo_preventivo": preventivo,
        "importo_approvato": float(getattr(existing_voce, "importo_approvato", 0.0) or 0.0),
        "importo_consuntivo": consuntivo,
        "importo_validato": float(getattr(existing_voce, "importo_validato", 0.0) or 0.0),
        "importo_presentato": consuntivo,
        "stato": "rendicontato" if completed_hours > 0 else "previsto",
    }


def collega_assegnazione_a_piano(db: Session, assignment_id: int):
    assignment = db.query(models.Assignment).filter(
        models.Assignment.id == assignment_id
    ).first()
    if not assignment:
        logger.warning(f"Assignment {assignment_id} non trovato")
        return None

    piano = get_piano_by_progetto(db, assignment.project_id)
    if not piano:
        logger.info(f"Progetto {assignment.project_id} senza piano finanziario: nessun collegamento automatico")
        return None

    voce = get_voce_by_assignment(db, assignment.id)
    if not voce:
        voce = get_voce_by_mansione(db, piano.id, assignment.role)
        if voce and voce.assignment_id not in (None, assignment.id):
            voce = None

    payload = _build_voce_payload_from_assignment(piano, assignment, existing_voce=voce)

    if voce:
        for key, value in payload.items():
            setattr(voce, key, value)
    else:
        voce = models.VocePianoFinanziario(**payload)
        db.add(voce)

    db.flush()
    voce.aggiorna_da_presenze(db)
    piano.aggiorna_budget_utilizzato(db)
    db.commit()
    db.refresh(voce)
    return voce


def aggiorna_voce_da_presenze(db: Session, voce_id: int):
    db_voce = get_voce_piano(db, voce_id)
    if not db_voce:
        return None
    db_voce.aggiorna_da_presenze(db)
    piano = db.query(models.PianoFinanziario).filter(
        models.PianoFinanziario.id == db_voce.piano_id
    ).first()
    if piano:
        piano.aggiorna_budget_utilizzato(db)
    db.commit()
    db.refresh(db_voce)
    return db_voce


def create_voce_piano(db: Session, voce: schemas.VocePianoFinanziarioCreate):
    piano = get_piano_finanziario(db, voce.piano_id)
    if not piano:
        raise ValueError("Piano finanziario non trovato")

    payload = voce.model_dump()
    payload.setdefault("macrovoce", "D")
    payload.setdefault("voce_codice", "CUSTOM")
    payload.setdefault("descrizione", payload.get("descrizione") or "")
    payload.setdefault("ore_previste", float(payload.get("ore_previste") or 0.0))
    payload.setdefault("ore_effettive", float(payload.get("ore_effettive") or 0.0))
    payload.setdefault("ore", float(payload.get("ore_effettive") or 0.0))
    payload.setdefault("tariffa_oraria", float(payload.get("tariffa_oraria") or 0.0))
    payload.setdefault("importo_approvato", float(payload.get("importo_approvato") or 0.0))
    payload.setdefault("importo_validato", float(payload.get("importo_validato") or 0.0))
    payload.setdefault("importo_presentato", float(payload.get("importo_consuntivo") or payload.get("importo_preventivo") or 0.0))
    payload.setdefault("progetto_label", None)
    payload.setdefault("edizione_label", None)

    db_obj = models.VocePianoFinanziario(**payload)
    db.add(db_obj)
    db.flush()
    _sync_piano_budget_utilizzato(db, voce.piano_id)
    db.commit()
    db.refresh(db_obj)
    return get_voce_piano(db, db_obj.id)


def update_voce_piano(
    db: Session,
    voce_id: int,
    voce: schemas.VocePianoFinanziarioUpdate,
):
    db_obj = get_voce_piano(db, voce_id)
    if not db_obj:
        return None

    update_data = voce.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_obj, key, value)

    if "importo_preventivo" in update_data and "importo_consuntivo" not in update_data:
        db_obj.importo_presentato = float(db_obj.importo_preventivo or 0.0)
    elif "importo_consuntivo" in update_data:
        db_obj.importo_presentato = float(db_obj.importo_consuntivo or 0.0)

    if "ore_effettive" in update_data and "ore" not in update_data:
        db_obj.ore = float(db_obj.ore_effettive or 0.0)

    _sync_piano_budget_utilizzato(db, db_obj.piano_id)
    db.commit()
    db.refresh(db_obj)
    return get_voce_piano(db, voce_id)


def delete_voce_piano(db: Session, voce_id: int):
    db_obj = get_voce_piano(db, voce_id)
    if not db_obj:
        return None

    piano_id = db_obj.piano_id
    result = db_obj
    db.delete(db_obj)
    db.flush()
    _sync_piano_budget_utilizzato(db, piano_id)
    db.commit()
    return result


def _normalize_voci_piano_payload(voci: List[schemas.VocePianoFinanziarioUpsert]) -> List[dict]:
    voice_map = get_voice_template_map()
    normalized = []
    fixed_seen = set()
    dynamic_seen = set()
    edition_tracker = defaultdict(set)

    for item in voci:
        data = item.model_dump()
        template = voice_map.get(data["voce_codice"])
        if not template:
            raise ValueError(f"Voce piano non riconosciuta: {data['voce_codice']}")

        data["macrovoce"] = template["macrovoce"]
        data["descrizione"] = (data.get("descrizione") or template["descrizione"]).strip()
        data["progetto_label"] = (data.get("progetto_label") or None)
        data["edizione_label"] = (data.get("edizione_label") or None)

        if template["is_dynamic"]:
            if not data["progetto_label"] or not data["edizione_label"]:
                raise ValueError(f"{data['voce_codice']} richiede progetto_label ed edizione_label")
            unique_key = (data["voce_codice"], data["progetto_label"], data["edizione_label"])
            if unique_key in dynamic_seen:
                raise ValueError(f"Duplicato non ammesso per {data['voce_codice']} / {data['progetto_label']} / {data['edizione_label']}")
            dynamic_seen.add(unique_key)
            edition_key = (data["voce_codice"], data["progetto_label"])
            edition_tracker[edition_key].add(data["edizione_label"])
            if len(edition_tracker[edition_key]) > 15:
                raise ValueError(f"{data['voce_codice']} supera il limite di 15 edizioni per progetto")
        else:
            data["progetto_label"] = None
            data["edizione_label"] = None
            if data["voce_codice"] in fixed_seen:
                raise ValueError(f"La voce {data['voce_codice']} può comparire una sola volta")
            fixed_seen.add(data["voce_codice"])

        normalized.append(data)

    for voce_codice, template in voice_map.items():
        if template["is_dynamic"]:
            continue
        if voce_codice not in fixed_seen:
            normalized.append({
                "id": None,
                "macrovoce": template["macrovoce"],
                "voce_codice": voce_codice,
                "descrizione": template["descrizione"],
                "progetto_label": None,
                "edizione_label": None,
                "ore": 0.0,
                "importo_consuntivo": 0.0,
                "importo_preventivo": 0.0,
                "importo_presentato": 0.0,
            })

    return normalized


@track_entity_event(
    "piano_finanziario",
    "updated",
    entity_id_getter=lambda result, args, kwargs: (
        getattr(result, "id", None)
        or kwargs.get("piano_id")
        or (args[1] if len(args) > 1 else None)
    ),
)
def bulk_upsert_voci_piano(db: Session, piano_id: int, payload: schemas.PianoFinanziarioBulkUpdate):
    piano = get_piano_finanziario(db, piano_id)
    if not piano:
        return None

    normalized = _normalize_voci_piano_payload(payload.voci)
    existing_by_id = {voce.id: voce for voce in piano.voci}
    kept_ids = set()

    for item in normalized:
        voice_id = item.pop("id", None)
        if voice_id and voice_id in existing_by_id:
            db_obj = existing_by_id[voice_id]
            for key, value in item.items():
                setattr(db_obj, key, value)
            kept_ids.add(db_obj.id)
        else:
            db_obj = models.VocePianoFinanziario(piano_id=piano_id, **item)
            db.add(db_obj)
            db.flush()
            kept_ids.add(db_obj.id)

    for existing in list(piano.voci):
        if existing.id not in kept_ids:
            db.delete(existing)

    db.commit()
    updated = get_piano_finanziario(db, piano_id)
    _create_audit_log(
        db,
        entity="piano_finanziario",
        action="update_voci",
        old_value={"piano_id": piano_id},
        new_value={"piano_id": piano_id, "updated_voci": len(normalized)},
    )
    db.commit()
    _emit_piano_budget_threshold_event(db, updated)
    return updated


def build_effective_piano_rows(piano: models.PianoFinanziario, db: Session | None = None) -> List[dict]:
    rows = [
        {
            "id": voce.id,
            "piano_id": voce.piano_id,
            "macrovoce": voce.macrovoce,
            "voce_codice": voce.voce_codice,
            "descrizione": voce.descrizione,
            "progetto_label": voce.progetto_label,
            "edizione_label": voce.edizione_label,
            "ore": float(voce.ore or voce.ore_effettive or 0.0),
            "ore_previste": float(voce.ore_previste or 0.0),
            "ore_effettive": float(voce.ore_effettive or voce.ore or 0.0),
            "tariffa_oraria": float(voce.tariffa_oraria or 0.0),
            "importo_consuntivo": float(voce.importo_consuntivo or 0.0),
            "importo_preventivo": float(voce.importo_preventivo or 0.0),
            "importo_approvato": float(voce.importo_approvato or 0.0),
            "importo_validato": float(voce.importo_validato or 0.0),
            "importo_presentato": float(voce.importo_presentato or 0.0),
            "created_at": voce.created_at,
            "updated_at": voce.updated_at,
            "collaborator_id": getattr(voce, 'collaborator_id', None),
            "assignment_id": getattr(voce, 'assignment_id', None),
            "mansione_riferimento": getattr(voce, 'mansione_riferimento', None),
        }
        for voce in piano.voci
    ]

    if db is None:
        return rows

    template_map = get_voice_template_map()
    available_codes = set(template_map.keys())
    dynamic_codes = {
        code for code, template in template_map.items()
        if template["is_dynamic"]
    }
    explicit_assignment_ids = {
        row["assignment_id"]
        for row in rows
        if row.get("assignment_id") is not None
    }

    attendance_subquery = (
        db.query(
            models.Attendance.assignment_id.label("assignment_id"),
            func.sum(models.Attendance.hours).label("ore_effettive"),
        )
        .group_by(models.Attendance.assignment_id)
        .subquery()
    )

    assignments = (
        db.query(
            models.Assignment,
            models.Collaborator.first_name,
            models.Collaborator.last_name,
            attendance_subquery.c.ore_effettive,
        )
        .join(models.Collaborator, models.Collaborator.id == models.Assignment.collaborator_id)
        .outerjoin(attendance_subquery, attendance_subquery.c.assignment_id == models.Assignment.id)
        .filter(
            models.Assignment.project_id == piano.progetto_id,
            models.Assignment.is_active == True,
        )
        .all()
    )

    fixed_aggregates: Dict[str, dict] = {}
    generated_dynamic_rows: List[dict] = []

    for assignment, first_name, last_name, ore_effettive in assignments:
        if assignment.id in explicit_assignment_ids:
            continue

        voce_codice, _ = _normalize_assignment_role_to_voce(assignment.role, available_codes)
        if not voce_codice:
            continue

        template = template_map[voce_codice]
        assigned_hours = float(assignment.assigned_hours or 0.0)
        effective_hours = float(ore_effettive or 0.0)
        hourly_rate = float(assignment.hourly_rate or 0.0)
        preventivo = round(assigned_hours * hourly_rate, 2)
        consuntivo = round(effective_hours * hourly_rate, 2)
        collaborator_name = " ".join(part for part in [first_name, last_name] if part).strip() or f"Collaboratore {assignment.collaborator_id}"
        edizione_label = (assignment.edizione_label or "").strip() or collaborator_name

        if template["is_dynamic"]:
            generated_dynamic_rows.append({
                "id": None,
                "piano_id": piano.id,
                "macrovoce": template["macrovoce"],
                "voce_codice": voce_codice,
                "descrizione": template["descrizione"],
                "progetto_label": piano.progetto.name if piano.progetto else None,
                "edizione_label": edizione_label,
                "ore": assigned_hours,
                "importo_consuntivo": consuntivo,
                "importo_preventivo": preventivo,
                "importo_presentato": 0.0,
                "created_at": piano.created_at,
                "updated_at": piano.updated_at,
                "collaborator_id": assignment.collaborator_id,
            })
            continue

        aggregate = fixed_aggregates.setdefault(voce_codice, {
            "ore": 0.0,
            "importo_consuntivo": 0.0,
            "importo_preventivo": 0.0,
            "importo_presentato": 0.0,
        })
        aggregate["ore"] += assigned_hours
        aggregate["importo_consuntivo"] += consuntivo
        aggregate["importo_preventivo"] += preventivo

    for row in rows:
        aggregate = fixed_aggregates.get(row["voce_codice"])
        if aggregate:
            row["ore"] = round(aggregate["ore"], 2)
            row["importo_consuntivo"] = round(aggregate["importo_consuntivo"], 2)
            row["importo_preventivo"] = round(aggregate["importo_preventivo"], 2)

    existing_dynamic_rows = [row for row in rows if row["voce_codice"] in dynamic_codes]
    existing_dynamic_index = {
        (row["voce_codice"], row["progetto_label"] or "", row["edizione_label"] or ""): row
        for row in existing_dynamic_rows
    }

    for generated_row in generated_dynamic_rows:
        match_key = (
            generated_row["voce_codice"],
            generated_row["progetto_label"] or "",
            generated_row["edizione_label"] or "",
        )
        matched_row = existing_dynamic_index.get(match_key)
        if matched_row:
            matched_row["ore"] = generated_row["ore"]
            matched_row["importo_consuntivo"] = generated_row["importo_consuntivo"]
            matched_row["importo_preventivo"] = generated_row["importo_preventivo"]
        else:
            rows.append(generated_row)

    rows = [
        row for row in rows
        if row["voce_codice"] not in dynamic_codes
        or any(float(row[field] or 0.0) for field in ("ore", "importo_consuntivo", "importo_preventivo", "importo_presentato"))
    ]

    return rows


def _normalize_assignment_role_to_voce(role: str | None, available_codes: set[str] | None = None) -> tuple[str | None, str | None]:
    role_str = (role or "").strip()
    if not role_str:
        return (None, None)

    known_codes = available_codes or set(get_voice_template_map().keys())
    upper_role = role_str.upper()
    for code in sorted(known_codes, key=len, reverse=True):
        if upper_role.startswith(code.upper()):
            return (code, role_str)

    normalized = " ".join(role_str.lower().replace("-", " ").replace("_", " ").split())
    keyword_map = [
        ("docente", "B.2"),
        ("docenza", "B.2"),
        ("tutor", "B.3"),
        ("coordin", "B.1"),
        ("progett", "A.1"),
        ("fabbisogn", "A.2"),
        ("promoz", "A.3"),
        ("monitor", "A.4"),
        ("valutaz", "A.4"),
        ("diffusion", "A.5"),
        ("designer", "C.1"),
        ("amminist", "C.2"),
        ("rendicont", "C.3"),
        ("revis", "C.4"),
        ("fidejuss", "C.5"),
        ("assicur", "D.2"),
    ]
    for keyword, voce_codice in keyword_map:
        if keyword in normalized and voce_codice in known_codes:
            return (voce_codice, role_str)

    return (None, role_str)


def build_piano_finanziario_riepilogo(piano: models.PianoFinanziario, db: Session = None) -> dict:
    totals = {
        "consuntivo": defaultdict(float),
        "preventivo": defaultdict(float),
    }
    alerts = []

    effective_rows = build_effective_piano_rows(piano, db=db)

    for voce in effective_rows:
        totals["consuntivo"][voce["macrovoce"]] += float(voce["importo_consuntivo"] or 0.0)
        totals["preventivo"][voce["macrovoce"]] += float(voce["importo_preventivo"] or 0.0)

    totale_consuntivo = sum(totals["consuntivo"].values())
    totale_preventivo = sum(totals["preventivo"].values())
    contributo_richiesto = totals["consuntivo"]["A"] + totals["consuntivo"]["B"] + totals["consuntivo"]["C"]
    cofinanziamento = totals["consuntivo"]["D"]

    macrovoci = []
    for macrovoce in ["A", "B", "C", "D"]:
        importo_consuntivo = round(totals["consuntivo"][macrovoce], 2)
        importo_preventivo = round(totals["preventivo"][macrovoce], 2)
        limite = MACROVOCE_LIMITS.get(macrovoce)
        percentuale_consuntivo = round((importo_consuntivo / totale_consuntivo) * 100, 2) if totale_consuntivo else 0.0
        percentuale_preventivo = round((importo_preventivo / totale_preventivo) * 100, 2) if totale_preventivo else 0.0
        alert_level = "ok"
        sforata = False

        if limite is not None:
            if percentuale_consuntivo > limite:
                alert_level = "danger"
                sforata = True
                alerts.append({
                    "level": "danger",
                    "code": f"macrovoce_{macrovoce.lower()}_over_limit",
                    "message": f"La Macrovoce {macrovoce} supera il limite del {limite:.0f}% sul consuntivo.",
                })
            elif percentuale_consuntivo >= limite * 0.9:
                alert_level = "warning"
                alerts.append({
                    "level": "warning",
                    "code": f"macrovoce_{macrovoce.lower()}_near_limit",
                    "message": f"La Macrovoce {macrovoce} è vicina al limite del {limite:.0f}% sul consuntivo.",
                })

        macrovoci.append({
            "macrovoce": macrovoce,
            "titolo": MACROVOCE_TITLES[macrovoce],
            "limite_percentuale": limite,
            "importo_consuntivo": importo_consuntivo,
            "importo_preventivo": importo_preventivo,
            "percentuale_consuntivo": percentuale_consuntivo,
            "percentuale_preventivo": percentuale_preventivo,
            "alert_level": alert_level,
            "sforata": sforata,
        })

    voce_c6 = next((voce for voce in effective_rows if voce["voce_codice"] == "C.6"), None)
    importo_c6 = float(voce_c6["importo_preventivo"] or 0.0) if voce_c6 else 0.0
    percentuale_c6 = round((importo_c6 / totale_preventivo) * 100, 2) if totale_preventivo else 0.0
    if totale_preventivo and percentuale_c6 > 10:
        alerts.append({
            "level": "danger",
            "code": "c6_over_limit",
            "message": "La voce C.6 supera il limite del 10% sul totale preventivo.",
        })
    elif totale_preventivo and percentuale_c6 >= 9:
        alerts.append({
            "level": "warning",
            "code": "c6_near_limit",
            "message": "La voce C.6 è vicina al limite del 10% sul totale preventivo.",
        })

    if totals["consuntivo"]["D"] > 0:
        alerts.append({
            "level": "info",
            "code": "macrovoce_d_cofinanziamento",
            "message": "La Macrovoce D viene conteggiata solo come cofinanziamento aziendale.",
        })

    # Aggrega le ore di presenze effettive per ruolo (solo se db disponibile)
    ore_per_ruolo = []
    ore_effettive_totali = 0.0

    if db is not None:
        voce_map = {v.voce_codice: v for v in piano.voci}
        template_map = get_voice_template_map()
        available_codes = set(template_map.keys())

        rows = (
            db.query(
                models.Assignment.collaborator_id,
                models.Collaborator.first_name,
                models.Collaborator.last_name,
                models.Assignment.role,
                models.Assignment.hourly_rate,
                func.sum(models.Attendance.hours).label("ore_effettive"),
                func.count(models.Attendance.id).label("n_presenze"),
            )
            .join(models.Collaborator, models.Collaborator.id == models.Assignment.collaborator_id)
            .join(models.Attendance, models.Attendance.assignment_id == models.Assignment.id)
            .filter(
                models.Assignment.project_id == piano.progetto_id,
                models.Assignment.is_active == True,
                models.Collaborator.is_active == True,
            )
            .group_by(
                models.Assignment.collaborator_id,
                models.Collaborator.first_name,
                models.Collaborator.last_name,
                models.Assignment.role,
                models.Assignment.hourly_rate,
            )
            .all()
        )

        for row in rows:
            ore = float(row.ore_effettive or 0)
            costo = round(ore * float(row.hourly_rate or 0), 2)
            ore_effettive_totali += ore
            voce_codice, role_str = _normalize_assignment_role_to_voce(row.role, available_codes)
            collaborator_name = " ".join(
                part for part in [row.first_name, row.last_name] if part
            ).strip() or None
            voce = voce_map.get(voce_codice) if voce_codice else None
            template = template_map.get(voce_codice) if voce_codice else None

            ore_per_ruolo.append({
                "collaborator_id": row.collaborator_id,
                "collaborator_name": collaborator_name,
                "role": role_str,
                "n_presenze": int(row.n_presenze or 0),
                "ore_effettive": round(ore, 2),
                "costo_effettivo": costo,
                "voce_codice": voce_codice,
                "voce_label": (
                    f"{voce_codice} - {(voce.descrizione if voce else template['descrizione'])}"
                    if voce_codice and (voce or template)
                    else None
                ),
            })

        ore_per_ruolo.sort(
            key=lambda item: (
                item["voce_codice"] or "ZZZ",
                item["collaborator_name"] or "",
                -item["ore_effettive"],
            )
        )

    return {
        "piano_id": piano.id,
        "totale_consuntivo": round(totale_consuntivo, 2),
        "totale_preventivo": round(totale_preventivo, 2),
        "contributo_richiesto": round(contributo_richiesto, 2),
        "cofinanziamento": round(cofinanziamento, 2),
        "macrovoci": macrovoci,
        "alerts": alerts,
        "ore_per_ruolo": ore_per_ruolo,
        "ore_effettive_totali": round(ore_effettive_totali, 2),
    }


# ── Piani Fondimpresa ───────────────────────

def get_piani_fondimpresa(db: Session, progetto_id: Optional[int] = None, skip: int = 0, limit: int = 100):
    query = db.query(models.PianoFinanziarioFondimpresa).options(
        joinedload(models.PianoFinanziarioFondimpresa.progetto)
    )
    if progetto_id is not None:
        query = query.filter(models.PianoFinanziarioFondimpresa.progetto_id == progetto_id)
    return query.order_by(desc(models.PianoFinanziarioFondimpresa.anno), desc(models.PianoFinanziarioFondimpresa.created_at)).offset(skip).limit(limit).all()


def get_piano_fondimpresa(db: Session, piano_id: int):
    return db.query(models.PianoFinanziarioFondimpresa).options(
        joinedload(models.PianoFinanziarioFondimpresa.progetto),
        selectinload(models.PianoFinanziarioFondimpresa.voci).selectinload(models.VoceFondimpresa.righe_nominativo),
        selectinload(models.PianoFinanziarioFondimpresa.voci).selectinload(models.VoceFondimpresa.documenti),
        selectinload(models.PianoFinanziarioFondimpresa.dettaglio_budget).selectinload(models.DettaglioBudgetFondimpresa.consulenti),
        selectinload(models.PianoFinanziarioFondimpresa.dettaglio_budget).selectinload(models.DettaglioBudgetFondimpresa.costi_fissi),
        selectinload(models.PianoFinanziarioFondimpresa.dettaglio_budget).selectinload(models.DettaglioBudgetFondimpresa.margini),
    ).filter(models.PianoFinanziarioFondimpresa.id == piano_id).first()


def create_piano_fondimpresa(db: Session, piano: schemas.PianoFondimpresaCreate):
    existing = db.query(models.PianoFinanziarioFondimpresa).filter(
        models.PianoFinanziarioFondimpresa.progetto_id == piano.progetto_id,
        models.PianoFinanziarioFondimpresa.anno == piano.anno,
    ).first()
    if existing:
        raise ValueError("Esiste già un piano Fondimpresa per questo progetto e anno")

    project = get_project(db, piano.progetto_id)
    if not project:
        raise ValueError("Progetto non trovato")

    db_obj = models.PianoFinanziarioFondimpresa(**piano.model_dump())
    db.add(db_obj)
    db.flush()

    for row in build_default_voci_fondimpresa():
        db.add(models.VoceFondimpresa(piano_id=db_obj.id, **row))

    db.add(models.DettaglioBudgetFondimpresa(piano_id=db_obj.id))
    db.commit()
    return get_piano_fondimpresa(db, db_obj.id)


def _recalculate_voce_fondimpresa_totale(voce: models.VoceFondimpresa):
    totale_righe = sum((float(row.ore or 0.0) * float(row.costo_orario or 0.0)) for row in voce.righe_nominativo)
    totale_documenti = sum(float(documento.importo_imputato or 0.0) for documento in voce.documenti)
    voce.totale_voce = round(max(totale_righe, totale_documenti), 2)


def bulk_upsert_voci_fondimpresa(db: Session, piano_id: int, payload: schemas.PianoFondimpresaBulkUpdate):
    piano = get_piano_fondimpresa(db, piano_id)
    if not piano:
        return None

    template_map = get_fondimpresa_voice_template_map()
    existing_by_id = {voce.id: voce for voce in piano.voci}
    kept_ids = set()

    for item in payload.voci:
        data = item.model_dump()
        template = template_map.get(data["voce_codice"])
        if not template:
            raise ValueError(f"Voce Fondimpresa non riconosciuta: {data['voce_codice']}")

        voce_id = data.pop("id", None)
        righe = data.pop("righe_nominativo", [])
        data.pop("documenti", None)
        data["sezione"] = template["sezione"]
        data["descrizione"] = data.get("descrizione") or template["descrizione"]
        data["note_temporali"] = data.get("note_temporali") or template["note_temporali"]

        if voce_id and voce_id in existing_by_id:
            voce = existing_by_id[voce_id]
            for key, value in data.items():
                setattr(voce, key, value)
        else:
            voce = models.VoceFondimpresa(piano_id=piano_id, **data)
            db.add(voce)
            db.flush()
        kept_ids.add(voce.id)

        existing_righe_by_id = {row.id: row for row in voce.righe_nominativo}
        kept_row_ids = set()
        for row_data in righe:
            row_payload = row_data.copy()
            row_id = row_payload.pop("id", None)
            totale = round((float(row_payload.get("ore") or 0.0) * float(row_payload.get("costo_orario") or 0.0)), 2)
            row_payload["totale"] = totale
            if row_id and row_id in existing_righe_by_id:
                row = existing_righe_by_id[row_id]
                for key, value in row_payload.items():
                    setattr(row, key, value)
            else:
                row = models.RigaNominativoFondimpresa(voce_id=voce.id, **row_payload)
                db.add(row)
                db.flush()
            kept_row_ids.add(row.id)

        for existing_row in list(voce.righe_nominativo):
            if existing_row.id not in kept_row_ids:
                db.delete(existing_row)

        _recalculate_voce_fondimpresa_totale(voce)

    for existing in list(piano.voci):
        if existing.id not in kept_ids:
            db.delete(existing)

    db.commit()
    return get_piano_fondimpresa(db, piano_id)


def bulk_upsert_documenti_fondimpresa(db: Session, piano_id: int, payload: schemas.PianoFondimpresaDocumentiBulkUpdate):
    piano = get_piano_fondimpresa(db, piano_id)
    if not piano:
        return None

    voci_by_codice = {voce.voce_codice: voce for voce in piano.voci}
    for item in payload.voci:
        voce = None
        if item.id:
            voce = next((entry for entry in piano.voci if entry.id == item.id), None)
        if voce is None:
            voce = voci_by_codice.get(item.voce_codice)
        if voce is None:
            raise ValueError(f"Voce Fondimpresa non trovata: {item.voce_codice}")

        existing_doc_by_id = {doc.id: doc for doc in voce.documenti}
        kept_doc_ids = set()
        for document_data in item.documenti:
            payload_doc = document_data.model_dump()
            doc_id = payload_doc.pop("id", None)
            if payload_doc["importo_imputato"] > payload_doc["importo_totale"]:
                raise ValueError(f"Il documento {payload_doc.get('numero_documento') or 'senza numero'} supera l'importo totale disponibile")
            if doc_id and doc_id in existing_doc_by_id:
                document = existing_doc_by_id[doc_id]
                for key, value in payload_doc.items():
                    setattr(document, key, value)
            else:
                document = models.DocumentoFondimpresa(voce_id=voce.id, **payload_doc)
                db.add(document)
                db.flush()
            kept_doc_ids.add(document.id)

        for existing_doc in list(voce.documenti):
            if existing_doc.id not in kept_doc_ids:
                db.delete(existing_doc)

        _recalculate_voce_fondimpresa_totale(voce)

    db.commit()
    return get_piano_fondimpresa(db, piano_id)


def update_dettaglio_budget_fondimpresa(db: Session, piano_id: int, payload: schemas.DettaglioBudgetFondimpresaUpdate):
    piano = get_piano_fondimpresa(db, piano_id)
    if not piano:
        return None

    if not piano.dettaglio_budget:
        piano.dettaglio_budget = models.DettaglioBudgetFondimpresa(piano_id=piano_id)
        db.add(piano.dettaglio_budget)
        db.flush()

    budget = piano.dettaglio_budget

    existing_consulenti = {row.id: row for row in budget.consulenti}
    kept_consulenti = set()
    for item in payload.consulenti:
        row = item.model_dump()
        row_id = row.pop("id", None)
        row["totale"] = round((float(row.get("ore") or 0.0) * float(row.get("costo_orario") or 0.0)), 2)
        if row_id and row_id in existing_consulenti:
            db_row = existing_consulenti[row_id]
            for key, value in row.items():
                setattr(db_row, key, value)
        else:
            db_row = models.BudgetConsulenteFondimpresa(budget_id=budget.id, **row)
            db.add(db_row)
            db.flush()
        kept_consulenti.add(db_row.id)
    for existing in list(budget.consulenti):
        if existing.id not in kept_consulenti:
            db.delete(existing)

    existing_costi = {row.id: row for row in budget.costi_fissi}
    kept_costi = set()
    for item in payload.costi_fissi:
        row = item.model_dump()
        row_id = row.pop("id", None)
        if row_id and row_id in existing_costi:
            db_row = existing_costi[row_id]
            for key, value in row.items():
                setattr(db_row, key, value)
        else:
            db_row = models.BudgetCostoFissoFondimpresa(budget_id=budget.id, **row)
            db.add(db_row)
            db.flush()
        kept_costi.add(db_row.id)
    for existing in list(budget.costi_fissi):
        if existing.id not in kept_costi:
            db.delete(existing)

    totale_piano = build_piano_fondimpresa_riepilogo(piano)["totale_escluso_cofinanziamento"]
    existing_margini = {row.id: row for row in budget.margini}
    kept_margini = set()
    for item in payload.margini:
        row = item.model_dump()
        row_id = row.pop("id", None)
        row["totale"] = round((totale_piano * float(row.get("percentuale") or 0.0)) / 100, 2)
        if row_id and row_id in existing_margini:
            db_row = existing_margini[row_id]
            for key, value in row.items():
                setattr(db_row, key, value)
        else:
            db_row = models.BudgetMargineFondimpresa(budget_id=budget.id, **row)
            db.add(db_row)
            db.flush()
        kept_margini.add(db_row.id)
    for existing in list(budget.margini):
        if existing.id not in kept_margini:
            db.delete(existing)

    db.commit()
    return get_piano_fondimpresa(db, piano_id)


def build_piano_fondimpresa_riepilogo(piano: models.PianoFinanziarioFondimpresa) -> dict:
    totals = defaultdict(float)
    alerts = []

    for voce in piano.voci:
        totale_righe = sum((float(row.totale or 0.0) for row in voce.righe_nominativo))
        totale_documenti = sum((float(documento.importo_imputato or 0.0) for documento in voce.documenti))
        totale_voce = max(float(voce.totale_voce or 0.0), totale_righe, totale_documenti)
        totals[voce.sezione] += totale_voce

        for documento in voce.documenti:
            if float(documento.importo_imputato or 0.0) > float(documento.importo_totale or 0.0):
                alerts.append({
                    "level": "danger",
                    "code": f"documento_overrun_{documento.id}",
                    "message": f"Il documento {documento.numero_documento or documento.id} supera l'importo totale disponibile.",
                })

    totale_escluso_cofinanziamento = round(totals["A"] + totals["C"] + totals["D"], 2)
    totale_preventivo = float(piano.totale_preventivo or 0.0)
    differenza = round(totale_preventivo - totale_escluso_cofinanziamento, 2)

    sezioni = []
    for sezione in ["A", "B", "C", "D"]:
        totale = round(totals[sezione], 2)
        percentuale = round((totale / totale_escluso_cofinanziamento) * 100, 2) if sezione != "B" and totale_escluso_cofinanziamento else 0.0
        limits = FONDIMPRESA_LIMITS.get(sezione, {})
        min_limit = limits.get("min")
        max_limit = limits.get("max")
        alert_level = "ok"

        if sezione == "A" and min_limit is not None and percentuale < min_limit:
            alert_level = "danger"
            alerts.append({
                "level": "danger",
                "code": "fondimpresa_a_under_min",
                "message": f"La Sezione A è sotto la soglia minima del {min_limit:.0f}%.",
            })
        if sezione in {"C", "D"} and max_limit is not None and percentuale > max_limit:
            alert_level = "danger"
            alerts.append({
                "level": "danger",
                "code": f"fondimpresa_{sezione.lower()}_over_max",
                "message": f"La Sezione {sezione} supera la soglia massima del {max_limit:.0f}%.",
            })

        sezioni.append({
            "sezione": sezione,
            "titolo": FONDIMPRESA_TITLES[sezione],
            "totale": totale,
            "percentuale": percentuale,
            "min_percentuale": min_limit,
            "max_percentuale": max_limit,
            "alert_level": alert_level,
        })

    if totale_escluso_cofinanziamento:
        perc_sum = round(sum(item["percentuale"] for item in sezioni if item["sezione"] != "B"), 2)
        if abs(perc_sum - 100.0) > 0.1:
            alerts.append({
                "level": "warning",
                "code": "fondimpresa_percentage_incoherent",
                "message": "La somma percentuale di A, C e D non restituisce 100%.",
            })

    if differenza < 0:
        alerts.append({
            "level": "warning",
            "code": "fondimpresa_budget_overrun",
            "message": "Il consuntivo supera il totale preventivo approvato.",
        })

    return {
        "piano_id": piano.id,
        "totale_a": round(totals["A"], 2),
        "totale_b": round(totals["B"], 2),
        "totale_c": round(totals["C"], 2),
        "totale_d": round(totals["D"], 2),
        "totale_escluso_cofinanziamento": totale_escluso_cofinanziamento,
        "totale_preventivo": totale_preventivo,
        "differenza_preventivo_consuntivo": differenza,
        "sezioni": sezioni,
        "alerts": alerts,
    }


# ── Listini ──────────────────────────────────

def get_listini(db: Session, search: str = None, tipo_cliente: str = None, attivo: bool = None,
                skip: int = 0, limit: int = 50):
    q = db.query(models.Listino)
    if attivo is not None:
        q = q.filter(models.Listino.attivo == attivo)
    if tipo_cliente:
        q = q.filter(models.Listino.tipo_cliente == tipo_cliente)
    if search:
        q = q.filter(models.Listino.nome.ilike(f"%{search}%"))
    total = q.count()
    items = q.order_by(models.Listino.nome).offset(skip).limit(limit).all()
    return items, total


def get_listino(db: Session, listino_id: int):
    return (db.query(models.Listino)
              .options(selectinload(models.Listino.voci).selectinload(models.ListinoVoce.prodotto))
              .filter(models.Listino.id == listino_id).first())


def create_listino(db: Session, listino: schemas.ListinoCreate):
    db_obj = models.Listino(**listino.model_dump())
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def update_listino(db: Session, listino_id: int, listino: schemas.ListinoUpdate):
    db_obj = db.query(models.Listino).filter(models.Listino.id == listino_id).first()
    if not db_obj:
        return None
    for k, v in listino.model_dump(exclude_unset=True).items():
        setattr(db_obj, k, v)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def delete_listino(db: Session, listino_id: int):
    db_obj = db.query(models.Listino).filter(models.Listino.id == listino_id).first()
    if db_obj:
        db_obj.attivo = False
        db.commit()
    return db_obj


# ── Listino Voci ─────────────────────────────

def get_voci_listino(db: Session, listino_id: int):
    return (db.query(models.ListinoVoce)
              .options(selectinload(models.ListinoVoce.prodotto))
              .filter(models.ListinoVoce.listino_id == listino_id)
              .order_by(models.ListinoVoce.id).all())


def get_voce(db: Session, voce_id: int):
    return (db.query(models.ListinoVoce)
              .options(selectinload(models.ListinoVoce.prodotto))
              .filter(models.ListinoVoce.id == voce_id).first())


def create_voce(db: Session, voce: schemas.ListinoVoceCreate):
    db_obj = models.ListinoVoce(**voce.model_dump())
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    # Reload with prodotto
    return get_voce(db, db_obj.id)


def update_voce(db: Session, voce_id: int, voce: schemas.ListinoVoceUpdate):
    db_obj = db.query(models.ListinoVoce).filter(models.ListinoVoce.id == voce_id).first()
    if not db_obj:
        return None
    for k, v in voce.model_dump(exclude_unset=True).items():
        setattr(db_obj, k, v)
    db.commit()
    return get_voce(db, voce_id)


def delete_voce(db: Session, voce_id: int):
    db_obj = db.query(models.ListinoVoce).filter(models.ListinoVoce.id == voce_id).first()
    if db_obj:
        db.delete(db_obj)
        db.commit()
    return db_obj


def get_prezzo_prodotto_in_listino(db: Session, prodotto_id: int, listino_id: int):
    """Recupera il prezzo finale di un prodotto in un listino specifico."""
    voce = (db.query(models.ListinoVoce)
              .options(selectinload(models.ListinoVoce.prodotto))
              .filter(
                  models.ListinoVoce.listino_id == listino_id,
                  models.ListinoVoce.prodotto_id == prodotto_id
              ).first())
    if not voce or not voce.prodotto:
        return None
    return {
        "prodotto_id": prodotto_id,
        "listino_id": listino_id,
        "prezzo_base": voce.prodotto.prezzo_base,
        "prezzo_override": voce.prezzo_override,
        "sconto_percentuale": voce.sconto_percentuale or 0.0,
        "prezzo_finale": calcola_prezzo_finale(voce.prodotto.prezzo_base, voce.prezzo_override, voce.sconto_percentuale),
        "unita_misura": voce.prodotto.unita_misura or 'ora',
    }


# ═══════════════════════════════════════════════
# BLOCCO 4 — Preventivi + Ordini
# ═══════════════════════════════════════════════

def _next_preventivo_number(db: Session, anno: int):
    """Calcola il prossimo numero progressivo per un preventivo nell'anno dato."""
    result = db.query(func.max(models.Preventivo.numero_progressivo)).filter(
        models.Preventivo.anno == anno
    ).scalar()
    prog = (result or 0) + 1
    numero = f"PRV-{anno}-{prog:03d}"
    return anno, prog, numero


def _next_ordine_number(db: Session, anno: int):
    """Calcola il prossimo numero progressivo per un ordine nell'anno dato."""
    result = db.query(func.max(models.Ordine.numero_progressivo)).filter(
        models.Ordine.anno == anno
    ).scalar()
    prog = (result or 0) + 1
    numero = f"ORD-{anno}-{prog:03d}"
    return anno, prog, numero


def _calcola_importo_riga(quantita: float, prezzo_unitario: float, sconto: float) -> float:
    return round(quantita * prezzo_unitario * (1 - (sconto or 0) / 100), 4)


# ── Preventivo CRUD ───────────────────────────

def get_preventivo(db: Session, preventivo_id: int):
    return (db.query(models.Preventivo)
              .options(
                  selectinload(models.Preventivo.righe).selectinload(models.PreventivoRiga.prodotto),
                  selectinload(models.Preventivo.azienda_cliente),
                  selectinload(models.Preventivo.consulente),
                  selectinload(models.Preventivo.ordine),
              )
              .filter(models.Preventivo.id == preventivo_id)
              .first())


def get_preventivi(db: Session, skip: int = 0, limit: int = 100,
                   stato: Optional[str] = None, azienda_id: Optional[int] = None,
                   search: Optional[str] = None, attivo: Optional[bool] = None):
    q = db.query(models.Preventivo).options(
        selectinload(models.Preventivo.azienda_cliente),
        selectinload(models.Preventivo.consulente),
    )
    if stato:
        q = q.filter(models.Preventivo.stato == stato)
    if azienda_id:
        q = q.filter(models.Preventivo.azienda_cliente_id == azienda_id)
    if attivo is not None:
        q = q.filter(models.Preventivo.attivo == attivo)
    if search:
        term = f"%{search.lower()}%"
        q = q.filter(
            or_(
                func.lower(models.Preventivo.numero).like(term),
                func.lower(models.Preventivo.oggetto).like(term),
            )
        )
    total = q.count()
    items = q.order_by(desc(models.Preventivo.created_at)).offset(skip).limit(limit).all()
    return items, total


def create_preventivo(db: Session, data: schemas.PreventivoCreate):
    anno = datetime.now().year
    anno_val, prog, numero = _next_preventivo_number(db, anno)
    db_prev = models.Preventivo(
        numero=numero,
        anno=anno_val,
        numero_progressivo=prog,
        azienda_cliente_id=data.azienda_cliente_id,
        listino_id=data.listino_id,
        consulente_id=data.consulente_id,
        oggetto=data.oggetto,
        data_scadenza=data.data_scadenza,
        note=data.note,
        stato='bozza',
    )
    db.add(db_prev)
    db.flush()  # get id without commit

    for i, riga_data in enumerate(data.righe or []):
        importo = _calcola_importo_riga(riga_data.quantita, riga_data.prezzo_unitario, riga_data.sconto_percentuale)
        riga = models.PreventivoRiga(
            preventivo_id=db_prev.id,
            prodotto_id=riga_data.prodotto_id,
            descrizione_custom=riga_data.descrizione_custom,
            quantita=riga_data.quantita,
            prezzo_unitario=riga_data.prezzo_unitario,
            sconto_percentuale=riga_data.sconto_percentuale,
            importo=importo,
            ordine=riga_data.ordine if riga_data.ordine else i,
        )
        db.add(riga)

    db.commit()
    db.refresh(db_prev)
    return get_preventivo(db, db_prev.id)


def update_preventivo(db: Session, preventivo_id: int, data: schemas.PreventivoUpdate):
    db_obj = db.query(models.Preventivo).filter(models.Preventivo.id == preventivo_id).first()
    if not db_obj:
        return None
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(db_obj, field, val)
    db.commit()
    return get_preventivo(db, preventivo_id)


def delete_preventivo(db: Session, preventivo_id: int):
    db_obj = db.query(models.Preventivo).filter(models.Preventivo.id == preventivo_id).first()
    if db_obj:
        db.delete(db_obj)
        db.commit()
    return db_obj


# ── Stato machine transitions ─────────────────

TRANSIZIONI_VALIDE = {
    'bozza': ['inviato'],
    'inviato': ['accettato', 'rifiutato'],
    'accettato': [],
    'rifiutato': [],
}


def transizione_stato(db: Session, preventivo_id: int, nuovo_stato: str):
    """Applica una transizione di stato al preventivo. Restituisce (obj, error_msg)."""
    db_obj = db.query(models.Preventivo).filter(models.Preventivo.id == preventivo_id).first()
    if not db_obj:
        return None, "Preventivo non trovato"
    stati_consentiti = TRANSIZIONI_VALIDE.get(db_obj.stato, [])
    if nuovo_stato not in stati_consentiti:
        return None, f"Transizione {db_obj.stato}→{nuovo_stato} non consentita"
    db_obj.stato = nuovo_stato
    db.commit()
    return get_preventivo(db, preventivo_id), None


def converti_in_ordine(db: Session, preventivo_id: int):
    """Converte un preventivo accettato in ordine. Restituisce (ordine, error_msg)."""
    prev = get_preventivo(db, preventivo_id)
    if not prev:
        return None, "Preventivo non trovato"
    if prev.stato != 'accettato':
        return None, f"Solo i preventivi 'accettato' possono essere convertiti (stato attuale: {prev.stato})"
    if prev.ordine:
        return None, "Esiste già un ordine per questo preventivo"

    anno = datetime.now().year
    anno_val, prog, numero = _next_ordine_number(db, anno)
    ordine = models.Ordine(
        numero=numero,
        anno=anno_val,
        numero_progressivo=prog,
        preventivo_id=preventivo_id,
        azienda_cliente_id=prev.azienda_cliente_id,
        stato='in_lavorazione',
    )
    db.add(ordine)
    db.commit()
    db.refresh(ordine)
    return get_ordine(db, ordine.id), None


# ── PreventivoRiga CRUD ───────────────────────

def get_riga(db: Session, riga_id: int):
    return (db.query(models.PreventivoRiga)
              .options(selectinload(models.PreventivoRiga.prodotto))
              .filter(models.PreventivoRiga.id == riga_id)
              .first())


def create_riga(db: Session, preventivo_id: int, data: schemas.PreventivoRigaCreate):
    importo = _calcola_importo_riga(data.quantita, data.prezzo_unitario, data.sconto_percentuale)
    riga = models.PreventivoRiga(
        preventivo_id=preventivo_id,
        prodotto_id=data.prodotto_id,
        descrizione_custom=data.descrizione_custom,
        quantita=data.quantita,
        prezzo_unitario=data.prezzo_unitario,
        sconto_percentuale=data.sconto_percentuale,
        importo=importo,
        ordine=data.ordine,
    )
    db.add(riga)
    db.commit()
    db.refresh(riga)
    return get_riga(db, riga.id)


def update_riga(db: Session, riga_id: int, data: schemas.PreventivoRigaUpdate):
    riga = db.query(models.PreventivoRiga).filter(models.PreventivoRiga.id == riga_id).first()
    if not riga:
        return None
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(riga, field, val)
    # ricalcola importo
    riga.importo = _calcola_importo_riga(riga.quantita, riga.prezzo_unitario, riga.sconto_percentuale)
    db.commit()
    return get_riga(db, riga_id)


def delete_riga(db: Session, riga_id: int):
    riga = db.query(models.PreventivoRiga).filter(models.PreventivoRiga.id == riga_id).first()
    if riga:
        db.delete(riga)
        db.commit()
    return riga


# ── Ordini CRUD ───────────────────────────────

def get_ordine(db: Session, ordine_id: int):
    return (db.query(models.Ordine)
              .options(
                  selectinload(models.Ordine.azienda_cliente),
                  selectinload(models.Ordine.preventivo),
              )
              .filter(models.Ordine.id == ordine_id)
              .first())


def get_ordini(db: Session, skip: int = 0, limit: int = 100,
               stato: Optional[str] = None, azienda_id: Optional[int] = None,
               search: Optional[str] = None):
    q = db.query(models.Ordine).options(
        selectinload(models.Ordine.azienda_cliente),
        selectinload(models.Ordine.preventivo),
    )
    if stato:
        q = q.filter(models.Ordine.stato == stato)
    if azienda_id:
        q = q.filter(models.Ordine.azienda_cliente_id == azienda_id)
    if search:
        term = f"%{search.lower()}%"
        q = q.filter(func.lower(models.Ordine.numero).like(term))
    total = q.count()
    items = q.order_by(desc(models.Ordine.created_at)).offset(skip).limit(limit).all()
    return items, total


def update_ordine(db: Session, ordine_id: int, data: schemas.OrdineUpdate):
    db_obj = db.query(models.Ordine).filter(models.Ordine.id == ordine_id).first()
    if not db_obj:
        return None
    for field, val in data.model_dump(exclude_unset=True).items():
        setattr(db_obj, field, val)
    db.commit()
    return get_ordine(db, ordine_id)


# ── Sistema Agenti CRUD ──────────────────────

def create_agent_run(
    db: Session,
    agent_type: str,
    triggered_by: str,
    trigger_details: Optional[str] = None,
):
    db_obj = models.AgentRun(
        agent_type=agent_type,
        triggered_by=triggered_by,
        trigger_details=trigger_details,
        status="running",
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def get_agent_run(db: Session, run_id: int):
    return (
        db.query(models.AgentRun)
        .options(selectinload(models.AgentRun.suggestions))
        .filter(models.AgentRun.id == run_id)
        .first()
    )


def get_agent_runs(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    agent_type: Optional[str] = None,
    status: Optional[str] = None,
):
    query = db.query(models.AgentRun)
    if agent_type:
        query = query.filter(models.AgentRun.agent_type == agent_type)
    if status:
        query = query.filter(models.AgentRun.status == status)
    return (
        query.order_by(desc(models.AgentRun.started_at), desc(models.AgentRun.id))
        .offset(skip)
        .limit(limit)
        .all()
    )


def complete_agent_run(
    db: Session,
    run_id: int,
    status: str,
    items_processed: int,
    items_with_issues: int,
    suggestions_created: int,
    error_message: Optional[str] = None,
):
    db_obj = db.query(models.AgentRun).filter(models.AgentRun.id == run_id).first()
    if not db_obj:
        return None

    completed_at = datetime.now()
    execution_time_ms = None
    if db_obj.started_at:
        execution_time_ms = int((completed_at - db_obj.started_at).total_seconds() * 1000)

    db_obj.status = status
    db_obj.completed_at = completed_at
    db_obj.items_processed = items_processed
    db_obj.items_with_issues = items_with_issues
    db_obj.suggestions_created = suggestions_created
    db_obj.error_message = error_message
    db_obj.execution_time_ms = execution_time_ms
    db.commit()
    db.refresh(db_obj)
    return db_obj


def get_latest_run_by_type(db: Session, agent_type: str):
    return (
        db.query(models.AgentRun)
        .filter(models.AgentRun.agent_type == agent_type)
        .order_by(desc(models.AgentRun.started_at), desc(models.AgentRun.id))
        .first()
    )


def create_suggestion(
    db: Session,
    run_id: int,
    suggestion_type: str,
    priority: str,
    entity_type: str,
    entity_id: Optional[int],
    title: str,
    description: Optional[str],
    suggested_action: Optional[str],
    confidence_score: Optional[float] = None,
    auto_fix_available: bool = False,
    auto_fix_payload: Optional[str] = None,
):
    db_obj = models.AgentSuggestion(
        run_id=run_id,
        suggestion_type=suggestion_type,
        priority=priority,
        entity_type=entity_type,
        entity_id=entity_id,
        title=title,
        description=description,
        suggested_action=suggested_action,
        confidence_score=confidence_score,
        auto_fix_available=auto_fix_available,
        auto_fix_payload=auto_fix_payload,
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def get_suggestion(db: Session, suggestion_id: int):
    return (
        db.query(models.AgentSuggestion)
        .options(
            joinedload(models.AgentSuggestion.run),
            selectinload(models.AgentSuggestion.review_actions),
        )
        .filter(models.AgentSuggestion.id == suggestion_id)
        .first()
    )


def get_suggestions(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    entity_type: Optional[str] = None,
):
    query = db.query(models.AgentSuggestion)
    if status:
        query = query.filter(models.AgentSuggestion.status == status)
    if priority:
        query = query.filter(models.AgentSuggestion.priority == priority)
    if entity_type:
        query = query.filter(models.AgentSuggestion.entity_type == entity_type)
    return (
        query.order_by(desc(models.AgentSuggestion.created_at), desc(models.AgentSuggestion.id))
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_pending_suggestions(db: Session):
    priority_order = text(
        "CASE "
        "WHEN priority = 'critical' THEN 1 "
        "WHEN priority = 'high' THEN 2 "
        "WHEN priority = 'medium' THEN 3 "
        "WHEN priority = 'low' THEN 4 "
        "ELSE 5 END"
    )
    return (
        db.query(models.AgentSuggestion)
        .filter(models.AgentSuggestion.status == "pending")
        .order_by(priority_order, desc(models.AgentSuggestion.created_at), desc(models.AgentSuggestion.id))
        .all()
    )


def update_suggestion_status(db: Session, suggestion_id: int, status: str):
    db_obj = db.query(models.AgentSuggestion).filter(models.AgentSuggestion.id == suggestion_id).first()
    if not db_obj:
        return None
    db_obj.status = status
    db.commit()
    db.refresh(db_obj)
    return db_obj


def bulk_update_suggestions_status(db: Session, suggestion_ids: List[int], status: str):
    if not suggestion_ids:
        return []
    (
        db.query(models.AgentSuggestion)
        .filter(models.AgentSuggestion.id.in_(suggestion_ids))
        .update({models.AgentSuggestion.status: status}, synchronize_session=False)
    )
    db.commit()
    return (
        db.query(models.AgentSuggestion)
        .filter(models.AgentSuggestion.id.in_(suggestion_ids))
        .order_by(desc(models.AgentSuggestion.created_at), desc(models.AgentSuggestion.id))
        .all()
    )


def create_review_action(
    db: Session,
    suggestion_id: int,
    action: str,
    reviewed_by,
    notes: Optional[str] = None,
    auto_fix_applied: bool = False,
    result_success: Optional[bool] = None,
    result_message: Optional[str] = None,
):
    db_obj = models.AgentReviewAction(
        suggestion_id=suggestion_id,
        action=action,
        reviewed_by=str(reviewed_by),
        notes=notes,
        auto_fix_applied=auto_fix_applied,
        result_success=result_success,
        result_message=result_message,
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def get_review_actions_for_suggestion(db: Session, suggestion_id: int):
    return (
        db.query(models.AgentReviewAction)
        .filter(models.AgentReviewAction.suggestion_id == suggestion_id)
        .order_by(desc(models.AgentReviewAction.reviewed_at), desc(models.AgentReviewAction.id))
        .all()
    )
