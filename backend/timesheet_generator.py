"""
Generatore di timesheet PDF per collaboratori.
Un timesheet per ogni (collaboratore, progetto, mansione).
Configurabile per ente erogatore (Formazienda, FAPI, ecc).
"""
from datetime import datetime
from pathlib import Path
from typing import Optional
import logging

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from io import BytesIO

logger = logging.getLogger(__name__)

FONDO_CONFIG = {
    "formazienda": {
        "mostra_importo": False,
        "firme": ["collaboratore", "designer"],
        "label_firma_1": "Il/La Collaboratore/trice",
        "label_firma_2": "Il Responsabile (Designer)",
    },
    "fapi": {
        "mostra_importo": False,
        "firme": ["collaboratore"],
        "label_firma_1": "Il/La Collaboratore/trice",
        "label_firma_2": None,
    },
    "fondimpresa": {
        "mostra_importo": False,
        "firme": ["collaboratore"],
        "label_firma_1": "Il/La Collaboratore/trice",
        "label_firma_2": None,
    },
    "default": {
        "mostra_importo": False,
        "firme": ["collaboratore"],
        "label_firma_1": "Il/La Collaboratore/trice",
        "label_firma_2": None,
    },
}


def _get_fondo_config(ente_erogatore: Optional[str]) -> dict:
    normalized = (ente_erogatore or "").strip().lower()
    for key in FONDO_CONFIG:
        if key in normalized:
            return FONDO_CONFIG[key]
    return FONDO_CONFIG["default"]


class TimesheetGenerator:
    """Genera timesheet PDF per (collaboratore, progetto, mansione)."""

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_styles()

    def _setup_styles(self):
        self.styles.add(ParagraphStyle(
            name='TSTitle',
            parent=self.styles['Heading1'],
            fontSize=14,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=6,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
        self.styles.add(ParagraphStyle(
            name='TSSubtitle',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#444444'),
            spaceAfter=4,
            alignment=TA_CENTER,
        ))
        self.styles.add(ParagraphStyle(
            name='TSValue',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=4,
            fontName='Helvetica-Bold'
        ))
        self.styles.add(ParagraphStyle(
            name='TSSmall',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#888888'),
        ))

    def generate(
        self,
        *,
        collaborator_name: str,
        collaborator_fiscal_code: str,
        project_name: str,
        project_cup: Optional[str],
        ente_attuatore: Optional[str],
        ente_erogatore: Optional[str],
        avviso: Optional[str],
        ruolo: str,
        contract_type: Optional[str],
        ore_assegnate: float,
        tariffa_oraria: float,
        data_inizio_contratto: datetime,
        data_fine_contratto: datetime,
        presenze: list,
        logo_path: Optional[str] = None,
        designer_name: Optional[str] = None,
    ) -> BytesIO:
        config = _get_fondo_config(ente_erogatore)
        # SQLAlchemy restituisce Numeric come Decimal; ReportLab e i totali
        # delle presenze lavorano con float. Normalizziamo una volta al confine.
        ore_assegnate_num = float(ore_assegnate or 0)
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm,
        )

        story = []

        if logo_path and Path(logo_path).exists():
            try:
                logo = Image(logo_path, width=4*cm, height=2*cm, kind='proportional')
                logo.hAlign = 'LEFT'
                story.append(logo)
                story.append(Spacer(1, 0.3*cm))
            except Exception as exc:
                logger.warning("Logo non caricabile: {}".format(exc))

        story.append(Paragraph("TIMESHEET", self.styles['TSTitle']))
        story.append(Paragraph("Registro Ore di Attività", self.styles['TSSubtitle']))
        story.append(Spacer(1, 0.4*cm))

        info_data = [
            ["Collaboratore:", collaborator_name, "Codice Fiscale:", collaborator_fiscal_code or "—"],
            ["Progetto:", project_name, "CUP:", project_cup or "—"],
            ["Ente Attuatore:", ente_attuatore or "—", "Ente Erogatore:", ente_erogatore or "—"],
            ["Avviso:", avviso or "—", "Tipo Contratto:", contract_type or "—"],
            ["Mansione:", ruolo, "Data Inizio:", data_inizio_contratto.strftime("%d/%m/%Y")],
            ["Data Fine:", data_fine_contratto.strftime("%d/%m/%Y"), "", ""],
        ]

        info_table = Table(info_data, colWidths=[3.5*cm, 6*cm, 3.5*cm, 4*cm])
        info_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#666666')),
            ('TEXTCOLOR', (2, 0), (2, -1), colors.HexColor('#666666')),
            ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#1a1a1a')),
            ('TEXTCOLOR', (3, 0), (3, -1), colors.HexColor('#1a1a1a')),
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.HexColor('#f8f8f8'), colors.white]),
            ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#dddddd')),
            ('PADDING', (0, 0), (-1, -1), 5),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(info_table)
        story.append(Spacer(1, 0.5*cm))

        story.append(Paragraph("Dettaglio Presenze", self.styles['TSValue']))
        story.append(Spacer(1, 0.2*cm))

        presence_header = ["Data", "Ora Inizio", "Ora Fine", "Ore", "Note", "Firma"]
        presence_rows = [presence_header]

        for p in sorted(presenze, key=lambda x: x['date']):
            date_str = p['date'].strftime("%d/%m/%Y") if hasattr(p['date'], 'strftime') else str(p['date'])
            start_str = p['start_time'].strftime("%H:%M") if hasattr(p['start_time'], 'strftime') else str(p['start_time'])
            end_str = p['end_time'].strftime("%H:%M") if hasattr(p['end_time'], 'strftime') else str(p['end_time'])
            presence_rows.append([
                date_str,
                start_str,
                end_str,
                "{:.1f}h".format(float(p['hours'])),
                p.get('notes') or "",
                "",
            ])

        if not presenze:
            presence_rows.append(["Nessuna presenza registrata", "", "", "", "", ""])

        presence_table = Table(
            presence_rows,
            colWidths=[2.5*cm, 2.5*cm, 2.5*cm, 1.8*cm, 5.2*cm, 2.5*cm]
        )
        presence_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (4, 1), (4, -1), 'LEFT'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
            ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#cccccc')),
            ('PADDING', (0, 0), (-1, -1), 5),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LINEBELOW', (0, 0), (-1, 0), 1, colors.HexColor('#2c3e50')),
        ]))
        story.append(presence_table)
        story.append(Spacer(1, 0.5*cm))

        totale_ore = sum(float(p['hours']) for p in presenze)

        riepilogo_data = [
            ["Ore Assegnate", "Ore Effettive", "Completamento"],
            [
                "{:.1f} h".format(ore_assegnate_num),
                "{:.1f} h".format(totale_ore),
                "{:.0f}%".format(
                    (totale_ore / ore_assegnate_num * 100)
                    if ore_assegnate_num > 0
                    else 0
                ),
            ]
        ]

        col_width = 17*cm / 3
        riepilogo_table = Table(riepilogo_data, colWidths=[col_width, col_width, col_width])
        riepilogo_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#27ae60')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#cccccc')),
            ('PADDING', (0, 0), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#eafaf1')),
        ]))
        story.append(riepilogo_table)
        story.append(Spacer(1, 1*cm))

        label_1 = config["label_firma_1"]
        label_2 = config.get("label_firma_2")

        if label_2:
            designer_label = label_2
            if designer_name:
                designer_label = "{}\n({})".format(label_2, designer_name)
            firma_data = [
                [label_1, "", designer_label],
                ["", "", ""],
                ["", "", ""],
                ["_______________________", "", "_______________________"],
                ["Data: _______________", "", "Data: _______________"],
            ]
            firma_table = Table(firma_data, colWidths=[7*cm, 3*cm, 7*cm])
        else:
            firma_data = [
                [label_1],
                [""],
                [""],
                ["_______________________"],
                ["Data: _______________"],
            ]
            firma_table = Table(firma_data, colWidths=[17*cm])

        firma_table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#444444')),
            ('PADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(firma_table)
        story.append(Spacer(1, 0.5*cm))

        story.append(Paragraph(
            "Documento generato il {} dal sistema Pythonpro".format(
                datetime.now().strftime("%d/%m/%Y %H:%M")
            ),
            self.styles['TSSmall']
        ))

        doc.build(story)
        buffer.seek(0)
        return buffer
