"""Mutazioni atomiche della checklist e relativo event log."""
from datetime import datetime, timezone
from sqlalchemy import and_
import models

ATTIVITA_STATE_TRANSITIONS = {
    "da_fare": {"in_corso", "completata", "non_applicabile"},
    "in_corso": {"completata", "da_fare", "non_applicabile"},
    "completata": {"da_fare"}, "non_applicabile": {"da_fare"},
}

def _event(db, activity, kind, *, user_id=None, agent=None, payload=None):
    db.add(models.AttivitaEvento(attivita_id=activity.id, tipo_evento=kind, payload=payload,
                                 actor_user_id=user_id, actor_agente=agent))

def apply_piano_attivita(db, suggestion, *, user_id):
    if not user_id: raise ValueError("Applicatore umano obbligatorio")
    import json
    payload = json.loads(suggestion.auto_fix_payload or "{}")
    project_id = payload.get("project_id") or suggestion.entity_id
    created = existing = 0
    for item in payload.get("attivita", []):
        q = db.query(models.AttivitaOperativa).filter_by(project_id=project_id, fase=item["fase"], titolo=item["titolo"])
        if q.first(): existing += 1; continue
        activity = models.AttivitaOperativa(project_id=project_id, avviso_revisione_id=item.get("avviso_revisione_id"),
            playbook_voce_id=item.get("playbook_voce_id"), avviso_scadenza_id=item.get("avviso_scadenza_id"),
            fase=item["fase"], ordine=item.get("ordine", 0), titolo=item["titolo"], descrizione=item.get("descrizione"),
            scadenza=item.get("scadenza"), tassativa=item.get("tassativa", False), origin_suggestion_id=suggestion.id,
            created_by_user_id=user_id)
        db.add(activity); db.flush(); _event(db, activity, "creata", user_id=user_id); created += 1
    db.commit(); return {"create": created, "esistenti": existing}

def cambia_stato(db, *, attivita_id, nuovo_stato, user_id, nota=None):
    if not user_id:
        raise ValueError("Utente attore obbligatorio")
    activity = db.query(models.AttivitaOperativa).filter_by(id=attivita_id).with_for_update().one_or_none()
    if not activity: raise ValueError("Attività non trovata")
    if nuovo_stato not in ATTIVITA_STATE_TRANSITIONS.get(activity.stato, set()):
        raise ValueError(f"Transizione {activity.stato} -> {nuovo_stato} non ammessa")
    old = activity.stato; activity.stato = nuovo_stato
    if nuovo_stato == "completata": activity.completata_da_user_id = user_id; activity.completata_il = datetime.now(timezone.utc)
    elif old == "completata": activity.completata_da_user_id = None; activity.completata_il = None
    _event(db, activity, "riaperta" if old == "completata" and nuovo_stato == "da_fare" else "stato_cambiato",
           user_id=user_id, payload={"da": old, "a": nuovo_stato, "nota": nota} if nota else {"da": old, "a": nuovo_stato})
    db.commit(); return activity

def aggiorna_attivita(db, *, attivita_id, user_id, scadenza=None, assegnatario=None, note=None):
    if not user_id:
        raise ValueError("Utente attore obbligatorio")
    activity = db.get(models.AttivitaOperativa, attivita_id)
    if not activity: raise ValueError("Attività non trovata")
    if scadenza is not None and scadenza != activity.scadenza: activity.scadenza = scadenza; _event(db, activity, "scadenza_modificata", user_id=user_id, payload={"scadenza": str(scadenza)})
    if assegnatario is not None and assegnatario != activity.assegnatario_user_id: activity.assegnatario_user_id = assegnatario; _event(db, activity, "assegnata", user_id=user_id, payload={"user_id": assegnatario})
    if note is not None and note != activity.note: activity.note = note; _event(db, activity, "nota", user_id=user_id, payload={"nota": note})
    db.commit(); return activity

def lista_attivita(db, *, project_id, fase=None, stato=None):
    q = db.query(models.AttivitaOperativa).filter(models.AttivitaOperativa.project_id == project_id)
    if fase: q = q.filter(models.AttivitaOperativa.fase == fase)
    if stato: q = q.filter(models.AttivitaOperativa.stato == stato)
    return q.order_by(models.AttivitaOperativa.fase, models.AttivitaOperativa.ordine, models.AttivitaOperativa.scadenza).all()
