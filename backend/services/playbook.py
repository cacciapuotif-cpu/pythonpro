"""Servizio di dominio per playbook dichiarativi versionati."""
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
import models

def _save(db, value):
    try:
        db.add(value); db.flush(); return value
    except IntegrityError as exc:
        db.rollback(); raise ValueError("Vincolo playbook non rispettato") from exc

def create_playbook(db, *, nome, fondo="altro", ente_erogatore=None, descrizione=None, created_by_user_id=None):
    p = _save(db, models.Playbook(nome=nome.strip(), fondo=fondo, ente_erogatore=ente_erogatore, descrizione=descrizione))
    v = _save(db, models.PlaybookVersione(playbook_id=p.id, numero_versione=1, created_by_user_id=created_by_user_id))
    p.versione_corrente_id = v.id; db.flush(); db.commit(); return p

def create_next_version(db, *, playbook_id, note=None, created_by_user_id=None):
    p = db.query(models.Playbook).filter(models.Playbook.id == playbook_id).with_for_update().one_or_none()
    if not p: raise ValueError("Playbook non trovato")
    last = db.query(func.max(models.PlaybookVersione.numero_versione)).filter_by(playbook_id=playbook_id).scalar() or 0
    previous = p.versione_corrente
    v = _save(db, models.PlaybookVersione(playbook_id=playbook_id, numero_versione=last + 1,
        versione_precedente_id=previous.id if previous else None, note=note, created_by_user_id=created_by_user_id))
    for old in (previous.voci if previous else []):
        if old.stato == "validata":
            db.add(models.PlaybookVoce(playbook_versione_id=v.id, fase=old.fase, ordine=old.ordine, titolo=old.titolo,
                descrizione=old.descrizione, contenuto=old.contenuto, schema_version=old.schema_version,
                applicabilita=old.applicabilita, origine=old.origine, testo_originale=old.testo_originale,
                riferimento_articolo=old.riferimento_articolo, stato="validata", confidence=old.confidence,
                validata_da_user_id=old.validata_da_user_id, validata_il=old.validata_il, carried_from_voce_id=old.id))
    p.versione_corrente_id = v.id; db.commit(); return v

def add_voce_manuale(db, *, versione_id, fase, ordine=0, titolo, contenuto, created_by_user_id,
                     descrizione=None, applicabilita=None, testo_originale=None, riferimento_articolo=None):
    now = datetime.now(timezone.utc)
    voce = models.PlaybookVoce(playbook_versione_id=versione_id, fase=fase, ordine=ordine, titolo=titolo.strip(),
        descrizione=descrizione, contenuto=contenuto, applicabilita=applicabilita, origine="manuale", stato="validata",
        testo_originale=testo_originale, riferimento_articolo=riferimento_articolo,
        validata_da_user_id=created_by_user_id, validata_il=now)
    _save(db, voce); db.commit(); return voce

def review_voce(db, *, voce_id, azione, reviewer_user_id, nota=None):
    if not reviewer_user_id: raise ValueError("Reviewer umano obbligatorio")
    voce = db.get(models.PlaybookVoce, voce_id)
    if not voce or voce.stato != "proposta": raise ValueError("Voce non proposta")
    if azione not in ("valida", "rifiuta"): raise ValueError("Azione review non supportata")
    voce.stato = "validata" if azione == "valida" else "rifiutata"
    voce.validata_da_user_id = reviewer_user_id if azione == "valida" else None
    voce.validata_il = datetime.now(timezone.utc) if azione == "valida" else None
    db.commit(); return voce

def get_playbook_operativo(db, *, fondo, ente_erogatore=None):
    q = db.query(models.Playbook).filter(models.Playbook.fondo == fondo, models.Playbook.is_active.is_(True))
    exact = q.filter(models.Playbook.ente_erogatore == ente_erogatore).first() if ente_erogatore else None
    p = exact or q.filter(models.Playbook.ente_erogatore.is_(None)).first()
    return [v for v in (p.versione_corrente.voci if p and p.versione_corrente else []) if v.stato == "validata"]

def apply_voce_suggestion(db, suggestion, *, user_id):
    if not user_id: raise ValueError("Reviewer umano obbligatorio")
    import json
    payload = json.loads(suggestion.auto_fix_payload or "{}")
    voce_data = payload.get("voce") or {}
    playbook_id = payload.get("playbook_id")
    if playbook_id:
        p = db.get(models.Playbook, playbook_id)
        if not p:
            raise ValueError("Playbook indicato non trovato")
    else:
        doc = db.get(models.AvvisoDocumento, payload.get("documento_id"))
        avviso = db.get(models.Avviso, doc.avviso_id) if doc else None
        if not avviso:
            raise ValueError("Documento o avviso sorgente non trovato")
        query = db.query(models.Playbook).filter_by(fondo=avviso.fondo, is_active=True)
        p = query.filter_by(ente_erogatore=avviso.ente_erogatore).first()
        p = p or query.filter(models.Playbook.ente_erogatore.is_(None)).first()
        if not p:
            p = create_playbook(
                db,
                nome=f"Playbook {avviso.ente_erogatore or avviso.fondo}",
                fondo=avviso.fondo,
                ente_erogatore=avviso.ente_erogatore,
                created_by_user_id=user_id,
            )
    v = p.versione_corrente or create_next_version(db, playbook_id=p.id, created_by_user_id=user_id)
    voce = models.PlaybookVoce(
        playbook_versione_id=v.id,
        fase=voce_data["fase"],
        ordine=voce_data.get("ordine", 0),
        titolo=voce_data["titolo"].strip(),
        descrizione=voce_data.get("descrizione"),
        contenuto=voce_data.get("contenuto", {"tipo": "attivita_semplice"}),
        origine="vademecum",
        stato="validata",
        testo_originale=voce_data.get("testo_originale"),
        riferimento_articolo=voce_data.get("riferimento_articolo"),
        confidence=voce_data.get("confidence"),
        needs_careful_review=bool(voce_data.get("needs_careful_review", False)),
        origin_suggestion_id=suggestion.id,
        validata_da_user_id=user_id,
        validata_il=datetime.now(timezone.utc),
    )
    _save(db, voce)
    db.commit()
    return {"applied": [f"playbook_voce:{voce.id}"], "skipped": []}
