"""Prompt v1 per la classificazione documenti del DocumentProcessor."""
from __future__ import annotations

import json

PROMPT_VERSION = "document_processor_v1"

SYSTEM_PROMPT = (
    "Sei un assistente per la verifica di documenti amministrativi italiani. "
    "Analizza il documento e rispondi SOLO con JSON valido. "
    "Non aggiungere testo fuori dal JSON."
)


def build_user_prompt(
    *,
    filename: str,
    entity_name: str,
    expected_doc_type: str,
    text_content: str,
    extraction_hint: dict,
) -> str:
    return (
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
