"""API checklist operative e playbook."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models
from auth import User, get_current_user
from database import get_db
from schemas_attivita import AttivitaPatch, PlaybookCreate, StatoChange, VoceCreate
from services.attivita import aggiorna_attivita, cambia_stato, lista_attivita
from services.playbook import add_voce_manuale, create_next_version, create_playbook, get_playbook_operativo, review_voce

router = APIRouter(prefix="/api/v1/attivita", tags=["Attività"])

def require_attivita_write(user: User = Depends(get_current_user)):
    if user.role not in {"admin", "manager", "operatore"}: raise HTTPException(403, "Ruolo non autorizzato")
    return user
def require_attivita_admin(user: User = Depends(get_current_user)):
    if user.role != "admin": raise HTTPException(403, "Solo admin")
    return user
def _domain(call):
    try: return call()
    except ValueError as exc: raise HTTPException(409, str(exc)) from exc

@router.post("/playbooks")
def post_playbook(body: PlaybookCreate, db: Session = Depends(get_db), user: User = Depends(require_attivita_admin)):
    return _domain(lambda: create_playbook(db, **body.model_dump(), created_by_user_id=user.id))
@router.get("/playbooks")
def list_playbooks(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    return db.query(models.Playbook).filter_by(is_active=True).order_by(models.Playbook.fondo, models.Playbook.nome).all()
@router.get("/playbooks/{playbook_id}/voci")
def list_voci(playbook_id: int, stato: str | None = "validata", db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    p = db.get(models.Playbook, playbook_id)
    if not p or not p.versione_corrente: raise HTTPException(404, "Playbook non trovato")
    stati_ammessi = {"proposta", "validata", "rifiutata", "superata"}
    if stato is not None and stato not in stati_ammessi:
        raise HTTPException(422, "Stato voce non valido")
    return [v for v in p.versione_corrente.voci if stato is None or v.stato == stato]
@router.post("/playbooks/{playbook_id}/voci")
def post_voce(playbook_id: int, body: VoceCreate, db: Session = Depends(get_db), user: User = Depends(require_attivita_admin)):
    p = db.get(models.Playbook, playbook_id)
    if not p or not p.versione_corrente: raise HTTPException(404, "Playbook non trovato")
    return _domain(lambda: add_voce_manuale(db, versione_id=p.versione_corrente_id, created_by_user_id=user.id, **body.model_dump()))
@router.post("/playbooks/voci/{voce_id}/review")
def post_review(voce_id: int, azione: str, db: Session = Depends(get_db), user: User = Depends(require_attivita_admin)):
    return _domain(lambda: review_voce(db, voce_id=voce_id, azione=azione, reviewer_user_id=user.id))
@router.post("/playbooks/{playbook_id}/versioni")
def post_version(playbook_id: int, note: str | None = None, db: Session = Depends(get_db), user: User = Depends(require_attivita_admin)):
    return _domain(lambda: create_next_version(db, playbook_id=playbook_id, note=note, created_by_user_id=user.id))

@router.get("/projects/{project_id}")
def project_activities(project_id: int, fase: str | None = None, stato: str | None = None, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    return lista_attivita(db, project_id=project_id, fase=fase, stato=stato)
@router.post("/{attivita_id}/stato")
def change_state(attivita_id: int, body: StatoChange, db: Session = Depends(get_db), user: User = Depends(require_attivita_write)):
    return _domain(lambda: cambia_stato(db, attivita_id=attivita_id, nuovo_stato=body.nuovo_stato.value, user_id=user.id, nota=body.nota))
@router.patch("/{attivita_id}")
def patch_activity(attivita_id: int, body: AttivitaPatch, db: Session = Depends(get_db), user: User = Depends(require_attivita_write)):
    return _domain(lambda: aggiorna_attivita(db, attivita_id=attivita_id, user_id=user.id, **body.model_dump(exclude_unset=True)))
@router.get("/{attivita_id}/eventi")
def events(attivita_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    activity = db.get(models.AttivitaOperativa, attivita_id)
    if not activity: raise HTTPException(404, "Attività non trovata")
    return activity.eventi
