from sqlalchemy.orm import Session, joinedload, selectinload, contains_eager
from sqlalchemy import and_, or_, desc, asc, func, text, select
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timedelta
from functools import lru_cache
import models
import schemas
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor

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
            db_collaborator.updated_at = func.now()
            db.commit()
            db.refresh(db_collaborator)
            logger.info(f"Soft deleted collaborator: {collaborator_id}")
        return db_collaborator
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting collaborator {collaborator_id}: {e}")
        raise

def get_project(db: Session, project_id: int):
    return db.query(models.Project).filter(models.Project.id == project_id).first()

def get_projects(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Project).offset(skip).limit(limit).all()

def create_project(db: Session, project: schemas.ProjectCreate):
    # Versione MINIMALISTA - solo add
    db_project = models.Project(**project.dict())
    db.add(db_project)
    return db_project

def update_project(db: Session, project_id: int, project: schemas.ProjectUpdate):
    db_project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if db_project:
        update_data = project.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_project, key, value)
        db.commit()
        db.refresh(db_project)
    return db_project

def delete_project(db: Session, project_id: int):
    db_project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if db_project:
        db.delete(db_project)
        db.commit()
    return db_project

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

def check_attendance_overlap(
    db: Session,
    collaborator_id: int,
    start_time: datetime,
    end_time: datetime,
    exclude_attendance_id: Optional[int] = None
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
    # Costruisci query per trovare sovrapposizioni
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

    if overlapping:
        logger.warning(
            f"Sovrapposizione oraria rilevata per collaboratore {collaborator_id}: "
            f"Nuova presenza [{start_time} - {end_time}] sovrapposta con "
            f"presenza esistente ID {overlapping.id} [{overlapping.start_time} - {overlapping.end_time}]"
        )

    return overlapping

def create_attendance(db: Session, attendance: schemas.AttendanceCreate):
    try:
        # VALIDAZIONE SOVRAPPOSIZIONI ORARIE
        # Verifica che il collaboratore non sia già presente nello stesso orario
        overlapping = check_attendance_overlap(
            db,
            attendance.collaborator_id,
            attendance.start_time,
            attendance.end_time
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

        # Calcolo automatico delle ore se non fornito
        attendance_data = attendance.dict()
        if not attendance_data.get('hours'):
            start = attendance_data['start_time']
            end = attendance_data['end_time']
            attendance_data['hours'] = (end - start).total_seconds() / 3600

        # Validazione ore rimanenti dell'assegnazione
        if attendance_data.get('assignment_id'):
            assignment = db.query(models.Assignment).filter(
                models.Assignment.id == attendance_data['assignment_id']
            ).first()

            if assignment:
                ore_completate = assignment.completed_hours or 0
                ore_assegnate = assignment.assigned_hours
                ore_rimanenti = ore_assegnate - ore_completate

                if attendance_data['hours'] > ore_rimanenti:
                    raise ValueError(
                        f"Le ore inserite ({attendance_data['hours']}h) superano le ore rimanenti "
                        f"({ore_rimanenti}h) per questa mansione"
                    )

        db_attendance = models.Attendance(**attendance_data)
        db.add(db_attendance)
        db.commit()
        db.refresh(db_attendance)

        # Aggiorna statistiche dell'assegnazione se presente
        if db_attendance.assignment_id:
            update_assignment_progress(db, db_attendance.assignment_id)

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
                exclude_attendance_id=attendance_id  # Escludi la presenza stessa
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

        # Validazione ore rimanenti se cambiano le ore o l'assegnazione
        new_assignment_id = update_data.get('assignment_id', db_attendance.assignment_id)
        new_hours = update_data.get('hours', db_attendance.hours)

        if new_assignment_id:
            assignment = db.query(models.Assignment).filter(
                models.Assignment.id == new_assignment_id
            ).first()

            if assignment:
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

        for key, value in update_data.items():
            setattr(db_attendance, key, value)
        db.commit()
        db.refresh(db_attendance)

        # Aggiorna statistiche della vecchia assegnazione se è cambiata
        if old_assignment_id and old_assignment_id != db_attendance.assignment_id:
            update_assignment_progress(db, old_assignment_id)

        # Aggiorna statistiche della nuova assegnazione
        if db_attendance.assignment_id:
            update_assignment_progress(db, db_attendance.assignment_id)

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

def get_assignments(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Assignment).offset(skip).limit(limit).all()

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
        # Crea oggetto con i campi iniziali impostati esplicitamente
        assignment_data = assignment.dict()
        assignment_data['completed_hours'] = 0.0
        assignment_data['progress_percentage'] = 0.0
        assignment_data['is_active'] = True

        db_assignment = models.Assignment(**assignment_data)
        db.add(db_assignment)
        db.flush()  # Ottieni l'ID senza commit

        # Crea relazione many-to-many se non esiste
        collaborator = get_collaborator(db, assignment.collaborator_id)
        project = get_project(db, assignment.project_id)
        if collaborator and project and project not in collaborator.projects:
            collaborator.projects.append(project)
            db.commit()

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
        for key, value in update_data.items():
            setattr(db_assignment, key, value)
        db.commit()
        db.refresh(db_assignment)
    return db_assignment

def delete_assignment(db: Session, assignment_id: int):
    db_assignment = db.query(models.Assignment).filter(models.Assignment.id == assignment_id).first()
    if db_assignment:
        db.delete(db_assignment)
        db.commit()
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


def get_contract_templates(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    tipo_contratto: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None
):
    """
    Recupera lista template contratti con filtri opzionali

    Args:
        skip: Record da saltare (paginazione)
        limit: Numero massimo di record
        tipo_contratto: Filtra per tipo contratto specifico
        is_active: Filtra per stato attivo
        search: Cerca nel nome template o descrizione
    """
    query = db.query(models.ContractTemplate)

    # Filtri
    if tipo_contratto:
        query = query.filter(models.ContractTemplate.tipo_contratto == tipo_contratto)

    if is_active is not None:
        query = query.filter(models.ContractTemplate.is_active == is_active)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (models.ContractTemplate.nome_template.ilike(search_term)) |
            (models.ContractTemplate.descrizione.ilike(search_term))
        )

    # Ordinamento: template di default per primi, poi per data creazione
    return query.order_by(
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
        models.ContractTemplate.tipo_contratto == tipo_contratto,
        models.ContractTemplate.is_active == True
    )

    if use_default:
        query = query.filter(models.ContractTemplate.is_default == True)

    return query.first()


def get_contract_templates_count(
    db: Session,
    tipo_contratto: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None
):
    """Conta i template con gli stessi filtri della lista"""
    query = db.query(models.ContractTemplate)

    if tipo_contratto:
        query = query.filter(models.ContractTemplate.tipo_contratto == tipo_contratto)

    if is_active is not None:
        query = query.filter(models.ContractTemplate.is_active == is_active)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (models.ContractTemplate.nome_template.ilike(search_term)) |
            (models.ContractTemplate.descrizione.ilike(search_term))
        )

    return query.count()


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
    template_data = template.dict()

    # Se questo è il template di default, rimuovi il flag dagli altri
    if template_data.get('is_default', False):
        db.query(models.ContractTemplate).filter(
            models.ContractTemplate.tipo_contratto == template_data['tipo_contratto'],
            models.ContractTemplate.is_default == True
        ).update({'is_default': False})

    db_template = models.ContractTemplate(**template_data)
    db.add(db_template)
    db.commit()
    db.refresh(db_template)

    logger.info(f"Created contract template: {db_template.nome_template} (ID: {db_template.id})")
    return db_template


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

    update_data = template.dict(exclude_unset=True)

    # Se cambia il flag default
    if update_data.get('is_default', False) and not db_template.is_default:
        # Rimuovi default dagli altri template dello stesso tipo
        tipo_contratto = update_data.get('tipo_contratto', db_template.tipo_contratto)
        db.query(models.ContractTemplate).filter(
            models.ContractTemplate.tipo_contratto == tipo_contratto,
            models.ContractTemplate.is_default == True,
            models.ContractTemplate.id != template_id
        ).update({'is_default': False})

    # Applica aggiornamenti
    for key, value in update_data.items():
        setattr(db_template, key, value)

    db.commit()
    db.refresh(db_template)

    logger.info(f"Updated contract template: {db_template.nome_template} (ID: {template_id})")
    return db_template


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

    if soft_delete:
        db_template.is_active = False
        db.commit()
        db.refresh(db_template)
        logger.info(f"Soft-deleted contract template ID {template_id}")
    else:
        db.delete(db_template)
        db.commit()
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