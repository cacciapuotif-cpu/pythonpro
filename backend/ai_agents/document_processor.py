"""Analizza un documento allegato tramite LLM e restituisce un risultato strutturato."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DOC_TYPE_EXTRACTION_HINTS = {
    "visura_camerale": {
        "ragione_sociale": "",
        "partita_iva": "",
        "codice_fiscale": "",
        "codice_ateco": "",
        "indirizzo": "",
        "citta": "",
        "cap": "",
        "provincia": "",
        "pec": "",
        "email": "",
        "telefono": "",
        "legale_rappresentante_nome": "",
        "legale_rappresentante_cognome": "",
        "legale_rappresentante_codice_fiscale": "",
        "oggetto_sociale": "",
    },
    "durc": {
        "ragione_sociale": "",
        "partita_iva": "",
        "codice_fiscale": "",
        "numero_protocollo": "",
        "data_emissione": "",
        "data_scadenza": "",
        "esito_regolarita": "",
    },
    "certificato_attribuzione_partita_iva": {
        "ragione_sociale": "",
        "partita_iva": "",
        "codice_fiscale": "",
        "data_inizio_attivita": "",
        "indirizzo": "",
        "citta": "",
        "cap": "",
        "provincia": "",
    },
    "statuto": {
        "ragione_sociale": "",
        "partita_iva": "",
        "codice_fiscale": "",
        "oggetto_sociale": "",
        "forma_giuridica": "",
        "capitale_sociale": "",
    },
    "atto_costitutivo": {
        "ragione_sociale": "",
        "partita_iva": "",
        "codice_fiscale": "",
        "data_costituzione": "",
        "forma_giuridica": "",
        "soci": [],
    },
    "curriculum": {
        "profilo_professionale": "",
        "skills": [],
        "education": "",
    },
    "documento_identita": {
        "codice_fiscale": "",
        "data_scadenza": "",
        "numero_documento": "",
    },
}


@dataclass
class DocumentResult:
    valid: Optional[bool]          # True=valido, False=non valido, None=indeterminato
    doc_type: str
    issues: List[str] = field(default_factory=list)
    extracted_data: Dict[str, Any] = field(default_factory=dict)
    raw_llm_output: Optional[str] = None
    confidence: float = 0.0        # 0.0-1.0: soglia auto-apply=0.85, conferma=0.60


class DocumentProcessor:
    def process(
        self,
        file_path: Optional[str],
        entity_name: str,
        expected_doc_type: str,
    ) -> DocumentResult:
        if not file_path:
            return DocumentResult(valid=None, doc_type="none")

        text_content = _extract_text(file_path)

        try:
            data = call_llm_for_document(
                file_path=file_path,
                text_content=text_content,
                entity_name=entity_name,
                expected_doc_type=expected_doc_type,
            )
        except Exception as exc:
            logger.warning("DocumentProcessor: LLM non disponibile (%s), manual review", exc)
            return DocumentResult(valid=None, doc_type=expected_doc_type, raw_llm_output=None)

        if isinstance(data, str):
            return _apply_confidence_decision(_parse_llm_result(data, expected_doc_type))

        return _apply_confidence_decision(_parse_llm_result_dict(data, expected_doc_type))


def call_llm_for_document(
    *,
    file_path: str,
    text_content: str,
    entity_name: str,
    expected_doc_type: str,
) -> dict:
    """
    Chiama il provider LLM configurato e ritorna un dizionario JSON.
    Lancia eccezione se LLM non disponibile o timeout.
    """
    from .llm import call_ollama_json

    filename = Path(file_path).name
    normalized_doc_type = (expected_doc_type or "").strip().lower().replace(" ", "_")
    extraction_hint = DOC_TYPE_EXTRACTION_HINTS.get(normalized_doc_type, {})

    system_prompt = (
        "Sei un assistente per la verifica di documenti amministrativi italiani. "
        "Analizza il documento e rispondi SOLO con JSON valido. "
        "Non aggiungere testo fuori dal JSON."
    )
    user_prompt = (
        f"Documento: '{filename}'\n"
        f"Mittente: {entity_name}\n"
        f"Tipo atteso: {expected_doc_type}\n"
        f"Contenuto (parziale):\n{text_content[:2000]}\n\n"
        "Rispondi SOLO con JSON nel formato:\n"
        + json.dumps({
            "valid": True,
            "doc_type": expected_doc_type,
            "confidence": 0.9,
            "issues": [],
            "extracted_data": extraction_hint,
        }, ensure_ascii=True)
        + "\n\nDove confidence va da 0.0 a 1.0: 0.9+=valido certo, 0.7-0.9=probabilmente valido, 0.5-0.7=incerto, sotto 0.5=non valido"
    )

    return call_ollama_json(system_prompt=system_prompt, user_prompt=user_prompt)


def _infer_confidence(valid: Optional[bool], issues: list) -> float:
    """Stima confidence quando il LLM non la fornisce esplicitamente."""
    if valid is True and not issues:
        return 0.90
    if valid is True and issues:
        return 0.72
    if valid is False and issues:
        return 0.88
    return 0.55


def _extract_text(file_path: str) -> str:
    """Estrae testo dal file. Fallback su nome file se pdfplumber non disponibile."""
    path = Path(file_path)
    if path.suffix.lower() == ".pdf":
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                pages_text = []
                for page in pdf.pages[:5]:
                    t = page.extract_text()
                    if t:
                        pages_text.append(t)
            return "\n".join(pages_text)[:4000]
        except Exception as exc:
            logger.debug("pdfplumber non disponibile o errore (%s), fallback su nome file", exc)
    return f"[File: {path.name}]"


def _parse_llm_result_dict(data: dict, expected_doc_type: str) -> DocumentResult:
    """Parsa il dizionario JSON dal LLM. In caso di errore: valid=None."""
    if not data:
        return DocumentResult(valid=None, doc_type=expected_doc_type, confidence=0.0)

    valid = bool(data.get("valid")) if data.get("valid") is not None else None
    issues = list(data.get("issues") or [])

    raw_confidence = data.get("confidence")
    if raw_confidence is not None:
        try:
            confidence = float(raw_confidence)
            confidence = max(0.0, min(1.0, confidence))
        except (ValueError, TypeError):
            confidence = _infer_confidence(valid, issues)
    else:
        confidence = _infer_confidence(valid, issues)

    if confidence >= 0.85 and not issues and valid is False:
        logger.debug(
            "DocumentProcessor: confidence %.2f alta con zero issues, override valid False -> True",
            confidence,
        )
        valid = True

    return DocumentResult(
        valid=valid,
        doc_type=str(data.get("doc_type") or expected_doc_type),
        issues=issues,
        extracted_data=dict(data.get("extracted_data") or {}),
        raw_llm_output=json.dumps(data),
        confidence=confidence,
    )


def _parse_llm_result(raw: str, expected_doc_type: str) -> DocumentResult:
    """Compatibilita backward: parsa stringa JSON. Usa _parse_llm_result_dict internamente."""
    if not raw:
        return DocumentResult(valid=None, doc_type=expected_doc_type, confidence=0.0)
    try:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("nessun JSON trovato")
        data = json.loads(raw[start:end + 1])
        return _parse_llm_result_dict(data, expected_doc_type)
    except Exception as exc:
        logger.warning("DocumentProcessor: JSON malformato (%s), manual review", exc)
        return DocumentResult(valid=None, doc_type=expected_doc_type, raw_llm_output=raw, confidence=0.0)


def _apply_confidence_decision(result: DocumentResult) -> DocumentResult:
    if result.raw_llm_output and result.confidence == 0.0 and not result.extracted_data and not result.issues:
        logger.info("DocumentProcessor: output LLM non parseabile -> revisione manuale (%s)", result.doc_type)
        return result

    if result.valid is False and result.issues:
        logger.info(
            "DocumentProcessor: documento esplicitamente non valido -> rifiutato (%s, confidence %.2f)",
            result.doc_type,
            result.confidence,
        )
        return result

    if result.confidence >= 0.85:
        result.valid = True
        logger.info(
            "DocumentProcessor: confidence %.2f -> auto-validato (%s)",
            result.confidence,
            result.doc_type,
        )
        return result

    if result.confidence >= 0.60:
        result.valid = None
        logger.info(
            "DocumentProcessor: confidence %.2f -> caricato/revisione umana (%s)",
            result.confidence,
            result.doc_type,
        )
        return result

    result.valid = False
    if not result.issues:
        result.issues = ["Confidence sotto soglia minima per validazione automatica"]
    logger.info(
        "DocumentProcessor: confidence %.2f -> rifiutato (%s)",
        result.confidence,
        result.doc_type,
    )
    return result
