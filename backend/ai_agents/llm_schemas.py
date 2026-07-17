"""Schemi Pydantic per validare l'output LLM degli agenti.

Output malformato -> ValidationError -> ValueError al chiamante -> retry;
esauriti i retry si va in fallback (mail: testo deterministico; documenti:
manual_review). Nessun output LLM viene applicato senza passare da qui.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class MailCopySchema(BaseModel):
    subject: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1)

    @field_validator("subject", "body", mode="before")
    @classmethod
    def _coerce_str(cls, value: Any) -> Any:
        if value is None:
            raise ValueError("campo mancante")
        return str(value).strip()


class DocumentResultSchema(BaseModel):
    valid: Optional[bool] = None
    doc_type: str = ""
    confidence: Optional[float] = None
    issues: list[str] = Field(default_factory=list)
    extracted_data: dict[str, Any] = Field(default_factory=dict)

    @field_validator("doc_type", mode="before")
    @classmethod
    def _coerce_doc_type(cls, value: Any) -> Any:
        return str(value or "").strip()

    @field_validator("confidence", mode="before")
    @classmethod
    def _clamp_confidence(cls, value: Any) -> Any:
        if value is None or value == "":
            return None
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            raise ValueError("confidence non numerica")

    @field_validator("issues", mode="before")
    @classmethod
    def _coerce_issues(cls, value: Any) -> Any:
        if value is None:
            return []
        if not isinstance(value, (list, tuple)):
            raise ValueError("issues deve essere una lista")
        return [str(item) for item in value]

    @field_validator("extracted_data", mode="before")
    @classmethod
    def _coerce_extracted(cls, value: Any) -> Any:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("extracted_data deve essere un oggetto")
        return value


_TIPI_SCADENZA_VALIDI = {"presentazione", "avvio", "chiusura", "rendicontazione", "altro"}


def _clamp01(value: Any, default: float = 0.5) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


class AvvisoRegolaLLM(BaseModel):
    chiave: str
    sottocategoria: Optional[str] = None
    valore: Any = None
    unita: Optional[str] = None
    testo_originale: str
    riferimento_articolo: Optional[str] = None
    confidence: float = 0.5

    @field_validator("confidence", mode="before")
    @classmethod
    def _clamp_confidence(cls, value: Any) -> float:
        return _clamp01(value)


class AvvisoScadenzaLLM(BaseModel):
    tipo: str = "altro"
    data: str
    descrizione: str
    tassativa: bool = False
    testo_originale: str
    riferimento_articolo: Optional[str] = None
    confidence: float = 0.5

    @field_validator("tipo", mode="before")
    @classmethod
    def _coerce_tipo(cls, value: Any) -> str:
        normalized = str(value or "").strip().lower()
        return normalized if normalized in _TIPI_SCADENZA_VALIDI else "altro"

    @field_validator("confidence", mode="before")
    @classmethod
    def _clamp_confidence(cls, value: Any) -> float:
        return _clamp01(value)


class AvvisoEstrazioneLLM(BaseModel):
    regole: list[AvvisoRegolaLLM] = []
    scadenze: list[AvvisoScadenzaLLM] = []

    @field_validator("regole", "scadenze", mode="before")
    @classmethod
    def _drop_invalid_items(cls, value: Any, info) -> list:
        if not isinstance(value, list):
            return []
        model = AvvisoRegolaLLM if info.field_name == "regole" else AvvisoScadenzaLLM
        valid = []
        for item in value:
            try:
                valid.append(model.model_validate(item))
            except Exception:
                continue
        return valid
