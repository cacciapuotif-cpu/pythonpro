"""Contratti API e payload dichiarativi del sottosistema attività."""
from __future__ import annotations
from datetime import date, datetime
from enum import Enum
from typing import Annotated, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator

class FaseAttivita(str, Enum):
    presentazione = "presentazione"; avvio = "avvio"; gestione = "gestione"; rendicontazione = "rendicontazione"
class StatoAttivita(str, Enum):
    da_fare = "da_fare"; in_corso = "in_corso"; completata = "completata"; non_applicabile = "non_applicabile"

class _Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

class AttivitaSemplice(_Schema):
    tipo: Literal["attivita_semplice"]
class ScadenzaRelativa(_Schema):
    tipo: Literal["scadenza_relativa"]
    ancora: Literal["presentazione", "avvio", "chiusura", "rendicontazione"]
    offset_giorni: int
class DocumentoContenuto(_Schema):
    tipo: Literal["documento"]
    tipo_documento: str = Field(min_length=1, max_length=200)
VoceContenuto = Annotated[Union[AttivitaSemplice, ScadenzaRelativa, DocumentoContenuto], Field(discriminator="tipo")]

class PlaybookCreate(_Schema):
    nome: str = Field(min_length=1, max_length=200)
    fondo: str = "altro"
    ente_erogatore: Optional[str] = None
    descrizione: Optional[str] = None
class VoceCreate(_Schema):
    fase: FaseAttivita; ordine: int = 0; titolo: str = Field(min_length=1, max_length=300)
    descrizione: Optional[str] = None; contenuto: VoceContenuto; applicabilita: Optional[dict] = None
    testo_originale: Optional[str] = None; riferimento_articolo: Optional[str] = None
class StatoChange(_Schema):
    nuovo_stato: StatoAttivita; nota: Optional[str] = None
class AttivitaPatch(_Schema):
    scadenza: Optional[date] = None; assegnatario_user_id: Optional[int] = None; note: Optional[str] = None
