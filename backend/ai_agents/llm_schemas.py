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
