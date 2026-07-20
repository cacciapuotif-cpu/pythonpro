"""Massimali effettivi per le voci di piano finanziario (E1.3/E1.4).

Precedenza:

1. ``AvvisoRegola`` **validata** sulla revisione avviso agganciata al piano
   (``categoria`` in ``massimali``/``parametri_costo``, ``chiave`` che matcha
   la categoria voce docenza/tutoraggio);
2. fallback: ``MassimaleFondo`` per (tipo_fondo, anno), come storicamente.

Il valore della regola è il JSON prodotto da ``ai_agents/avviso_extractor``
(``schemas_avvisi.RuleValue``): forma canonica ``{"tipo": "denaro", "importo":
X, "valuta": "EUR"}`` oppure ``{"tipo": "numero"|"ore", "valore": X}``; per
robustezza sono accettati anche ``{"importo": X}``, ``{"valore": X}`` e lo
scalare nudo. Tipi non monetari/orari (percentuale, testo, intervallo, ...)
o valori non numerici NON vengono interpretati: warning e fallback al fondo —
mai limiti inventati.

Servizio puro (nessuna dipendenza da router): sarà consumato anche
dall'anteprima template (badge fonte massimale).
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from sqlalchemy.orm import Session

import models

logger = logging.getLogger(__name__)

FONTE_REGOLA_AVVISO = "regola_avviso"
FONTE_MASSIMALE_FONDO = "massimale_fondo"

#: categorie AvvisoRegola pertinenti per i limiti di costo
_CATEGORIE_REGOLA = ("massimali", "parametri_costo")

#: token della chiave regola che identificano la categoria voce
_CATEGORIA_TOKENS = {
    "docenza": {"docenza", "docente", "docenti"},
    "tutoraggio": {"tutoraggio", "tutor", "tutoring"},
}

#: token che segnalano un limite ORARIO (preferiti se più regole matchano)
_HOURLY_TOKENS = {"orario", "oraria", "orarie", "orari", "ora", "ore", "h"}

#: tipi RuleValue interpretabili come limite di costo orario; gli altri
#: (percentuale, testo, intervallo, formula, ...) NON vanno letti come €/h
_TIPI_VALORE_INTERPRETABILI = {"denaro", "numero", "ore"}


@dataclass(frozen=True)
class MassimaleEffettivo:
    limite: Decimal
    fonte: str
    riferimento_articolo: Optional[str]
    testo_originale: Optional[str]


def _normalize_tokens(chiave: str) -> set[str]:
    """Chiave snake_case libera dell'estrattore -> set di token normalizzati
    (minuscole, senza accenti, separatori non alfanumerici)."""
    flattened = unicodedata.normalize("NFKD", chiave or "")
    flattened = "".join(ch for ch in flattened if not unicodedata.combining(ch))
    return {tok for tok in re.split(r"[^a-z0-9]+", flattened.lower()) if tok}


def _to_decimal(raw: Any) -> Optional[Decimal]:
    if isinstance(raw, bool) or raw is None:
        return None
    try:
        value = Decimal(str(raw).strip().replace(",", "."))
    except (InvalidOperation, ValueError):
        return None
    return value if value >= 0 else None


def _estrai_limite(valore: Any) -> Optional[Decimal]:
    """Estrae il limite numerico dal JSON `valore` della regola.

    Forme accettate: scalare; dict con ``importo`` o ``valore`` (con o senza
    ``tipo``; se ``tipo`` è presente deve essere denaro/numero/ore).
    Ritorna None se non interpretabile: il chiamante logga e fa fallback.
    """
    if isinstance(valore, dict):
        tipo = valore.get("tipo")
        if tipo is not None and str(tipo).strip().lower() not in _TIPI_VALORE_INTERPRETABILI:
            return None
        for key in ("importo", "valore"):
            if key in valore:
                return _to_decimal(valore[key])
        return None
    return _to_decimal(valore)


def _massimale_da_regola(db: Session, piano, categoria: str) -> Optional[MassimaleEffettivo]:
    if not getattr(piano, "avviso_revisione_id", None):
        return None
    categoria_tokens = _CATEGORIA_TOKENS.get(categoria)
    if not categoria_tokens:
        return None

    regole = (
        db.query(models.AvvisoRegola)
        .filter(
            models.AvvisoRegola.avviso_revisione_id == piano.avviso_revisione_id,
            models.AvvisoRegola.stato == "validata",
            models.AvvisoRegola.categoria.in_(_CATEGORIE_REGOLA),
        )
        .order_by(models.AvvisoRegola.id)
        .all()
    )
    matched = [r for r in regole if _normalize_tokens(r.chiave) & categoria_tokens]
    if not matched:
        return None

    # A parità di match, preferisci le regole con indicazione oraria esplicita
    orarie = [r for r in matched if _normalize_tokens(r.chiave) & _HOURLY_TOKENS]
    candidates = orarie or matched

    for regola in candidates:
        limite = _estrai_limite(regola.valore)
        if limite is not None:
            return MassimaleEffettivo(
                limite=limite,
                fonte=FONTE_REGOLA_AVVISO,
                riferimento_articolo=regola.riferimento_articolo,
                testo_originale=regola.testo_originale,
            )
        logger.warning(
            "Regola avviso %s (chiave=%r, revisione=%s): valore non interpretabile "
            "come limite %s (%r) — fallback a MassimaleFondo",
            regola.id, regola.chiave, regola.avviso_revisione_id, categoria, regola.valore,
        )
    return None


def _massimale_da_fondo(db: Session, piano, categoria: str) -> Optional[MassimaleEffettivo]:
    massimale = (
        db.query(models.MassimaleFondo)
        .filter(
            models.MassimaleFondo.tipo_fondo == piano.tipo_fondo,
            models.MassimaleFondo.anno == piano.anno,
        )
        .first()
    )
    if not massimale:
        return None
    if categoria == "docenza":
        limite = massimale.massimale_orario_docenza
    elif categoria == "tutoraggio":
        limite = massimale.massimale_orario_tutoraggio
    else:
        return None
    if limite is None:
        return None
    return MassimaleEffettivo(
        limite=Decimal(str(limite)),
        fonte=FONTE_MASSIMALE_FONDO,
        riferimento_articolo=None,
        testo_originale=None,
    )


def get_massimale_effettivo(db: Session, piano, categoria: str) -> Optional[MassimaleEffettivo]:
    """Massimale orario effettivo per la categoria voce (docenza/tutoraggio).

    Precedenza: regola avviso validata sulla revisione del piano, altrimenti
    MassimaleFondo (tipo_fondo, anno). None = nessun limite verificabile.
    """
    categoria = (categoria or "").strip().lower()
    if categoria not in _CATEGORIA_TOKENS:
        return None
    return _massimale_da_regola(db, piano, categoria) or _massimale_da_fondo(db, piano, categoria)
