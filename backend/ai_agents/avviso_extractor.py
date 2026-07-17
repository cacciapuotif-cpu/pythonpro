"""Collector puro per l'estrazione LLM di regole/scadenze da una revisione avviso.

NON scrive su DB: ritorna {"summary", "suggestions"}; la persistenza avviene
solo in agent_workflows.run_agent_workflow (regola registry).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional
from zoneinfo import ZoneInfo

from pydantic import TypeAdapter

import models
import schemas_avvisi as avvisi_schemas
from file_upload import UPLOAD_DIR

from .llm import call_ollama_json
from .llm_schemas import AvvisoEstrazioneLLM
from .prompts.avviso_extractor_v1 import (
    GRUPPI_CATEGORIE,
    SYSTEM_PROMPT_ESTRAZIONE,
    build_extraction_prompt,
)

logger = logging.getLogger(__name__)

CONFIDENCE_REVIEW_THRESHOLD = 0.75
MAX_PROMPT_CHARS = 24000
_TZ_ROME = ZoneInfo("Europe/Rome")
_rule_value_adapter = TypeAdapter(avvisi_schemas.RuleValue)


def _normalize_rule_value(raw: Any) -> tuple[dict, bool]:
    """Ritorna (valore validato, needs_careful_review per valore non conforme)."""
    try:
        validated = _rule_value_adapter.validate_python(raw)
        return validated.model_dump(mode="json"), False
    except Exception:
        return {"tipo": "testo", "valore": json.dumps(raw, ensure_ascii=False, default=str)}, True


def _parse_deadline_date(raw: str):
    from datetime import datetime

    value = datetime.fromisoformat(str(raw).strip())
    if value.tzinfo is None:
        value = value.replace(tzinfo=_TZ_ROME)
    return value


def _categoria_for(chiave_gruppo: str, categorie: list[str], sottocategoria: Optional[str]) -> str:
    if sottocategoria and sottocategoria in categorie:
        return sottocategoria
    return categorie[0] if categorie else "altro"


def collect_avviso_extraction_suggestions(
    db,
    *,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    input_payload: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    if entity_type != "avviso_revisione" or not entity_id:
        raise ValueError("avviso_extractor richiede entity_type=avviso_revisione ed entity_id")
    revision = (
        db.query(models.AvvisoRevisione)
        .filter(models.AvvisoRevisione.id == entity_id)
        .first()
    )
    if revision is None:
        raise ValueError(f"Revisione avviso {entity_id} non trovata")
    if not revision.cleaned_md_path:
        raise ValueError("La revisione non ha un markdown pulito: eseguire prima la pulizia")
    cleaned = (UPLOAD_DIR / revision.cleaned_md_path).read_text(encoding="utf-8")
    testo = cleaned[:MAX_PROMPT_CHARS]

    suggestions: list[dict[str, Any]] = []
    gruppi_falliti = 0
    for gruppo, categorie in GRUPPI_CATEGORIE.items():
        prompt = build_extraction_prompt(gruppo, categorie, testo)
        try:
            raw = call_ollama_json(system_prompt=SYSTEM_PROMPT_ESTRAZIONE, user_prompt=prompt)
        except Exception as exc:
            gruppi_falliti += 1
            logger.warning("avviso_extractor: gruppo %s fallito: %s", gruppo, exc)
            continue
        parsed = AvvisoEstrazioneLLM.model_validate(raw if isinstance(raw, dict) else {})
        for regola in parsed.regole:
            valore, valore_sospetto = _normalize_rule_value(regola.valore)
            needs_review = valore_sospetto or regola.confidence < CONFIDENCE_REVIEW_THRESHOLD
            proposal = {
                "categoria": _categoria_for(gruppo, categorie, regola.sottocategoria),
                "sottocategoria": regola.sottocategoria,
                "chiave": regola.chiave,
                "valore": valore,
                "unita": regola.unita,
                "testo_originale": regola.testo_originale,
                "riferimento_articolo": regola.riferimento_articolo,
                "confidence": round(regola.confidence, 4),
                "needs_careful_review": needs_review,
            }
            suggestions.append({
                "suggestion_type": "avviso_regola_proposta",
                "entity_type": "avviso_revisione",
                "entity_id": revision.id,
                "severity": "medium",
                "title": f"Regola proposta: {regola.chiave}",
                "description": regola.testo_originale[:500],
                "payload": {"gruppo": gruppo, "raw": regola.model_dump(mode="json")},
                "confidence_score": regola.confidence,
                "auto_fix_available": True,
                "auto_fix_payload": {
                    "kind": "avviso_estrazione",
                    "target": "regola",
                    "revision_id": revision.id,
                    "proposal": proposal,
                },
            })
        for scadenza in parsed.scadenze:
            try:
                data = _parse_deadline_date(scadenza.data)
            except ValueError:
                logger.warning("avviso_extractor: data scadenza non parsabile: %r", scadenza.data)
                continue
            proposal = {
                "tipo": scadenza.tipo,
                "data": data.isoformat(),
                "descrizione": scadenza.descrizione,
                "tassativa": scadenza.tassativa,
                "testo_originale": scadenza.testo_originale,
                "riferimento_articolo": scadenza.riferimento_articolo,
                "confidence": round(scadenza.confidence, 4),
                "needs_careful_review": scadenza.confidence < CONFIDENCE_REVIEW_THRESHOLD,
            }
            suggestions.append({
                "suggestion_type": "avviso_scadenza_proposta",
                "entity_type": "avviso_revisione",
                "entity_id": revision.id,
                "severity": "medium",
                "title": f"Scadenza proposta: {scadenza.tipo} {data.date().isoformat()}",
                "description": scadenza.descrizione[:500],
                "payload": {"raw": scadenza.model_dump(mode="json")},
                "confidence_score": scadenza.confidence,
                "auto_fix_available": True,
                "auto_fix_payload": {
                    "kind": "avviso_estrazione",
                    "target": "scadenza",
                    "revision_id": revision.id,
                    "proposal": proposal,
                },
            })

    summary = {
        "revision_id": revision.id,
        "gruppi_totali": len(GRUPPI_CATEGORIE),
        "gruppi_falliti": gruppi_falliti,
        "regole_proposte": sum(1 for s in suggestions if s["suggestion_type"] == "avviso_regola_proposta"),
        "scadenze_proposte": sum(1 for s in suggestions if s["suggestion_type"] == "avviso_scadenza_proposta"),
    }
    return {"summary": summary, "suggestions": suggestions}
