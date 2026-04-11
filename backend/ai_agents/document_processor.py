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
            raw = call_llm_for_document(
                file_path=file_path,
                text_content=text_content,
                entity_name=entity_name,
                expected_doc_type=expected_doc_type,
            )
        except Exception as exc:
            logger.warning("DocumentProcessor: LLM non disponibile (%s), manual review", exc)
            return DocumentResult(valid=None, doc_type=expected_doc_type, raw_llm_output=None)

        return _parse_llm_result(raw, expected_doc_type)


def call_llm_for_document(
    *,
    file_path: str,
    text_content: str,
    entity_name: str,
    expected_doc_type: str,
) -> str:
    """
    Chiama il provider LLM configurato e ritorna la risposta raw (stringa JSON).
    Lancia eccezione se LLM non disponibile o timeout.
    """
    from .llm import get_agent_llm_config, _call_ollama, _call_openclaw

    config = get_agent_llm_config()
    if not config.enabled:
        raise RuntimeError("Provider LLM non abilitato")

    filename = Path(file_path).name
    normalized_doc_type = (expected_doc_type or "").strip().lower().replace(" ", "_")
    extraction_hint = DOC_TYPE_EXTRACTION_HINTS.get(normalized_doc_type, {})
    system_prompt = (
        "Sei un assistente per la verifica di documenti amministrativi. "
        "Analizza il documento fornito e rispondi SOLO con JSON valido. "
        "Non aggiungere testo fuori dal JSON."
    )
    user_prompt = (
        f"Documento allegato: '{filename}'\n"
        f"Mittente: {entity_name}\n"
        f"Tipo documento atteso: {expected_doc_type}\n"
        f"Contenuto estratto (parziale):\n{text_content[:2000]}\n\n"
        "Rispondi con JSON:\n"
        '{"valid": true/false, "doc_type": "tipo_rilevato", "issues": ["problema1"], "extracted_data": %s}'
        % json.dumps(extraction_hint, ensure_ascii=True)
    )

    if config.provider == "ollama":
        result = _call_ollama(config, system_prompt=system_prompt, user_prompt=user_prompt)
    else:
        result = _call_openclaw(config, system_prompt=system_prompt, user_prompt=user_prompt)

    return result.raw_text or result.body


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


def _parse_llm_result(raw: str, expected_doc_type: str) -> DocumentResult:
    """Parsa la stringa raw JSON dal LLM. In caso di errore: valid=None."""
    if not raw:
        return DocumentResult(valid=None, doc_type=expected_doc_type, raw_llm_output=raw)

    try:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("nessun oggetto JSON trovato")
        data = json.loads(raw[start:end + 1])
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("DocumentProcessor: JSON malformato (%s), manual review", exc)
        return DocumentResult(valid=None, doc_type=expected_doc_type, raw_llm_output=raw)

    return DocumentResult(
        valid=bool(data.get("valid")) if data.get("valid") is not None else None,
        doc_type=str(data.get("doc_type") or expected_doc_type),
        issues=list(data.get("issues") or []),
        extracted_data=dict(data.get("extracted_data") or {}),
        raw_llm_output=raw,
    )
