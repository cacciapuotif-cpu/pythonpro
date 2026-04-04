"""Router per il modulo Piano Finanziario Formazienda."""

from io import BytesIO
import logging
import re
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from sqlalchemy.orm import Session

import crud
import schemas
from database import get_db
from piano_finanziario_config import MACROVOCE_TITLES, get_voice_template_map, ordered_templates

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/piani-finanziari", tags=["Piani Finanziari"])


def _serialize_template_documento(template):
    if not template:
        return None
    return schemas.TemplateDocumentoSelezionato(
        id=template.id,
        nome_template=template.nome_template,
        ambito_template=template.ambito_template,
        chiave_documento=template.chiave_documento,
        ente_erogatore=template.ente_erogatore,
        avviso=template.avviso,
        progetto_id=template.progetto_id,
        ente_attuatore_id=template.ente_attuatore_id,
    )

def _effective_avviso_code(piano):
    return (getattr(getattr(piano, "avviso_rel", None), "codice", None) or piano.avviso or "").strip()


def _derive_piano_template_key(ente_erogatore: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", (ente_erogatore or "").strip().lower()).strip("_")
    return f"piano_finanziario_{normalized}" if normalized else "piano_finanziario_standard"


def _resolve_piano_template(piano, db: Session):
    if getattr(piano, "template", None):
        return piano.template
    ente = piano.ente_erogatore or (getattr(piano.progetto, "ente_erogatore", None) if piano.progetto else None)
    return crud.resolve_document_template(
        db,
        ambito_template="piano_finanziario",
        chiave_documento=_derive_piano_template_key(ente),
        progetto_id=piano.progetto_id,
        ente_attuatore_id=getattr(piano.progetto, "ente_attuatore_id", None) if piano.progetto else None,
        ente_erogatore=ente,
        avviso=_effective_avviso_code(piano) or (getattr(piano.progetto, "avviso", None) if piano.progetto else None),
    )


def _build_detail_response(piano, db: Session | None = None) -> schemas.PianoFinanziarioDettaglio:
    effective_rows = crud.build_effective_piano_rows(piano, db=db)
    riepilogo = crud.build_piano_finanziario_riepilogo(piano, db=db)
    totale_consuntivo = riepilogo["totale_consuntivo"]
    voci = [
        schemas.VocePianoFinanziario(
            id=voce["id"] or 0,
            piano_id=voce["piano_id"],
            macrovoce=voce["macrovoce"],
            voce_codice=voce["voce_codice"],
            descrizione=voce["descrizione"],
            progetto_label=voce["progetto_label"],
            edizione_label=voce["edizione_label"],
            ore=float(voce["ore"] or 0.0),
            importo_consuntivo=float(voce["importo_consuntivo"] or 0.0),
            importo_preventivo=float(voce["importo_preventivo"] or 0.0),
            importo_presentato=float(voce["importo_presentato"] or 0.0),
            created_at=voce["created_at"],
            updated_at=voce["updated_at"],
            totale_consuntivo_riferimento=totale_consuntivo,
        )
        for voce in sorted(
            effective_rows,
            key=lambda item: (item["macrovoce"], item["voce_codice"], item["progetto_label"] or "", item["edizione_label"] or ""),
        )
    ]
    template_documento = _serialize_template_documento(_resolve_piano_template(piano, db)) if db else None
    return schemas.PianoFinanziarioDettaglio(
        id=piano.id,
        progetto_id=piano.progetto_id,
        template_id=piano.template_id,
        anno=piano.anno,
        ente_erogatore=piano.ente_erogatore,
        avviso=_effective_avviso_code(piano),
        avviso_id=getattr(piano, "avviso_id", None),
        avviso_rel=schemas.Avviso.model_validate(piano.avviso_rel) if getattr(piano, "avviso_rel", None) else None,
        created_at=piano.created_at,
        updated_at=piano.updated_at,
        progetto=schemas.Project.model_validate(piano.progetto),
        voci=voci,
        template_documento=template_documento,
    )


def _ordered_export_rows(piano):
    by_code = {}
    for voce in piano.voci:
        by_code.setdefault(voce.voce_codice, []).append(voce)

    rows = []
    for template in ordered_templates():
        voce_codice = template["voce_codice"]
        if template["is_dynamic"]:
            dynamic_rows = sorted(
                by_code.get(voce_codice, []),
                key=lambda item: (item.progetto_label or "", item.edizione_label or ""),
            )
            rows.extend(dynamic_rows)
        else:
            fixed_row = next(iter(by_code.get(voce_codice, [])), None)
            rows.append(fixed_row or template)
    return rows


def _build_excel_workbook(piano):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Piano Finanziario"

    bold = Font(bold=True)
    header_fill = PatternFill(fill_type="solid", fgColor="D9EAF7")
    total_fill = PatternFill(fill_type="solid", fgColor="E5E7EB")
    section_fill = PatternFill(fill_type="solid", fgColor="C7D2FE")

    sheet["A1"] = f"Piano Finanziario - {piano.progetto.name}"
    sheet["A1"].font = Font(bold=True, size=14)
    sheet["A2"] = f"Anno {piano.anno} · Ente Erogatore {piano.ente_erogatore} · Avviso {_effective_avviso_code(piano)}"
    current_row = 4

    macro_total_rows = {}
    data_rows_for_percent = []
    consuntivo_col = "E"
    percent_col = "F"
    preventivo_col = "G"

    voice_map = get_voice_template_map()
    export_rows = _ordered_export_rows(piano)

    for macrovoce in ["A", "B", "C", "D"]:
        sheet.merge_cells(start_row=current_row, start_column=1, end_row=current_row, end_column=7)
        title_cell = sheet.cell(row=current_row, column=1, value=MACROVOCE_TITLES[macrovoce])
        title_cell.font = bold
        title_cell.fill = section_fill
        current_row += 1

        headers = ["ID / Voce", "Progetto", "Edizione", "Ore", "Consuntivo (€)", "%", "Preventivo (€)"]
        for idx, label in enumerate(headers, start=1):
            cell = sheet.cell(row=current_row, column=idx, value=label)
            cell.font = bold
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")
        current_row += 1

        section_start_row = current_row
        for item in export_rows:
            row_macrovoce = item.macrovoce if hasattr(item, "macrovoce") else item["macrovoce"]
            if row_macrovoce != macrovoce:
                continue

            voce_codice = item.voce_codice if hasattr(item, "voce_codice") else item["voce_codice"]
            descrizione = item.descrizione if hasattr(item, "descrizione") else item["descrizione"]
            progetto_label = item.progetto_label if hasattr(item, "progetto_label") else item.get("progetto_label")
            edizione_label = item.edizione_label if hasattr(item, "edizione_label") else item.get("edizione_label")
            ore = float(item.ore or 0.0) if hasattr(item, "ore") else 0.0
            importo_consuntivo = float(item.importo_consuntivo or 0.0) if hasattr(item, "importo_consuntivo") else 0.0
            importo_preventivo = float(item.importo_preventivo or 0.0) if hasattr(item, "importo_preventivo") else 0.0

            sheet.cell(row=current_row, column=1, value=f"{voce_codice} - {descrizione}")
            sheet.cell(row=current_row, column=2, value=progetto_label)
            sheet.cell(row=current_row, column=3, value=edizione_label)
            sheet.cell(row=current_row, column=4, value=ore)
            sheet.cell(row=current_row, column=5, value=importo_consuntivo)
            sheet.cell(row=current_row, column=7, value=importo_preventivo)
            data_rows_for_percent.append(current_row)
            current_row += 1

        total_row = current_row
        sheet.cell(row=total_row, column=1, value=f"Totale Macrovoce {macrovoce}")
        sheet.cell(row=total_row, column=4, value=f"=SUM(D{section_start_row}:D{total_row - 1})")
        sheet.cell(row=total_row, column=5, value=f"=SUM(E{section_start_row}:E{total_row - 1})")
        sheet.cell(row=total_row, column=7, value=f"=SUM(G{section_start_row}:G{total_row - 1})")
        for col in range(1, 8):
            sheet.cell(row=total_row, column=col).font = bold
            sheet.cell(row=total_row, column=col).fill = total_fill
        macro_total_rows[macrovoce] = total_row
        current_row += 2

    summary_start = current_row
    totale_row = summary_start
    contributo_row = summary_start + 1
    cofin_row = summary_start + 2

    sheet.cell(row=totale_row, column=1, value="Totale consuntivo / preventivo").font = bold
    sheet.cell(row=totale_row, column=5, value=f"=E{macro_total_rows['A']}+E{macro_total_rows['B']}+E{macro_total_rows['C']}+E{macro_total_rows['D']}")
    sheet.cell(row=totale_row, column=7, value=f"=G{macro_total_rows['A']}+G{macro_total_rows['B']}+G{macro_total_rows['C']}+G{macro_total_rows['D']}")

    sheet.cell(row=contributo_row, column=1, value="Contributo richiesto").font = bold
    sheet.cell(row=contributo_row, column=5, value=f"=E{macro_total_rows['A']}+E{macro_total_rows['B']}+E{macro_total_rows['C']}")

    sheet.cell(row=cofin_row, column=1, value="Cofinanziamento").font = bold
    sheet.cell(row=cofin_row, column=5, value=f"=E{macro_total_rows['D']}")

    for row_num in list(data_rows_for_percent) + list(macro_total_rows.values()):
        sheet.cell(row=row_num, column=6, value=f"=IF($E${totale_row}=0,0,E{row_num}/$E${totale_row})")

    for row_num in [totale_row, contributo_row, cofin_row]:
        for col in range(1, 8):
            sheet.cell(row=row_num, column=col).font = bold
            sheet.cell(row=row_num, column=col).fill = total_fill

    for column in [consuntivo_col, percent_col, preventivo_col]:
        for row in range(1, cofin_row + 1):
            sheet[f"{column}{row}"].number_format = "€ #,##0.00" if column != percent_col else "0.00%"

    for row in range(1, cofin_row + 1):
        sheet[f"D{row}"].number_format = "#,##0.00"

    for column_letter, width in {"A": 40, "B": 20, "C": 18, "D": 12, "E": 16, "F": 10, "G": 16}.items():
        sheet.column_dimensions[column_letter].width = width

    return workbook


@router.get("/", response_model=List[schemas.PianoFinanziario])
def list_piani_finanziari(
    progetto_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return crud.get_piani_finanziari(db, progetto_id=progetto_id, skip=skip, limit=limit)


@router.post("/", response_model=schemas.PianoFinanziarioDettaglio, status_code=status.HTTP_201_CREATED)
def create_piano_finanziario(
    payload: schemas.PianoFinanziarioCreate,
    db: Session = Depends(get_db),
):
    try:
        piano = crud.create_piano_finanziario(db, payload)
        return _build_detail_response(piano, db=db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{piano_id}", response_model=schemas.PianoFinanziarioDettaglio)
def get_piano_finanziario(piano_id: int, db: Session = Depends(get_db)):
    piano = crud.get_piano_finanziario(db, piano_id)
    if not piano:
        raise HTTPException(status_code=404, detail="Piano finanziario non trovato")
    return _build_detail_response(piano, db=db)


@router.put("/{piano_id}/voci", response_model=schemas.PianoFinanziarioDettaglio)
def update_voci_piano_finanziario(
    piano_id: int,
    payload: schemas.PianoFinanziarioBulkUpdate,
    db: Session = Depends(get_db),
):
    try:
        piano = crud.bulk_upsert_voci_piano(db, piano_id, payload)
        if not piano:
            raise HTTPException(status_code=404, detail="Piano finanziario non trovato")
        return _build_detail_response(piano, db=db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{piano_id}/riepilogo", response_model=schemas.PianoFinanziarioRiepilogo)
def get_riepilogo_piano_finanziario(piano_id: int, db: Session = Depends(get_db)):
    piano = crud.get_piano_finanziario(db, piano_id)
    if not piano:
        raise HTTPException(status_code=404, detail="Piano finanziario non trovato")
    return crud.build_piano_finanziario_riepilogo(piano, db=db)


@router.get("/{piano_id}/export-excel")
def export_piano_finanziario_excel(piano_id: int, db: Session = Depends(get_db)):
    piano = crud.get_piano_finanziario(db, piano_id)
    if not piano:
        raise HTTPException(status_code=404, detail="Piano finanziario non trovato")

    workbook = _build_excel_workbook(piano)
    stream = BytesIO()
    workbook.save(stream)
    stream.seek(0)
    filename = f"piano_finanziario_{piano.progetto.name.replace(' ', '_')}_{piano.anno}.xlsx"
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
