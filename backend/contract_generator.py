"""
Modulo per la generazione di contratti PDF compilati automaticamente

Include protezione contro nomi file riservati Windows (nul, con, prn, aux, etc.)
per compatibilità con OneDrive.
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, Any
import tempfile
from jinja2 import Environment, FileSystemLoader
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from io import BytesIO

# Importa validatore per nomi riservati Windows
from windows_filename_validator import (
    sanitize_filename,
    is_valid_filename,
    generate_safe_filename
)


class ContractGenerator:
    """Generatore di contratti PDF"""

    def __init__(self):
        self.template_dir = Path(__file__).parent / "contract_templates"
        self.output_dir = Path(tempfile.gettempdir()) / "pythonpro_contracts_output"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Setup Jinja2
        self.jinja_env = Environment(loader=FileSystemLoader(str(self.template_dir)))

        # Setup ReportLab styles
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Configura stili custom per i documenti"""
        # Stile titolo
        self.styles.add(ParagraphStyle(
            name='ContractTitle',
            parent=self.styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))

        # Stile testo contratto
        self.styles.add(ParagraphStyle(
            name='ContractBody',
            parent=self.styles['BodyText'],
            fontSize=11,
            textColor=colors.HexColor('#333333'),
            alignment=TA_JUSTIFY,
            spaceAfter=12,
            leading=14
        ))

        # Stile intestazione
        self.styles.add(ParagraphStyle(
            name='ContractHeader',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#666666'),
            spaceAfter=20
        ))

    def generate_contract(
        self,
        assignment_data: Dict[str, Any],
        contract_type: str = None,
        ente_print_config=None,
    ) -> BytesIO:
        """
        Genera un contratto PDF compilato con i dati dell'assignment

        Args:
            assignment_data: Dizionario con tutti i dati dell'assignment
            contract_type: Tipo di contratto (se non specificato, usa quello dell'assignment)

        Returns:
            BytesIO contenente il PDF generato
        """
        # Determina il tipo di contratto
        if not contract_type:
            contract_type = assignment_data.get('contract_type', 'professionale')

        # Prepara i dati per il template
        context = self._prepare_context(assignment_data)

        # Genera il PDF
        buffer = BytesIO()
        printing_enabled = bool(
            ente_print_config
            and getattr(ente_print_config, "print_config_enabled", False)
        )
        decoration = None
        if printing_enabled:
            from services.entity_printing import page_decoration

            decoration = page_decoration(ente_print_config)
            doc = SimpleDocTemplate(buffer, pagesize=A4, **decoration.margins)
        else:
            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                rightMargin=2*cm,
                leftMargin=2*cm,
                topMargin=2*cm,
                bottomMargin=2*cm
            )

        # Costruisci il contenuto
        story = []

        # Intestazione
        story.append(Paragraph("CONTRATTO DI COLLABORAZIONE", self.styles['ContractTitle']))
        story.append(Spacer(1, 0.5*cm))

        # Tipo di contratto
        contract_type_label = self._get_contract_type_label(contract_type)
        story.append(Paragraph(f"<b>Tipologia:</b> {contract_type_label}", self.styles['ContractHeader']))
        story.append(Spacer(1, 0.5*cm))

        # Parti contraenti
        story.append(Paragraph("<b>TRA</b>", self.styles['ContractBody']))
        story.append(Spacer(1, 0.3*cm))

        # Committente (da configurare)
        ente_nome = assignment_data.get('ente_attuatore') or '[RAGIONE SOCIALE COMMITTENTE]'
        ente_piva = assignment_data.get('ente_attuatore_piva') or '[P.IVA COMMITTENTE]'
        ente_indirizzo = assignment_data.get('ente_attuatore_indirizzo') or '[INDIRIZZO COMMITTENTE]'
        story.append(Paragraph(
            f"<b>Il Committente:</b> {ente_nome}<br/>"
            f"con sede in {ente_indirizzo}<br/>"
            f"P.IVA: {ente_piva}",
            self.styles['ContractBody']
        ))
        story.append(Spacer(1, 0.5*cm))

        story.append(Paragraph("<b>E</b>", self.styles['ContractBody']))
        story.append(Spacer(1, 0.3*cm))

        # Collaboratore
        collaborator_text = (
            f"<b>Il Collaboratore:</b> {context['collaborator_name']}<br/>"
            f"nato/a a {context['collaborator_birthplace']} il {context['collaborator_birthdate']}<br/>"
            f"residente in {context['collaborator_address']}<br/>"
            f"C.F.: {context['collaborator_fiscal_code']}"
        )
        story.append(Paragraph(collaborator_text, self.styles['ContractBody']))
        story.append(Spacer(1, 0.8*cm))

        # Oggetto del contratto
        story.append(Paragraph("<b>PREMESSO CHE</b>", self.styles['ContractBody']))
        story.append(Spacer(1, 0.3*cm))

        premises_text = (
            f"- Il Committente necessita di una collaborazione per il progetto denominato "
            f"<b>'{context['project_name']}'</b>;<br/>"
            f"- Il Collaboratore possiede le competenze necessarie per svolgere l'attività di "
            f"<b>{context['role']}</b>;<br/>"
            f"- Le parti intendono regolare la loro collaborazione secondo i termini di seguito indicati."
        )
        story.append(Paragraph(premises_text, self.styles['ContractBody']))
        story.append(Spacer(1, 0.8*cm))

        # Clausole principali
        story.append(Paragraph("<b>SI CONVIENE E SI STIPULA QUANTO SEGUE</b>", self.styles['ContractBody']))
        story.append(Spacer(1, 0.5*cm))

        # Articolo 1 - Oggetto
        story.append(Paragraph("<b>Art. 1 - Oggetto della collaborazione</b>", self.styles['ContractBody']))
        art1_text = (
            f"Il Collaboratore si impegna a svolgere l'attività di <b>{context['role']}</b> "
            f"per il progetto '<b>{context['project_name']}</b>' come da specifiche concordate."
        )
        story.append(Paragraph(art1_text, self.styles['ContractBody']))
        story.append(Spacer(1, 0.5*cm))

        if assignment_data.get('voce_piano_mansione') or assignment_data.get('materia_docenza'):
            story.append(Paragraph("<b>Informazioni piano finanziario</b>", self.styles['ContractBody']))
            finance_lines = []
            if assignment_data.get('voce_piano_mansione'):
                finance_lines.append(f"Voce Piano / Mansione: <b>{assignment_data.get('voce_piano_mansione')}</b>")
            if assignment_data.get('materia_docenza'):
                finance_lines.append(f"Materia della docenza: <b>{assignment_data.get('materia_docenza')}</b>")
            if assignment_data.get('modalita_erogazione'):
                finance_lines.append(f"Modalità erogazione: <b>{assignment_data.get('modalita_erogazione')}</b>")
            if assignment_data.get('ore_previste_modulo'):
                finance_lines.append(f"Ore previste: <b>{assignment_data.get('ore_previste_modulo')}h</b>")
            if assignment_data.get('progetto_fapi_modulo'):
                finance_lines.append(f"Progetto FAPI: <b>{assignment_data.get('progetto_fapi_modulo')}</b>")
            story.append(Paragraph("<br/>".join(finance_lines), self.styles['ContractBody']))
            story.append(Spacer(1, 0.5*cm))

        # Articolo 2 - Durata
        story.append(Paragraph("<b>Art. 2 - Durata</b>", self.styles['ContractBody']))
        art2_text = (
            f"La presente collaborazione avrà durata dal <b>{context['start_date']}</b> "
            f"al <b>{context['end_date']}</b>, per un totale di <b>{context['assigned_hours']} ore</b>."
        )
        story.append(Paragraph(art2_text, self.styles['ContractBody']))
        story.append(Spacer(1, 0.5*cm))

        # Articolo 3 - Compenso
        story.append(Paragraph("<b>Art. 3 - Compenso</b>", self.styles['ContractBody']))
        art3_text = (
            f"Per l'attività svolta, il Collaboratore riceverà un compenso di:<br/>"
            f"- Tariffa oraria: <b>€ {context['hourly_rate']}/ora</b><br/>"
            f"- Ore totali: <b>{context['assigned_hours']} ore</b><br/>"
            f"- <b>Compenso totale: € {context['total_amount']}</b> (escluse ritenute e oneri di legge)"
        )
        story.append(Paragraph(art3_text, self.styles['ContractBody']))
        story.append(Spacer(1, 0.5*cm))

        # Articolo 4 - Modalità di esecuzione
        story.append(Paragraph("<b>Art. 4 - Modalità di esecuzione</b>", self.styles['ContractBody']))
        story.append(Paragraph(
            "Il Collaboratore svolgerà la propria attività in piena autonomia, senza vincolo di subordinazione, "
            "utilizzando i propri mezzi e strumenti di lavoro, salvo quanto diversamente concordato.",
            self.styles['ContractBody']
        ))
        story.append(Spacer(1, 0.8*cm))

        # Firme
        firma_data = [
            ['Data: ____________________', ''],
            ['', ''],
            ['Il Committente', 'Il Collaboratore'],
            ['', ''],
            ['_____________________', '_____________________']
        ]

        firma_table = Table(firma_data, colWidths=[8*cm, 8*cm])
        firma_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 2), (-1, 2), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
        ]))
        story.append(firma_table)

        # Genera il PDF
        if decoration:
            doc.build(
                story,
                onFirstPage=decoration.on_first_page,
                onLaterPages=decoration.on_later_pages,
            )
        else:
            doc.build(story)
        buffer.seek(0)

        return buffer

    def _prepare_context(self, assignment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepara i dati per il template"""
        # Formatta le date
        start_date = assignment_data.get('start_date', '')
        end_date = assignment_data.get('end_date', '')

        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        if isinstance(end_date, str):
            end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))

        # Calcola il totale
        total_amount = assignment_data.get('assigned_hours', 0) * assignment_data.get('hourly_rate', 0)

        # Dati collaboratore
        collaborator = assignment_data.get('collaborator', {})
        birthdate = collaborator.get('birth_date', '')
        if birthdate and isinstance(birthdate, str):
            birthdate = datetime.fromisoformat(birthdate.replace('Z', '+00:00')).strftime('%d/%m/%Y')

        return {
            'collaborator_name': assignment_data.get('collaborator_name') or f"{collaborator.get('last_name', '')} {collaborator.get('first_name', '')}".strip(),
            'collaborator_email': collaborator.get('email', ''),
            'collaborator_fiscal_code': assignment_data.get('collaborator_fiscal_code') or collaborator.get('fiscal_code', 'N/A'),
            'collaborator_birthplace': collaborator.get('birthplace', 'N/A'),
            'collaborator_birthdate': birthdate or 'N/A',
            'collaborator_address': assignment_data.get('collaborator_address') or f"{collaborator.get('address', 'N/A')}, {collaborator.get('city', '')}",
            'project_name': assignment_data.get('project_name') or assignment_data.get('project', {}).get('name', 'N/A'),
            'project_description': assignment_data.get('project', {}).get('description', ''),
            'role': assignment_data.get('role', 'N/A'),
            'assigned_hours': assignment_data.get('assigned_hours', 0),
            'hourly_rate': f"{assignment_data.get('hourly_rate', 0):.2f}",
            'total_amount': f"{total_amount:.2f}",
            'start_date': start_date.strftime('%d/%m/%Y') if start_date else 'N/A',
            'end_date': end_date.strftime('%d/%m/%Y') if end_date else 'N/A',
            'contract_type': assignment_data.get('contract_type', 'professionale'),
            'today': datetime.now().strftime('%d/%m/%Y')
        }

    def _get_contract_type_label(self, contract_type: str) -> str:
        """Restituisce l'etichetta del tipo di contratto"""
        labels = {
            'professionale': 'Contratto di Collaborazione Professionale',
            'occasionale': 'Contratto di Prestazione Occasionale',
            'ordine_servizio': 'Ordine di Servizio',
            'contratto_progetto': 'Contratto a Progetto'
        }
        return labels.get(contract_type, 'Contratto di Collaborazione')


    def generate_from_template(
        self,
        template_html: str,
        context: dict,
        ente_logo_path: str = None,
        ente_print_config=None,
    ):
        """
        Genera PDF da template HTML con placeholder Jinja2.
        Usa ReportLab per la conversione HTML -> PDF.
        """
        from jinja2 import Environment, BaseLoader
        from reportlab.platypus import Paragraph, Spacer, SimpleDocTemplate, Image
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        import re

        env = Environment(loader=BaseLoader(), variable_start_string="{{", variable_end_string="}}")
        try:
            tmpl = env.from_string(template_html)
            html_compiled = tmpl.render(**context)
        except Exception as exc:
            html_compiled = template_html
            import logging
            logging.getLogger(__name__).warning("Errore Jinja2 template: %s", exc)

        html_work = html_compiled

        for tag in ["</p>", "</div>", "</h1>", "</h2>", "</h3>", "<br>", "<br/>", "<br />"]:
            html_work = html_work.replace(tag, "\n")
        for tag in ["</li>", "</tr>"]:
            html_work = html_work.replace(tag, "\n")
        for tag in ["</th>", "</td>"]:
            html_work = html_work.replace(tag, " ")

        text_clean = re.sub(r"<[^>]+>", "", html_work)

        import html as html_module
        text_clean = html_module.unescape(text_clean)

        text_clean = re.sub(r"[ \t]+", " ", text_clean)
        text_clean = re.sub(r"\n[ \t]+", "\n", text_clean)
        text_clean = re.sub(r"\n{3,}", "\n\n", text_clean)
        text_clean = text_clean.strip()

        paragraphs_raw = text_clean.split("\n")

        buffer = BytesIO()
        printing_enabled = bool(
            ente_print_config
            and getattr(ente_print_config, "print_config_enabled", False)
        )
        decoration = None
        if printing_enabled:
            from services.entity_printing import page_decoration

            decoration = page_decoration(ente_print_config)
            doc = SimpleDocTemplate(buffer, pagesize=A4, **decoration.margins)
        else:
            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                rightMargin=2*cm,
                leftMargin=2*cm,
                topMargin=2*cm,
                bottomMargin=2*cm,
            )

        story = []

        if ente_logo_path and not printing_enabled:
            import os
            full_logo = os.path.join("/app/uploads", ente_logo_path) if not ente_logo_path.startswith("/") else ente_logo_path
            if os.path.exists(full_logo):
                try:
                    logo = Image(full_logo, width=4*cm, height=2*cm, kind="proportional")
                    logo.hAlign = "LEFT"
                    story.append(logo)
                    story.append(Spacer(1, 0.4*cm))
                except Exception:
                    pass

        body_style = ParagraphStyle(
            "TemplateBody",
            parent=self.styles["BodyText"],
            fontSize=10,
            leading=14,
            spaceAfter=8,
        )

        for para in paragraphs_raw:
            para = para.strip()
            if not para:
                continue
            story.append(Paragraph(para, body_style))

        story.append(Spacer(1, 1*cm))

        firma_data = [
            ["Il Committente", "", "Il/La Collaboratore/trice"],
            ["", "", ""],
            ["", "", ""],
            ["_______________________", "", "_______________________"],
            ["Data: _______________", "", "Data: _______________"],
        ]
        from reportlab.platypus import Table, TableStyle
        firma_table = Table(firma_data, colWidths=[7*cm, 3*cm, 7*cm])
        firma_table.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("PADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(firma_table)

        if decoration:
            doc.build(
                story,
                onFirstPage=decoration.on_first_page,
                onLaterPages=decoration.on_later_pages,
            )
        else:
            doc.build(story)
        buffer.seek(0)
        return buffer

    def save_contract(self, assignment_data: Dict[str, Any], filename: str = None) -> Path:
        """
        Genera e salva un contratto su file.

        Protegge automaticamente contro nomi file riservati Windows
        (nul, con, prn, aux, com1-9, lpt1-9) e nomi problematici (null, None, undefined).

        Args:
            assignment_data: Dati dell'assignment
            filename: Nome del file (opzionale, viene generato automaticamente se non fornito)

        Returns:
            Path al file salvato

        Raises:
            ValueError: Se il filename fornito è invalido e non può essere sanitizzato
        """
        if not filename:
            # Ottieni dati collaboratore e progetto
            collaborator_last_name = assignment_data.get('collaborator', {}).get('last_name', '')
            project_name_raw = assignment_data.get('project', {}).get('name', '')

            # Sanitizza i nomi usando il validatore Windows
            # Questo previene nomi riservati Windows E nomi problematici come "null"
            collaborator_name = sanitize_filename(
                collaborator_last_name if collaborator_last_name else 'collaboratore',
                default='collaboratore'
            )
            # Rimuovi estensione se presente
            collaborator_name = Path(collaborator_name).stem

            project_name = sanitize_filename(
                project_name_raw if project_name_raw else 'progetto',
                default='progetto'
            )
            # Rimuovi estensione se presente
            project_name = Path(project_name).stem

            # Genera filename sicuro con timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"contratto_{collaborator_name}_{project_name}_{timestamp}.pdf"

        # Sanitizza il filename finale per sicurezza
        # Questo assicura che anche filename forniti dall'esterno siano sicuri
        filename = sanitize_filename(filename, default="contratto.pdf")

        # Assicurati che abbia estensione .pdf
        if not filename.endswith('.pdf'):
            filename = f"{Path(filename).stem}.pdf"

        # Verifica finale che il nome sia valido
        if not is_valid_filename(filename):
            # Se ancora invalido, genera un nome sicuro automaticamente
            filename = generate_safe_filename("contratto", "pdf", add_uuid=True)

        # Genera il PDF
        buffer = self.generate_contract(assignment_data)

        # Salva su file
        output_path = self.output_dir / filename
        with open(output_path, 'wb') as f:
            f.write(buffer.read())

        return output_path
