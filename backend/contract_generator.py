"""
Modulo per la generazione di contratti PDF compilati automaticamente

Include protezione contro nomi file riservati Windows (nul, con, prn, aux, etc.)
per compatibilità con OneDrive.
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, Any
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
        self.output_dir = Path(__file__).parent / "contracts_output"
        self.output_dir.mkdir(exist_ok=True)

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

    def generate_contract(self, assignment_data: Dict[str, Any], contract_type: str = None) -> BytesIO:
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
        story.append(Paragraph(
            f"<b>Il Committente:</b> [RAGIONE SOCIALE COMMITTENTE]<br/>"
            f"con sede in [INDIRIZZO COMMITTENTE]<br/>"
            f"P.IVA: [P.IVA COMMITTENTE]<br/>"
            f"rappresentata da [NOME RAPPRESENTANTE]",
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
            'collaborator_name': f"{collaborator.get('first_name', '')} {collaborator.get('last_name', '')}",
            'collaborator_email': collaborator.get('email', ''),
            'collaborator_fiscal_code': collaborator.get('fiscal_code', 'N/A'),
            'collaborator_birthplace': collaborator.get('birthplace', 'N/A'),
            'collaborator_birthdate': birthdate or 'N/A',
            'collaborator_address': f"{collaborator.get('address', 'N/A')}, {collaborator.get('city', '')}",
            'project_name': assignment_data.get('project', {}).get('name', 'N/A'),
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
