"""Rendering condiviso della carta intestata degli enti attuatori.

Il modulo è deliberatamente opt-in: ``print_config_enabled=False`` non deve
mai cambiare la pipeline PDF storica. I generatori chiamanti mantengono quindi
il proprio ramo legacy e usano queste funzioni solo quando la configurazione è
abilitata.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Callable

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib import colors

from file_upload import get_file_path


@dataclass
class EntityPageDecoration:
    margins: dict[str, float]
    on_first_page: Callable
    on_later_pages: Callable


def mask_iban(value: str | None) -> str:
    clean = "".join(str(value or "").split()).upper()
    if not clean:
        return ""
    if len(clean) <= 4:
        return clean
    return f"{clean[:2]}••••••••••••••••••••{clean[-4:]}"


def select_location(entity, location_id: int | None = None):
    locations = [location for location in getattr(entity, "sedi", []) if location.is_active]
    if location_id is not None:
        return next((location for location in locations if location.id == location_id), None)
    return (
        next((location for location in locations if location.tipo == "legale"), None)
        or next((location for location in locations if location.is_principale), None)
        or (locations[0] if locations else None)
    )


def select_bank_account(entity, account_id: int | None = None):
    accounts = [account for account in getattr(entity, "conti_correnti", []) if account.is_active]
    if account_id is not None:
        return next((account for account in accounts if account.id == account_id), None)
    return next((account for account in accounts if account.is_predefinito), None) or (
        accounts[0] if accounts else None
    )


def _letterhead_reader(entity):
    stored_path = getattr(entity, "letterhead_path", None)
    if not stored_path:
        return None
    path = Path(get_file_path(stored_path))
    if path.suffix.lower() != ".pdf":
        return ImageReader(str(path))

    # pdfplumber dipende già da pypdfium2: nessuna nuova dipendenza runtime.
    import pypdfium2

    document = pypdfium2.PdfDocument(str(path))
    page = document[0]
    bitmap = page.render(scale=2)
    image = bitmap.to_pil()
    reader = ImageReader(image)
    # ImageReader mantiene il PIL materializzato, quindi il documento PDF può
    # essere chiuso prima del build ReportLab.
    page.close()
    document.close()
    return reader


def page_decoration(entity) -> EntityPageDecoration:
    page_width, page_height = A4
    letterhead = _letterhead_reader(entity)
    logo_path = None
    if getattr(entity, "logo_path", None):
        logo_path = str(get_file_path(entity.logo_path))

    logo_width = float(entity.print_logo_width_mm) * mm
    logo_height = float(entity.print_logo_height_mm) * mm
    logo_x = float(entity.print_logo_x_mm) * mm
    # La UI esprime Y come distanza dal bordo superiore.
    logo_y = page_height - (float(entity.print_logo_y_mm) * mm) - logo_height
    footer = (getattr(entity, "print_footer", None) or "").strip()
    letterhead_all_pages = entity.print_letterhead_pages == "all"

    def draw(canvas, _doc, *, first_page: bool):
        canvas.saveState()
        if letterhead is not None and (first_page or letterhead_all_pages):
            canvas.drawImage(
                letterhead,
                0,
                0,
                width=page_width,
                height=page_height,
                preserveAspectRatio=False,
                mask="auto",
            )
        if logo_path:
            canvas.drawImage(
                logo_path,
                logo_x,
                logo_y,
                width=logo_width,
                height=logo_height,
                preserveAspectRatio=True,
                mask="auto",
            )
        if footer:
            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(colors.HexColor("#4b5563"))
            canvas.drawCentredString(page_width / 2, 8 * mm, footer[:300])
        canvas.restoreState()

    return EntityPageDecoration(
        margins={
            "topMargin": float(entity.print_margin_top_mm) * mm,
            "bottomMargin": float(entity.print_margin_bottom_mm) * mm,
            "leftMargin": float(entity.print_margin_left_mm) * mm,
            "rightMargin": float(entity.print_margin_right_mm) * mm,
        },
        on_first_page=lambda canvas, doc: draw(canvas, doc, first_page=True),
        on_later_pages=lambda canvas, doc: draw(canvas, doc, first_page=False),
    )


def generate_print_preview(entity) -> BytesIO:
    """Genera un documento neutro che non crea contratti o record applicativi."""
    decoration = page_decoration(entity)
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, **decoration.margins)
    styles = getSampleStyleSheet()
    body = ParagraphStyle("PreviewBody", parent=styles["BodyText"], leading=15, spaceAfter=10)
    story = [
        Paragraph("Anteprima configurazione di stampa", styles["Title"]),
        Spacer(1, 5 * mm),
        Paragraph(
            f"Ente attuatore: <b>{entity.ragione_sociale}</b><br/>"
            "Questo documento è una prova grafica e non ha valore contrattuale.",
            body,
        ),
        Table(
            [
                ["Campo di prova", "Valore"],
                ["Partita IVA", entity.partita_iva or "—"],
                ["Sede legale", entity.indirizzo_completo or "—"],
                ["Pagina", "1 di 2"],
            ],
            colWidths=[55 * mm, 95 * mm],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5e7eb")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9ca3af")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("PADDING", (0, 0), (-1, -1), 7),
                ]
            ),
        ),
    ]
    # Testa anche l'impostazione "tutte le pagine" producendo abbastanza
    # contenuto da attraversare almeno una seconda pagina.
    for index in range(48):
        story.append(
            Paragraph(
                f"Riga di prova {index + 1}: verifica margini, leggibilità e sovrapposizioni.",
                body,
            )
        )
    doc.build(
        story,
        onFirstPage=decoration.on_first_page,
        onLaterPages=decoration.on_later_pages,
    )
    output.seek(0)
    return output
