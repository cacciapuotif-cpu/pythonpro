"""Router per gestione aziende clienti."""

from fastapi import APIRouter, Depends, File, HTTPException, Request, status, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.exc import IntegrityError
from typing import List, Optional
import logging
from auth import User, get_current_user, normalize_role, UserRole
from services.azienda_deletion import build_azienda_deletion_impact, permanently_delete_azienda
from services.delivery_locations import create_azienda_sede_operativa
from services.azienda_excel import build_workbook, import_workbook, preview_workbook
from services.azienda_field_spec import public_spec
from services.audit_log import write_audit_log

import crud
import models
import schemas
from database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/aziende-clienti", tags=["Aziende Clienti"])

class AziendaPermanentDeleteRequest(BaseModel):
    confirmation_phrase: str
    linked_records_confirmed: bool = False

def _require_write(current_user: User = Depends(get_current_user)) -> User:
    if normalize_role(current_user.role) not in {UserRole.ADMIN.value, UserRole.OPERATORE.value}:
        raise HTTPException(status_code=403, detail="Solo amministratori e operatori possono modificare le aziende")
    return current_user

def _require_admin(current_user: User = Depends(get_current_user)) -> User:
    if normalize_role(current_user.role) != UserRole.ADMIN.value:
        raise HTTPException(status_code=403, detail="Solo un amministratore può eliminare definitivamente un'azienda")
    return current_user

SORT_FIELDS = {"ragione_sociale", "citta", "created_at", "partita_iva"}


@router.get("/field-spec")
def get_azienda_field_spec(_user: User = Depends(get_current_user)):
    """Unica fonte di etichette, gruppi e regole usata anche da Excel."""
    return public_spec()


@router.get("/import-template.xlsx")
def download_azienda_import_template(_user: User = Depends(_require_write)):
    workbook = build_workbook(include_example=True)
    return StreamingResponse(
        workbook,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="template_aziende_clienti.xlsx"'},
    )


async def _read_excel_upload(file: UploadFile) -> bytes:
    name = (file.filename or "").lower()
    if not name.endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="Carica un file Excel .xlsx")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Il file Excel è vuoto")
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Il file supera il limite di 10 MB")
    return content


@router.post("/import-preview")
async def preview_azienda_import(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user: User = Depends(_require_write),
):
    try:
        return preview_workbook(await _read_excel_upload(file), db)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Preview import aziende fallita")
        raise HTTPException(status_code=400, detail=f"File Excel non leggibile: {exc}")


@router.post("/import-execute")
async def execute_azienda_import(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user: User = Depends(_require_write),
):
    try:
        return import_workbook(await _read_excel_upload(file), db)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Import aziende fallito")
        raise HTTPException(status_code=400, detail=f"Importazione non completata: {exc}")


@router.get("/export.xlsx")
def export_aziende_excel(
    db: Session = Depends(get_db),
    _user: User = Depends(_require_admin),
):
    """Export round-trip. L'IBAN integrale è limitato agli amministratori."""
    companies = db.query(models.AziendaCliente).options(
        joinedload(models.AziendaCliente.agenzia),
        joinedload(models.AziendaCliente.consulente),
        selectinload(models.AziendaCliente.sedi_operative),
        selectinload(models.AziendaCliente.conti_correnti),
        selectinload(models.AziendaCliente.fund_memberships),
    ).order_by(models.AziendaCliente.ragione_sociale).all()
    workbook = build_workbook(companies, include_example=True, reveal_sensitive=True)
    return StreamingResponse(
        workbook,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="aziende_clienti_export.xlsx"'},
    )


@router.post("/", response_model=schemas.AziendaCliente, status_code=status.HTTP_201_CREATED)
def create_azienda_cliente(azienda: schemas.AziendaClienteCreate, db: Session = Depends(get_db)):
    """Crea una nuova azienda cliente."""
    try:
        if azienda.partita_iva:
            piva_conflict = crud.find_partita_iva_conflict(
                db,
                azienda.partita_iva,
                entity_type="azienda_cliente",
            )
            if piva_conflict:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=piva_conflict["message"]
                )
        db_obj = crud.create_azienda_cliente(db, azienda)
        logger.info(f"Azienda creata: {db_obj.ragione_sociale} (ID: {db_obj.id})")
        return db_obj
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Errore creazione azienda cliente: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Errore nella creazione dell'azienda cliente")


@router.get("/", response_model=schemas.PaginatedResponse[schemas.AziendaCliente])
def get_aziende_clienti(
    search: Optional[str] = Query(None, description="Ricerca su ragione sociale, PEC, P.IVA"),
    citta: Optional[str] = Query(None),
    agenzia_id: Optional[int] = Query(None),
    consulente_id: Optional[int] = Query(None),
    attivo: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort_by: str = Query("ragione_sociale"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db)
):
    """Lista aziende clienti paginata con filtri e ordinamento."""
    if sort_by not in SORT_FIELDS:
        sort_by = "ragione_sociale"
    items, total, pages = crud.get_aziende_clienti(
        db, search=search, citta=citta, agenzia_id=agenzia_id, consulente_id=consulente_id,
        attivo=attivo, page=page, limit=limit, sort_by=sort_by, order=order
    )
    return schemas.PaginatedResponse(
        items=items,
        total=total,
        page=page,
        pages=pages,
        has_next=page < pages
    )


@router.get("/search", response_model=List[schemas.AziendaCliente])
def search_aziende(
    q: str = Query(..., min_length=2, description="Testo di ricerca (min 2 caratteri)"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """Full-text search rapida su ragione_sociale (per autocomplete)."""
    items, _, _ = crud.get_aziende_clienti(db, search=q, attivo=True, page=1, limit=limit)
    return items


@router.get("/{azienda_id}", response_model=schemas.AziendaClienteWithConsulente)
def get_azienda_cliente(azienda_id: int, db: Session = Depends(get_db)):
    db_obj = crud.get_azienda_cliente(db, azienda_id)
    if not db_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Azienda cliente non trovata")
    return db_obj


@router.get("/{azienda_id}/conti-correnti/{account_id}/iban")
def reveal_azienda_account_iban(
    azienda_id: int,
    account_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account = db.query(models.AziendaClienteBankAccount).filter(
        models.AziendaClienteBankAccount.id == account_id,
        models.AziendaClienteBankAccount.azienda_cliente_id == azienda_id,
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Conto corrente non trovato")
    allowed = normalize_role(current_user.role) in {UserRole.ADMIN.value, UserRole.OPERATORE.value}
    write_audit_log(
        db,
        user_id=current_user.id,
        azione="iban_reveal",
        risorsa_tipo="azienda_cliente_bank_account",
        risorsa_id=account.id,
        dati_dopo={"authorized": allowed, "azienda_cliente_id": azienda_id},
        ip_address=request.client.host if request.client else None,
        esito="success" if allowed else "denied",
    )
    db.commit()
    if not allowed:
        raise HTTPException(status_code=403, detail="Ruolo non autorizzato a visualizzare l'IBAN")
    return {"id": account.id, "iban": account.iban}


@router.post(
    "/{azienda_id}/sedi-operative",
    response_model=schemas.AziendaClienteSedeOperativa,
    status_code=status.HTTP_201_CREATED,
)
def add_azienda_sede_operativa(
    azienda_id: int,
    sede: schemas.AziendaClienteSedeOperativaWrite,
    db: Session = Depends(get_db),
    _user: User = Depends(_require_write),
):
    """Crea una sede riusabile nell'anagrafica dell'azienda."""
    try:
        return create_azienda_sede_operativa(db, azienda_id, sede)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.put("/{azienda_id}", response_model=schemas.AziendaCliente)
def update_azienda_cliente(azienda_id: int, azienda: schemas.AziendaClienteUpdate,
                            db: Session = Depends(get_db)):
    try:
        if azienda.partita_iva:
            piva_conflict = crud.find_partita_iva_conflict(
                db,
                azienda.partita_iva,
                entity_type="azienda_cliente",
                entity_id=azienda_id,
            )
            if piva_conflict:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=piva_conflict["message"]
                )
        db_obj = crud.update_azienda_cliente(db, azienda_id, azienda)
        if not db_obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="Azienda cliente non trovata")
        return db_obj
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{azienda_id}", response_model=schemas.AziendaCliente)
def delete_azienda_cliente(azienda_id: int, db: Session = Depends(get_db), _user: User = Depends(_require_write)):
    """Soft delete: imposta attivo=False."""
    try:
        db_obj = crud.delete_azienda_cliente(db, azienda_id)
        if not db_obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="Azienda cliente non trovata")
        return db_obj
    except HTTPException:
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossibile eliminare: esistono preventivi o ordini collegati a questa azienda. Eliminali prima."
        )

@router.get("/{azienda_id}/deletion-impact")
def azienda_deletion_impact(azienda_id: int, db: Session = Depends(get_db), _user: User = Depends(_require_admin)):
    impact = build_azienda_deletion_impact(db, azienda_id)
    if impact is None:
        raise HTTPException(status_code=404, detail="Azienda cliente non trovata")
    return impact

@router.delete("/{azienda_id}/permanent")
def hard_delete_azienda(azienda_id: int, confirmation: AziendaPermanentDeleteRequest, db: Session = Depends(get_db), current_user: User = Depends(_require_admin)):
    impact = build_azienda_deletion_impact(db, azienda_id)
    if impact is None:
        raise HTTPException(status_code=404, detail="Azienda cliente non trovata")
    if not impact["eliminabile"]:
        raise HTTPException(status_code=409, detail={"message": "Azienda non eliminabile: esistono collegamenti", "collegamenti": impact["collegamenti"], "impact": impact})
    if not confirmation.linked_records_confirmed or confirmation.confirmation_phrase != impact["confirmation_phrase"]:
        raise HTTPException(status_code=400, detail="Conferma collegamenti e frase obbligatorie")
    return permanently_delete_azienda(db, azienda_id, user_id=current_user.id)

@router.post("/bulk-permanent")
def bulk_hard_delete_aziende(azienda_ids: list[int], db: Session = Depends(get_db), current_user: User = Depends(_require_admin)):
    results = []
    for azienda_id in azienda_ids:
        impact = build_azienda_deletion_impact(db, azienda_id)
        if not impact:
            results.append({"id": azienda_id, "deleted": False, "reason": "non trovata"})
        elif not impact["eliminabile"]:
            results.append({"id": azienda_id, "deleted": False, "reason": "collegamenti", "collegamenti": impact["collegamenti"]})
        else:
            results.append({"id": azienda_id, "deleted": True, **permanently_delete_azienda(db, azienda_id, user_id=current_user.id)})
    return {"results": results}


@router.post("/bulk-import")
def bulk_import_aziende_clienti(
    aziende: List[schemas.AziendaClienteCreate],
    db: Session = Depends(get_db),
):
    success_count = 0
    error_count = 0
    errors = []
    created_ids = []

    for index, azienda_data in enumerate(aziende):
        try:
            existing = db.query(models.AziendaCliente).filter(
                models.AziendaCliente.partita_iva == azienda_data.partita_iva
            ).first() if azienda_data.partita_iva else None
            result = (
                crud.update_azienda_cliente(db, existing.id, schemas.AziendaClienteUpdate(**azienda_data.model_dump()))
                if existing else crud.create_azienda_cliente(db, azienda_data)
            )
            created_ids.append(result.id)
            success_count += 1
        except Exception as exc:
            db.rollback()
            error_count += 1
            errors.append({
                "index": index + 1,
                "name": azienda_data.ragione_sociale,
                "error": str(exc),
            })

    return {
        "success_count": success_count,
        "error_count": error_count,
        "total": len(aziende),
        "errors": errors,
        "created_ids": created_ids,
        "message": f"Importazione completata: {success_count} su {len(aziende)} aziende importate con successo",
    }
