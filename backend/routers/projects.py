"""
Router per gestione progetti
Gestisce CRUD progetti e associazioni con collaboratori
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload
from typing import List, Optional
import logging
import re

import crud
import models
import schemas
from auth import User, get_current_user, normalize_role, UserRole
from database import get_db
from services.audit_log import write_audit_log
from services import dissociazione_progetto

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/projects", tags=["Projects"])


@router.post("/", response_model=schemas.Project, response_model_by_alias=False)
def create_project(
    project: schemas.ProjectCreateExtended,
    db: Session = Depends(get_db)
):
    """CREA UN NUOVO PROGETTO FORMATIVO"""
    try:
        result = crud.create_project(db=db, project=project)
        db.commit()
        db.refresh(result)
        logger.info(f"Progetto creato: ID {result.id}")
        return result
    except ValueError as exc:
        db.rollback()
        logger.info("Progetto rifiutato per dati non validi: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as e:
        db.rollback()
        logger.error(f"Errore creazione progetto: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[schemas.Project], response_model_by_alias=False)
def read_projects(
    skip: int = 0,
    limit: int = 100,
    is_active: Optional[bool] = True,
    db: Session = Depends(get_db)
):
    """OTTIENI LISTA DI TUTTI I PROGETTI"""
    projects = crud.get_projects(db, skip=skip, limit=limit, is_active=is_active)
    return projects


@router.get("/{project_id}", response_model=schemas.Project, response_model_by_alias=False)
def read_project(
    project_id: int,
    db: Session = Depends(get_db)
):
    """OTTIENI UN PROGETTO SPECIFICO"""
    db_project = crud.get_project(db, project_id=project_id)
    if db_project is None:
        raise HTTPException(status_code=404, detail="Progetto non trovato")
    return db_project


def _delivery_project_or_422(project_id: int, db: Session) -> models.Project:
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Progetto non trovato")
    if not crud.project_has_current_convenzione(db, project_id):
        raise HTTPException(
            status_code=422,
            detail="Collega prima la convenzione al progetto",
        )
    if project.ente_attuatore_id is None:
        raise HTTPException(
            status_code=422,
            detail="La convenzione collegata non identifica un ente attuatore",
        )
    return project


@router.get(
    "/{project_id}/delivery-context",
    response_model=schemas.ProjectDeliveryContext,
    response_model_by_alias=False,
)
def read_project_delivery_context(
    project_id: int,
    db: Session = Depends(get_db),
):
    """Ente derivato e stato bloccante della convenzione per lo Step Delivery."""
    project = db.query(models.Project).options(
        selectinload(models.Project.ente_attuatore).selectinload(
            models.ImplementingEntity.sedi
        )
    ).filter(models.Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Progetto non trovato")

    has_convenzione = crud.project_has_current_convenzione(db, project_id)
    if not has_convenzione:
        blocked_reason = "Collega prima la convenzione al progetto"
    elif project.ente_attuatore_id is None:
        blocked_reason = "La convenzione collegata non identifica un ente attuatore"
    else:
        blocked_reason = None

    return {
        "project_id": project.id,
        "has_convenzione": has_convenzione,
        "blocked_reason": blocked_reason,
        # L'ente gia' identificato sul progetto resta visibile in sola lettura
        # anche quando manca la convenzione corrente. Il blocco impedisce
        # comunque aziende/allievi e salvataggio: non e' un fallback manuale.
        "ente_attuatore": project.ente_attuatore,
    }


@router.get(
    "/{project_id}/delivery-companies",
    response_model=schemas.ProjectDeliveryCompanyPage,
    response_model_by_alias=False,
)
def read_project_delivery_companies(
    project_id: int,
    q: Optional[str] = Query(default=None, max_length=200),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """Aziende del perimetro progetto, o del catalogo globale se il fondo non ne dichiara."""
    project = _delivery_project_or_422(project_id, db)
    from services.atto_concessorio_registry import fornisce_aziende_beneficiarie

    query = db.query(models.AziendaCliente).options(
        selectinload(models.AziendaCliente.sedi_operative)
    ).filter(models.AziendaCliente.attivo.is_(True))

    if fornisce_aziende_beneficiarie(project.ente_erogatore):
        query = query.join(
            models.AziendaClienteProjectLink,
            models.AziendaClienteProjectLink.azienda_cliente_id == models.AziendaCliente.id,
        ).filter(models.AziendaClienteProjectLink.project_id == project_id)
    # Formazienda (e fondi che non dichiarano aziende): l'atto non porta un
    # perimetro, quindi la ricerca copre il catalogo intero, come un
    # progetto FAPI privo di convenzione userebbe se non fosse bloccato.

    normalized_q = (q or "").strip()
    if normalized_q:
        pattern = f"%{normalized_q}%"
        query = query.filter(or_(
            models.AziendaCliente.ragione_sociale.ilike(pattern),
            models.AziendaCliente.partita_iva.ilike(pattern),
        ))

    total = query.count()
    items = query.order_by(
        models.AziendaCliente.ragione_sociale.asc(),
        models.AziendaCliente.id.asc(),
    ).offset(offset).limit(limit).all()
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(items) < total,
    }


@router.get(
    "/{project_id}/delivery-companies/{azienda_id}/students",
    response_model=schemas.ProjectDeliveryStudentPage,
    response_model_by_alias=False,
)
def read_project_delivery_company_students(
    project_id: int,
    azienda_id: int,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """Allievi caricati soltanto on-demand per un'azienda nel perimetro."""
    project = _delivery_project_or_422(project_id, db)
    from services.atto_concessorio_registry import fornisce_aziende_beneficiarie
    in_perimeter = True
    if fornisce_aziende_beneficiarie(project.ente_erogatore):
        in_perimeter = db.query(models.AziendaClienteProjectLink.id).filter(
            models.AziendaClienteProjectLink.project_id == project_id,
            models.AziendaClienteProjectLink.azienda_cliente_id == azienda_id,
        ).first()
    if in_perimeter is None:
        raise HTTPException(
            status_code=404,
            detail="Azienda non presente nel perimetro del progetto",
        )

    query = db.query(models.Allievo).filter(
        models.Allievo.azienda_cliente_id == azienda_id,
        models.Allievo.attivo.is_(True),
    )
    total = query.count()
    items = query.order_by(
        models.Allievo.cognome.asc(),
        models.Allievo.nome.asc(),
        models.Allievo.id.asc(),
    ).offset(offset).limit(limit).all()
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(items) < total,
    }


@router.get(
    "/{project_id}/full-context",
    response_model=schemas.ProjectFullContext,
    response_model_by_alias=False,
    summary="Super-Context Progetto per Agenti AI",
    description=(
        "Restituisce in una singola risposta il contesto operativo completo del progetto: "
        "anagrafica progetto, ente attuatore, piani finanziari attivi e stato ore collaboratori "
        "aggregato. Endpoint pensato per tool-use AI con payload semantico pronto."
    ),
)
def read_project_full_context(
    project_id: int,
    db: Session = Depends(get_db),
):
    full_context = crud.get_project_full_context(db, project_id=project_id)
    if full_context is None:
        raise HTTPException(status_code=404, detail="Progetto non trovato")
    return full_context


def _format_hours(value) -> float:
    return float(value or 0)


def _modulo_to_dict(modulo: models.ModuloFormativo) -> dict:
    return {
        "id": modulo.id,
        "project_id": modulo.project_id,
        "azienda_beneficiaria_id": modulo.azienda_beneficiaria_id,
        "codice_progetto_fapi": modulo.codice_progetto_fapi,
        "titolo_modulo": modulo.titolo_modulo,
        "materia": modulo.materia,
        "modalita_erogazione": modulo.modalita_erogazione,
        "tipo_attivita": modulo.tipo_attivita,
        "ore_previste": _format_hours(modulo.ore_previste),
        "obiettivo": modulo.obiettivo,
    }


def _suffix_order(codice_progetto_fapi: str | None) -> int | None:
    match = re.search(r"(\d{2})$", codice_progetto_fapi or "")
    if not match:
        return None
    return int(match.group(1))


def _ordered_aziende_for_moduli(project_id: int, codice_piano: str | None, db: Session) -> list[models.AziendaCliente]:
    links = db.query(models.AziendaClienteProjectLink).join(models.AziendaCliente).filter(
        models.AziendaClienteProjectLink.project_id == project_id
    ).order_by(models.AziendaClienteProjectLink.id.asc()).all()
    aziende_by_link_order = [link.azienda for link in links if link.azienda]

    # Il formulario/convenzione FAPI 20250611CMIA001 dichiara l'ordine Allegato A
    # dei sottoprogetti in modo diverso dall'ordine storico dei link creati in DB.
    if codice_piano == "20250611CMIA001":
        wanted = [
            "power impianti",
            "pasticceria galdiero",
            "martinelli carmela",
            "maximercato",
            "ass. san vincenzo",
        ]
        aziende = []
        for needle in wanted:
            match = next(
                (
                    azienda for azienda in aziende_by_link_order
                    if needle in (azienda.ragione_sociale or "").lower()
                ),
                None,
            )
            if match:
                aziende.append(match)
        if len(aziende) == len(wanted):
            return aziende

    return aziende_by_link_order


@router.get("/{project_id}/moduli-formativi")
def read_project_moduli_formativi(
    project_id: int,
    db: Session = Depends(get_db),
):
    """Restituisce i moduli FAPI del progetto raggruppati per codice progetto FAPI."""
    project = crud.get_project(db, project_id=project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Progetto non trovato")

    moduli = db.query(models.ModuloFormativo).filter(
        models.ModuloFormativo.project_id == project_id
    ).order_by(
        models.ModuloFormativo.codice_progetto_fapi.asc(),
        models.ModuloFormativo.tipo_attivita.asc(),
        models.ModuloFormativo.id.asc(),
    ).all()

    aziende = _ordered_aziende_for_moduli(project_id, project.codice_fapi, db)
    grouped: dict[str, dict] = {}

    for modulo in moduli:
        codice = modulo.codice_progetto_fapi or "SENZA_CODICE"
        order = _suffix_order(codice)
        # Formazienda materializza esplicitamente l'azienda dell'edizione.
        # Il fallback per suffisso conserva la compatibilita' coi moduli FAPI
        # storici che non valorizzano la FK diretta.
        azienda = modulo.azienda_beneficiaria
        if azienda is None:
            azienda = aziende[order - 1] if order and 0 < order <= len(aziende) else None

        if codice not in grouped:
            partecipanti = None
            if azienda:
                partecipanti = db.query(models.Allievo).join(
                    models.allievo_project,
                    models.allievo_project.c.allievo_id == models.Allievo.id,
                ).filter(
                    models.allievo_project.c.project_id == project_id,
                    models.Allievo.azienda_cliente_id == azienda.id,
                ).count()
            grouped[codice] = {
                "codice_progetto_fapi": codice,
                "azienda": (
                    {"id": azienda.id, "ragione_sociale": azienda.ragione_sociale}
                    if azienda else None
                ),
                "partecipanti": partecipanti,
                "moduli_formativi": [],
                "moduli_propedeutici": [],
                "ore_formative_totali": 0.0,
                "ore_propedeutiche_totali": 0.0,
            }

        modulo_payload = _modulo_to_dict(modulo)
        ore = _format_hours(modulo.ore_previste)
        if modulo.tipo_attivita == "propedeutica":
            grouped[codice]["moduli_propedeutici"].append(modulo_payload)
            grouped[codice]["ore_propedeutiche_totali"] += ore
        else:
            grouped[codice]["moduli_formativi"].append(modulo_payload)
            grouped[codice]["ore_formative_totali"] += ore

    progetti_fapi = [grouped[key] for key in sorted(grouped.keys())]
    return {
        "project_id": project_id,
        "progetti_fapi": progetti_fapi,
        "ore_totali": sum(
            _format_hours(modulo.ore_previste)
            for modulo in moduli
            if modulo.tipo_attivita != "propedeutica"
        ),
        "moduli_totali": len(moduli),
    }


@router.get("/{project_id}/moduli-formativi/{modulo_id}/voce-piano")
def read_project_modulo_voce_piano(
    project_id: int,
    modulo_id: int,
    db: Session = Depends(get_db),
):
    """Restituisce la voce del piano finanziario collegata al modulo FAPI."""
    project = crud.get_project(db, project_id=project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Progetto non trovato")

    modulo = db.query(models.ModuloFormativo).filter(
        models.ModuloFormativo.id == modulo_id,
        models.ModuloFormativo.project_id == project_id,
    ).first()
    if modulo is None:
        raise HTTPException(status_code=404, detail="Modulo formativo non trovato")

    piano = crud.get_piano_by_progetto(db, project_id)
    if piano is None:
        raise HTTPException(status_code=404, detail="Piano finanziario non trovato")

    voce = db.query(models.VocePianoFinanziario).filter(
        models.VocePianoFinanziario.piano_id == piano.id,
        models.VocePianoFinanziario.modulo_formativo_id == modulo_id,
    ).order_by(models.VocePianoFinanziario.id.asc()).first()
    if voce is None:
        raise HTTPException(status_code=404, detail="Voce piano non trovata per questo modulo")

    return {
        "voce_codice": voce.voce_codice,
        "voce_descrizione": voce.sottocategoria or voce.descrizione or voce.mansione_riferimento,
        "azienda": voce.progetto_label or voce.descrizione,
        "materia": voce.mansione_riferimento or modulo.materia,
        "ore_previste": _format_hours(voce.ore_previste if voce.ore_previste is not None else modulo.ore_previste),
        "tariffa_oraria": float(voce.tariffa_oraria or 0.0),
        "importo": float(voce.importo_preventivo or 0.0),
    }


@router.put("/{project_id}", response_model=schemas.Project, response_model_by_alias=False)
def update_project(
    project_id: int,
    project: schemas.ProjectUpdateExtended,
    db: Session = Depends(get_db)
):
    """AGGIORNA UN PROGETTO ESISTENTE"""
    try:
        db_project = crud.update_project(db, project_id, project)
        if db_project is None:
            raise HTTPException(status_code=404, detail="Progetto non trovato")
        return db_project
    except dissociazione_progetto.DissociazioneBloccata as exc:
        # UX-8: omettere un id dalla lista e' una dissociazione, e passa dalle
        # stesse guardie della DELETE dedicata. Qui non si forza: per superare
        # un blocco forzabile si usa l'endpoint esplicito, che pretende motivo.
        db.rollback()
        raise HTTPException(status_code=409, detail=exc.as_detail())
    except crud.DeliveryValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc))
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        db.rollback()
        raise


@router.delete("/{project_id}")
def delete_project(
    project_id: int,
    db: Session = Depends(get_db)
):
    """ELIMINA UN PROGETTO"""
    db_project = crud.delete_project(db, project_id)
    if db_project is None:
        raise HTTPException(status_code=404, detail="Progetto non trovato")
    return {"message": "Progetto eliminato con successo"}


# ── Dissociazione allievi / aziende (UX-8) ───────────────────────────

def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _is_admin(current_user: User) -> bool:
    return normalize_role(current_user.role) == UserRole.ADMIN.value


def _valida_forzatura(payload: schemas.DissociazioneRequest | None, current_user: User):
    """La forzatura e' un atto riservato: solo admin, solo con motivo."""
    if payload is None or not payload.forza:
        return
    if not _is_admin(current_user):
        raise HTTPException(
            status_code=403,
            detail="Solo un amministratore puo' forzare la dissociazione",
        )


@router.delete("/{project_id}/allievi/{allievo_id}", response_model=schemas.DissociazioneResponse)
def dissocia_allievo_da_progetto(
    project_id: int,
    allievo_id: int,
    request: Request,
    payload: Optional[schemas.DissociazioneRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stacca un allievo dal progetto applicando le guardie di dominio.

    Blocco assoluto sull'attestato emesso; ore frequentate e dati retributivi
    sono superabili da un admin con motivo scritto, che finisce in audit.
    """
    if not db.query(models.Project.id).filter(models.Project.id == project_id).first():
        raise HTTPException(status_code=404, detail="Progetto non trovato")

    link = (
        db.query(models.AllievoProject)
        .filter(
            models.AllievoProject.project_id == project_id,
            models.AllievoProject.allievo_id == allievo_id,
        )
        .first()
    )
    if link is None:
        raise HTTPException(
            status_code=404, detail="Allievo non associato a questo progetto"
        )

    _valida_forzatura(payload, current_user)
    forza = bool(payload and payload.forza)
    motivo = payload.motivo if payload else None

    blocchi = dissociazione_progetto.blocchi_dissociazione_allievo(db, project_id, allievo_id)
    try:
        dissociazione_progetto.verifica_dissociazione_allievo(
            db, project_id, allievo_id, forza=forza
        )
    except dissociazione_progetto.DissociazioneBloccata as exc:
        write_audit_log(
            db,
            user_id=current_user.id,
            azione="project_allievo_dissociato",
            risorsa_tipo="project",
            risorsa_id=project_id,
            dati_prima={"allievo_id": allievo_id},
            dati_dopo={"blocchi": [b.codice for b in exc.blocchi], "forza": forza},
            ip_address=_client_ip(request),
            esito="blocked",
        )
        db.commit()
        raise HTTPException(status_code=409, detail=exc.as_detail())

    stato_prima = {
        "allievo_id": allievo_id,
        "stato": link.stato,
        "ore_frequentate": float(link.ore_frequentate or 0),
        "attestato_emesso": bool(link.attestato_emesso),
    }
    db.delete(link)

    write_audit_log(
        db,
        user_id=current_user.id,
        azione="project_allievo_dissociato",
        risorsa_tipo="project",
        risorsa_id=project_id,
        dati_prima=stato_prima,
        dati_dopo={
            "allievo_id": allievo_id,
            "dissociato": True,
            "forzata": forza,
            "motivo": motivo,
            "blocchi_superati": [b.codice for b in blocchi],
        },
        ip_address=_client_ip(request),
        esito="success",
    )
    db.commit()

    logger.info(
        "UX-8 allievo %s dissociato dal progetto %s (forzata=%s)",
        allievo_id, project_id, forza,
    )
    return schemas.DissociazioneResponse(
        project_id=project_id,
        entita="allievo",
        entita_id=allievo_id,
        dissociato=True,
        forzata=forza,
        blocchi_superati=[schemas.DissociazioneBloccoItem(**b.as_dict()) for b in blocchi],
    )


@router.delete("/{project_id}/aziende/{azienda_id}", response_model=schemas.DissociazioneResponse)
def dissocia_azienda_da_progetto(
    project_id: int,
    azienda_id: int,
    request: Request,
    payload: Optional[schemas.DissociazioneRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stacca un'azienda dal progetto.

    Nessuna cascata implicita: finche' l'azienda porta suoi allievi sul
    progetto la dissociazione e' bloccata, e il blocco non e' forzabile.
    """
    if not db.query(models.Project.id).filter(models.Project.id == project_id).first():
        raise HTTPException(status_code=404, detail="Progetto non trovato")

    link = (
        db.query(models.AziendaClienteProjectLink)
        .filter(
            models.AziendaClienteProjectLink.project_id == project_id,
            models.AziendaClienteProjectLink.azienda_cliente_id == azienda_id,
        )
        .first()
    )
    if link is None:
        raise HTTPException(
            status_code=404, detail="Azienda non associata a questo progetto"
        )

    _valida_forzatura(payload, current_user)
    forza = bool(payload and payload.forza)

    try:
        dissociazione_progetto.verifica_dissociazione_azienda(
            db, project_id, azienda_id, forza=forza
        )
    except dissociazione_progetto.DissociazioneBloccata as exc:
        write_audit_log(
            db,
            user_id=current_user.id,
            azione="project_azienda_dissociata",
            risorsa_tipo="project",
            risorsa_id=project_id,
            dati_prima={"azienda_id": azienda_id},
            dati_dopo={"blocchi": [b.codice for b in exc.blocchi], "forza": forza},
            ip_address=_client_ip(request),
            esito="blocked",
        )
        db.commit()
        raise HTTPException(status_code=409, detail=exc.as_detail())

    stato_prima = {
        "azienda_id": azienda_id,
        "regime_aiuto": link.regime_aiuto,
        "stato": link.stato,
    }
    db.delete(link)

    write_audit_log(
        db,
        user_id=current_user.id,
        azione="project_azienda_dissociata",
        risorsa_tipo="project",
        risorsa_id=project_id,
        dati_prima=stato_prima,
        dati_dopo={"azienda_id": azienda_id, "dissociato": True},
        ip_address=_client_ip(request),
        esito="success",
    )
    db.commit()

    logger.info("UX-8 azienda %s dissociata dal progetto %s", azienda_id, project_id)
    return schemas.DissociazioneResponse(
        project_id=project_id,
        entita="azienda",
        entita_id=azienda_id,
        dissociato=True,
    )


# ── Aziende beneficiarie (regime aiuto) ──────────────────────────────

def _beneficiario_to_schema(link: models.AziendaClienteProjectLink) -> schemas.ProjectBeneficiario:
    return schemas.ProjectBeneficiario(
        azienda_id=link.azienda_cliente_id,
        ragione_sociale=link.azienda.ragione_sociale if link.azienda else "",
        regime_aiuto=link.regime_aiuto,
        plafond_dichiarato=link.plafond_dichiarato,
        cofinanziamento_perc=link.cofinanziamento_perc,
        stato=link.stato,
    )


@router.get("/{project_id}/beneficiari", response_model=schemas.ProjectBeneficiariResponse)
def read_project_beneficiari(project_id: int, db: Session = Depends(get_db)):
    """Aziende beneficiarie del progetto con regime aiuto e plafond."""
    if not db.query(models.Project.id).filter(models.Project.id == project_id).first():
        raise HTTPException(status_code=404, detail="Progetto non trovato")
    links = (
        db.query(models.AziendaClienteProjectLink)
        .filter(models.AziendaClienteProjectLink.project_id == project_id)
        .all()
    )
    return schemas.ProjectBeneficiariResponse(
        beneficiari=[_beneficiario_to_schema(link) for link in links]
    )


@router.patch("/{project_id}/beneficiari/{azienda_id}/regime", response_model=schemas.ProjectBeneficiario)
def update_project_beneficiario_regime(
    project_id: int,
    azienda_id: int,
    payload: schemas.BeneficiarioRegimeUpdate,
    db: Session = Depends(get_db)
):
    """Aggiorna regime aiuto e plafond dichiarato di un'azienda beneficiaria."""
    link = (
        db.query(models.AziendaClienteProjectLink)
        .filter(
            models.AziendaClienteProjectLink.project_id == project_id,
            models.AziendaClienteProjectLink.azienda_cliente_id == azienda_id,
        )
        .first()
    )
    if not link:
        raise HTTPException(status_code=404, detail="Azienda beneficiaria non trovata per questo progetto")
    link.regime_aiuto = None if payload.regime_aiuto == "non_definito" else payload.regime_aiuto
    if payload.plafond_dichiarato is not None:
        link.plafond_dichiarato = payload.plafond_dichiarato
    db.commit()
    db.refresh(link)
    return _beneficiario_to_schema(link)
