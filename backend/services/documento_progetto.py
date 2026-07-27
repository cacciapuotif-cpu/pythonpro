"""UX-6 — associazione di un atto/convenzione a un progetto gia' esistente.

Caricare un documento dentro un progetto non deve mai generare un progetto
gemello: i dati estratti vanno riversati sul progetto corrente. Questo modulo
tiene la parte di dominio della riconciliazione, cosi' i router restano sottili
e la stessa regola vale per tutti i fondi.

Regola non negoziabile: **nessuna sovrascrittura silenziosa**. Un campo vuoto
sul progetto viene arricchito; un campo gia' valorizzato e discordante diventa
un conflitto, che l'utente deve accettare campo per campo. Un dato gia'
validato da un operatore non viene ribaltato da un parser.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterable, Optional


@dataclass(frozen=True)
class CampoDocumento:
    """Campo del progetto alimentabile dal documento."""

    nome: str
    etichetta: str
    tipo: str  # "testo" | "data" | "numero"


# Campi che un atto/convenzione puo' alimentare sul progetto. L'ordine e'
# quello in cui il diff viene mostrato all'operatore.
CAMPI_DOCUMENTO: tuple[CampoDocumento, ...] = (
    CampoDocumento("codice_fapi", "Codice piano", "testo"),
    CampoDocumento("name", "Titolo del piano", "testo"),
    CampoDocumento("cup", "CUP", "testo"),
    CampoDocumento("id_piano_esterno", "ID piano sul portale del fondo", "testo"),
    CampoDocumento("avviso", "Avviso", "testo"),
    CampoDocumento("delibera_numero", "Numero delibera", "testo"),
    CampoDocumento("delibera_data", "Data delibera", "data"),
    CampoDocumento("data_approvazione", "Data approvazione", "data"),
    CampoDocumento("costo_totale", "Costo totale", "numero"),
    CampoDocumento("contributo_ente", "Contributo del fondo", "numero"),
    CampoDocumento("cofinanziamento", "Cofinanziamento", "numero"),
    CampoDocumento("budget", "Budget", "numero"),
    CampoDocumento("ente_attuatore_id", "Ente attuatore", "numero"),
    CampoDocumento("convenzione_file_path", "Documento allegato", "testo"),
)

_CAMPI_PER_NOME = {c.nome: c for c in CAMPI_DOCUMENTO}


def parse_data(valore: Any) -> Optional[date]:
    """Data da stringa ISO; ``None`` se assente o non interpretabile."""
    if valore is None or valore == "":
        return None
    if isinstance(valore, datetime):
        return valore.date()
    if isinstance(valore, date):
        return valore
    try:
        return datetime.strptime(str(valore), "%Y-%m-%d").date()
    except ValueError:
        return None


def _coerce(campo: CampoDocumento, valore: Any) -> Any:
    if valore is None or valore == "":
        return None
    if campo.tipo == "data":
        return parse_data(valore)
    if campo.tipo == "numero":
        try:
            return float(valore)
        except (TypeError, ValueError):
            return None
    return str(valore).strip() or None


def _vuoto(valore: Any) -> bool:
    """Un campo e' vuoto solo se non ha valore: lo zero e' un valore."""
    return valore is None or (isinstance(valore, str) and not valore.strip())


def _uguali(campo: CampoDocumento, attuale: Any, estratto: Any) -> bool:
    if campo.tipo == "numero":
        try:
            return abs(float(attuale) - float(estratto)) < 0.005
        except (TypeError, ValueError):
            return False
    if campo.tipo == "data":
        return parse_data(attuale) == parse_data(estratto)
    return str(attuale).strip() == str(estratto).strip()


def _serializza(valore: Any) -> Any:
    if isinstance(valore, (date, datetime)):
        return valore.isoformat()
    return valore


def calcola_diff(progetto, estratti: dict[str, Any]) -> list[dict[str, Any]]:
    """Confronto campo per campo tra progetto e dati estratti dal documento.

    Ritorna solo i campi per cui il documento porta effettivamente un valore.
    ``conflitto=True`` significa: il progetto ha gia' un valore diverso, quindi
    l'applicazione richiede una scelta esplicita dell'operatore.
    """
    diff: list[dict[str, Any]] = []
    for campo in CAMPI_DOCUMENTO:
        estratto = _coerce(campo, estratti.get(campo.nome))
        if estratto is None:
            continue
        attuale = getattr(progetto, campo.nome, None)
        if not _vuoto(attuale) and _uguali(campo, attuale, estratto):
            continue
        diff.append({
            "campo": campo.nome,
            "etichetta": campo.etichetta,
            "valore_attuale": _serializza(attuale),
            "valore_estratto": _serializza(estratto),
            "conflitto": not _vuoto(attuale),
        })
    return diff


def applica_estratti(
    progetto,
    estratti: dict[str, Any],
    campi_da_applicare: Optional[Iterable[str]] = None,
) -> dict[str, list[str]]:
    """Riversa i dati estratti sul progetto rispettando i conflitti.

    I campi vuoti sono arricchiti sempre; quelli in conflitto solo se elencati
    in ``campi_da_applicare``. Ritorna i nomi dei campi applicati e di quelli
    lasciati indietro, cosi' il chiamante puo' dirlo all'operatore.
    """
    accettati = set(campi_da_applicare or ())
    applicati: list[str] = []
    non_applicati: list[str] = []

    for voce in calcola_diff(progetto, estratti):
        campo = _CAMPI_PER_NOME[voce["campo"]]
        if voce["conflitto"] and campo.nome not in accettati:
            non_applicati.append(campo.nome)
            continue
        setattr(progetto, campo.nome, _coerce(campo, estratti.get(campo.nome)))
        applicati.append(campo.nome)

    return {"campi_applicati": applicati, "campi_in_conflitto_non_applicati": non_applicati}


def documento_riconosciuto(piano: dict[str, Any]) -> bool:
    """Il parser ha identificato il documento come atto del fondo?

    Senza almeno il codice del piano o il titolo non c'e' nulla che identifichi
    l'atto: creare un progetto da un simile estratto produce solo un fantasma
    col nome di fallback. E' quello che ha generato il progetto 13 in
    produzione.
    """
    return bool((piano.get("codice_fapi") or "").strip() or (piano.get("titolo") or "").strip())
