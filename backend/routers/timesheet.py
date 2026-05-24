"""
Router per generazione e gestione timesheet PDF.
GET  /assignments/{id}/timesheet         → genera o scarica timesheet esistente
POST /assignments/{id}/timesheet/unlock  → sblocca (solo responsabile/admin)
GET  /projects/{id}/timesheets           → lista timesheet del progetto
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from database import get_db
from models import Assignment, Attendance, ImplementingEntity, TimesheetGenerato, Project
from timesheet_generator import TimesheetGenerator
from datetime import datetime
import unicodedata
import os
import io

router = APIRouter(prefix="/api/v1", tags=["timesheet"])


def _safe_filename(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(text))
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return ascii_text.replace(" ", "_").replace("/", "-").replace(".", "").replace(",", "")


def _get_assignment_full(db: Session, assignment_id: int):
    return db.query(Assignment).options(
        joinedload(Assignment.collaborator),
        joinedload(Assignment.project),
    ).filter(Assignment.id == assignment_id).first()


def _build_timesheet_pdf(db: Session, assignment) -> bytes:
    project = assignment.project

    ente_attuatore_nome = None
    logo_path = None
    if project.ente_attuatore_id:
        ente = db.query(ImplementingEntity).filter(
            ImplementingEntity.id == project.ente_attuatore_id
        ).first()
        if ente:
            ente_attuatore_nome = ente.ragione_sociale
            logo_path = ente.logo_path

    designer = db.query(Assignment).options(
        joinedload(Assignment.collaborator)
    ).filter(
        Assignment.project_id == project.id,
        Assignment.is_active == True,
        Assignment.role.ilike("%designer%"),
        Assignment.id != assignment.id,
    ).first()
    designer_name = None
    if designer:
        designer_name = "{} {}".format(
            designer.collaborator.first_name,
            designer.collaborator.last_name
        )

    presenze = db.query(Attendance).filter(
        Attendance.assignment_id == assignment.id
    ).order_by(Attendance.date).all()

    presenza_list = [
        {
            'date': p.date,
            'start_time': p.start_time,
            'end_time': p.end_time,
            'hours': p.hours,
            'notes': p.notes,
        }
        for p in presenze
    ]

    generator = TimesheetGenerator()
    pdf_buffer = generator.generate(
        collaborator_name="{} {}".format(
            assignment.collaborator.first_name,
            assignment.collaborator.last_name
        ),
        collaborator_fiscal_code=assignment.collaborator.fiscal_code,
        project_name=project.name,
        project_cup=project.cup,
        ente_attuatore=ente_attuatore_nome,
        ente_erogatore=project.ente_erogatore,
        avviso=project.avviso,
        ruolo=assignment.role,
        contract_type=assignment.contract_type,
        ore_assegnate=assignment.assigned_hours,
        tariffa_oraria=assignment.hourly_rate,
        data_inizio_contratto=assignment.start_date,
        data_fine_contratto=assignment.end_date,
        presenze=presenza_list,
        logo_path=logo_path,
        designer_name=designer_name,
    )
    return pdf_buffer.read()


@router.get("/assignments/{assignment_id}/timesheet")
def genera_o_scarica_timesheet(
    assignment_id: int,
    rigenera: bool = Query(False, description="Forza rigenerazione anche se esiste PDF bloccato"),
    db: Session = Depends(get_db),
):
    assignment = _get_assignment_full(db, assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment non trovato")

    existing = db.query(TimesheetGenerato).filter(
        TimesheetGenerato.assignment_id == assignment_id
    ).order_by(desc(TimesheetGenerato.generato_il)).first()

    if existing and existing.bloccato and not rigenera:
        if os.path.exists(existing.pdf_path):
            return FileResponse(
                path=existing.pdf_path,
                media_type="application/pdf",
                filename=existing.pdf_filename,
            )

    pdf_bytes = _build_timesheet_pdf(db, assignment)

    upload_dir = "/app/uploads/timesheets"
    os.makedirs(upload_dir, exist_ok=True)

    collab_name = "{}_{}".format(
        _safe_filename(assignment.collaborator.last_name),
        _safe_filename(assignment.collaborator.first_name)
    ).upper()
    ruolo_safe = _safe_filename(assignment.role)[:30]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = "timesheet_{}_{}_{}.pdf".format(collab_name, ruolo_safe, timestamp)
    pdf_path = os.path.join(upload_dir, filename)

    with open(pdf_path, 'wb') as f:
        f.write(pdf_bytes)

    record = TimesheetGenerato(
        assignment_id=assignment_id,
        pdf_path=pdf_path,
        pdf_filename=filename,
        bloccato=True,
    )
    db.add(record)
    db.commit()

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename={}".format(filename)}
    )


@router.post("/assignments/{assignment_id}/timesheet/unlock")
def sblocca_timesheet(
    assignment_id: int,
    sbloccato_da: str = Query(..., description="Username di chi sblocca"),
    db: Session = Depends(get_db),
):
    existing = db.query(TimesheetGenerato).filter(
        TimesheetGenerato.assignment_id == assignment_id,
        TimesheetGenerato.bloccato == True,
    ).order_by(desc(TimesheetGenerato.generato_il)).first()

    if not existing:
        raise HTTPException(status_code=404, detail="Nessun timesheet bloccato trovato")

    existing.bloccato = False
    existing.sbloccato_da = sbloccato_da
    existing.sbloccato_il = datetime.now()
    db.commit()

    return {"message": "Timesheet sbloccato", "assignment_id": assignment_id, "sbloccato_da": sbloccato_da}


@router.get("/projects/{project_id}/timesheets")
def lista_timesheets_progetto(
    project_id: int,
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Progetto non trovato")

    assignments = db.query(Assignment).options(
        joinedload(Assignment.collaborator),
    ).filter(
        Assignment.project_id == project_id,
        Assignment.is_active == True,
    ).order_by(Assignment.role, Assignment.id).all()

    result = []
    for a in assignments:
        presenze_count = db.query(Attendance).filter(
            Attendance.assignment_id == a.id
        ).count()

        ore_effettive = db.query(
            __import__('sqlalchemy').func.coalesce(
                __import__('sqlalchemy').func.sum(Attendance.hours), 0.0
            )
        ).filter(Attendance.assignment_id == a.id).scalar()

        ultimo_timesheet = db.query(TimesheetGenerato).filter(
            TimesheetGenerato.assignment_id == a.id
        ).order_by(desc(TimesheetGenerato.generato_il)).first()

        result.append({
            "assignment_id": a.id,
            "collaboratore": "{} {}".format(a.collaborator.first_name, a.collaborator.last_name),
            "ruolo": a.role,
            "ore_assegnate": a.assigned_hours,
            "ore_effettive": float(ore_effettive or 0),
            "presenze_count": presenze_count,
            "timesheet_generato": ultimo_timesheet is not None,
            "timesheet_bloccato": ultimo_timesheet.bloccato if ultimo_timesheet else False,
            "timesheet_generato_il": ultimo_timesheet.generato_il.isoformat() if ultimo_timesheet else None,
            "url_download": "/assignments/{}/timesheet".format(a.id),
            "url_sblocca": "/assignments/{}/timesheet/unlock".format(a.id),
        })

    return {
        "project_id": project_id,
        "project_name": project.name,
        "assignments": result,
    }
