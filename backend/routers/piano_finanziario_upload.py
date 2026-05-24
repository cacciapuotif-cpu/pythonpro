"""Router per upload piano finanziario FAPI (XLSX)."""
import os
import uuid
import shutil
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session

import models
from database import get_db
from auth import get_current_user, User
import fapi_preview_store as _preview_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["fapi-piano-finanziario"])

UPLOAD_DIR = "/app/uploads/piani_finanziari"
os.makedirs(UPLOAD_DIR, exist_ok=True)


class ConfirmPianoRequest(BaseModel):
    preview_token: str


@router.post("/{project_id}/upload-piano-finanziario")
async def upload_piano_finanziario(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Progetto non trovato")

    fname = file.filename or ""
    if not (fname.lower().endswith(".xlsx") or fname.lower().endswith(".xls")):
        raise HTTPException(status_code=400, detail="File deve essere un XLSX")

    token = str(uuid.uuid4())
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(UPLOAD_DIR, f"{project_id}_{timestamp}_{token}.xlsx")

    try:
        with open(dest, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Errore salvataggio: {exc}")

    try:
        from services.parsers.fapi.piano_finanziario_parser import parse_piano_finanziario
        result = parse_piano_finanziario(dest)
    except Exception as exc:
        os.remove(dest)
        raise HTTPException(status_code=500, detail=f"Errore parsing XLSX: {exc}")

    _preview_store.store(token, {
        "project_id": project_id,
        "file_path": dest,
        **result,
    })

    return {
        "preview_token": token,
        "project_id": project_id,
        **result,
    }


@router.post("/{project_id}/confirm-piano-finanziario")
def confirm_piano_finanziario(
    project_id: int,
    body: ConfirmPianoRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Progetto non trovato")

    preview = _preview_store.pop(body.preview_token)
    if not preview:
        raise HTTPException(status_code=404, detail="Preview token non trovato o scaduto")

    if preview["project_id"] != project_id:
        raise HTTPException(status_code=400, detail="Token non appartiene a questo progetto")

    anno = datetime.now().year

    # trova o crea piano finanziario FAPI per questo progetto
    piano = db.query(models.PianoFinanziario).filter(
        models.PianoFinanziario.progetto_id == project_id,
        models.PianoFinanziario.tipo_fondo == "fapi",
    ).first()

    totale_importo = preview.get("totale_importo") or 0
    totale_ore = preview.get("totale_ore") or 0

    if not piano:
        try:
            piano = models.PianoFinanziario(
                progetto_id=project_id,
                anno=anno,
                ente_erogatore="FAPI",
                avviso=project.codice_fapi or "",
                tipo_fondo="fapi",
                nome=f"Piano Finanziario FAPI — {project.codice_fapi or project.name}",
                codice_piano=project.codice_fapi,
                budget_totale=totale_importo,
                budget_approvato=totale_importo,
                data_inizio=datetime.now(),
                data_fine=datetime(anno + 1, 12, 31),
                stato="bozza",
            )
            db.add(piano)
            db.flush()
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Errore creazione piano finanziario: {exc}")

    # helper: estrae macrovoce dal codice (A.1.1.1 → 'A')
    def _macrovoce(codice: str) -> str:
        c = (codice or "A")[0].upper()
        return c if c in "ABCD" else "A"

    # helper: mappa descrizione → categoria
    def _categoria(desc: str | None, materia: str | None) -> str:
        combined = f"{desc or ''} {materia or ''}".lower()
        if (materia or "").strip().lower().startswith("tutor"):
            return "tutoraggio"
        for kw, cat in [
            ("docenz", "docenza"), ("tutor", "tutoraggio"),
            ("progett", "progettazione"), ("material", "materiali_didattici"),
            ("aula", "aula"), ("attrezzat", "attrezzature"),
            ("certific", "certificazioni"), ("viaggio", "viaggi"),
            ("retribuz", "altro"), ("assicuraz", "altro"),
            ("promoz", "altro"), ("monitor", "altro"),
            ("coordinam", "coordinamento"), ("direzione", "coordinamento"),
        ]:
            if kw in combined:
                return cat
        return "altro"

    voci_create = 0
    from services.parsers.fapi.piano_finanziario_parser import resolve_modulo_formativo_id

    for v in preview.get("voci", []):
        try:
            codice = v.get("voce_codice") or "A"
            desc = v.get("voce_descrizione")
            materia = v.get("materia")
            categoria = _categoria(desc, materia)
            ore_previste = float(v.get("ore_previste") or 0)
            importo_preventivo = float(v.get("importo_totale") or 0)
            if not importo_preventivo and categoria == "docenza" and ore_previste:
                importo_preventivo = round(ore_previste * 50.0, 2)
            tariffa_oraria = round(importo_preventivo / ore_previste, 2) if ore_previste else 0.0
            voce = models.VocePianoFinanziario(
                piano_id=piano.id,
                modulo_formativo_id=resolve_modulo_formativo_id(db, project, v),
                macrovoce=_macrovoce(codice),
                voce_codice=codice,
                categoria=categoria,
                sottocategoria=desc,
                mansione_riferimento=materia,
                descrizione=v.get("azienda"),
                progetto_label=v.get("azienda"),
                ore_previste=ore_previste,
                ore=ore_previste,
                tariffa_oraria=tariffa_oraria,
                importo_preventivo=importo_preventivo,
                stato="previsto",
            )
            db.add(voce)
            voci_create += 1
        except Exception as exc:
            logger.warning("Errore creazione voce piano: %s — %s", v, exc)

    db.commit()

    return {
        "project_id": project_id,
        "piano_id": piano.id,
        "voci_create": voci_create,
        "totale_ore": totale_ore,
        "totale_importo": totale_importo,
    }
