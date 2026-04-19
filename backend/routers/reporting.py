"""
Router per generazione report e statistiche
Gestisce timesheet, KPI e report aggregati
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, date
from pydantic import BaseModel
import logging
import csv
import os
import uuid

import crud
import schemas
from database import SessionLocal, get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/reporting", tags=["Reporting"])
EXPORTS_DIR = "/tmp/exports"


class TimesheetExportFilters(BaseModel):
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    collaborator_id: Optional[int] = None
    project_id: Optional[int] = None


def _build_timesheet_range(from_date: Optional[date], to_date: Optional[date]):
    start_dt = datetime.combine(from_date, datetime.min.time()) if from_date else None
    end_dt = datetime.combine(to_date, datetime.max.time()) if to_date else None
    return start_dt, end_dt


def _generate_timesheet_export_file(filters: TimesheetExportFilters, export_id: str) -> str:
    os.makedirs(EXPORTS_DIR, exist_ok=True)
    file_path = os.path.join(EXPORTS_DIR, f"{export_id}.csv")
    start_dt, end_dt = _build_timesheet_range(filters.from_date, filters.to_date)

    db = SessionLocal()
    try:
        with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["attendance_id", "date", "collaborator", "project", "start_time", "end_time", "hours", "notes"])

            skip = 0
            page_size = 1000
            while True:
                attendances = crud.get_attendances(
                    db,
                    skip=skip,
                    limit=page_size,
                    collaborator_id=filters.collaborator_id,
                    project_id=filters.project_id,
                    start_date=start_dt,
                    end_date=end_dt,
                    include_details=True,
                )
                if not attendances:
                    break

                for attendance in attendances:
                    collaborator = attendance.collaborator
                    project = attendance.project
                    writer.writerow([
                        attendance.id,
                        attendance.date.isoformat() if attendance.date else "",
                        f"{collaborator.first_name} {collaborator.last_name}" if collaborator else "",
                        project.name if project else "",
                        attendance.start_time.isoformat() if attendance.start_time else "",
                        attendance.end_time.isoformat() if attendance.end_time else "",
                        float(attendance.hours or 0.0),
                        attendance.notes or "",
                    ])

                if len(attendances) < page_size:
                    break
                skip += page_size
    finally:
        db.close()

    return file_path


def _serialize_template_documento(template):
    if not template:
        return None
    return {
        "id": template.id,
        "nome_template": template.nome_template,
        "ambito_template": template.ambito_template,
        "chiave_documento": template.chiave_documento,
        "ente_erogatore": template.ente_erogatore,
        "avviso": template.avviso,
        "progetto_id": template.progetto_id,
        "ente_attuatore_id": template.ente_attuatore_id,
    }


@router.get("/timesheet")
def get_timesheet_report(
    from_date: Optional[date] = Query(None, alias="from", description="Data inizio periodo (YYYY-MM-DD)"),
    to_date: Optional[date] = Query(None, alias="to", description="Data fine periodo (YYYY-MM-DD)"),
    collaborator_id: Optional[int] = Query(None, description="ID collaboratore specifico"),
    project_id: Optional[int] = Query(None, description="ID progetto specifico"),
    chiave_documento: Optional[str] = Query(None, description="Chiave template timesheet da usare (es. timesheet_mensile)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """
    GENERA REPORT TIMESHEET PRESENZE

    Restituisce un report dettagliato delle presenze con totali ore lavorate.

    Parametri query:
    - from: Data inizio periodo (opzionale)
    - to: Data fine periodo (opzionale)
    - collaborator_id: Filtra per collaboratore specifico (opzionale)
    - project_id: Filtra per progetto specifico (opzionale)

    Il report include:
    - Dettaglio presenze per collaboratore e progetto
    - Totale ore per collaboratore
    - Totale ore per progetto
    - Totale generale
    """
    try:
        start_dt, end_dt = _build_timesheet_range(from_date, to_date)
        attendances = crud.get_attendances(
            db,
            skip=skip,
            limit=limit,
            collaborator_id=collaborator_id,
            project_id=project_id,
            start_date=start_dt,
            end_date=end_dt
        )
        total = crud.get_attendances_count(
            db,
            collaborator_id=collaborator_id,
            project_id=project_id,
            start_date=start_dt,
            end_date=end_dt,
        )
        total_hours = crud.get_attendances_total_hours(
            db,
            collaborator_id=collaborator_id,
            project_id=project_id,
            start_date=start_dt,
            end_date=end_dt,
        )

        progetto = crud.get_project(db, project_id) if project_id else None
        template_timesheet = crud.resolve_document_template(
            db,
            ambito_template="timesheet",
            chiave_documento=chiave_documento or "timesheet_standard",
            progetto_id=project_id,
            ente_attuatore_id=getattr(progetto, "ente_attuatore_id", None) if progetto else None,
            ente_erogatore=getattr(progetto, "ente_erogatore", None) if progetto else None,
            avviso=getattr(progetto, "avviso", None) if progetto else None,
        )

        # Prepara struttura dati per il report
        report_data = {
            "periodo": {
                "from": from_date.isoformat() if from_date else None,
                "to": to_date.isoformat() if to_date else None
            },
            "template_documento": _serialize_template_documento(template_timesheet),
            "items": [],
            "presenze": [],
            "total": total,
            "skip": skip,
            "limit": limit,
            "has_more": skip + limit < total,
            "totali": {
                "ore_totali": total_hours,
                "numero_presenze": total,
                "per_collaboratore": {},
                "per_progetto": {}
            }
        }
        report_data["period"] = report_data["periodo"]
        report_data["attendances"] = []
        report_data["total_hours"] = report_data["totali"]["ore_totali"]

        # Elabora presenze
        for attendance in attendances:
            collaboratore = crud.get_collaborator(db, attendance.collaborator_id)
            progetto = crud.get_project(db, attendance.project_id)

            presenza_data = {
                "id": attendance.id,
                "data": attendance.date.isoformat() if attendance.date else None,
                "ore_lavorate": float(attendance.hours) if attendance.hours else 0,
                "collaboratore": {
                    "id": collaboratore.id if collaboratore else None,
                    "nome_completo": f"{collaboratore.first_name} {collaboratore.last_name}" if collaboratore else "N/A"
                },
                "progetto": {
                    "id": progetto.id if progetto else None,
                    "nome": progetto.name if progetto else "N/A"
                },
                "note": attendance.notes
            }

            report_data["items"].append(presenza_data)
            report_data["presenze"].append(presenza_data)
            report_data["attendances"].append(presenza_data)

            # Aggiorna totali
            ore = float(attendance.hours) if attendance.hours else 0

            # Totali per collaboratore
            if collaboratore:
                collab_key = f"{collaboratore.id}_{collaboratore.first_name}_{collaboratore.last_name}"
                if collab_key not in report_data["totali"]["per_collaboratore"]:
                    report_data["totali"]["per_collaboratore"][collab_key] = {
                        "id": collaboratore.id,
                        "nome": f"{collaboratore.first_name} {collaboratore.last_name}",
                        "ore_totali": 0
                    }
                report_data["totali"]["per_collaboratore"][collab_key]["ore_totali"] += ore

            # Totali per progetto
            if progetto:
                prog_key = f"{progetto.id}_{progetto.name}"
                if prog_key not in report_data["totali"]["per_progetto"]:
                    report_data["totali"]["per_progetto"][prog_key] = {
                        "id": progetto.id,
                        "nome": progetto.name,
                        "ore_totali": 0
                    }
                report_data["totali"]["per_progetto"][prog_key]["ore_totali"] += ore

        # Converti dict in list per JSON response
        report_data["totali"]["per_collaboratore"] = list(report_data["totali"]["per_collaboratore"].values())
        report_data["totali"]["per_progetto"] = list(report_data["totali"]["per_progetto"].values())
        report_data["total_hours"] = report_data["totali"]["ore_totali"]

        logger.info(f"Generated timesheet report: {len(attendances)} attendances")
        return report_data

    except Exception as e:
        logger.error(f"Error generating timesheet report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore nella generazione del report: {str(e)}"
        )


@router.post("/timesheet/export")
def export_timesheet_async(
    filters: TimesheetExportFilters,
    background_tasks: BackgroundTasks,
):
    export_id = str(uuid.uuid4())
    background_tasks.add_task(_generate_timesheet_export_file, filters, export_id)
    return {"export_id": export_id, "status": "processing"}


@router.get("/timesheet/export/{export_id}")
def get_timesheet_export(export_id: str):
    file_path = os.path.join(EXPORTS_DIR, f"{export_id}.csv")
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="text/csv", filename=f"timesheet-{export_id}.csv")
    return {"export_id": export_id, "status": "processing"}


@router.get("/summary")
def get_summary_report(
    from_date: Optional[date] = Query(None, alias="from", description="Data inizio periodo (YYYY-MM-DD)"),
    to_date: Optional[date] = Query(None, alias="to", description="Data fine periodo (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """
    GENERA REPORT RIEPILOGATIVO KPI

    Restituisce un riepilogo con KPI principali del sistema.

    Parametri query:
    - from: Data inizio periodo (opzionale)
    - to: Data fine periodo (opzionale)

    Il report include:
    - Totale collaboratori attivi
    - Totale progetti attivi
    - Totale ore lavorate nel periodo
    - Media ore per collaboratore
    - Media ore per progetto
    - Progetti più attivi
    - Collaboratori più attivi
    - Distribuzione contratti per tipo
    """
    try:
        # KPI base - count queries, no bulk load
        total_collaborators = crud.get_collaborators_count(db)
        total_projects = crud.get_projects_count(db)
        total_entities = crud.get_implementing_entities_count(db)

        # Aggregate attendances in pages to avoid OOM
        start_dt = datetime.combine(from_date, datetime.min.time()) if from_date else None
        end_dt = datetime.combine(to_date, datetime.max.time()) if to_date else None

        total_hours = 0.0
        total_attendances_count = 0
        project_hours: dict = {}
        collaborator_hours: dict = {}
        _page_size = 1000
        _skip = 0
        while True:
            _page = crud.get_attendances(db, skip=_skip, limit=_page_size, start_date=start_dt, end_date=end_dt)
            if not _page:
                break
            for att in _page:
                ore = float(att.hours) if att.hours else 0
                total_hours += ore
                total_attendances_count += 1
                project_hours[att.project_id] = project_hours.get(att.project_id, 0) + ore
                collaborator_hours[att.collaborator_id] = collaborator_hours.get(att.collaborator_id, 0) + ore
            if len(_page) < _page_size:
                break
            _skip += _page_size

        # Calcola medie
        avg_hours_per_collaborator = total_hours / total_collaborators if total_collaborators > 0 else 0
        avg_hours_per_project = total_hours / total_projects if total_projects > 0 else 0

        # Analisi progetti più attivi
        top_projects_details = []
        for proj_id, hours in sorted(project_hours.items(), key=lambda x: x[1], reverse=True)[:5]:
            progetto = crud.get_project(db, proj_id)
            if progetto:
                top_projects_details.append({"id": progetto.id, "nome": progetto.name, "ore_totali": hours})

        # Analisi collaboratori più attivi
        top_collaborators_details = []
        for collab_id, hours in sorted(collaborator_hours.items(), key=lambda x: x[1], reverse=True)[:5]:
            collaboratore = crud.get_collaborator(db, collab_id)
            if collaboratore:
                top_collaborators_details.append({
                    "id": collaboratore.id,
                    "nome": f"{collaboratore.first_name} {collaboratore.last_name}",
                    "ore_totali": hours
                })

        # Distribuzione contratti per tipo - paginated
        contract_distribution: dict = {}
        _skip = 0
        while True:
            _page = crud.get_assignments(db, skip=_skip, limit=1000)
            if not _page:
                break
            for assignment in _page:
                contract_type = assignment.contract_type or "Non specificato"
                contract_distribution[contract_type] = contract_distribution.get(contract_type, 0) + 1
            if len(_page) < 1000:
                break
            _skip += 1000

        summary_data = {
            "periodo": {
                "from": from_date.isoformat() if from_date else None,
                "to": to_date.isoformat() if to_date else None
            },
            "kpi_generali": {
                "totale_collaboratori": total_collaborators,
                "totale_progetti": total_projects,
                "totale_enti_attuatori": total_entities,
                "totale_ore_lavorate": round(total_hours, 2),
                "totale_presenze": total_attendances_count,
                "media_ore_per_collaboratore": round(avg_hours_per_collaborator, 2),
                "media_ore_per_progetto": round(avg_hours_per_project, 2)
            },
            "top_5_progetti": top_projects_details,
            "top_5_collaboratori": top_collaborators_details,
            "distribuzione_contratti": [
                {"tipo": tipo, "numero": count}
                for tipo, count in contract_distribution.items()
            ]
        }

        logger.info("Generated summary report")
        return summary_data

    except Exception as e:
        logger.error(f"Error generating summary report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore nella generazione del riepilogo: {str(e)}"
        )


@router.get("/collaborator/{collaborator_id}/stats")
def get_collaborator_statistics(
    collaborator_id: int,
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    db: Session = Depends(get_db)
):
    """
    STATISTICHE DETTAGLIATE PER UN SINGOLO COLLABORATORE

    Restituisce statistiche complete per un collaboratore:
    - Totale ore lavorate
    - Progetti su cui ha lavorato
    - Distribuzione ore per progetto
    - Media ore giornaliere
    - Assegnazioni attive
    """
    try:
        collaboratore = crud.get_collaborator(db, collaborator_id)
        if not collaboratore:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Collaboratore non trovato"
            )

        # Recupera presenze - paginated to avoid OOM
        _start_dt = datetime.combine(from_date, datetime.min.time()) if from_date else None
        _end_dt = datetime.combine(to_date, datetime.max.time()) if to_date else None
        total_hours = 0.0
        total_attendances_count = 0
        project_hours: dict = {}
        giorni_set: set = set()
        _page_size = 1000
        _skip = 0
        while True:
            _page = crud.get_attendances(db, skip=_skip, limit=_page_size, collaborator_id=collaborator_id, start_date=_start_dt, end_date=_end_dt)
            if not _page:
                break
            for att in _page:
                ore = float(att.hours_worked) if att.hours_worked else 0
                total_hours += ore
                total_attendances_count += 1
                project_hours[att.project_id] = project_hours.get(att.project_id, 0) + ore
                if att.date:
                    giorni_set.add(att.date)
            if len(_page) < _page_size:
                break
            _skip += _page_size

        projects_details = []
        for proj_id, hours in project_hours.items():
            progetto = crud.get_project(db, proj_id)
            if progetto:
                projects_details.append({
                    "id": progetto.id,
                    "nome": progetto.name,
                    "ore_lavorate": hours
                })

        # Calcola media giornaliera
        num_giorni = len(giorni_set)
        media_ore_giornaliere = total_hours / num_giorni if num_giorni > 0 else 0

        # Assegnazioni attive
        assignments = crud.get_assignments_by_collaborator(db, collaborator_id)

        stats_data = {
            "collaboratore": {
                "id": collaboratore.id,
                "nome_completo": f"{collaboratore.first_name} {collaboratore.last_name}",
                "email": collaboratore.email
            },
            "periodo": {
                "from": from_date.isoformat() if from_date else None,
                "to": to_date.isoformat() if to_date else None
            },
            "statistiche": {
                "totale_ore_lavorate": round(total_hours, 2),
                "numero_presenze": total_attendances_count,
                "numero_progetti": len(project_hours),
                "numero_assegnazioni_attive": len(assignments),
                "media_ore_giornaliere": round(media_ore_giornaliere, 2)
            },
            "progetti": projects_details
        }

        return stats_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating collaborator statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore nella generazione delle statistiche: {str(e)}"
        )


@router.get("/project/{project_id}/stats")
def get_project_statistics(
    project_id: int,
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    db: Session = Depends(get_db)
):
    """
    STATISTICHE DETTAGLIATE PER UN SINGOLO PROGETTO

    Restituisce statistiche complete per un progetto:
    - Totale ore lavorate
    - Collaboratori che hanno lavorato
    - Distribuzione ore per collaboratore
    - Budget utilizzato vs previsto
    - Avanzamento progetto
    """
    try:
        progetto = crud.get_project(db, project_id)
        if not progetto:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Progetto non trovato"
            )

        # Recupera presenze - paginated to avoid OOM
        _start_dt = datetime.combine(from_date, datetime.min.time()) if from_date else None
        _end_dt = datetime.combine(to_date, datetime.max.time()) if to_date else None
        total_hours = 0.0
        total_attendances_count = 0
        collaborator_hours: dict = {}
        _page_size = 1000
        _skip = 0
        while True:
            _page = crud.get_attendances(db, skip=_skip, limit=_page_size, project_id=project_id, start_date=_start_dt, end_date=_end_dt)
            if not _page:
                break
            for att in _page:
                ore = float(att.hours_worked) if att.hours_worked else 0
                total_hours += ore
                total_attendances_count += 1
                collaborator_hours[att.collaborator_id] = collaborator_hours.get(att.collaborator_id, 0) + ore
            if len(_page) < _page_size:
                break
            _skip += _page_size

        collaborators_details = []
        for collab_id, hours in collaborator_hours.items():
            collaboratore = crud.get_collaborator(db, collab_id)
            if collaboratore:
                collaborators_details.append({
                    "id": collaboratore.id,
                    "nome": f"{collaboratore.first_name} {collaboratore.last_name}",
                    "ore_lavorate": hours
                })

        # Assegnazioni sul progetto
        assignments = crud.get_assignments_by_project(db, project_id)

        total_assigned_hours = sum(
            float(ass.assigned_hours) if ass.assigned_hours else 0
            for ass in assignments
        )

        # Calcola percentuale completamento
        percentuale_completamento = (total_hours / total_assigned_hours * 100) if total_assigned_hours > 0 else 0

        stats_data = {
            "progetto": {
                "id": progetto.id,
                "nome": progetto.name,
                "descrizione": progetto.description,
                "cup": progetto.cup
            },
            "periodo": {
                "from": from_date.isoformat() if from_date else None,
                "to": to_date.isoformat() if to_date else None
            },
            "statistiche": {
                "totale_ore_lavorate": round(total_hours, 2),
                "totale_ore_previste": round(total_assigned_hours, 2),
                "numero_presenze": total_attendances_count,
                "numero_collaboratori": len(collaborator_hours),
                "numero_assegnazioni": len(assignments),
                "percentuale_completamento": round(percentuale_completamento, 2)
            },
            "collaboratori": collaborators_details
        }

        return stats_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating project statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore nella generazione delle statistiche: {str(e)}"
        )
