"""Parser PDF per il Formulario di candidatura Formazienda (Allegato A).

Complementare all'Atto di adesione (Allegato E): l'Allegato E porta l'ente
e gli importi approvati, l'Allegato A porta le imprese beneficiarie, il
progetto formativo e le macrovoci di dettaglio. Nessuno dei due basta da
solo (vedi atto_adesione_parser.py per le trappole sulle date, identiche
qui: il piede di pagina "Data approvazione" e' del MODULO, non del piano).
"""
import re
from typing import Any

_RE_TITOLO_PIANO = re.compile(r"I\.1\.\s*Titolo Piano Formativo\s*\n(.+)")
_RE_TIPOLOGIA_PIANO = re.compile(r"I\.2\.\s*Tipologia Piano Formativo\s*\n(.+)")
_RE_TEMATICHE = re.compile(r"I\.3\.\s*Tematiche di intervento\s*\n((?:•.+\n?)+)")

_RE_ANAGRAFICA = re.compile(
    r"Ragione sociale\s+(.+?)\s*\n"
    r"Sede legale in\s+(.+?)\s+Cap\s+(\d{5})\s+Citt[aà]\s+(.+?)\s+Prov\.\s+(\S+)\s*\n"
    r"Tel\.\s*(\S*)\s*\n"
    r"eMail\s*(\S*)\s*Pec\s*(\S*)\s*\n"
    r"Codice Fiscale\s+(\S+)\s+Partita IVA\s+(\d{11})\s*\n"
    r"Legale rappresentante\s*\([^)]*\)\s*:\s*(.+?)\s*\n",
    re.IGNORECASE,
)

_RE_DELEGA_TIPOLOGIA = re.compile(r"Tipologia Soggetto Delegato\s*\n(.+)")
_RE_DELEGA_IMPORTO = re.compile(
    r"Importo attivit[aà] in delega\s+([\d.,]+)\s*€\s+([\d.,]+)\s*%",
    re.IGNORECASE,
)


def _clean_importo(raw: str) -> float | None:
    try:
        return float(raw.strip().replace(".", "").replace(",", "."))
    except Exception:
        return None


def _clean_pct(raw: str) -> float | None:
    try:
        return float(raw.strip().replace(",", "."))
    except Exception:
        return None


def _parse_anagrafica_blocco(testo: str) -> dict[str, Any] | None:
    m = _RE_ANAGRAFICA.search(testo)
    if not m:
        return None
    legale = m.group(11).strip()
    parti = legale.split()
    cognome, nome = (" ".join(parti[:-1]), parti[-1]) if len(parti) >= 2 else (legale, None)
    return {
        "ragione_sociale": m.group(1).strip(),
        "indirizzo": m.group(2).strip(),
        "cap": m.group(3).strip(),
        "citta": m.group(4).strip(),
        "provincia": m.group(5).strip(),
        "telefono": m.group(6).strip() or None,
        "email": m.group(7).strip() or None,
        "pec": m.group(8).strip() or None,
        "codice_fiscale": m.group(9).strip(),
        "partita_iva": m.group(10).strip(),
        "legale_rappresentante_cognome": cognome,
        "legale_rappresentante_nome": nome,
    }


def parse_formulario(pdf_path: str) -> dict[str, Any]:
    warnings: list[str] = []
    try:
        import pdfplumber
    except ImportError:
        return {"warnings": ["pdfplumber non disponibile"], "imprese_beneficiarie": [],
                "soggetti_partner": [], "progetti_formativi": [], "riepilogo": {}}

    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages_text = [p.extract_text() or "" for p in pdf.pages]
    except Exception as exc:
        return {"warnings": [f"Impossibile leggere PDF: {exc}"], "imprese_beneficiarie": [],
                "soggetti_partner": [], "progetti_formativi": [], "riepilogo": {}}

    full_text = "\n".join(pages_text)

    # Sezione 1 termina all'inizio della Sezione 2: e' il confine che tiene
    # separati Soggetto Gestore/Delegato dalle imprese beneficiarie (trappola
    # #1 e #2 del campione: nessuno dei due e' una beneficiaria).
    idx_sezione2 = full_text.find("Sezione 2.")
    sezione1 = full_text[: idx_sezione2 if idx_sezione2 != -1 else len(full_text)]

    piano: dict[str, Any] = {}
    m = _RE_TITOLO_PIANO.search(sezione1)
    piano["titolo"] = m.group(1).strip() if m else None
    m = _RE_TIPOLOGIA_PIANO.search(sezione1)
    piano["tipologia"] = m.group(1).strip() if m else None
    m = _RE_TEMATICHE.search(sezione1)
    piano["tematiche"] = (
        [riga.lstrip("•").strip() for riga in m.group(1).strip().splitlines() if riga.strip()]
        if m else []
    )
    if not piano["titolo"]:
        warnings.append("Titolo piano non trovato in Sezione 1")

    idx_gestore = sezione1.find("I.4.")
    idx_delega = sezione1.find("I.5.")
    idx_partner = sezione1.find("I.6.")
    blocco_gestore = sezione1[idx_gestore:idx_delega] if idx_gestore != -1 else ""
    blocco_delega = sezione1[idx_delega:idx_partner] if idx_delega != -1 and idx_partner != -1 else ""

    soggetto_gestore = _parse_anagrafica_blocco(blocco_gestore) or {}
    if not soggetto_gestore:
        warnings.append("Soggetto Gestore non trovato in I.4")

    soggetto_delegato: dict[str, Any] = {}
    dati_delega = _parse_anagrafica_blocco(blocco_delega)
    if dati_delega:
        soggetto_delegato = dict(dati_delega)
        m = _RE_DELEGA_TIPOLOGIA.search(blocco_delega)
        soggetto_delegato["tipologia"] = m.group(1).strip() if m else None
        m = _RE_DELEGA_IMPORTO.search(sezione1)
        if m:
            soggetto_delegato["importo"] = _clean_importo(m.group(1))
            soggetto_delegato["percentuale"] = _clean_pct(m.group(2))
        else:
            soggetto_delegato["importo"] = None
            soggetto_delegato["percentuale"] = None
            warnings.append("Importo/percentuale del soggetto delegato non trovati (I.5.2)")
    # I.6 Soggetti Terzi Partner: nel campione e' vuoto. Nessun blocco
    # "Ragione sociale" tra I.6 e la fine della Sezione 1 = nessun partner,
    # non un errore di parsing (trappola #6-stile: campo assente e' vuoto).
    soggetti_partner: list[dict[str, Any]] = []

    return {
        "piano": piano,
        "soggetto_gestore": soggetto_gestore,
        "soggetto_delegato": soggetto_delegato,
        "soggetti_partner": soggetti_partner,
        "imprese_beneficiarie": [],
        "progetti_formativi": [],
        "riepilogo": {},
        "warnings": warnings,
    }
