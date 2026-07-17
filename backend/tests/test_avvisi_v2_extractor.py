"""ONDATA ARCHIVIO AVVISI — V2: schemi LLM, collector avviso_extractor, pipeline, apply."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_agents.llm_schemas import AvvisoEstrazioneLLM
from ai_agents.prompts.avviso_extractor_v1 import (
    GRUPPI_CATEGORIE,
    SYSTEM_PROMPT_ESTRAZIONE,
    build_extraction_prompt,
)


def test_estrazione_schema_clamps_confidence_and_drops_invalid_items():
    parsed = AvvisoEstrazioneLLM.model_validate({
        "regole": [
            {
                "chiave": "contributo_massimo",
                "valore": {"tipo": "denaro", "importo": "50000", "valuta": "EUR"},
                "testo_originale": "Il contributo massimo è 50.000 euro",
                "confidence": 1.7,
            },
            {"senza_campi_obbligatori": True},
        ],
        "scadenze": [
            {
                "tipo": "tipologia_ignota",
                "data": "2026-09-30",
                "descrizione": "Termine presentazione",
                "testo_originale": "entro il 30/09/2026",
                "confidence": -3,
            }
        ],
    })
    assert len(parsed.regole) == 1
    assert parsed.regole[0].confidence == 1.0
    assert len(parsed.scadenze) == 1
    assert parsed.scadenze[0].tipo == "altro"
    assert parsed.scadenze[0].confidence == 0.0


def test_gruppi_categorie_cover_expected_categories():
    flat = [c for cats in GRUPPI_CATEGORIE.values() for c in cats]
    assert "massimali" in flat and "rendicontazione" in flat
    assert GRUPPI_CATEGORIE["scadenze"] == []


def test_build_extraction_prompt_mentions_categories_and_text():
    prompt = build_extraction_prompt("economiche", ["massimali", "parametri_costo"], "# Art. 5\nMassimale 50k")
    assert "massimali" in prompt and "parametri_costo" in prompt
    assert "Massimale 50k" in prompt
    assert "JSON" in SYSTEM_PROMPT_ESTRAZIONE
