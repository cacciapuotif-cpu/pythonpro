"""
Router per gestione assegnazioni dettagliate
Gestisce mansioni, contratti e generazione PDF
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
import tempfile
from datetime import datetime
from io import BytesIO
import html
import re
from xml.sax.saxutils import escape

import crud
import schemas
from database import get_db
from validators import EnhancedAssignmentCreate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/assignments", tags=["Assignments"])
PAGE_BREAK_MARKER = "__PAGE_BREAK__"


def _split_street_and_number(address: str | None) -> tuple[str, str]:
    """Estrae via e numero civico da un indirizzo libero."""
    if not address:
        return ("N/A", "N/A")

    cleaned = re.sub(r"\s+", " ", address).strip()
    match = re.match(r"^(.*?)(?:,\s*|\s+)(\d+[A-Za-z/-]*)$", cleaned)
    if match:
        return (match.group(1).strip() or "N/A", match.group(2).strip() or "N/A")
    return (cleaned, "N/A")


def _build_contract_context(
    collaborator,
    project,
    ente,
    date_format: str,
    role: str,
    hours: float,
    hourly_rate: float,
    start_date,
    end_date,
    contract_signed_date=None
) -> tuple[dict, dict]:
    """Costruisce il contesto completo per i placeholder del contratto."""
    compenso_totale = hours * hourly_rate
    signature_date = contract_signed_date
    signature_date_formatted = signature_date.strftime(date_format) if signature_date else 'N/A'
    collaborator_address = ", ".join(
        part for part in [collaborator.address or "", collaborator.city or ""] if part
    ) or "N/A"
    ente_sede_via, ente_sede_numero_civico = _split_street_and_number(ente.indirizzo if ente else None)
    progetto_sede_completa = ", ".join(
        part for part in [
            project.sede_aziendale_via or "",
            project.sede_aziendale_numero_civico or "",
            project.sede_aziendale_comune or ""
        ] if part
    ) or "N/A"

    context = {
        'collaboratore_nome': collaborator.first_name,
        'collaboratore_cognome': collaborator.last_name,
        'collaboratore_nome_completo': f"{collaborator.first_name} {collaborator.last_name}",
        'collaboratore_codice_fiscale': collaborator.fiscal_code or 'N/A',
        'collaboratore_luogo_nascita': collaborator.birthplace or 'N/A',
        'collaboratore_data_nascita': collaborator.birth_date.strftime(date_format) if collaborator.birth_date else 'N/A',
        'collaboratore_indirizzo': collaborator.address or 'N/A',
        'collaboratore_citta': collaborator.city or 'N/A',
        'collaboratore_titolo_studio': collaborator.education or 'N/A',
        'progetto_nome': project.name,
        'progetto_descrizione': project.description or '',
        'progetto_cup': project.cup or 'N/A',
        'progetto_atto_approvazione': project.atto_approvazione or 'N/A',
        'progetto_data_inizio': project.start_date.strftime(date_format) if project.start_date else 'N/A',
        'progetto_data_fine': project.end_date.strftime(date_format) if project.end_date else 'N/A',
        'progetto_sede_aziendale_comune': project.sede_aziendale_comune or 'N/A',
        'progetto_sede_aziendale_via': project.sede_aziendale_via or 'N/A',
        'progetto_sede_aziendale_numero_civico': project.sede_aziendale_numero_civico or 'N/A',
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
        'ente_legale_rappresentante_data_nascita': ente.legale_rappresentante_data_nascita.strftime(date_format) if ente.legale_rappresentante_data_nascita else 'N/A',
        'ente_legale_rappresentante_comune_residenza': ente.legale_rappresentante_comune_residenza or 'N/A',
        'ente_legale_rappresentante_via_residenza': ente.legale_rappresentante_via_residenza or 'N/A',
        'ente_legale_rappresentante_codice_fiscale': ente.legale_rappresentante_codice_fiscale or 'N/A',
        'ente_referente': ente.legale_rappresentante_nome_completo or ente.referente_nome_completo or 'N/A',
        'ente_pec': ente.pec or 'N/A',
        'ente_email': ente.email or 'N/A',
        'ente_telefono': ente.telefono or 'N/A',
        'mansione': role,
        'ore_previste': str(hours),
        'tariffa_oraria': f"€ {hourly_rate:.2f}",
        'compenso_totale': f"€ {compenso_totale:.2f}",
        'data_inizio': start_date.strftime(date_format) if start_date else 'N/A',
        'data_fine': end_date.strftime(date_format) if end_date else 'N/A',
        'data_firma_contratto': signature_date_formatted,
        'data_sottoscrizione_contratto': signature_date_formatted,
        'contract_signed_date': signature_date_formatted,
        'data_oggi': datetime.now().strftime(date_format)
    }

    legacy_context = {
        'NOME': collaborator.first_name,
        'COGNOME': collaborator.last_name,
        'LUOGO_NASCITA': collaborator.birthplace or 'N/A',
        'DATA_NASCITA': context['collaboratore_data_nascita'],
        'RESIDENZA': collaborator_address,
        'CODICE_FISCALE': collaborator.fiscal_code or 'N/A',
        'ATTIVITA': role,
        'MATERIA_INSEGNAMENTO': role,
        'ORE': str(hours),
        'COSTO_UNITARIO': f"{hourly_rate:.2f}",
        'COSTO_TOTALE': f"{compenso_totale:.2f}",
        'PERIODO_DAL': context['data_inizio'],
        'PERIODO_AL': context['data_fine'],
        'SEDE_AZIENDALE': ente.indirizzo_completo or 'N/A',
        'CODICE_PROGETTO': project.cup or project.name,
        'RUOLO_PROGETTUALE': role
    }

    return context, legacy_context


def _render_contract_template_text(template_text: str, context: dict, legacy_context: dict) -> str:
    """Render minimale compatibile con placeholder {{var}} e «VARIABILE»."""
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


def _html_to_text_blocks(raw_html: str) -> list[str]:
    """Converte HTML complesso in blocchi testuali leggibili per ReportLab."""
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

# Verifica disponibilità generatore contratti
try:
    from contract_generator import ContractGenerator
    CONTRACT_GENERATOR_AVAILABLE = True
except ImportError:
    logger.warning("contract_generator non disponibile")
    CONTRACT_GENERATOR_AVAILABLE = False
    ContractGenerator = None


@router.post("/", response_model=schemas.Assignment)
def create_assignment(
    assignment: EnhancedAssignmentCreate,
    db: Session = Depends(get_db)
):
    """CREA UNA NUOVA ASSEGNAZIONE"""
    try:
        logger.info(f"Ricevuta richiesta creazione assegnazione: {assignment.dict()}")

        collaborator = crud.get_collaborator(db, assignment.collaborator_id)
        if not collaborator:
            raise HTTPException(status_code=404, detail="Collaboratore non trovato")

        project = crud.get_project(db, assignment.project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Progetto non trovato")

        assignment_data = schemas.AssignmentCreate(**assignment.dict())
        result = crud.create_assignment(db=db, assignment=assignment_data)
        db.commit()
        db.refresh(result)

        logger.info(f"Assegnazione creata con successo: ID {result.id}")
        return result

    except HTTPException:
        raise
    except ValueError as e:
        db.rollback()
        logger.warning(f"Validazione assegnazione fallita: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        logger.error(f"Errore creazione assegnazione: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[schemas.Assignment])
def read_assignments(
    skip: int = 0,
    limit: int = 100,
    is_active: Optional[bool] = True,
    db: Session = Depends(get_db)
):
    """OTTIENI LISTA DELLE ASSEGNAZIONI"""
    assignments = crud.get_assignments(db, skip=skip, limit=limit, is_active=is_active)
    return assignments


@router.get("/{assignment_id}", response_model=schemas.Assignment)
def read_assignment(
    assignment_id: int,
    db: Session = Depends(get_db)
):
    """OTTIENI UNA ASSEGNAZIONE SPECIFICA"""
    db_assignment = crud.get_assignment(db, assignment_id=assignment_id)
    if db_assignment is None:
        raise HTTPException(status_code=404, detail="Assegnazione non trovata")
    return db_assignment


@router.put("/{assignment_id}", response_model=schemas.Assignment)
def update_assignment(
    assignment_id: int,
    assignment: schemas.AssignmentUpdate,
    db: Session = Depends(get_db)
):
    """AGGIORNA UNA ASSEGNAZIONE"""
    db_assignment = crud.update_assignment(db, assignment_id, assignment)
    if db_assignment is None:
        raise HTTPException(status_code=404, detail="Assegnazione non trovata")
    return db_assignment


@router.delete("/{assignment_id}")
def delete_assignment(
    assignment_id: int,
    db: Session = Depends(get_db)
):
    """ELIMINA UNA ASSEGNAZIONE"""
    db_assignment = crud.delete_assignment(db, assignment_id)
    if db_assignment is None:
        raise HTTPException(status_code=404, detail="Assegnazione non trovata")
    return {"message": "Assegnazione eliminata con successo"}


@router.get("/{assignment_id}/generate-contract")
def generate_contract_pdf(
    assignment_id: int,
    db: Session = Depends(get_db)
):
    """
    GENERA UN CONTRATTO PDF PER UNA ASSEGNAZIONE

    Compila automaticamente un contratto con i dati del collaboratore,
    progetto, mansione, ore e importo.
    """
    try:
        assignment = crud.get_assignment(db, assignment_id=assignment_id)
        if not assignment:
            raise HTTPException(status_code=404, detail="Assegnazione non trovata")

        collaborator = crud.get_collaborator(db, assignment.collaborator_id)
        project = crud.get_project(db, assignment.project_id)

        if not collaborator or not project:
            raise HTTPException(status_code=404, detail="Dati incompleti per generare il contratto")

        # Retrocompatibilita: il route legacy converge sul motore template-based quando possibile.
        if project.ente_attuatore_id:
            from routers.contract_templates import _generate_contract_pdf_response

            try:
                return _generate_contract_pdf_response(
                    schemas.ContractGenerationRequest(
                        collaboratore_id=assignment.collaborator_id,
                        progetto_id=assignment.project_id,
                        ente_attuatore_id=project.ente_attuatore_id,
                        mansione=assignment.role,
                        ore_previste=assignment.assigned_hours,
                        tariffa_oraria=assignment.hourly_rate,
                        data_inizio=assignment.start_date,
                        data_fine=assignment.end_date,
                        contract_signed_date=assignment.contract_signed_date,
                        tipo_contratto=assignment.contract_type or 'professionale'
                    ),
                    db
                )
            except HTTPException as template_error:
                logger.warning(
                    "Fallback legacy generator per assignment %s: %s",
                    assignment_id,
                    template_error.detail
                )

        if not CONTRACT_GENERATOR_AVAILABLE:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Sistema di generazione contratti non disponibile"
            )

        assignment_data = {
            'id': assignment.id,
            'role': assignment.role,
            'assigned_hours': assignment.assigned_hours,
            'hourly_rate': assignment.hourly_rate,
            'start_date': assignment.start_date.isoformat() if assignment.start_date else None,
            'end_date': assignment.end_date.isoformat() if assignment.end_date else None,
            'contract_type': assignment.contract_type,
            'collaborator': {
                'first_name': collaborator.first_name,
                'last_name': collaborator.last_name,
                'email': collaborator.email,
                'fiscal_code': collaborator.fiscal_code,
                'birthplace': collaborator.birthplace,
                'birth_date': collaborator.birth_date.isoformat() if collaborator.birth_date else None,
                'address': collaborator.address,
                'city': collaborator.city
            },
            'project': {
                'name': project.name,
                'description': project.description
            }
        }

        generator = ContractGenerator()
        pdf_buffer = generator.generate_contract(assignment_data)

        filename = f"contratto_{collaborator.last_name}_{project.name.replace(' ', '_')}.pdf"

        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            tmp.write(pdf_buffer.read())
            tmp_path = tmp.name

        logger.info(f"Contratto generato per assignment {assignment_id}")

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
