import json
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import crud
import crud_avvisi
import models
import schemas
import schemas_avvisi as avvisi_schemas
from ai_agents.control import agent_enabled, disabled_reason
from auth import User, get_current_user
from database import get_db
from file_upload import sanitize_filename
from services.avviso_ingest import prepare_revision_content, run_extraction_pipeline, save_ingest_markdown

router = APIRouter(prefix="/api/v1/avvisi", tags=["Avvisi"])


def require_avvisi_write(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in {"admin", "manager"}:
        raise HTTPException(status_code=403, detail="Ruolo non autorizzato alla gestione avvisi")
    return current_user


@router.get("/", response_model=List[schemas.Avviso], response_model_by_alias=False)
def read_avvisi(
    skip: int = 0,
    limit: int = 100,
    ente_erogatore: Optional[str] = None,
    active_only: bool = True,
    db: Session = Depends(get_db),
):
    return crud.get_avvisi(
        db,
        skip=skip,
        limit=limit,
        ente_erogatore=ente_erogatore,
        active_only=active_only,
    )


@router.post("/", response_model=schemas.Avviso, response_model_by_alias=False)
def create_avviso(avviso: schemas.AvvisoCreate, db: Session = Depends(get_db)):
    try:
        return crud.create_avviso(db, avviso)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Avviso duplicato per codice/ente erogatore")


@router.get("/{avviso_id}", response_model=schemas.Avviso, response_model_by_alias=False)
def read_avviso(avviso_id: int, db: Session = Depends(get_db)):
    db_avviso = crud.get_avviso(db, avviso_id)
    if db_avviso is None:
        raise HTTPException(status_code=404, detail="Avviso non trovato")
    return db_avviso


@router.put("/{avviso_id}", response_model=schemas.Avviso, response_model_by_alias=False)
def update_avviso(avviso_id: int, avviso: schemas.AvvisoUpdate, db: Session = Depends(get_db)):
    try:
        db_avviso = crud.update_avviso(db, avviso_id, avviso)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Avviso duplicato per codice/ente erogatore")
    if db_avviso is None:
        raise HTTPException(status_code=404, detail="Avviso non trovato")
    return db_avviso


@router.delete("/{avviso_id}")
def delete_avviso(
    avviso_id: int,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_avvisi_write),
):
    db_avviso = crud.delete_avviso(db, avviso_id)
    if db_avviso is None:
        raise HTTPException(status_code=404, detail="Avviso non trovato")
    return {"message": "Avviso disattivato con successo", "id": avviso_id}


@router.get("/{avviso_id}/revisioni", response_model=list[avvisi_schemas.AvvisoRevisioneRead])
def list_revisioni(avviso_id: int, db: Session = Depends(get_db)):
    if not crud_avvisi.get_avviso(db, avviso_id):
        raise HTTPException(status_code=404, detail="Avviso non trovato")
    return (
        db.query(models.AvvisoRevisione)
        .filter(models.AvvisoRevisione.avviso_id == avviso_id)
        .order_by(models.AvvisoRevisione.numero_revisione.desc())
        .all()
    )


@router.post(
    "/{avviso_id}/revisioni/ingest",
    response_model=avvisi_schemas.AvvisoRevisioneIngestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_revisione(
    avviso_id: int,
    file: UploadFile = File(...),
    titolo: str = Form(..., min_length=1, max_length=300),
    etichetta_revisione: Optional[str] = Form(None, max_length=50),
    esegui_estrazione: bool = Form(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_avvisi_write),
):
    if not crud_avvisi.get_avviso(db, avviso_id):
        raise HTTPException(status_code=404, detail="Avviso non trovato")
    contents = await file.read()
    try:
        stored = save_ingest_markdown(avviso_id, file.filename or "", contents)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    duplicate = (
        db.query(models.AvvisoRevisione.id)
        .filter(
            models.AvvisoRevisione.avviso_id == avviso_id,
            models.AvvisoRevisione.source_sha256 == stored.sha256,
        )
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="Documento sorgente già ingerito per questo avviso")
    payload = avvisi_schemas.AvvisoRevisioneCreate(
        titolo=titolo,
        etichetta_revisione=etichetta_revisione,
        source_md_path=stored.storage_key,
        original_filename=sanitize_filename(file.filename or "avviso.md"),
        source_sha256=stored.sha256,
    )
    try:
        revision = crud_avvisi.create_next_revision(
            db, avviso_id, payload, created_by_user_id=current_user.id
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    estrazione: Optional[dict] = None
    if esegui_estrazione and agent_enabled("avviso_extractor"):
        run = run_extraction_pipeline(db, revision.id, user_id=current_user.id)
        summary = json.loads(run.result_summary) if run.result_summary else {}
        estrazione = {
            "run_id": run.id,
            "status": run.status,
            "suggestions_count": run.suggestions_count,
            "summary": summary,
        }
    else:
        prepare_revision_content(db, revision.id)
        motivo = (
            disabled_reason("avviso_extractor")
            if esegui_estrazione
            else "Estrazione non richiesta"
        )
        estrazione = {"skipped": motivo}
    db.refresh(revision)
    return avvisi_schemas.AvvisoRevisioneIngestResponse(
        revisione=avvisi_schemas.AvvisoRevisioneRead.model_validate(revision),
        estrazione=estrazione,
    )
