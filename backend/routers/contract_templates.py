"""
Router per gestione template contratti e generazione PDF
Gestisce CRUD template e generazione contratti personalizzati
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import logging
import tempfile
import mammoth
from io import BytesIO
import html
import re
from xml.sax.saxutils import escape

import crud
import schemas
from database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/contracts", tags=["Contract Templates"])
PAGE_BREAK_MARKER = "__PAGE_BREAK__"


def _split_street_and_number(address: str | None) -> tuple[str, str]:
    if not address:
        return ("N/A", "N/A")

    cleaned = re.sub(r"\s+", " ", address).strip()
    match = re.match(r"^(.*?)(?:,\s*|\s+)(\d+[A-Za-z/-]*)$", cleaned)
    if match:
        return (match.group(1).strip() or "N/A", match.group(2).strip() or "N/A")
    return (cleaned, "N/A")


def _html_to_text_blocks(raw_html: str) -> list[str]:
    """Converte HTML importato da DOCX in blocchi testuali compatibili con ReportLab."""
    if not raw_html:
        return []

    # Supporta esplicitamente i salti pagina dichiarati nel template HTML.
    text = re.sub(
        (
            r'(?is)<[^>]*('
            r'style\s*=\s*"[^"]*page-break-before\s*:\s*always[^"]*"|'
            r"style\s*=\s*'[^']*page-break-before\s*:\s*always[^']*'|"
            r'class\s*=\s*"[^"]*page-break[^"]*"|'
            r"class\s*=\s*'[^']*page-break[^']*'|"
            r'data-page-break\s*=\s*"before"|'
            r"data-page-break\s*=\s*'before'"
            r')[^>]*>'
        ),
        f"\n{PAGE_BREAK_MARKER}\n",
        raw_html
    )
    text = re.sub(r'(?i)<br\s*/?>', '\n', text)
    text = re.sub(r'(?i)</(p|div|h1|h2|h3|h4|h5|h6|li|tr|table|ul|ol)>', '\n', text)
    text = re.sub(r'(?i)<li[^>]*>', '- ', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = html.unescape(text)
    text = text.replace('\r', '\n')
    text = re.sub(r'\n{3,}', '\n\n', text)

    blocks = []
    for block in text.split('\n'):
        cleaned = re.sub(r'\s+', ' ', block).strip()
        if cleaned:
            blocks.append(cleaned)
    return blocks


def _is_page_break_block(block: str) -> bool:
    return block == PAGE_BREAK_MARKER


def _should_page_break_before_block(contract_type: str | None, block: str) -> bool:
    """Forza una nuova pagina per sezioni specifiche del contratto occasionale."""
    if _is_page_break_block(block):
        return True

    if contract_type != "occasionale" or not block:
        return False

    normalized = re.sub(r"\s+", " ", block).strip().lower()
    return normalized in {
        "autocerticazione",
        "autocertificazione occasionale",
    }


def _render_contract_template_text(template_text: str, context: dict, legacy_context: dict) -> str:
    """Render compatibile con placeholder Jinja/HTML e con segnaposto legacy «VARIABILE»."""
    if not template_text:
        return ""

    rendered = template_text

    for key, value in context.items():
        value = "" if value is None else str(value)
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
        rendered = rendered.replace(f"{{{{ {key} }}}}", value)

    for key, value in legacy_context.items():
        value = "" if value is None else str(value)
        rendered = rendered.replace(f"«{key}»", value)

    return rendered


@router.post("/", response_model=schemas.ContractTemplate)
def create_contract_template(
    template: schemas.ContractTemplateCreate,
    db: Session = Depends(get_db)
):
    """
    CREA UN NUOVO TEMPLATE CONTRATTO

    Campi obbligatori:
    - nome_template
    - tipo_contratto (professionale, occasionale, ordine_servizio, contratto_progetto)
    - contenuto_html (HTML con variabili {{variabile}})

    Variabili disponibili per il template:
    - Collaboratore: {{collaboratore_nome}}, {{collaboratore_cognome}}, {{collaboratore_codice_fiscale}}, ecc.
    - Progetto: {{progetto_nome}}, {{progetto_descrizione}}, {{progetto_cup}}
    - Ente: {{ente_ragione_sociale}}, {{ente_piva}}, {{ente_indirizzo_completo}}, ecc.
    - Contratto: {{mansione}}, {{ore_previste}}, {{tariffa_oraria}}, {{compenso_totale}}, ecc.
    - Sistema: {{data_oggi}}, {{data_firma_contratto}}, {{contract_signed_date}}

    Se is_default=True, questo diventa il template di default per il tipo_contratto
    """
    try:
        db_template = crud.create_contract_template(db, template)
        logger.info(f"Template contratto creato: {db_template.nome_template} (ID: {db_template.id})")
        return db_template

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Errore creazione template contratto: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Errore nella creazione del template"
        )


@router.get("/", response_model=List[schemas.ContractTemplate])
def get_contract_templates(
    skip: int = 0,
    limit: int = 100,
    ambito_template: Optional[str] = None,
    chiave_documento: Optional[str] = None,
    ente_attuatore_id: Optional[int] = None,
    progetto_id: Optional[int] = None,
    ente_erogatore: Optional[str] = None,
    avviso: Optional[str] = None,
    tipo_contratto: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    RECUPERA LISTA TEMPLATE CONTRATTI

    Parametri query:
    - skip: Salta N record (paginazione)
    - limit: Massimo record da restituire
    - ambito_template: Filtra per famiglia documento
    - chiave_documento: Filtra per chiave documento
    - ente_attuatore_id: Filtra per ente applicabile
    - progetto_id: Filtra per progetto applicabile
    - ente_erogatore: Filtra per fondo/ente erogatore applicabile
    - avviso: Filtra per avviso applicabile
    - tipo_contratto: Filtra per tipo specifico
    - is_active: Filtra per stato attivo
    - search: Cerca nel nome o descrizione template
    """
    templates = crud.get_contract_templates(
        db,
        skip=skip,
        limit=limit,
        ambito_template=ambito_template,
        chiave_documento=chiave_documento,
        ente_attuatore_id=ente_attuatore_id,
        progetto_id=progetto_id,
        ente_erogatore=ente_erogatore,
        avviso=avviso,
        tipo_contratto=tipo_contratto,
        is_active=is_active,
        search=search
    )
    return templates


@router.get("/count")
def get_contract_templates_count(
    ambito_template: Optional[str] = None,
    chiave_documento: Optional[str] = None,
    ente_attuatore_id: Optional[int] = None,
    progetto_id: Optional[int] = None,
    ente_erogatore: Optional[str] = None,
    avviso: Optional[str] = None,
    tipo_contratto: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """CONTA IL NUMERO TOTALE DI TEMPLATE (per paginazione frontend)"""
    count = crud.get_contract_templates_count(
        db,
        ambito_template=ambito_template,
        chiave_documento=chiave_documento,
        ente_attuatore_id=ente_attuatore_id,
        progetto_id=progetto_id,
        ente_erogatore=ente_erogatore,
        avviso=avviso,
        tipo_contratto=tipo_contratto,
        is_active=is_active,
        search=search
    )
    return {"count": count}


@router.get("/{template_id}", response_model=schemas.ContractTemplate)
def get_contract_template(
    template_id: int,
    db: Session = Depends(get_db)
):
    """RECUPERA UN SINGOLO TEMPLATE CONTRATTO"""
    template = crud.get_contract_template(db, template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template contratto non trovato"
        )
    return template


@router.get("/{template_id}/variables")
def get_contract_template_variables(
    template_id: int,
    db: Session = Depends(get_db)
):
    """
    RECUPERA UN TEMPLATE CON LE VARIABILI DISPONIBILI

    Restituisce il template completo più un oggetto 'variabili_disponibili'
    che elenca tutte le variabili che possono essere usate nel template
    """
    template_with_vars = crud.get_template_with_variables(db, template_id)
    if not template_with_vars:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template contratto non trovato"
        )
    return template_with_vars


@router.put("/{template_id}", response_model=schemas.ContractTemplate)
def update_contract_template(
    template_id: int,
    template: schemas.ContractTemplateUpdate,
    db: Session = Depends(get_db)
):
    """
    AGGIORNA UN TEMPLATE CONTRATTO ESISTENTE

    Tutti i campi sono opzionali. Vengono aggiornati solo i campi forniti.

    Se is_default viene impostato a True, rimuove automaticamente
    il flag di default dagli altri template dello stesso tipo
    """
    try:
        updated_template = crud.update_contract_template(db, template_id, template)
        logger.info(f"Template contratto aggiornato: ID {template_id}")
        return updated_template

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Errore aggiornamento template {template_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Errore nell'aggiornamento del template"
        )


@router.delete("/{template_id}")
def delete_contract_template(
    template_id: int,
    soft_delete: bool = True,
    db: Session = Depends(get_db)
):
    """
    ELIMINA O DISATTIVA UN TEMPLATE CONTRATTO

    Parametri:
    - soft_delete=true (default): Disattiva il template (is_active=False) mantenendo lo storico
    - soft_delete=false: Eliminazione fisica definitiva

    Il soft delete è consigliato per mantenere traccia dei contratti già generati
    """
    try:
        deleted_template = crud.delete_contract_template(db, template_id, soft_delete=soft_delete)

        if soft_delete:
            return {
                "message": "Template disattivato con successo",
                "template_id": template_id,
                "soft_delete": True
            }
        else:
            return {
                "message": "Template eliminato con successo",
                "template_id": template_id,
                "soft_delete": False
            }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Errore eliminazione template {template_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Errore nell'eliminazione del template"
        )


@router.get("/by-type/{tipo_contratto}")
def get_default_template_by_type(
    tipo_contratto: str,
    db: Session = Depends(get_db)
):
    """
    RECUPERA IL TEMPLATE DI DEFAULT PER UN TIPO DI CONTRATTO

    Utile per ottenere il template da usare quando si genera un contratto
    senza specificare un template_id specifico
    """
    template = crud.get_contract_template_by_type(db, tipo_contratto, use_default=True)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Nessun template di default trovato per tipo: {tipo_contratto}"
        )
    return template


@router.post("/convert-docx-to-html")
async def convert_docx_to_html(
    file: UploadFile = File(...)
):
    """
    CONVERTE UN FILE DOCX IN HTML

    Endpoint per caricare un file DOCX e convertirlo automaticamente in HTML
    da usare come template contratto.

    Il file viene:
    1. Caricato e validato (deve essere .docx)
    2. Convertito in HTML usando mammoth
    3. Restituito come stringa HTML pulita

    Questo HTML può essere poi usato nel campo contenuto_html del template.
    """
    try:
        # Valida il tipo di file
        if not file.filename.lower().endswith('.docx'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Il file deve essere in formato .docx"
            )

        # Leggi il contenuto del file
        content = await file.read()

        # Converti DOCX in HTML usando mammoth
        result = mammoth.convert_to_html(BytesIO(content))
        html_content = result.value

        # Log eventuali messaggi/warning dalla conversione
        if result.messages:
            for message in result.messages:
                logger.warning(f"Mammoth conversion message: {message}")

        # Pulizia HTML: rimuovi stili inline eccessivi se necessario
        # (mammoth di default produce HTML abbastanza pulito)

        logger.info(f"File DOCX '{file.filename}' convertito in HTML con successo")

        return JSONResponse({
            "success": True,
            "html": html_content,
            "filename": file.filename,
            "messages": [str(m) for m in result.messages] if result.messages else []
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Errore conversione DOCX: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore nella conversione del file DOCX: {str(e)}"
        )


@router.post("/generate-contract")
async def generate_contract_from_template(
    request: schemas.ContractGenerationRequest,
    db: Session = Depends(get_db)
):
    """
    GENERA UN CONTRATTO PDF USANDO UN TEMPLATE PERSONALIZZATO

    Richiede:
    - collaboratore_id: ID del collaboratore
    - progetto_id: ID del progetto
    - ente_attuatore_id: ID dell'ente attuatore
    - mansione: Mansione/ruolo
    - ore_previste: Ore totali previste
    - tariffa_oraria: Tariffa oraria in euro
    - data_inizio: Data inizio contratto
    - data_fine: Data fine contratto
    - template_id (opzionale): ID del template da usare
    - tipo_contratto (opzionale): Se template_id non fornito, usa il default per questo tipo

    Il sistema:
    1. Recupera tutti i dati dalle tabelle (collaboratore, progetto, ente)
    2. Recupera il template (specificato o default)
    3. Sostituisce le variabili {{variabile}} con i dati reali
    4. Include il logo dell'ente se presente e configurato nel template
    5. Genera e restituisce il PDF del contratto
    """
    return _generate_contract_pdf_response(request, db)


def _generate_contract_pdf_response(
    request: schemas.ContractGenerationRequest,
    db: Session
):
    """Motore condiviso per generazione PDF template-based, riusabile dal route legacy."""
    try:
        collaboratore = crud.get_collaborator(db, request.collaboratore_id)
        if not collaboratore:
            raise HTTPException(status_code=404, detail="Collaboratore non trovato")

        progetto = crud.get_project(db, request.progetto_id)
        if not progetto:
            raise HTTPException(status_code=404, detail="Progetto non trovato")

        ente = crud.get_implementing_entity(db, request.ente_attuatore_id)
        if not ente:
            raise HTTPException(status_code=404, detail="Ente attuatore non trovato")

        if request.template_id:
            template = crud.get_contract_template(db, request.template_id)
            if not template or not template.is_active:
                raise HTTPException(status_code=404, detail="Template non trovato o non attivo")
        elif request.tipo_contratto:
            template = crud.get_contract_template_by_type(db, request.tipo_contratto, use_default=True)
            if not template:
                raise HTTPException(
                    status_code=404,
                    detail=f"Nessun template di default per tipo: {request.tipo_contratto}"
                )
        else:
            raise HTTPException(
                status_code=400,
                detail="Specificare template_id o tipo_contratto"
            )

        from jinja2 import Template as JinjaTemplate

        compenso_totale = request.ore_previste * request.tariffa_oraria

        ente_sede_via, ente_sede_numero_civico = _split_street_and_number(ente.indirizzo)
        progetto_sede_completa = ", ".join(
            part for part in [
                progetto.sede_aziendale_via or "",
                progetto.sede_aziendale_numero_civico or "",
                progetto.sede_aziendale_comune or ""
            ] if part
        ) or "N/A"

        context = {
            'collaboratore_nome': collaboratore.first_name,
            'collaboratore_cognome': collaboratore.last_name,
            'collaboratore_nome_completo': f"{collaboratore.first_name} {collaboratore.last_name}",
            'collaboratore_codice_fiscale': collaboratore.fiscal_code or 'N/A',
            'collaboratore_luogo_nascita': collaboratore.birthplace or 'N/A',
            'collaboratore_data_nascita': collaboratore.birth_date.strftime(template.formato_data) if collaboratore.birth_date else 'N/A',
            'collaboratore_indirizzo': collaboratore.address or 'N/A',
            'collaboratore_citta': collaboratore.city or 'N/A',
            'collaboratore_titolo_studio': collaboratore.education or 'N/A',
            'progetto_nome': progetto.name,
            'progetto_descrizione': progetto.description or '',
            'progetto_cup': progetto.cup or 'N/A',
            'progetto_atto_approvazione': progetto.atto_approvazione or 'N/A',
            'progetto_data_inizio': progetto.start_date.strftime(template.formato_data) if progetto.start_date else 'N/A',
            'progetto_data_fine': progetto.end_date.strftime(template.formato_data) if progetto.end_date else 'N/A',
            'progetto_sede_aziendale_comune': progetto.sede_aziendale_comune or 'N/A',
            'progetto_sede_aziendale_via': progetto.sede_aziendale_via or 'N/A',
            'progetto_sede_aziendale_numero_civico': progetto.sede_aziendale_numero_civico or 'N/A',
            'progetto_sede_aziendale_completa': progetto_sede_completa,
            'ente_ragione_sociale': ente.ragione_sociale,
            'ente_forma_giuridica': ente.forma_giuridica or 'N/A',
            'ente_piva': ente.partita_iva,
            'ente_codice_fiscale': ente.codice_fiscale or 'N/A',
            'ente_indirizzo_completo': ente.indirizzo_completo or 'N/A',
            'ente_sede_comune': ente.citta or 'N/A',
            'ente_sede_via': ente_sede_via,
            'ente_sede_numero_civico': ente_sede_numero_civico,
            'ente_legale_rappresentante_nome': ente.legale_rappresentante_nome or 'N/A',
            'ente_legale_rappresentante_cognome': ente.legale_rappresentante_cognome or 'N/A',
            'ente_legale_rappresentante_nome_completo': ente.legale_rappresentante_nome_completo or 'N/A',
            'ente_legale_rappresentante_luogo_nascita': ente.legale_rappresentante_luogo_nascita or 'N/A',
            'ente_legale_rappresentante_data_nascita': ente.legale_rappresentante_data_nascita.strftime(template.formato_data) if ente.legale_rappresentante_data_nascita else 'N/A',
            'ente_legale_rappresentante_comune_residenza': ente.legale_rappresentante_comune_residenza or 'N/A',
            'ente_legale_rappresentante_via_residenza': ente.legale_rappresentante_via_residenza or 'N/A',
            'ente_legale_rappresentante_codice_fiscale': ente.legale_rappresentante_codice_fiscale or 'N/A',
            'ente_referente': ente.legale_rappresentante_nome_completo or ente.referente_nome_completo or 'N/A',
            'ente_pec': ente.pec or 'N/A',
            'ente_email': ente.email or 'N/A',
            'ente_telefono': ente.telefono or 'N/A',
            'mansione': request.mansione,
            'ore_previste': str(request.ore_previste),
            'tariffa_oraria': template.formato_importo.format(request.tariffa_oraria),
            'compenso_totale': template.formato_importo.format(compenso_totale),
            'data_inizio': request.data_inizio.strftime(template.formato_data),
            'data_fine': request.data_fine.strftime(template.formato_data),
            'data_firma_contratto': request.contract_signed_date.strftime(template.formato_data) if request.contract_signed_date else 'N/A',
            'data_sottoscrizione_contratto': request.contract_signed_date.strftime(template.formato_data) if request.contract_signed_date else 'N/A',
            'contract_signed_date': request.contract_signed_date.strftime(template.formato_data) if request.contract_signed_date else 'N/A',
            'data_oggi': datetime.now().strftime(template.formato_data)
        }

        collaborator_address = ", ".join(
            part for part in [collaboratore.address or "", collaboratore.city or ""] if part
        ) or "N/A"

        legacy_context = {
            'NOME': collaboratore.first_name,
            'COGNOME': collaboratore.last_name,
            'LUOGO_NASCITA': collaboratore.birthplace or 'N/A',
            'DATA_NASCITA': context['collaboratore_data_nascita'],
            'RESIDENZA': collaborator_address,
            'CODICE_FISCALE': collaboratore.fiscal_code or 'N/A',
            'Titolo_di_studio': collaboratore.education or 'N/A',
            'TITOLO_DI_STUDIO': collaboratore.education or 'N/A',
            'ATTIVITA': request.mansione,
            'MATERIA_INSEGNAMENTO': request.mansione,
            'ORE': str(request.ore_previste),
            'COSTO_UNITARIO': f"{request.tariffa_oraria:.2f}",
            'COSTO_TOTALE': f"{compenso_totale:.2f}",
            'PERIODO_DAL': context['data_inizio'],
            'PERIODO_AL': context['data_fine'],
            'SEDE_AZIENDALE': ente.indirizzo_completo or 'N/A',
            'CODICE_PROGETTO': progetto.cup or progetto.name,
            'RUOLO_PROGETTUALE': request.mansione,
            'ATTO_DI_APPROVAZIONE': progetto.atto_approvazione or 'N/A',
            'ENTE_ATTUATORE': ente.ragione_sociale,
            'LEGALE_RAPPRESENTANTE': ente.legale_rappresentante_nome_completo or ente.referente_nome_completo or 'N/A'
        }

        jinja_template = JinjaTemplate(template.contenuto_html)
        contenuto_compilato = _render_contract_template_text(
            jinja_template.render(**context),
            context,
            legacy_context
        )

        intestazione_compilata = None
        if template.intestazione:
            jinja_header = JinjaTemplate(template.intestazione)
            intestazione_compilata = _render_contract_template_text(
                jinja_header.render(**context),
                context,
                legacy_context
            )

        pie_pagina_compilato = None
        if template.pie_pagina:
            jinja_footer = JinjaTemplate(template.pie_pagina)
            pie_pagina_compilato = _render_contract_template_text(
                jinja_footer.render(**context),
                context,
                legacy_context
            )

        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib.utils import ImageReader
        from io import BytesIO

        header_logo_path = None
        header_logo_width = None
        header_logo_height = None
        if template.include_logo_ente and template.posizione_logo == "header" and ente.logo_path:
            try:
                from file_upload import get_file_path
                header_logo_path = get_file_path(ente.logo_path)

                image_reader = ImageReader(header_logo_path)
                image_width_px, image_height_px = image_reader.getSize()
                aspect_ratio = (image_width_px / image_height_px) if image_height_px else 1

                if aspect_ratio > 2.5:
                    header_logo_width = 8 * cm
                else:
                    header_logo_width = {'small': 3*cm, 'medium': 5*cm, 'large': 7*cm}[template.dimensione_logo]

                header_logo_height = (
                    header_logo_width / aspect_ratio if aspect_ratio else header_logo_width * 0.6
                )
            except Exception as e:
                logger.warning(f"Errore caricamento logo header: {e}")
                header_logo_path = None
                header_logo_width = None
                header_logo_height = None

        top_margin = max(2 * cm, (header_logo_height or 0) + 1.6 * cm)
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=top_margin,
            bottomMargin=2*cm
        )
        story = []
        styles = getSampleStyleSheet()
        body_style = ParagraphStyle(
            'RenderedContractBody',
            parent=styles['BodyText'],
            leading=14,
            spaceAfter=8
        )

        def draw_header_logo(canvas, doc_obj):
            if not header_logo_path or not header_logo_width or not header_logo_height:
                return

            page_height = doc_obj.pagesize[1]
            y_position = page_height - header_logo_height - 0.8 * cm
            canvas.drawImage(
                header_logo_path,
                doc_obj.leftMargin,
                y_position,
                width=header_logo_width,
                height=header_logo_height,
                preserveAspectRatio=True,
                mask='auto'
            )

        if intestazione_compilata:
            for block in _html_to_text_blocks(intestazione_compilata):
                story.append(Paragraph(escape(block), body_style))
            story.append(Spacer(1, 0.5*cm))

        for block in _html_to_text_blocks(contenuto_compilato):
            if story and _should_page_break_before_block(template.tipo_contratto, block):
                story.append(PageBreak())
                if _is_page_break_block(block):
                    continue
            if _is_page_break_block(block):
                continue
            story.append(Paragraph(escape(block), body_style))
        story.append(Spacer(1, 1*cm))

        if pie_pagina_compilato:
            for block in _html_to_text_blocks(pie_pagina_compilato):
                story.append(Paragraph(escape(block), body_style))

        if template.include_logo_ente and template.posizione_logo == "footer" and ente.logo_path:
            try:
                from file_upload import get_file_path
                logo_path = get_file_path(ente.logo_path)
                image_reader = ImageReader(logo_path)
                image_width_px, image_height_px = image_reader.getSize()
                aspect_ratio = (image_width_px / image_height_px) if image_height_px else 1
                logo_width = {'small': 2*cm, 'medium': 3*cm, 'large': 4*cm}[template.dimensione_logo]
                logo_height = logo_width / aspect_ratio if aspect_ratio else logo_width * 0.6

                story.append(Spacer(1, 0.5*cm))
                img = Image(logo_path, width=logo_width, height=logo_height)
                story.append(img)
            except Exception as e:
                logger.warning(f"Errore caricamento logo footer: {e}")

        doc.build(story, onFirstPage=draw_header_logo, onLaterPages=draw_header_logo)
        buffer.seek(0)

        crud.increment_template_usage(db, template.id)

        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            tmp.write(buffer.read())
            tmp_path = tmp.name

        filename = f"contratto_{collaboratore.last_name}_{ente.ragione_sociale}_{datetime.now().strftime('%Y%m%d')}.pdf"

        logger.info(f"Contratto generato per collaboratore {collaboratore.id} con template {template.id}")

        return FileResponse(
            tmp_path,
            media_type='application/pdf',
            filename=filename,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Errore generazione contratto: {e}")
        raise HTTPException(status_code=500, detail=f"Errore nella generazione del contratto: {str(e)}")
