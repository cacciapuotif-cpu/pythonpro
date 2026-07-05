"""
Router Sprint 7: Contract Generator, Certification Agent, portale allievi.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from database import get_db
from models import Assignment, Collaborator, Project, ImplementingEntity, AgentSuggestion, VocePianoFinanziario
from contract_generator import ContractGenerator
import io

router = APIRouter(prefix="/api/v1", tags=["sprint7"])


def _modalita_label(value: str | None) -> str:
    labels = {
        "aula": "Aula",
        "training_on_job": "Training on job",
        "fad_sincrona": "FAD sincrona",
        "fad_asincrona": "FAD asincrona",
        "propedeutica": "Propedeutica",
    }
    return labels.get(value or "", value or "")


def _assignment_financial_context(db: Session, assignment: Assignment) -> dict:
    modulo = getattr(assignment, "modulo_formativo", None)
    if not modulo and assignment.modulo_formativo_id:
        from models import ModuloFormativo
        modulo = db.query(ModuloFormativo).filter(ModuloFormativo.id == assignment.modulo_formativo_id).first()

    voce_query = db.query(VocePianoFinanziario)
    voce = voce_query.filter(VocePianoFinanziario.assignment_id == assignment.id).order_by(VocePianoFinanziario.id.asc()).first()
    if not voce and assignment.modulo_formativo_id:
        voce = voce_query.filter(
            VocePianoFinanziario.modulo_formativo_id == assignment.modulo_formativo_id
        ).order_by(VocePianoFinanziario.id.asc()).first()

    if not modulo and not voce:
        return {}

    azienda = getattr(modulo, "azienda_beneficiaria", None) if modulo else None
    progetto_fapi = ""
    if modulo:
        progetto_fapi = modulo.codice_progetto_fapi or ""
        if azienda and azienda.ragione_sociale:
            progetto_fapi = f"{progetto_fapi} - {azienda.ragione_sociale}".strip(" -")

    voce_label = ""
    if voce:
        voce_label = " ".join(part for part in [
            voce.voce_codice,
            voce.sottocategoria or voce.descrizione,
            "-",
            voce.mansione_riferimento or (modulo.materia if modulo else None),
        ] if part)

    return {
        "voce_piano_mansione": voce_label,
        "materia_docenza": (voce.mansione_riferimento if voce else None) or getattr(modulo, "materia", None) or assignment.materia or "",
        "modalita_erogazione": _modalita_label(getattr(modulo, "modalita_erogazione", None) or assignment.modalita_erogazione),
        "ore_previste_modulo": str(int(voce.ore_previste) if voce and voce.ore_previste and float(voce.ore_previste).is_integer() else (voce.ore_previste if voce else getattr(modulo, "ore_previste", "") or "")),
        "progetto_fapi_modulo": progetto_fapi,
    }


def _financial_html_block(context: dict) -> str:
    if not context:
        return ""
    return (
        "<p><strong>Voce Piano / Mansione:</strong> {voce_piano_mansione}<br/>"
        "<strong>Materia della docenza:</strong> {materia_docenza}<br/>"
        "<strong>Modalita erogazione:</strong> {modalita_erogazione}<br/>"
        "<strong>Ore previste:</strong> {ore_previste_modulo}h<br/>"
        "<strong>Progetto FAPI:</strong> {progetto_fapi_modulo}</p>"
    ).format(**context)


@router.post("/agents/contract-generator/run")
def run_contract_generator(
    project_id: int = None,
    db: Session = Depends(get_db),
):
    from ai_agents.contract_agent import run_contract_agent
    result = run_contract_agent(db, project_id=project_id)
    return result


@router.post("/agents/certification/run")
def run_certification(
    project_id: int = None,
    db: Session = Depends(get_db),
):
    from ai_agents.certification_agent import run_certification_agent
    result = run_certification_agent(db, project_id=project_id)
    return result


@router.get("/assignments/{assignment_id}/contract")
def genera_contratto(
    assignment_id: int,
    db: Session = Depends(get_db),
):
    from models import ContractTemplate
    import unicodedata

    assignment = db.query(Assignment).options(
        joinedload(Assignment.collaborator),
        joinedload(Assignment.project),
        joinedload(Assignment.modulo_formativo),
    ).filter(Assignment.id == assignment_id).first()

    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment non trovato")

    collab = assignment.collaborator
    project = assignment.project

    ente = None
    if project.ente_attuatore_id:
        ente = db.query(ImplementingEntity).filter(
            ImplementingEntity.id == project.ente_attuatore_id
        ).first()

    contract_type = assignment.contract_type or "occasionale"
    template = db.query(ContractTemplate).filter(
        ContractTemplate.tipo_contratto == contract_type,
        ContractTemplate.is_default == True,
        ContractTemplate.is_active == True,
    ).first()

    if not template:
        template = db.query(ContractTemplate).filter(
            ContractTemplate.tipo_contratto == contract_type,
            ContractTemplate.is_active == True,
        ).first()

    generator = ContractGenerator()
    financial_context = _assignment_financial_context(db, assignment)

    if template and template.contenuto_html:
        jinja_context = {
            "collaboratore_nome": collab.first_name or "",
            "collaboratore_cognome": collab.last_name or "",
            "collaboratore_cf": collab.fiscal_code or "",
            "collaboratore_piva": collab.partita_iva or "",
            "collaboratore_indirizzo": "{}, {}".format(
                collab.address or "", collab.city or ""
            ).strip(", "),
            "ente_ragione_sociale": ente.ragione_sociale if ente else "",
            "ente_piva": getattr(ente, "partita_iva", "") or "" if ente else "",
            "ente_indirizzo_completo": getattr(ente, "indirizzo", "") or "" if ente else "",
            "ente_legale_rappresentante_nome_completo": getattr(ente, "legale_rappresentante_nome", "") or "" if ente else "",
            "progetto_nome": project.name or "",
            "progetto_cup": project.cup or "",
            "progetto_atto_approvazione": getattr(project, "atto_approvazione", "") or "",
            "progetto_sede_aziendale_completa": getattr(project, "sede_aziendale_comune", "") or "",
            "ruolo": assignment.role or "",
            "ore_totali": assignment.assigned_hours or 0,
            "tariffa_oraria": "{:.2f}".format(assignment.hourly_rate or 0),
            "compenso_totale": "{:.2f}".format(
                (assignment.assigned_hours or 0) * (assignment.hourly_rate or 0)
            ),
            "data_inizio": assignment.start_date.strftime("%d/%m/%Y") if assignment.start_date else "",
            "data_fine": assignment.end_date.strftime("%d/%m/%Y") if assignment.end_date else "",
            "data_firma_contratto": __import__("datetime").datetime.now().strftime("%d/%m/%Y"),
        }
        jinja_context.update(financial_context)

        template_html = template.contenuto_html
        if financial_context:
            template_html = f"{_financial_html_block(financial_context)}\n{template_html}"

        replacements = {
            "«COGNOME»": collab.last_name or "",
            "«NOME»": collab.first_name or "",
            "«CODICE_FISCALE»": collab.fiscal_code or "",
            "«RESIDENZA»": "{}, {}".format(collab.address or "", collab.city or "").strip(", "),
            "«LUOGO_NASCITA»": getattr(collab, "birthplace", "") or "",
            "«DATA_NASCITA»": collab.birth_date.strftime("%d/%m/%Y") if getattr(collab, "birth_date", None) else "",
            "«ATTIVITA»": assignment.role or "",
            "«MATERIA_INSEGNAMENTO»": assignment.role or "",
            "«ORE»": str(int(assignment.assigned_hours or 0)),
            "«COSTO_UNITARIO»": "{:.2f}".format(assignment.hourly_rate or 0),
            "«COSTO_TOTALE»": "{:.2f}".format((assignment.assigned_hours or 0) * (assignment.hourly_rate or 0)),
            "«PERIODO_DAL»": assignment.start_date.strftime("%d/%m/%Y") if assignment.start_date else "",
            "«PERIODO_AL»": assignment.end_date.strftime("%d/%m/%Y") if assignment.end_date else "",
            "«RUOLO_PROGETTUALE»": assignment.role or "",
            "«Titolo_di_studio»": getattr(collab, "education", "") or "",
            "«VOCE_PIANO_MANSIONE»": financial_context.get("voce_piano_mansione", ""),
            "«MATERIA_DOCENZA»": financial_context.get("materia_docenza", ""),
            "«MODALITA_EROGAZIONE»": financial_context.get("modalita_erogazione", ""),
            "«ORE_PREVISTE_MODULO»": financial_context.get("ore_previste_modulo", ""),
            "«PROGETTO_FAPI_MODULO»": financial_context.get("progetto_fapi_modulo", ""),
        }
        for placeholder, value in replacements.items():
            template_html = template_html.replace(placeholder, value)

        logo_path = ente.logo_path if ente else None
        pdf_buffer = generator.generate_from_template(
            template_html=template_html,
            context=jinja_context,
            ente_logo_path=logo_path,
        )
    else:
        assignment_data = {
            "id": assignment.id,
            "contract_type": contract_type,
            "role": assignment.role,
            "assigned_hours": assignment.assigned_hours,
            "hourly_rate": assignment.hourly_rate,
            "start_date": assignment.start_date,
            "end_date": assignment.end_date,
            "collaborator_name": "{} {}".format(
                collab.first_name or "", collab.last_name or ""
            ).strip(),
            "collaborator_fiscal_code": collab.fiscal_code,
            "project_name": project.name,
            "project_cup": project.cup,
            "ente_attuatore": ente.ragione_sociale if ente else None,
            "ente_attuatore_piva": getattr(ente, "partita_iva", None) if ente else None,
            "ente_attuatore_indirizzo": getattr(ente, "indirizzo", None) if ente else None,
            **financial_context,
        }
        pdf_buffer = generator.generate_contract(
            assignment_data=assignment_data,
            contract_type=contract_type,
        )

    def _safe(text):
        normalized = unicodedata.normalize("NFKD", str(text))
        return normalized.encode("ascii", "ignore").decode("ascii").replace(" ", "_")

    collab_safe = "{}_{}".format(
        _safe(collab.last_name or ""),
        _safe(collab.first_name or "")
    ).upper()
    filename = "contratto_{}_{}.pdf".format(collab_safe, assignment_id)

    return StreamingResponse(
        io.BytesIO(pdf_buffer.read()),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename={}".format(filename)}
    )


@router.get("/allievi/{allievo_id}/magic-link")
def get_magic_link(
    allievo_id: int,
    db: Session = Depends(get_db),
):
    from models import Allievo
    import hashlib, time

    allievo = db.query(Allievo).filter(Allievo.id == allievo_id).first()
    if not allievo:
        raise HTTPException(status_code=404, detail="Allievo non trovato")

    token = hashlib.sha256(
        "{}{}{}".format(allievo_id, allievo.email or "", int(time.time() // 86400)).encode()
    ).hexdigest()[:32]

    return {
        "allievo_id": allievo_id,
        "nome": "{} {}".format(allievo.nome or "", allievo.cognome or "").strip(),
        "email": allievo.email,
        "magic_link": "http://192.168.2.161:3001/portale-allievi?token={}".format(token),
        "valido_per": "24 ore",
    }


# Il portale allievi (magic token, accesso pubblico) vive in routers/portale_allievi.py
