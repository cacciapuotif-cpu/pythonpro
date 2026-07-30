"""
Router per generazione e gestione timesheet PDF.
POST /assignments/{id}/timesheet         → genera/rigenera il timesheet (scrive)
GET  /assignments/{id}/timesheet         → scarica il timesheet esistente (read-only)
POST /assignments/{id}/timesheet/unlock  → sblocca (solo responsabile/admin)
GET  /projects/{id}/timesheets           → lista timesheet del progetto

B5.1 (2026-07-23): separazione comando/interrogazione. La generazione (crea
TimesheetGenerato+righe, scrive il PDF su disco, committa) e' un side-effect e
avviene SOLO via POST. La GET e' idempotente e read-only: nessuna scrittura,
nessun commit; 404 se il timesheet non e' ancora stato generato.
"""
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from database import get_db
from auth import get_current_user, normalize_role, UserRole
from models import Assignment, Attendance, ImplementingEntity, TimesheetGenerato, TimesheetRiga, Project
from timesheet_generator import TimesheetGenerator
from datetime import datetime, timezone
from decimal import Decimal
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


def _build_timesheet_pdf(db: Session, assignment, presenze=None) -> bytes:
    project = assignment.project

    ente_attuatore_nome = None
    logo_path = None
    ente = None
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

    presenze = presenze if presenze is not None else db.query(Attendance).filter(
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
        ente_print_config=ente,
    )
    return pdf_buffer.read()


def _snapshot_pdf(db: Session, assignment, timesheet: TimesheetGenerato) -> bytes:
    righe = db.query(TimesheetRiga).filter(
        TimesheetRiga.timesheet_id == timesheet.id
    ).order_by(TimesheetRiga.date, TimesheetRiga.start_time, TimesheetRiga.id).all()
    return _build_timesheet_pdf(db, assignment, righe)


def _write_pdf(path: str, pdf_bytes: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as pdf_file:
        pdf_file.write(pdf_bytes)


@router.post("/assignments/{assignment_id}/timesheet")
def genera_timesheet(
    assignment_id: int,
    rigenera: bool = Query(False, description="Forza rigenerazione anche se esiste PDF bloccato"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """B5.1: comando di generazione. Crea/rigenera TimesheetGenerato+righe,
    scrive il PDF su disco e committa. Ritorna il PDF generato.

    Comportamento lock invariato: se esiste un timesheet bloccato e si chiede
    ``rigenera`` -> 409 (va sbloccato con motivazione). Se bloccato e non si
    rigenera, ritorna lo snapshot esistente (ricostruendo il file se mancante).
    RBAC: write operational su /api/v1/assignments -> admin + operatore.
    """
    assignment = _get_assignment_full(db, assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment non trovato")

    existing = db.query(TimesheetGenerato).filter(
        TimesheetGenerato.assignment_id == assignment_id
    ).order_by(desc(TimesheetGenerato.generato_il)).first()

    if existing and existing.bloccato:
        if rigenera:
            raise HTTPException(
                status_code=409,
                detail="Timesheet bloccato: sbloccarlo con motivazione prima di rigenerare",
            )
        if os.path.exists(existing.pdf_path):
            return FileResponse(
                path=existing.pdf_path,
                media_type="application/pdf",
                filename=existing.pdf_filename,
            )

        pdf_bytes = _snapshot_pdf(db, assignment, existing)
        _write_pdf(existing.pdf_path, pdf_bytes)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename={}".format(existing.pdf_filename)},
        )

    presenze = db.query(Attendance).filter(
        Attendance.assignment_id == assignment.id
    ).order_by(Attendance.date, Attendance.start_time, Attendance.id).all()
    pdf_bytes = _build_timesheet_pdf(db, assignment, presenze)

    upload_dir = os.path.join(os.getenv("UPLOADS_DIR", "/app/uploads"), "timesheets")
    collab_name = "{}_{}".format(
        _safe_filename(assignment.collaborator.last_name),
        _safe_filename(assignment.collaborator.first_name)
    ).upper()
    ruolo_safe = _safe_filename(assignment.role)[:30]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = "timesheet_{}_{}_{}.pdf".format(collab_name, ruolo_safe, timestamp)
    pdf_path = os.path.join(upload_dir, filename)

    _write_pdf(pdf_path, pdf_bytes)

    record = TimesheetGenerato(
        assignment_id=assignment_id,
        pdf_path=pdf_path,
        pdf_filename=filename,
        generato_da=current_user.username,
        generato_da_user_id=current_user.id,
        bloccato=True,
        totale_ore=sum((Decimal(str(p.hours)) for p in presenze), Decimal("0")),
        presenze_count=len(presenze),
    )
    try:
        db.add(record)
        db.flush()
        db.add_all([
            TimesheetRiga(
                timesheet_id=record.id,
                attendance_id=p.id,
                date=p.date,
                start_time=p.start_time,
                end_time=p.end_time,
                hours=p.hours,
                notes=p.notes,
            )
            for p in presenze
        ])
        db.commit()
    except Exception:
        db.rollback()
        try:
            os.remove(pdf_path)
        except FileNotFoundError:
            pass
        raise

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename={}".format(filename)}
    )


@router.get("/assignments/{assignment_id}/timesheet")
def scarica_timesheet(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """B5.1: interrogazione read-only. NON genera, NON scrive su disco, NON
    committa. Ritorna il PDF del timesheet gia' generato: dal file su disco se
    presente, altrimenti ricostruito in memoria dallo snapshot congelato (senza
    riscriverlo). 404 se il timesheet non e' ancora stato generato: la
    generazione va richiesta con POST sullo stesso path.

    RBAC invariato: il PDF contiene PII (nome collaboratore, ore, righe
    presenze) -> suffisso sensibile /timesheet -> admin + operatore.
    """
    assignment = _get_assignment_full(db, assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment non trovato")

    existing = db.query(TimesheetGenerato).filter(
        TimesheetGenerato.assignment_id == assignment_id
    ).order_by(desc(TimesheetGenerato.generato_il)).first()

    if not existing:
        raise HTTPException(
            status_code=404,
            detail="Timesheet non ancora generato: usa POST per generarlo.",
        )

    if os.path.exists(existing.pdf_path):
        return FileResponse(
            path=existing.pdf_path,
            media_type="application/pdf",
            filename=existing.pdf_filename,
        )

    # File mancante su disco: ricostruito in memoria dallo snapshot immutabile,
    # SENZA riscriverlo (read-only: nessun side-effect su disco o DB).
    pdf_bytes = _snapshot_pdf(db, assignment, existing)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename={}".format(existing.pdf_filename)},
    )


@router.post("/assignments/{assignment_id}/timesheet/unlock")
def sblocca_timesheet(
    assignment_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if normalize_role(current_user.role) not in {
        UserRole.ADMIN.value,
        UserRole.OPERATORE.value,
    }:
        raise HTTPException(status_code=403, detail="Permessi insufficienti")

    motivo = str(payload.get("motivo") or "").strip()
    if not motivo:
        raise HTTPException(status_code=422, detail="La motivazione dello sblocco è obbligatoria")

    existing = db.query(TimesheetGenerato).filter(
        TimesheetGenerato.assignment_id == assignment_id,
        TimesheetGenerato.bloccato == True,
    ).order_by(desc(TimesheetGenerato.generato_il)).first()

    if not existing:
        raise HTTPException(status_code=404, detail="Nessun timesheet bloccato trovato")

    existing.bloccato = False
    existing.sbloccato_da = current_user.username
    existing.sbloccato_da_user_id = current_user.id
    existing.sbloccato_il = datetime.now(timezone.utc)
    existing.sblocco_motivo = motivo
    db.commit()

    return {
        "message": "Timesheet sbloccato",
        "assignment_id": assignment_id,
        "sbloccato_da": current_user.username,
        "motivo": motivo,
    }


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
            # B5.1: POST genera/rigenera (side-effect), GET scarica (read-only).
            "url_genera": "/assignments/{}/timesheet".format(a.id),
            "url_download": "/assignments/{}/timesheet".format(a.id),
            "url_sblocca": "/assignments/{}/timesheet/unlock".format(a.id),
        })

    return {
        "project_id": project_id,
        "project_name": project.name,
        "assignments": result,
    }
