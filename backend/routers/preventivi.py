"""Router per la gestione dei preventivi commerciali."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional, List
from io import BytesIO
from datetime import datetime

import crud
import schemas
from database import get_db

# PDF libs (stessa dipendenza di contract_generator.py)
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT

router = APIRouter(prefix="/api/v1/preventivi", tags=["preventivi"])


# ── Endpoints ────────────────────────────────

@router.get("/stati", response_model=List[str])
def get_stati():
    """Restituisce i valori ammessi per lo stato del preventivo."""
    return ['bozza', 'inviato', 'accettato', 'rifiutato']


@router.get("/", response_model=schemas.PaginatedResponse)
def list_preventivi(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    stato: Optional[str] = Query(None),
    azienda_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    attivo: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
):
    items, total = crud.get_preventivi(db, skip=skip, limit=limit,
                                       stato=stato, azienda_id=azienda_id,
                                       search=search, attivo=attivo)
    page = skip // limit + 1 if limit else 1
    pages = (total + limit - 1) // limit if limit else 1
    serialized = [schemas.PreventivoRead.model_validate(p) for p in items]
    # Attach totale from hybrid property
    result = []
    for p, obj in zip(serialized, items):
        d = p.model_dump()
        d['totale'] = obj.totale
        result.append(d)
    return {"items": result, "total": total, "page": page, "pages": pages, "has_next": page < pages}


@router.post("/", response_model=schemas.PreventivoWithRighe, status_code=status.HTTP_201_CREATED)
def create_preventivo(data: schemas.PreventivoCreate, db: Session = Depends(get_db)):
    return crud.create_preventivo(db, data)


@router.get("/{preventivo_id}", response_model=schemas.PreventivoWithRighe)
def get_preventivo(preventivo_id: int, db: Session = Depends(get_db)):
    obj = crud.get_preventivo(db, preventivo_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Preventivo non trovato")
    return obj


@router.put("/{preventivo_id}", response_model=schemas.PreventivoWithRighe)
def update_preventivo(preventivo_id: int, data: schemas.PreventivoUpdate, db: Session = Depends(get_db)):
    obj = crud.update_preventivo(db, preventivo_id, data)
    if not obj:
        raise HTTPException(status_code=404, detail="Preventivo non trovato")
    return obj


@router.delete("/{preventivo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_preventivo(preventivo_id: int, db: Session = Depends(get_db)):
    obj = crud.delete_preventivo(db, preventivo_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Preventivo non trovato")


# ── State machine ─────────────────────────────

@router.put("/{preventivo_id}/invia", response_model=schemas.PreventivoWithRighe)
def invia_preventivo(preventivo_id: int, db: Session = Depends(get_db)):
    obj, err = crud.transizione_stato(db, preventivo_id, 'inviato')
    if err:
        raise HTTPException(status_code=400, detail=err)
    return obj


@router.put("/{preventivo_id}/accetta", response_model=schemas.PreventivoWithRighe)
def accetta_preventivo(preventivo_id: int, db: Session = Depends(get_db)):
    obj, err = crud.transizione_stato(db, preventivo_id, 'accettato')
    if err:
        raise HTTPException(status_code=400, detail=err)
    return obj


@router.put("/{preventivo_id}/rifiuta", response_model=schemas.PreventivoWithRighe)
def rifiuta_preventivo(preventivo_id: int, db: Session = Depends(get_db)):
    obj, err = crud.transizione_stato(db, preventivo_id, 'rifiutato')
    if err:
        raise HTTPException(status_code=400, detail=err)
    return obj


@router.post("/{preventivo_id}/converti-ordine", response_model=schemas.OrdineRead, status_code=status.HTTP_201_CREATED)
def converti_in_ordine(preventivo_id: int, db: Session = Depends(get_db)):
    ordine, err = crud.converti_in_ordine(db, preventivo_id)
    if err:
        raise HTTPException(status_code=400, detail=err)
    return ordine


# ── Righe ─────────────────────────────────────

@router.get("/{preventivo_id}/righe", response_model=List[schemas.PreventivoRigaRead])
def list_righe(preventivo_id: int, db: Session = Depends(get_db)):
    prev = crud.get_preventivo(db, preventivo_id)
    if not prev:
        raise HTTPException(status_code=404, detail="Preventivo non trovato")
    return prev.righe


@router.post("/{preventivo_id}/righe", response_model=schemas.PreventivoRigaRead, status_code=status.HTTP_201_CREATED)
def add_riga(preventivo_id: int, data: schemas.PreventivoRigaCreate, db: Session = Depends(get_db)):
    prev = crud.get_preventivo(db, preventivo_id)
    if not prev:
        raise HTTPException(status_code=404, detail="Preventivo non trovato")
    return crud.create_riga(db, preventivo_id, data)


@router.put("/{preventivo_id}/righe/{riga_id}", response_model=schemas.PreventivoRigaRead)
def update_riga(preventivo_id: int, riga_id: int, data: schemas.PreventivoRigaUpdate, db: Session = Depends(get_db)):
    riga = crud.update_riga(db, riga_id, data)
    if not riga:
        raise HTTPException(status_code=404, detail="Riga non trovata")
    return riga


@router.delete("/{preventivo_id}/righe/{riga_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_riga(preventivo_id: int, riga_id: int, db: Session = Depends(get_db)):
    riga = crud.delete_riga(db, riga_id)
    if not riga:
        raise HTTPException(status_code=404, detail="Riga non trovata")


# ── PDF ───────────────────────────────────────

@router.get("/{preventivo_id}/pdf")
def download_pdf(preventivo_id: int, db: Session = Depends(get_db)):
    prev = crud.get_preventivo(db, preventivo_id)
    if not prev:
        raise HTTPException(status_code=404, detail="Preventivo non trovato")

    pdf_bytes = _genera_pdf_preventivo(prev)
    filename = f"preventivo_{prev.numero}.pdf"

    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── PDF generator ─────────────────────────────

def _fmt_eur(value) -> str:
    try:
        return f"€ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "€ 0,00"


def _genera_pdf_preventivo(prev) -> bytes:
    """Genera il PDF del preventivo con reportlab."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle('PrevTitle', parent=styles['Heading1'], fontSize=18,
                               alignment=TA_CENTER, spaceAfter=6))
    styles.add(ParagraphStyle('PrevNumber', parent=styles['Normal'], fontSize=11,
                               alignment=TA_CENTER, textColor=colors.HexColor('#4361ee'), spaceAfter=20))
    styles.add(ParagraphStyle('PrevLabel', parent=styles['Normal'], fontSize=9,
                               textColor=colors.HexColor('#666666')))
    styles.add(ParagraphStyle('PrevValue', parent=styles['Normal'], fontSize=10, spaceAfter=4))
    styles.add(ParagraphStyle('TotaleRight', parent=styles['Normal'], fontSize=12,
                               alignment=TA_RIGHT, textColor=colors.HexColor('#1a1a1a')))

    story = []

    # Intestazione
    story.append(Paragraph("PREVENTIVO", styles['PrevTitle']))
    story.append(Paragraph(prev.numero, styles['PrevNumber']))

    # Metadati
    data_creazione = prev.created_at.strftime('%d/%m/%Y') if prev.created_at else '—'
    data_scadenza = prev.data_scadenza.strftime('%d/%m/%Y') if prev.data_scadenza else '—'
    azienda = prev.azienda_cliente.ragione_sociale if prev.azienda_cliente else '—'
    consulente = f"{prev.consulente.nome} {prev.consulente.cognome}" if prev.consulente else '—'

    meta_data = [
        ['Data emissione:', data_creazione, 'Scadenza:', data_scadenza],
        ['Cliente:', azienda, 'Consulente:', consulente],
        ['Stato:', prev.stato.upper(), 'Oggetto:', prev.oggetto or '—'],
    ]

    meta_table = Table(meta_data, colWidths=[3.5 * cm, 6 * cm, 3.5 * cm, 6 * cm])
    meta_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#666666')),
        ('TEXTCOLOR', (2, 0), (2, -1), colors.HexColor('#666666')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.HexColor('#f8fafc'), colors.white]),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 0.5 * cm))

    # Note
    if prev.note:
        story.append(Paragraph(f"<b>Note:</b> {prev.note}", styles['PrevValue']))
        story.append(Spacer(1, 0.3 * cm))

    # Righe
    story.append(Paragraph("Dettaglio voci", styles['Heading2']))

    header = ['#', 'Descrizione', 'Qtà', 'Prezzo unit.', 'Sconto', 'Importo']
    rows = [header]
    for i, riga in enumerate(prev.righe or [], 1):
        desc = riga.descrizione_custom or (riga.prodotto.nome if riga.prodotto else '—')
        rows.append([
            str(i),
            desc,
            str(riga.quantita).rstrip('0').rstrip('.') if '.' in str(riga.quantita) else str(riga.quantita),
            _fmt_eur(riga.prezzo_unitario),
            f"{riga.sconto_percentuale:.0f}%" if riga.sconto_percentuale else '—',
            _fmt_eur(riga.importo),
        ])

    col_widths = [1 * cm, 7 * cm, 1.5 * cm, 3 * cm, 2 * cm, 3.5 * cm]
    righe_table = Table(rows, colWidths=col_widths)
    righe_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4361ee')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(righe_table)

    # Totale
    story.append(Spacer(1, 0.4 * cm))
    totale_data = [
        ['', 'TOTALE:', _fmt_eur(prev.totale)],
    ]
    totale_table = Table(totale_data, colWidths=[12.5 * cm, 3 * cm, 3.5 * cm])
    totale_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('LINEABOVE', (1, 0), (-1, 0), 1.5, colors.HexColor('#4361ee')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(totale_table)

    doc.build(story)
    return buffer.getvalue()
