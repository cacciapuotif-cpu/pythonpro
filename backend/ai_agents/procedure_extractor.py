"""Collector proposal-only per vademecum e manuali markdown."""
from pathlib import Path
from .llm import call_ollama_json
from .llm_schemas import ProcedureEstrattoLLM
from .prompts.procedure_extractor_v1 import SYSTEM_PROMPT, build_prompt

MAX_PROMPT_CHARS = 24000

def collect_procedure_extractor_suggestions(db, *, documento_id, input_payload=None):
    import models
    from services.avviso_ingest import clean_markdown, segment_markdown
    doc = db.get(models.AvvisoDocumento, documento_id)
    if not doc or doc.tipo not in {"vademecum", "manuale_gestione"} or Path(doc.file_path).suffix.lower() != ".md":
        raise ValueError("Il documento deve essere un vademecum/manuale markdown")
    text = clean_markdown(Path(doc.file_path).read_text(encoding="utf-8"))
    segments = segment_markdown(text); groups=[]; current=""
    for segment in segments:
        candidate = (current + "\n\n" + segment.testo).strip()
        if current and len(candidate) > MAX_PROMPT_CHARS: groups.append(current); current = segment.testo
        else: current = candidate
    if current: groups.append(current)
    suggestions=[]; failed=0
    for group in groups:
        try: parsed = ProcedureEstrattoLLM.model_validate(call_ollama_json(system_prompt=SYSTEM_PROMPT, user_prompt=build_prompt(group)))
        except Exception: failed += 1; continue
        for voce in parsed.voci:
            content = {"tipo":voce.tipo_contenuto}
            if voce.tipo_contenuto == "scadenza_relativa": content.update(ancora=voce.ancora or "avvio", offset_giorni=voce.offset_giorni or 0)
            if voce.tipo_contenuto == "documento": content["tipo_documento"] = voce.tipo_documento or voce.titolo
            suggestions.append({"suggestion_type":"playbook_voce", "entity_type":"avviso_documento", "entity_id":doc.id,
                "severity":"medium", "title":f"Voce playbook proposta: {voce.titolo}", "description":voce.descrizione,
                "confidence_score":voce.confidence, "needs_careful_review":voce.confidence < .75, "auto_fix_available":True,
                "auto_fix_payload":{"kind":"playbook_voce", "documento_id":doc.id, "playbook_id":(input_payload or {}).get("playbook_id"),
                    "voce":{"fase":voce.fase, "titolo":voce.titolo, "descrizione":voce.descrizione, "contenuto":content,
                             "testo_originale":voce.testo_originale, "riferimento_articolo":voce.riferimento_articolo,
                             "confidence":voce.confidence, "needs_careful_review":voce.confidence < .75}}})
    return {"summary":{"gruppi_totali":len(groups), "gruppi_falliti":failed, "voci":len(suggestions)}, "suggestions":suggestions}
