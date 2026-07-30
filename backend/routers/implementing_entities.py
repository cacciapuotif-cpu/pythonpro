"""
Router per gestione enti attuatori
Gestisce CRUD enti attuatori con upload logo
"""

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, datetime
import logging
import os
from types import SimpleNamespace

import crud
import models
import schemas
from auth import User, UserRole, get_current_user, normalize_role
from database import get_db
from services.audit_log import write_audit_log
from services.entity_printing import generate_print_preview, mask_iban

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/entities", tags=["Implementing Entities"])


def _get_entity_or_404(db: Session, entity_id: int) -> models.ImplementingEntity:
    entity = crud.get_implementing_entity(db, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Ente attuatore non trovato")
    return entity


def _account_payload(account: models.ImplementingEntityBankAccount) -> dict:
    """Gli endpoint ordinari non restituiscono mai l'IBAN completo."""
    return {
        "id": account.id,
        "ente_id": account.ente_id,
        "banca": account.banca,
        "agenzia": account.agenzia,
        "iban": None,
        "iban_masked": mask_iban(account.iban),
        "bic_swift": account.bic_swift,
        "intestatario": account.intestatario,
        "is_predefinito": account.is_predefinito,
        "is_active": account.is_active,
        "note": account.note,
        "created_at": account.created_at,
        "updated_at": account.updated_at,
    }


def _entity_payload(entity: models.ImplementingEntity, *, include_projects: bool = False) -> dict:
    data = schemas.ImplementingEntity.model_validate(entity).model_dump()
    # Anche per admin gli elenchi e la scheda base restano mascherati. La
    # visualizzazione integrale passa dall'endpoint reveal, che scrive audit.
    data["iban"] = mask_iban(entity.iban) if entity.iban else None
    data["conti_correnti"] = [_account_payload(account) for account in entity.conti_correnti]
    if include_projects:
        data["projects"] = [
            schemas.Project.model_validate(project).model_dump() for project in entity.projects
        ]
    return data


def _ensure_location_uniqueness(
    db: Session,
    *,
    entity_id: int,
    tipo: str,
    is_principale: bool,
    is_active: bool,
    exclude_id: int | None = None,
) -> None:
    query = db.query(models.ImplementingEntityLocation).filter(
        models.ImplementingEntityLocation.ente_id == entity_id,
        models.ImplementingEntityLocation.is_active.is_(True),
    )
    if exclude_id is not None:
        query = query.filter(models.ImplementingEntityLocation.id != exclude_id)
    if is_active and tipo == "legale" and query.filter(
        models.ImplementingEntityLocation.tipo == "legale"
    ).first():
        raise HTTPException(status_code=409, detail="È consentita una sola sede legale attiva")
    if is_active and is_principale and query.filter(
        models.ImplementingEntityLocation.is_principale.is_(True)
    ).first():
        raise HTTPException(status_code=409, detail="È consentita una sola sede principale attiva")


def _sync_legacy_legal_location(entity: models.ImplementingEntity, location) -> None:
    if location.tipo != "legale" or not location.is_active:
        return
    entity.indirizzo = location.indirizzo
    entity.cap = location.cap
    entity.citta = location.citta
    entity.provincia = location.provincia
    entity.nazione = location.nazione


def _sync_legacy_default_account(entity: models.ImplementingEntity, account) -> None:
    if account.is_predefinito and account.is_active:
        entity.iban = account.iban
        entity.intestatario_conto = account.intestatario


@router.post("/", response_model=schemas.ImplementingEntity)
def create_implementing_entity(
    entity: schemas.ImplementingEntityCreate,
    db: Session = Depends(get_db)
):
    """
    CREA UN NUOVO ENTE ATTUATORE

    Campi obbligatori:
    - ragione_sociale
    - partita_iva (deve essere unica)

    Validazioni automatiche:
    - P.IVA: 11 cifre numeriche
    - IBAN: 27 caratteri formato IT
    - PEC/Email: formato email valido
    - CAP: 5 cifre
    """
    try:
        existing = crud.get_implementing_entity_by_piva(db, entity.partita_iva)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Esiste già un ente con P.IVA {entity.partita_iva}"
            )

        db_entity = crud.create_implementing_entity(db, entity)
        legal_location = models.ImplementingEntityLocation(
            ente_id=db_entity.id,
            tipo="legale",
            denominazione=f"{db_entity.ragione_sociale} - Sede legale",
            indirizzo=db_entity.indirizzo,
            cap=db_entity.cap,
            citta=db_entity.citta,
            provincia=db_entity.provincia,
            nazione=db_entity.nazione or "IT",
            email=db_entity.email,
            pec=db_entity.pec,
            telefono=db_entity.telefono,
            is_principale=True,
            is_active=True,
        )
        db.add(legal_location)
        if db_entity.iban:
            db.add(
                models.ImplementingEntityBankAccount(
                    ente_id=db_entity.id,
                    iban=db_entity.iban,
                    intestatario=db_entity.intestatario_conto or db_entity.ragione_sociale,
                    is_predefinito=True,
                    is_active=True,
                )
            )
        db.commit()
        db.refresh(db_entity)
        logger.info(f"Created implementing entity: {db_entity.ragione_sociale} (ID: {db_entity.id})")
        return _entity_payload(db_entity)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating implementing entity: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Errore nella creazione dell'ente attuatore"
        )


@router.get("/", response_model=List[schemas.ImplementingEntity])
def get_implementing_entities(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """
    RECUPERA LISTA ENTI ATTUATORI

    Parametri query:
    - skip: Salta N record (paginazione)
    - limit: Massimo record da restituire
    - search: Cerca per ragione_sociale, P.IVA, città o PEC
    - is_active: Filtra per stato attivo (true/false)
    """
    entities = crud.get_implementing_entities(
        db,
        skip=skip,
        limit=limit,
        search=search,
        is_active=is_active
    )
    return [_entity_payload(entity) for entity in entities]


@router.get("/count")
def get_implementing_entities_count(
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """CONTA IL NUMERO TOTALE DI ENTI (per paginazione frontend)"""
    count = crud.get_implementing_entities_count(db, search=search, is_active=is_active)
    return {"count": count}


@router.get("/{entity_id}", response_model=schemas.ImplementingEntityWithProjects)
def get_implementing_entity(
    entity_id: int,
    db: Session = Depends(get_db)
):
    """RECUPERA UN SINGOLO ENTE ATTUATORE CON I PROGETTI COLLEGATI"""
    entity = crud.get_implementing_entity_with_projects(db, entity_id)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ente attuatore non trovato"
        )
    return _entity_payload(entity, include_projects=True)


@router.put("/{entity_id}", response_model=schemas.ImplementingEntity)
def update_implementing_entity(
    entity_id: int,
    entity: schemas.ImplementingEntityUpdate,
    db: Session = Depends(get_db)
):
    """
    AGGIORNA UN ENTE ATTUATORE ESISTENTE

    Tutti i campi sono opzionali. Vengono aggiornati solo i campi forniti.
    """
    try:
        existing_entity = crud.get_implementing_entity(db, entity_id)
        if not existing_entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ente attuatore non trovato"
            )

        if entity.partita_iva and entity.partita_iva != existing_entity.partita_iva:
            duplicate = crud.get_implementing_entity_by_piva(db, entity.partita_iva)
            if duplicate and duplicate.id != entity_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Esiste già un altro ente con P.IVA {entity.partita_iva}"
                )

        updated_entity = crud.update_implementing_entity(db, entity_id, entity)
        legal_location = next(
            (location for location in updated_entity.sedi if location.tipo == "legale" and location.is_active),
            None,
        )
        changed = entity.model_dump(exclude_unset=True)
        if legal_location and {
            "indirizzo", "cap", "citta", "provincia", "nazione"
        }.intersection(changed):
            legal_location.indirizzo = updated_entity.indirizzo
            legal_location.cap = updated_entity.cap
            legal_location.citta = updated_entity.citta
            legal_location.provincia = updated_entity.provincia
            legal_location.nazione = updated_entity.nazione or "IT"
        if {"iban", "intestatario_conto"}.intersection(changed):
            default_account = next(
                (
                    account
                    for account in updated_entity.conti_correnti
                    if account.is_predefinito and account.is_active
                ),
                None,
            )
            if default_account and updated_entity.iban:
                default_account.iban = updated_entity.iban
                default_account.intestatario = (
                    updated_entity.intestatario_conto or updated_entity.ragione_sociale
                )
            elif updated_entity.iban:
                db.add(
                    models.ImplementingEntityBankAccount(
                        ente_id=updated_entity.id,
                        iban=updated_entity.iban,
                        intestatario=updated_entity.intestatario_conto or updated_entity.ragione_sociale,
                        is_predefinito=True,
                        is_active=True,
                    )
                )
        db.commit()
        db.refresh(updated_entity)
        logger.info(f"Updated implementing entity: ID {entity_id}")
        return _entity_payload(updated_entity)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating implementing entity {entity_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Errore nell'aggiornamento dell'ente"
        )


@router.delete("/{entity_id}")
def delete_implementing_entity(
    entity_id: int,
    soft_delete: bool = True,
    db: Session = Depends(get_db)
):
    """
    ELIMINA O DISATTIVA UN ENTE ATTUATORE

    Parametri:
    - soft_delete=true (default): Disattiva l'ente (is_active=False) mantenendo lo storico
    - soft_delete=false: Eliminazione fisica (fallisce se ci sono progetti collegati)
    """
    try:
        entity = crud.get_implementing_entity(db, entity_id)
        if not entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ente attuatore non trovato"
            )

        if soft_delete:
            deleted_entity = crud.soft_delete_implementing_entity(db, entity_id)
            logger.info(f"Soft-deleted implementing entity: ID {entity_id}")
            return {
                "message": "Ente disattivato con successo",
                "entity_id": entity_id,
                "soft_delete": True
            }
        else:
            deleted_entity = crud.delete_implementing_entity(db, entity_id)
            logger.info(f"Deleted implementing entity: ID {entity_id}")
            return {
                "message": "Ente eliminato con successo",
                "entity_id": entity_id,
                "soft_delete": False
            }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting implementing entity {entity_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Errore nell'eliminazione dell'ente"
        )


@router.get("/{entity_id}/projects", response_model=List[schemas.Project])
def get_entity_projects(
    entity_id: int,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    RECUPERA TUTTI I PROGETTI DI UN ENTE ATTUATORE

    Parametri:
    - status_filter: Filtra per stato progetto (active, completed, paused, cancelled)
    """
    entity = crud.get_implementing_entity(db, entity_id)
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ente attuatore non trovato"
        )

    projects = crud.get_projects_by_entity(db, entity_id, status=status_filter)
    return projects


# ====================================================
# SEDI MULTIPLE
# ====================================================

@router.get("/{entity_id}/locations", response_model=List[schemas.ImplementingEntityLocation])
def list_entity_locations(entity_id: int, db: Session = Depends(get_db)):
    _get_entity_or_404(db, entity_id)
    return db.query(models.ImplementingEntityLocation).filter(
        models.ImplementingEntityLocation.ente_id == entity_id
    ).order_by(
        models.ImplementingEntityLocation.is_active.desc(),
        models.ImplementingEntityLocation.tipo,
        models.ImplementingEntityLocation.id,
    ).all()


@router.post(
    "/{entity_id}/locations",
    response_model=schemas.ImplementingEntityLocation,
    status_code=status.HTTP_201_CREATED,
)
def create_entity_location(
    entity_id: int,
    payload: schemas.ImplementingEntityLocationCreate,
    db: Session = Depends(get_db),
):
    entity = _get_entity_or_404(db, entity_id)
    _ensure_location_uniqueness(
        db,
        entity_id=entity_id,
        tipo=payload.tipo,
        is_principale=payload.is_principale,
        is_active=payload.is_active,
    )
    location = models.ImplementingEntityLocation(
        ente_id=entity_id,
        **payload.model_dump(),
    )
    db.add(location)
    _sync_legacy_legal_location(entity, location)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Vincolo sede legale/principale non rispettato")
    db.refresh(location)
    return location


@router.put("/{entity_id}/locations/{location_id}", response_model=schemas.ImplementingEntityLocation)
def update_entity_location(
    entity_id: int,
    location_id: int,
    payload: schemas.ImplementingEntityLocationUpdate,
    db: Session = Depends(get_db),
):
    entity = _get_entity_or_404(db, entity_id)
    location = db.query(models.ImplementingEntityLocation).filter(
        models.ImplementingEntityLocation.id == location_id,
        models.ImplementingEntityLocation.ente_id == entity_id,
    ).first()
    if not location:
        raise HTTPException(status_code=404, detail="Sede non trovata")
    values = payload.model_dump(exclude_unset=True)
    final_tipo = values.get("tipo", location.tipo)
    final_principale = values.get("is_principale", location.is_principale)
    final_active = values.get("is_active", location.is_active)
    final_attiva_dal = values.get("attiva_dal", location.attiva_dal)
    final_dismessa_dal = values.get("dismessa_dal", location.dismessa_dal)
    final_accreditamento_data = values.get(
        "accreditamento_data", location.accreditamento_data
    )
    final_accreditamento_scadenza = values.get(
        "accreditamento_scadenza", location.accreditamento_scadenza
    )
    if final_attiva_dal and final_dismessa_dal and final_dismessa_dal < final_attiva_dal:
        raise HTTPException(
            status_code=422,
            detail="La data di dismissione non può precedere la data di attivazione",
        )
    if (
        final_accreditamento_data
        and final_accreditamento_scadenza
        and final_accreditamento_scadenza < final_accreditamento_data
    ):
        raise HTTPException(
            status_code=422,
            detail="La scadenza accreditamento non può precedere la data iniziale",
        )
    _ensure_location_uniqueness(
        db,
        entity_id=entity_id,
        tipo=final_tipo,
        is_principale=final_principale,
        is_active=final_active,
        exclude_id=location.id,
    )
    for key, value in values.items():
        setattr(location, key, value)
    if not location.is_active and not location.dismessa_dal:
        location.dismessa_dal = date.today()
    _sync_legacy_legal_location(entity, location)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Vincolo sede legale/principale non rispettato")
    db.refresh(location)
    return location


@router.delete("/{entity_id}/locations/{location_id}")
def deactivate_entity_location(
    entity_id: int,
    location_id: int,
    db: Session = Depends(get_db),
):
    _get_entity_or_404(db, entity_id)
    location = db.query(models.ImplementingEntityLocation).filter(
        models.ImplementingEntityLocation.id == location_id,
        models.ImplementingEntityLocation.ente_id == entity_id,
    ).first()
    if not location:
        raise HTTPException(status_code=404, detail="Sede non trovata")
    location.is_active = False
    location.is_principale = False
    location.dismessa_dal = location.dismessa_dal or date.today()
    db.commit()
    return {"message": "Sede disattivata", "location_id": location_id}


# ====================================================
# CONTI CORRENTI E ACCESSO IBAN
# ====================================================

def _ensure_default_account_uniqueness(
    db: Session,
    *,
    entity_id: int,
    is_predefinito: bool,
    is_active: bool,
    exclude_id: int | None = None,
) -> None:
    if not is_predefinito or not is_active:
        return
    query = db.query(models.ImplementingEntityBankAccount).filter(
        models.ImplementingEntityBankAccount.ente_id == entity_id,
        models.ImplementingEntityBankAccount.is_predefinito.is_(True),
        models.ImplementingEntityBankAccount.is_active.is_(True),
    )
    if exclude_id is not None:
        query = query.filter(models.ImplementingEntityBankAccount.id != exclude_id)
    if query.first():
        raise HTTPException(status_code=409, detail="È consentito un solo conto predefinito attivo")


@router.get("/{entity_id}/accounts", response_model=List[schemas.ImplementingEntityBankAccount])
def list_entity_accounts(entity_id: int, db: Session = Depends(get_db)):
    _get_entity_or_404(db, entity_id)
    accounts = db.query(models.ImplementingEntityBankAccount).filter(
        models.ImplementingEntityBankAccount.ente_id == entity_id
    ).order_by(
        models.ImplementingEntityBankAccount.is_active.desc(),
        models.ImplementingEntityBankAccount.is_predefinito.desc(),
        models.ImplementingEntityBankAccount.id,
    ).all()
    return [_account_payload(account) for account in accounts]


@router.post(
    "/{entity_id}/accounts",
    response_model=schemas.ImplementingEntityBankAccount,
    status_code=status.HTTP_201_CREATED,
)
def create_entity_account(
    entity_id: int,
    payload: schemas.ImplementingEntityBankAccountCreate,
    db: Session = Depends(get_db),
):
    entity = _get_entity_or_404(db, entity_id)
    _ensure_default_account_uniqueness(
        db,
        entity_id=entity_id,
        is_predefinito=payload.is_predefinito,
        is_active=payload.is_active,
    )
    account = models.ImplementingEntityBankAccount(ente_id=entity_id, **payload.model_dump())
    db.add(account)
    _sync_legacy_default_account(entity, account)
    try:
        db.commit()
    except (IntegrityError, ValueError):
        db.rollback()
        raise HTTPException(status_code=409, detail="Conto corrente non valido o già predefinito")
    db.refresh(account)
    return _account_payload(account)


@router.put(
    "/{entity_id}/accounts/{account_id}",
    response_model=schemas.ImplementingEntityBankAccount,
)
def update_entity_account(
    entity_id: int,
    account_id: int,
    payload: schemas.ImplementingEntityBankAccountUpdate,
    db: Session = Depends(get_db),
):
    entity = _get_entity_or_404(db, entity_id)
    account = db.query(models.ImplementingEntityBankAccount).filter(
        models.ImplementingEntityBankAccount.id == account_id,
        models.ImplementingEntityBankAccount.ente_id == entity_id,
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Conto corrente non trovato")
    values = payload.model_dump(exclude_unset=True)
    _ensure_default_account_uniqueness(
        db,
        entity_id=entity_id,
        is_predefinito=values.get("is_predefinito", account.is_predefinito),
        is_active=values.get("is_active", account.is_active),
        exclude_id=account.id,
    )
    for key, value in values.items():
        setattr(account, key, value)
    _sync_legacy_default_account(entity, account)
    try:
        db.commit()
    except (IntegrityError, ValueError):
        db.rollback()
        raise HTTPException(status_code=409, detail="Conto corrente non valido o già predefinito")
    db.refresh(account)
    return _account_payload(account)


@router.delete("/{entity_id}/accounts/{account_id}")
def deactivate_entity_account(
    entity_id: int,
    account_id: int,
    db: Session = Depends(get_db),
):
    _get_entity_or_404(db, entity_id)
    account = db.query(models.ImplementingEntityBankAccount).filter(
        models.ImplementingEntityBankAccount.id == account_id,
        models.ImplementingEntityBankAccount.ente_id == entity_id,
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Conto corrente non trovato")
    account.is_active = False
    account.is_predefinito = False
    db.commit()
    return {"message": "Conto corrente disattivato", "account_id": account_id}


@router.get("/{entity_id}/accounts/{account_id}/iban")
def reveal_entity_account_iban(
    entity_id: int,
    account_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account = db.query(models.ImplementingEntityBankAccount).filter(
        models.ImplementingEntityBankAccount.id == account_id,
        models.ImplementingEntityBankAccount.ente_id == entity_id,
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Conto corrente non trovato")
    allowed = normalize_role(current_user.role) in {
        UserRole.ADMIN.value,
        UserRole.OPERATORE.value,
    }
    write_audit_log(
        db,
        user_id=current_user.id,
        azione="iban_reveal",
        risorsa_tipo="implementing_entity_bank_account",
        risorsa_id=account.id,
        dati_dopo={"authorized": allowed, "entity_id": entity_id},
        ip_address=request.client.host if request.client else None,
        esito="success" if allowed else "denied",
    )
    db.commit()
    if not allowed:
        raise HTTPException(status_code=403, detail="Ruolo non autorizzato a visualizzare l'IBAN")
    return {"account_id": account.id, "iban": account.iban}


# ====================================================
# ANTEPRIMA CONFIGURAZIONE STAMPA
# ====================================================

@router.post("/{entity_id}/print-preview")
def preview_entity_print_configuration(
    entity_id: int,
    config: schemas.ImplementingEntityPrintConfig | None = Body(default=None),
    db: Session = Depends(get_db),
):
    entity = _get_entity_or_404(db, entity_id)
    values = {
        key: getattr(entity, key)
        for key in (
            "ragione_sociale",
            "partita_iva",
            "logo_path",
            "letterhead_path",
            "print_margin_top_mm",
            "print_margin_bottom_mm",
            "print_margin_left_mm",
            "print_margin_right_mm",
            "print_logo_width_mm",
            "print_logo_height_mm",
            "print_logo_x_mm",
            "print_logo_y_mm",
            "print_letterhead_pages",
            "print_footer",
        )
    }
    values["indirizzo_completo"] = entity.indirizzo_completo
    if config is not None:
        values.update(config.model_dump())
    preview_entity = SimpleNamespace(**values)
    output = generate_print_preview(preview_entity)
    return StreamingResponse(
        output,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="anteprima_ente_{entity_id}.pdf"',
            "Cache-Control": "no-store",
        },
    )


# ====================================================
# ENDPOINTS PER UPLOAD LOGO ENTE ATTUATORE
# ====================================================

@router.post("/{entity_id}/upload-logo")
async def upload_logo_ente_attuatore(
    entity_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    UPLOAD LOGO per ente attuatore

    - Formati permessi: PNG, JPG, JPEG, GIF
    - Dimensione massima: 5MB
    """
    from file_upload import save_uploaded_file, delete_file

    entity = crud.get_implementing_entity(db, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Ente attuatore non trovato")

    # ReportLab renderizza in modo affidabile solo formati raster. Tenere
    # questa lista allineata a file_upload.ALLOWED_ENTITY_LOGO_EXTENSIONS.
    allowed_extensions = ['.png', '.jpg', '.jpeg', '.gif']
    file_extension = os.path.splitext(file.filename)[1].lower()
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Formato file non supportato. Formati ammessi: {', '.join(allowed_extensions)}"
        )

    if entity.logo_path:
        try:
            await delete_file(entity.logo_path)
        except Exception as e:
            logger.warning(f"Errore eliminazione vecchio logo: {e}")

    try:
        filename, filepath = await save_uploaded_file(file, entity_id, "logo_ente")

        entity.logo_filename = filename
        entity.logo_path = filepath
        entity.logo_uploaded_at = datetime.now()
        db.commit()
        db.refresh(entity)

        logger.info(f"Logo uploadato per ente attuatore {entity_id}")

        return {
            "message": "Logo caricato con successo",
            "filename": filename,
            "uploaded_at": entity.logo_uploaded_at
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Errore upload logo: {e}")
        raise HTTPException(status_code=500, detail=f"Errore upload: {str(e)}")


@router.get("/{entity_id}/download-logo")
async def download_logo_ente_attuatore(
    entity_id: int,
    db: Session = Depends(get_db)
):
    """DOWNLOAD LOGO di un ente attuatore"""
    from file_upload import get_file_path

    entity = crud.get_implementing_entity(db, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Ente attuatore non trovato")

    if not entity.logo_path:
        raise HTTPException(status_code=404, detail="Nessun logo caricato per questo ente")

    file_path = get_file_path(entity.logo_path)

    return FileResponse(
        path=file_path,
        filename=entity.logo_filename,
        media_type="application/octet-stream"
    )


@router.delete("/{entity_id}/delete-logo")
async def delete_logo_ente_attuatore(
    entity_id: int,
    db: Session = Depends(get_db)
):
    """ELIMINA LOGO di un ente attuatore"""
    from file_upload import delete_file

    entity = crud.get_implementing_entity(db, entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Ente attuatore non trovato")

    if not entity.logo_path:
        raise HTTPException(status_code=404, detail="Nessun logo da eliminare")

    await delete_file(entity.logo_path)

    entity.logo_filename = None
    entity.logo_path = None
    entity.logo_uploaded_at = None
    db.commit()

    return {"message": "Logo eliminato con successo"}


# ====================================================
# CARTA INTESTATA (indipendente dal logo)
# ====================================================

@router.post("/{entity_id}/upload-letterhead")
async def upload_entity_letterhead(
    entity_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    from file_upload import delete_file, save_uploaded_file

    entity = _get_entity_or_404(db, entity_id)
    previous_path = entity.letterhead_path
    filename, filepath = await save_uploaded_file(file, entity_id, "carta_intestata_ente")
    entity.letterhead_filename = filename
    entity.letterhead_path = filepath
    entity.letterhead_uploaded_at = datetime.now()
    db.commit()
    db.refresh(entity)
    if previous_path and previous_path != filepath:
        await delete_file(previous_path)
    return {
        "message": "Carta intestata caricata con successo",
        "filename": filename,
        "uploaded_at": entity.letterhead_uploaded_at,
    }


@router.get("/{entity_id}/download-letterhead")
async def download_entity_letterhead(entity_id: int, db: Session = Depends(get_db)):
    from file_upload import get_file_path

    entity = _get_entity_or_404(db, entity_id)
    if not entity.letterhead_path:
        raise HTTPException(status_code=404, detail="Nessuna carta intestata caricata")
    path = get_file_path(entity.letterhead_path)
    media_type = "application/pdf" if path.suffix.lower() == ".pdf" else "image/*"
    return FileResponse(path=path, filename=entity.letterhead_filename, media_type=media_type)


@router.delete("/{entity_id}/delete-letterhead")
async def delete_entity_letterhead(entity_id: int, db: Session = Depends(get_db)):
    from file_upload import delete_file

    entity = _get_entity_or_404(db, entity_id)
    if not entity.letterhead_path:
        raise HTTPException(status_code=404, detail="Nessuna carta intestata da eliminare")
    await delete_file(entity.letterhead_path)
    entity.letterhead_filename = None
    entity.letterhead_path = None
    entity.letterhead_uploaded_at = None
    db.commit()
    return {"message": "Carta intestata eliminata con successo"}
