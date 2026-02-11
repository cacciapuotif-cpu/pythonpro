"""
Router per generazione report e statistiche
Gestisce timesheet, KPI e report aggregati
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, date
import logging

import crud
import schemas
from database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/reporting", tags=["Reporting"])


@router.get("/timesheet")
def get_timesheet_report(
    from_date: Optional[date] = Query(None, alias="from", description="Data inizio periodo (YYYY-MM-DD)"),
    to_date: Optional[date] = Query(None, alias="to", description="Data fine periodo (YYYY-MM-DD)"),
    collaborator_id: Optional[int] = Query(None, description="ID collaboratore specifico"),
    project_id: Optional[int] = Query(None, description="ID progetto specifico"),
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
        # Recupera presenze con filtri
        attendances = crud.get_attendances(
            db,
            skip=0,
            limit=10000,  # Limite alto per report completi
            collaborator_id=collaborator_id,
            project_id=project_id,
            start_date=datetime.combine(from_date, datetime.min.time()) if from_date else None,
            end_date=datetime.combine(to_date, datetime.max.time()) if to_date else None
        )

        # Prepara struttura dati per il report
        report_data = {
            "periodo": {
                "from": from_date.isoformat() if from_date else None,
                "to": to_date.isoformat() if to_date else None
            },
            "presenze": [],
            "totali": {
                "ore_totali": 0,
                "numero_presenze": len(attendances),
                "per_collaboratore": {},
                "per_progetto": {}
            }
        }

        # Elabora presenze
        for attendance in attendances:
            collaboratore = crud.get_collaborator(db, attendance.collaborator_id)
            progetto = crud.get_project(db, attendance.project_id)

            presenza_data = {
                "id": attendance.id,
                "data": attendance.date.isoformat() if attendance.date else None,
                "ore_lavorate": float(attendance.hours_worked) if attendance.hours_worked else 0,
                "collaboratore": {
                    "id": collaboratore.id if collaboratore else None,
                    "nome_completo": f"{collaboratore.first_name} {collaboratore.last_name}" if collaboratore else "N/A"
                },
                "progetto": {
                    "id": progetto.id if progetto else None,
                    "nome": progetto.name if progetto else "N/A"
                },
                "note": attendance.note
            }

            report_data["presenze"].append(presenza_data)

            # Aggiorna totali
            ore = float(attendance.hours_worked) if attendance.hours_worked else 0
            report_data["totali"]["ore_totali"] += ore

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

        logger.info(f"Generated timesheet report: {len(attendances)} attendances")
        return report_data

    except Exception as e:
        logger.error(f"Error generating timesheet report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore nella generazione del report: {str(e)}"
        )


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
        # KPI base
        total_collaborators = len(crud.get_collaborators(db, skip=0, limit=10000))
        total_projects = len(crud.get_projects(db, skip=0, limit=10000))
        total_entities = len(crud.get_implementing_entities(db, skip=0, limit=10000))

        # Presenze nel periodo
        attendances = crud.get_attendances(
            db,
            skip=0,
            limit=10000,
            start_date=datetime.combine(from_date, datetime.min.time()) if from_date else None,
            end_date=datetime.combine(to_date, datetime.max.time()) if to_date else None
        )

        total_hours = sum(
            float(att.hours_worked) if att.hours_worked else 0
            for att in attendances
        )

        # Calcola medie
        avg_hours_per_collaborator = total_hours / total_collaborators if total_collaborators > 0 else 0
        avg_hours_per_project = total_hours / total_projects if total_projects > 0 else 0

        # Analisi progetti più attivi
        project_hours = {}
        for att in attendances:
            project_id = att.project_id
            ore = float(att.hours_worked) if att.hours_worked else 0
            if project_id not in project_hours:
                project_hours[project_id] = ore
            else:
                project_hours[project_id] += ore

        top_projects = sorted(
            project_hours.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]

        top_projects_details = []
        for proj_id, hours in top_projects:
            progetto = crud.get_project(db, proj_id)
            if progetto:
                top_projects_details.append({
                    "id": progetto.id,
                    "nome": progetto.name,
                    "ore_totali": hours
                })

        # Analisi collaboratori più attivi
        collaborator_hours = {}
        for att in attendances:
            collab_id = att.collaborator_id
            ore = float(att.hours_worked) if att.hours_worked else 0
            if collab_id not in collaborator_hours:
                collaborator_hours[collab_id] = ore
            else:
                collaborator_hours[collab_id] += ore

        top_collaborators = sorted(
            collaborator_hours.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]

        top_collaborators_details = []
        for collab_id, hours in top_collaborators:
            collaboratore = crud.get_collaborator(db, collab_id)
            if collaboratore:
                top_collaborators_details.append({
                    "id": collaboratore.id,
                    "nome": f"{collaboratore.first_name} {collaboratore.last_name}",
                    "ore_totali": hours
                })

        # Distribuzione contratti per tipo
        assignments = crud.get_assignments(db, skip=0, limit=10000)
        contract_distribution = {}
        for assignment in assignments:
            contract_type = assignment.contract_type or "Non specificato"
            if contract_type not in contract_distribution:
                contract_distribution[contract_type] = 0
            contract_distribution[contract_type] += 1

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
                "totale_presenze": len(attendances),
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

        # Recupera presenze
        attendances = crud.get_attendances(
            db,
            skip=0,
            limit=10000,
            collaborator_id=collaborator_id,
            start_date=datetime.combine(from_date, datetime.min.time()) if from_date else None,
            end_date=datetime.combine(to_date, datetime.max.time()) if to_date else None
        )

        total_hours = sum(float(att.hours_worked) if att.hours_worked else 0 for att in attendances)

        # Ore per progetto
        project_hours = {}
        for att in attendances:
            proj_id = att.project_id
            ore = float(att.hours_worked) if att.hours_worked else 0
            if proj_id not in project_hours:
                project_hours[proj_id] = ore
            else:
                project_hours[proj_id] += ore

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
        num_giorni = len(set(att.date for att in attendances if att.date))
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
                "numero_presenze": len(attendances),
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

        # Recupera presenze
        attendances = crud.get_attendances(
            db,
            skip=0,
            limit=10000,
            project_id=project_id,
            start_date=datetime.combine(from_date, datetime.min.time()) if from_date else None,
            end_date=datetime.combine(to_date, datetime.max.time()) if to_date else None
        )

        total_hours = sum(float(att.hours_worked) if att.hours_worked else 0 for att in attendances)

        # Ore per collaboratore
        collaborator_hours = {}
        for att in attendances:
            collab_id = att.collaborator_id
            ore = float(att.hours_worked) if att.hours_worked else 0
            if collab_id not in collaborator_hours:
                collaborator_hours[collab_id] = ore
            else:
                collaborator_hours[collab_id] += ore

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
                "numero_presenze": len(attendances),
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
