"""Planner deterministico: legge dati validati e propone, non persiste."""
from datetime import date
import models
from services.playbook import get_playbook_operativo

PHASE = {"presentazione":"presentazione", "avvio":"avvio", "chiusura":"gestione", "rendicontazione":"rendicontazione", "altro":"gestione"}
ANCHOR = {"presentazione":"presentazione", "avvio":"avvio", "chiusura":"chiusura", "rendicontazione":"rendicontazione"}

def collect_activity_planner_suggestions(db, *, project_id, input_payload=None):
    project = db.get(models.Project, project_id)
    if not project: raise ValueError("Progetto non trovato")
    revision_id = project.avviso_revisione_id
    if not revision_id and project.avviso_id:
        avviso = db.get(models.Avviso, project.avviso_id); revision_id = avviso.revisione_corrente_id if avviso else None
    if not revision_id:
        return {"summary": {"reason":"progetto senza avviso/revisione", "count":0}, "suggestions": []}
    revision = db.get(models.AvvisoRevisione, revision_id)
    if not revision: return {"summary":{"reason":"revisione non trovata", "count":0}, "suggestions":[]}
    items, seen = [], set()
    deadlines = db.query(models.AvvisoScadenza).filter_by(avviso_revisione_id=revision_id, stato="validata").all()
    anchors = {d.tipo: d.data.date() for d in deadlines}
    for d in deadlines:
        item = {"fase":PHASE.get(d.tipo,"gestione"), "ordine":0, "titolo":d.descrizione[:300], "descrizione":d.descrizione,
                "scadenza":d.data.date().isoformat(), "tassativa":d.tassativa, "avviso_scadenza_id":d.id, "avviso_revisione_id":revision_id}
        key = (item["fase"], item["titolo"])
        if key not in seen: seen.add(key); items.append(item)
    avviso = revision.avviso
    for voce in get_playbook_operativo(db, fondo=avviso.fondo, ente_erogatore=avviso.ente_erogatore):
        applicability = voce.applicabilita or {}
        if applicability.get("fondo") and applicability["fondo"] != avviso.fondo: continue
        if applicability.get("ente_erogatore") and applicability["ente_erogatore"] != avviso.ente_erogatore: continue
        content = voce.contenuto or {}; item = {"fase":voce.fase, "ordine":voce.ordine, "titolo":voce.titolo, "descrizione":voce.descrizione,
            "playbook_voce_id":voce.id, "avviso_revisione_id":revision_id, "tassativa":False}
        if content.get("tipo") == "scadenza_relativa":
            anchor = anchors.get(content.get("ancora")); item["scadenza"] = (anchor.fromordinal(anchor.toordinal() + int(content.get("offset_giorni", 0))).isoformat() if anchor else None)
            if not anchor: item["needs_review"] = True
        key = (item["fase"], item["titolo"])
        if key not in seen: seen.add(key); items.append(item)
    existing = {(a.fase, a.titolo) for a in db.query(models.AttivitaOperativa).filter_by(project_id=project_id).all()}
    items = [i for i in items if (i["fase"], i["titolo"]) not in existing]
    if not items: return {"summary":{"reason":"nessuna attività applicabile nuova", "count":0}, "suggestions":[]}
    return {"summary":{"count":len(items), "revision_id":revision_id}, "suggestions":[{
        "suggestion_type":"piano_attivita", "entity_type":"project", "entity_id":project_id, "severity":"medium",
        "title":"Piano attività proposto", "description":f"{len(items)} attività da verificare", "confidence_score":1.0,
        "auto_fix_available":True, "auto_fix_payload":{"kind":"attivita_piano", "project_id":project_id, "attivita":items}}]}
