"""Contratti API/dominio per ONDATA ARCHIVIO AVVISI V1."""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class FondoAvviso(StrEnum):
    FONDIMPRESA = "fondimpresa"
    FORMAZIENDA = "formazienda"
    FAPI = "fapi"
    REGIONALE = "regionale"
    ALTRO = "altro"


class StatoAvviso(StrEnum):
    BOZZA = "bozza"
    ATTIVO = "attivo"
    IN_SCADENZA = "in_scadenza"
    SCADUTO = "scaduto"
    ARCHIVIATO = "archiviato"


class StatoEstrazioneRevisione(StrEnum):
    CARICATO = "caricato"
    PULITO = "pulito"
    SEGMENTATO = "segmentato"
    IN_ESTRAZIONE = "in_estrazione"
    ESTRATTO = "estratto"
    ERRORE = "errore"


class CategoriaRegola(StrEnum):
    MASSIMALI = "massimali"
    PARAMETRI_COSTO = "parametri_costo"
    DESTINATARI = "destinatari"
    BENEFICIARI = "beneficiari"
    AIUTI_DI_STATO = "aiuti_di_stato"
    PRESENTAZIONE = "presentazione"
    VALUTAZIONE = "valutazione"
    ATTUAZIONE = "attuazione"
    RENDICONTAZIONE = "rendicontazione"
    DELEGA = "delega"
    VARIAZIONI = "variazioni"
    ALTRO = "altro"


class StatoDatoAvviso(StrEnum):
    PROPOSTA = "proposta"
    VALIDATA = "validata"
    RIFIUTATA = "rifiutata"
    SUPERATA = "superata"


class TipoScadenza(StrEnum):
    PRESENTAZIONE = "presentazione"
    AVVIO = "avvio"
    CHIUSURA = "chiusura"
    RENDICONTAZIONE = "rendicontazione"
    ALTRO = "altro"


class TipoDocumentoAvviso(StrEnum):
    AVVISO = "avviso"
    ALLEGATO = "allegato"
    VADEMECUM = "vademecum"
    MANUALE_GESTIONE = "manuale_gestione"
    NOTA_INTERNA = "nota_interna"
    CONTRODEDUZIONE = "controdeduzione"
    ALTRO = "altro"


class TipoConoscenza(StrEnum):
    NOTA_OPERATIVA = "nota_operativa"
    ERRORE_DA_EVITARE = "errore_da_evitare"
    DECISIONE = "decisione"
    BUONA_PRASSI = "buona_prassi"
    ALTRO = "altro"


class EsitoProgettoAvviso(StrEnum):
    APPROVATO = "approvato"
    RIGETTATO = "rigettato"
    ATTUATO = "attuato"
    RENDICONTATO = "rendicontato"
    DECURTATO = "decurtato"
    CONTRODEDOTTO = "controdedotto"


class _Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class TextRuleValue(_Schema):
    tipo: Literal["testo"]
    valore: str = Field(min_length=1)


class MoneyRuleValue(_Schema):
    tipo: Literal["denaro"]
    importo: Decimal = Field(ge=0)
    valuta: str = Field(default="EUR", min_length=3, max_length=3)


class PercentRuleValue(_Schema):
    tipo: Literal["percentuale"]
    valore: Decimal = Field(ge=0, le=100)


class NumberRuleValue(_Schema):
    tipo: Literal["numero"]
    valore: Decimal


class HoursRuleValue(_Schema):
    tipo: Literal["ore"]
    valore: Decimal = Field(ge=0)


class DaysRuleValue(_Schema):
    tipo: Literal["durata_giorni"]
    valore: int = Field(ge=0)
    calendario: bool = True


class DateRuleValue(_Schema):
    tipo: Literal["data"]
    valore: date


class BoolRuleValue(_Schema):
    tipo: Literal["booleano"]
    valore: bool


class SetRuleValue(_Schema):
    tipo: Literal["insieme"]
    valori: list[str] = Field(min_length=1)


class RangeRuleValue(_Schema):
    tipo: Literal["intervallo"]
    minimo: Optional[Decimal] = None
    massimo: Optional[Decimal] = None
    inclusivo_min: bool = True
    inclusivo_max: bool = True

    @model_validator(mode="after")
    def validate_bounds(self):
        if self.minimo is None and self.massimo is None:
            raise ValueError("Almeno un estremo è obbligatorio")
        if self.minimo is not None and self.massimo is not None and self.minimo > self.massimo:
            raise ValueError("Il minimo non può superare il massimo")
        return self


class FormulaRuleValue(_Schema):
    tipo: Literal["formula"]
    espressione: str = Field(min_length=1)
    variabili: list[str] = Field(default_factory=list)


RuleValue = Annotated[
    Union[
        TextRuleValue,
        MoneyRuleValue,
        PercentRuleValue,
        NumberRuleValue,
        HoursRuleValue,
        DaysRuleValue,
        DateRuleValue,
        BoolRuleValue,
        SetRuleValue,
        RangeRuleValue,
        FormulaRuleValue,
    ],
    Field(discriminator="tipo"),
]


def _strip_required(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("Il valore non può essere vuoto")
    return normalized


class AvvisoCreate(_Schema):
    fondo: FondoAvviso
    numero: str = Field(min_length=1, max_length=50)
    anno: int = Field(ge=2000, le=2100)
    titolo: str = Field(min_length=1, max_length=300)
    descrizione_breve: Optional[str] = Field(default=None, max_length=4000)
    stato: StatoAvviso = StatoAvviso.BOZZA
    ente_erogatore: str = Field(min_length=1, max_length=150)
    codice: Optional[str] = Field(default=None, max_length=50)

    _normalize_numero = field_validator("numero", "titolo", "ente_erogatore")(_strip_required)


class AvvisoUpdate(_Schema):
    titolo: Optional[str] = Field(default=None, min_length=1, max_length=300)
    descrizione_breve: Optional[str] = Field(default=None, max_length=4000)
    stato: Optional[StatoAvviso] = None


class AvvisoRead(AvvisoCreate):
    id: int
    revisione_corrente_id: Optional[int] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None


class AvvisoRevisioneCreate(_Schema):
    titolo: str = Field(min_length=1, max_length=300)
    descrizione_breve: Optional[str] = Field(default=None, max_length=4000)
    etichetta_revisione: Optional[str] = Field(default=None, max_length=50)
    data_pubblicazione: Optional[date] = None
    data_scadenza_presentazione: Optional[datetime] = None
    source_md_path: str = Field(min_length=1, max_length=500)
    cleaned_md_path: Optional[str] = Field(default=None, max_length=500)
    source_pdf_path: Optional[str] = Field(default=None, max_length=500)
    original_filename: str = Field(min_length=1, max_length=255)
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("data_scadenza_presentazione")
    @classmethod
    def require_timezone(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError("La scadenza deve includere il fuso orario")
        return value


class AvvisoRevisioneRead(AvvisoRevisioneCreate):
    id: int
    avviso_id: int
    numero_revisione: int
    revisione_precedente_id: Optional[int] = None
    stato_estrazione: StatoEstrazioneRevisione
    diff_from_previous: Optional[dict[str, Any]] = None
    extraction_run_id: Optional[int] = None
    created_by_user_id: Optional[int] = None
    created_at: datetime


class AvvisoRegolaProposal(_Schema):
    categoria: CategoriaRegola
    sottocategoria: Optional[str] = Field(default=None, max_length=80)
    chiave: str = Field(pattern=r"^[a-z0-9]+(?:_[a-z0-9]+)*$", max_length=150)
    valore: RuleValue
    unita: Optional[str] = Field(default=None, max_length=50)
    applicabilita: dict[str, Any] = Field(default_factory=dict)
    testo_originale: str = Field(min_length=1)
    riferimento_articolo: Optional[str] = Field(default=None, max_length=120)
    riferimento_sezione: Optional[str] = Field(default=None, max_length=200)
    riferimento_pagina: Optional[str] = Field(default=None, max_length=50)
    confidence: Optional[Decimal] = Field(default=None, ge=0, le=1)
    needs_careful_review: bool = False
    origin_suggestion_id: Optional[int] = None


class AvvisoScadenzaProposal(_Schema):
    tipo: TipoScadenza
    data: datetime
    finestra_inizio: Optional[datetime] = None
    finestra_fine: Optional[datetime] = None
    descrizione: str = Field(min_length=1)
    tassativa: bool = False
    condizione: Optional[str] = None
    applicabilita: dict[str, Any] = Field(default_factory=dict)
    testo_originale: str = Field(min_length=1)
    riferimento_articolo: Optional[str] = Field(default=None, max_length=120)
    confidence: Optional[Decimal] = Field(default=None, ge=0, le=1)
    needs_careful_review: bool = False
    origin_suggestion_id: Optional[int] = None

    @model_validator(mode="after")
    def validate_temporal_data(self):
        for value in (self.data, self.finestra_inizio, self.finestra_fine):
            if value is not None and value.tzinfo is None:
                raise ValueError("Le scadenze devono includere il fuso orario")
        if self.finestra_inizio and self.finestra_fine and self.finestra_fine < self.finestra_inizio:
            raise ValueError("La fine finestra precede l'inizio")
        return self


class AvvisoDocumentoCreate(_Schema):
    avviso_revisione_id: Optional[int] = None
    tipo: TipoDocumentoAvviso
    original_filename: str = Field(min_length=1, max_length=255)
    file_path: str = Field(min_length=1, max_length=500)
    mime_type: Optional[str] = Field(default=None, max_length=100)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    note: Optional[str] = Field(default=None, max_length=4000)


class AvvisoConoscenzaCreate(_Schema):
    avviso_revisione_id: Optional[int] = None
    tipo: TipoConoscenza = TipoConoscenza.NOTA_OPERATIVA
    contenuto: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    riservatezza: Literal["interna", "ristretta"] = "interna"

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, values):
        return sorted({value.strip().lower() for value in values if value.strip()})


class AvvisoEsitoProgettoCreate(_Schema):
    avviso_revisione_id: Optional[int] = None
    project_id: int
    piano_finanziario_id: Optional[int] = None
    esito: EsitoProgettoAvviso
    data_evento: datetime
    importo_richiesto: Optional[Decimal] = Field(default=None, ge=0)
    importo_ammesso: Optional[Decimal] = Field(default=None, ge=0)
    importo_rendicontato: Optional[Decimal] = Field(default=None, ge=0)
    importo_riconosciuto: Optional[Decimal] = Field(default=None, ge=0)
    importo_decurtato: Optional[Decimal] = Field(default=None, ge=0)
    note: Optional[str] = None
    documento_id: Optional[int] = None

    @model_validator(mode="after")
    def validate_amounts(self):
        if (
            self.importo_rendicontato is not None
            and self.importo_riconosciuto is not None
            and self.importo_riconosciuto > self.importo_rendicontato
        ):
            raise ValueError("L'importo riconosciuto supera il rendicontato")
        if (
            self.importo_rendicontato is not None
            and self.importo_decurtato is not None
            and self.importo_decurtato > self.importo_rendicontato
        ):
            raise ValueError("L'importo decurtato supera il rendicontato")
        return self
