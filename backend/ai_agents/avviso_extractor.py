"""Collector puro per l'estrazione LLM di regole/scadenze da una revisione avviso.

NON scrive su DB: ritorna {"summary", "suggestions"}; la persistenza avviene
solo in agent_workflows.run_agent_workflow (regola registry).
"""
from __future__ import annotations

import json
import logging
import os
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


def _categorie_gruppo(gruppo: str) -> list[str]:
    categorie = GRUPPI_CATEGORIE[gruppo]
    return list(categorie) if categorie else ["scadenze"]


TUTTE_CATEGORIE = [
    categoria
    for gruppo in GRUPPI_CATEGORIE
    for categoria in _categorie_gruppo(gruppo)
]


def _normalize_rule_value(raw: Any) -> tuple[dict, bool]:
    """Ritorna (valore validato, needs_careful_review per valore non conforme)."""
    try:
        validated = _rule_value_adapter.validate_python(raw)
        return validated.model_dump(mode="json"), False
    except Exception as exc:
        # Una durata relativa dichiara un contratto operativo: degradarla a
        # testo nasconderebbe un ancoraggio/unità non validi e potrebbe farla
        # approvare come innocua regola v1. Le forme legacy sconosciute restano
        # invece consultabili come testo con revisione esplicita.
        if isinstance(raw, dict) and raw.get("tipo") == "durata_termine":
            raise ValueError("Regola durata_termine non conforme") from exc
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

    requested = (input_payload or {}).get("sezioni") or (input_payload or {}).get("groups")
    if requested:
        requested_set = {str(value) for value in requested}
        gruppi_da_processare = [
            gruppo for gruppo in GRUPPI_CATEGORIE if gruppo in requested_set
        ]
        invalidi = requested_set.difference(GRUPPI_CATEGORIE)
        if invalidi:
            raise ValueError("Sezioni estrazione non valide: {}".format(", ".join(sorted(invalidi))))
    else:
        gruppi_da_processare = list(GRUPPI_CATEGORIE)

    suggestions: list[dict[str, Any]] = []
    gruppi_falliti = 0
    sezioni_status: dict[str, str] = {}
    errori_sezioni: dict[str, str] = {}
    scartati_per_sezione: dict[str, int] = {}
    for gruppo in gruppi_da_processare:
        categorie = GRUPPI_CATEGORIE[gruppo]
        prompt = build_extraction_prompt(gruppo, categorie, testo)
        try:
            # Override per-agente: gli avvisi sono documenti PUBBLICI, quindi
            # l'estrazione può usare un LLM cloud (AVVISO_EXTRACTOR_LLM_PROVIDER,
            # es. "anthropic") più capace del locale su testo normativo. Se non
            # impostato, cade sul provider globale (Ollama locale).
            raw = call_ollama_json(
                system_prompt=SYSTEM_PROMPT_ESTRAZIONE,
                user_prompt=prompt,
                provider=os.getenv("AVVISO_EXTRACTOR_LLM_PROVIDER") or None,
                model=os.getenv("AVVISO_EXTRACTOR_LLM_MODEL") or None,
            )
            raw_dict = raw if isinstance(raw, dict) else {}
            parsed = AvvisoEstrazioneLLM.model_validate(raw_dict)
        except Exception as exc:
            gruppi_falliti += 1
            sezioni_status[gruppo] = "fallita"
            errori_sezioni[gruppo] = str(exc)[:500]
            scartati_per_sezione[gruppo] = 0
            logger.warning("avviso_extractor: gruppo %s fallito: %s", gruppo, exc)
            continue
        raw_rules = raw_dict.get("regole") if isinstance(raw_dict.get("regole"), list) else []
        raw_deadlines = raw_dict.get("scadenze") if isinstance(raw_dict.get("scadenze"), list) else []
        elementi_scartati = max(0, len(raw_rules) - len(parsed.regole))
        elementi_scartati += max(0, len(raw_deadlines) - len(parsed.scadenze))
        for regola in parsed.regole:
            try:
                valore, valore_sospetto = _normalize_rule_value(regola.valore)
            except ValueError as exc:
                elementi_scartati += 1
                logger.warning(
                    "avviso_extractor: regola %s scartata: %s",
                    regola.chiave,
                    exc,
                )
                continue
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
                elementi_scartati += 1
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

        scartati_per_sezione[gruppo] = elementi_scartati
        sezioni_status[gruppo] = "parziale" if elementi_scartati else "completa"

    sezioni_processate_nomi = [
        gruppo for gruppo, stato in sezioni_status.items() if stato in {"completa", "parziale"}
    ]
    sezioni_complete_nomi = [
        gruppo for gruppo, stato in sezioni_status.items() if stato == "completa"
    ]
    categorie_coperte = [
        categoria
        for gruppo in sezioni_complete_nomi
        for categoria in _categorie_gruppo(gruppo)
    ]
    sezioni_mancanti = [
        gruppo for gruppo in GRUPPI_CATEGORIE if gruppo not in sezioni_complete_nomi
    ]

    summary = {
        "revision_id": revision.id,
        "gruppi_totali": len(GRUPPI_CATEGORIE),
        "gruppi_falliti": gruppi_falliti,
        "sezioni_totali": len(GRUPPI_CATEGORIE),
        "sezioni_richieste": gruppi_da_processare,
        "sezioni_status": sezioni_status,
        "sezioni_processate": len(sezioni_processate_nomi),
        "sezioni_processate_nomi": sezioni_processate_nomi,
        "sezioni_complete": len(sezioni_complete_nomi),
        "sezioni_complete_nomi": sezioni_complete_nomi,
        "sezioni_mancanti": sezioni_mancanti,
        "categorie_totali": len(TUTTE_CATEGORIE),
        "categorie_coperte": categorie_coperte,
        "categorie_coperte_count": len(categorie_coperte),
        "categorie_mancanti": [
            categoria for categoria in TUTTE_CATEGORIE if categoria not in categorie_coperte
        ],
        "elementi_scartati": sum(scartati_per_sezione.values()),
        "elementi_scartati_per_sezione": scartati_per_sezione,
        "errori_sezioni": errori_sezioni,
        "regole_proposte": sum(1 for s in suggestions if s["suggestion_type"] == "avviso_regola_proposta"),
        "scadenze_proposte": sum(1 for s in suggestions if s["suggestion_type"] == "avviso_scadenza_proposta"),
    }
    return {"summary": summary, "suggestions": suggestions}
