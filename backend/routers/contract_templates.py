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

import crud
import schemas
from database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/contracts", tags=["Contract Templates"])


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
    - Sistema: {{data_oggi}}

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
    - tipo_contratto: Filtra per tipo specifico
    - is_active: Filtra per stato attivo
    - search: Cerca nel nome o descrizione template
    """
    templates = crud.get_contract_templates(
        db,
        skip=skip,
        limit=limit,
        tipo_contratto=tipo_contratto,
        is_active=is_active,
        search=search
    )
    return templates


@router.get("/count")
def get_contract_templates_count(
    tipo_contratto: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """CONTA IL NUMERO TOTALE DI TEMPLATE (per paginazione frontend)"""
    count = crud.get_contract_templates_count(
        db,
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
    try:
        # Recupera i dati
        collaboratore = crud.get_collaborator(db, request.collaboratore_id)
        if not collaboratore:
            raise HTTPException(status_code=404, detail="Collaboratore non trovato")

        progetto = crud.get_project(db, request.progetto_id)
        if not progetto:
            raise HTTPException(status_code=404, detail="Progetto non trovato")

        ente = crud.get_implementing_entity(db, request.ente_attuatore_id)
        if not ente:
            raise HTTPException(status_code=404, detail="Ente attuatore non trovato")

        # Recupera il template
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

        # Prepara i dati per le sostituzioni
        from jinja2 import Template as JinjaTemplate

        compenso_totale = request.ore_previste * request.tariffa_oraria

        context = {
            # Collaboratore
            'collaboratore_nome': collaboratore.first_name,
            'collaboratore_cognome': collaboratore.last_name,
            'collaboratore_nome_completo': f"{collaboratore.first_name} {collaboratore.last_name}",
            'collaboratore_codice_fiscale': collaboratore.fiscal_code,
            'collaboratore_luogo_nascita': collaboratore.birthplace or 'N/A',
            'collaboratore_data_nascita': collaboratore.birth_date.strftime(template.formato_data) if collaboratore.birth_date else 'N/A',
            'collaboratore_indirizzo': collaboratore.address or 'N/A',
            'collaboratore_citta': collaboratore.city or 'N/A',
            # Progetto
            'progetto_nome': progetto.name,
            'progetto_descrizione': progetto.description or '',
            'progetto_cup': progetto.cup or 'N/A',
            # Ente
            'ente_ragione_sociale': ente.ragione_sociale,
            'ente_piva': ente.partita_iva,
            'ente_indirizzo_completo': ente.indirizzo_completo,
            'ente_referente': ente.referente_nome_completo,
            'ente_pec': ente.pec or 'N/A',
            'ente_telefono': ente.telefono or 'N/A',
            # Contratto
            'mansione': request.mansione,
            'ore_previste': str(request.ore_previste),
            'tariffa_oraria': template.formato_importo.format(request.tariffa_oraria),
            'compenso_totale': template.formato_importo.format(compenso_totale),
            'data_inizio': request.data_inizio.strftime(template.formato_data),
            'data_fine': request.data_fine.strftime(template.formato_data),
            # Sistema
            'data_oggi': datetime.now().strftime(template.formato_data)
        }

        # Sostituisci le variabili nel contenuto HTML
        jinja_template = JinjaTemplate(template.contenuto_html)
        contenuto_compilato = jinja_template.render(**context)

        # Se ci sono intestazione o piè di pagina, compilali
        intestazione_compilata = None
        if template.intestazione:
            jinja_header = JinjaTemplate(template.intestazione)
            intestazione_compilata = jinja_header.render(**context)

        pie_pagina_compilato = None
        if template.pie_pagina:
            jinja_footer = JinjaTemplate(template.pie_pagina)
            pie_pagina_compilato = jinja_footer.render(**context)

        # Genera il PDF con ReportLab
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import cm
        from io import BytesIO

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
        story = []
        styles = getSampleStyleSheet()

        # Aggiungi logo se configurato e presente
        if template.include_logo_ente and template.posizione_logo == "header" and ente.logo_path:
            try:
                from file_upload import get_file_path
                logo_path = get_file_path(ente.logo_path)

                # Dimensioni logo
                logo_width = {'small': 3*cm, 'medium': 5*cm, 'large': 7*cm}[template.dimensione_logo]
                logo_height = logo_width * 0.6

                img = Image(logo_path, width=logo_width, height=logo_height)
                story.append(img)
                story.append(Spacer(1, 0.5*cm))
            except Exception as e:
                logger.warning(f"Errore caricamento logo: {e}")

        # Aggiungi intestazione se presente
        if intestazione_compilata:
            story.append(Paragraph(intestazione_compilata, styles['Normal']))
            story.append(Spacer(1, 0.5*cm))

        # Aggiungi contenuto principale
        story.append(Paragraph(contenuto_compilato, styles['BodyText']))
        story.append(Spacer(1, 1*cm))

        # Aggiungi piè di pagina se presente
        if pie_pagina_compilato:
            story.append(Paragraph(pie_pagina_compilato, styles['Normal']))

        # Logo nel footer se configurato
        if template.include_logo_ente and template.posizione_logo == "footer" and ente.logo_path:
            try:
                from file_upload import get_file_path
                logo_path = get_file_path(ente.logo_path)
                logo_width = {'small': 2*cm, 'medium': 3*cm, 'large': 4*cm}[template.dimensione_logo]
                logo_height = logo_width * 0.6

                story.append(Spacer(1, 0.5*cm))
                img = Image(logo_path, width=logo_width, height=logo_height)
                story.append(img)
            except Exception as e:
                logger.warning(f"Errore caricamento logo footer: {e}")

        # Genera PDF
        doc.build(story)
        buffer.seek(0)

        # Incrementa uso template
        crud.increment_template_usage(db, template.id)

        # Salva in file temporaneo
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
