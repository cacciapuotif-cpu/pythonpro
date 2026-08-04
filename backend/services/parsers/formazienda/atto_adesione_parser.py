"""Parser PDF per l'Atto di adesione Formazienda (Allegato E).

A differenza della convenzione FAPI, l'Allegato E non elenca mai aziende
beneficiarie ne' codici progetto: porta solo l'ente attuatore e i dati
del piano. Due trappole verificate sul documento reale:

1. Il piede di pagina ripete "Data approvazione: DD/MM/YYYY" su ogni
   pagina: e' l'approvazione del MODULO da parte del CDA (coincide con la
   tabella "Stato delle revisioni"), non l'approvazione del PIANO. La data
   del piano e' quella citata nelle premesse come "delibera del DD/MM/YYYY".
2. La data di sottoscrizione e' quella della firma digitale PAdES
   sull'ultima pagina, diversa sia dall'emissione del modulo sia dalla
   delibera: si riconosce dal contesto "Data DD/MM/YYYY" seguito da
   "Il dichiarante" / "Firma digitale", non dall'etichetta "Data" isolata.
"""
import re
from typing import Any

_RE_AVVISO = re.compile(r"Avviso\s+n\.?\s*(\d+/\d{4})", re.IGNORECASE)
_RE_ID_PIANO_TITOLO = re.compile(
    r"Piano Formativo ID\s+([A-Za-z0-9\-]+)\s+dal titolo\s+\"([^\"]+)\"",
    re.IGNORECASE,
)
_RE_DELIBERA_PIANO = re.compile(r"delibera del\s+(\d{1,2}/\d{1,2}/\d{4})", re.IGNORECASE)
_RE_IMPORTI = re.compile(
    r"A\s*-\s*Quota pubblica\s+B\s*-\s*Cofinanziamento\s+C\s*-\s*Autofinanziamento\s+"
    r"([\d.,]+)\s*€\s+([\d.,]+)\s*€\s+([\d.,]+)\s*€",
    re.IGNORECASE,
)
_RE_SOTTOSCRIZIONE = re.compile(
    r"Data\s+(\d{1,2}/\d{1,2}/\d{4})\s+Il dichiarante\s+Firma digitale",
    re.IGNORECASE,
)
_RE_ENTE_BLOCCO = re.compile(
    r"Il sottoscritto\s+(.+?)\s+nato\s+a\s+(.+?)\s+il\s+(\d{1,2}/\d{1,2}/\d{4})"
    r".*?residente in\s+(.+?)\s+Cap\s+\d{5}\s+Comune\s+(.+?)\s+Provincia\s+\S+"
    r".*?avente sede legale in\s+(.+?)\s+Cap\s+(\d{5})\s+Comune\s+(.+?)\s+Provincia\s+(\S+)"
    r".*?dell.{0,2}impresa\s+(.+?)\s+Codice Fiscale:\s*(\S+)\s+Partita IVA:\s*(\d{11})",
    re.IGNORECASE | re.DOTALL,
)


def _clean_importo(raw: str) -> float | None:
    try:
        return float(raw.strip().replace(".", "").replace(",", "."))
    except Exception:
        return None


def _parse_date(raw: str) -> str | None:
    try:
        d, m, y = re.split(r"[/\-.]", raw.strip())
        return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    except Exception:
        return None


def _split_cognome_nome(raw: str) -> tuple[str | None, str | None]:
    parti = raw.split()
    if len(parti) < 2:
        return (raw.strip() or None, None)
    return (" ".join(parti[:-1]), parti[-1])


def parse_atto_adesione(pdf_path: str) -> dict[str, Any]:
    warnings: list[str] = []

    try:
        import pdfplumber
    except ImportError:
        return {
            "piano": {}, "ente_attuatore": {}, "aziende_beneficiarie": [],
            "codici_progetto": [], "warnings": ["pdfplumber non disponibile"],
        }

    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages_text = [p.extract_text() or "" for p in pdf.pages]
    except Exception as exc:
        return {
            "piano": {}, "ente_attuatore": {}, "aziende_beneficiarie": [],
            "codici_progetto": [], "warnings": [f"Impossibile leggere PDF: {exc}"],
        }

    full_text = "\n".join(pages_text)
    flat = re.sub(r"\s+", " ", full_text)

    m = _RE_ID_PIANO_TITOLO.search(flat)
    id_piano_esterno = m.group(1) if m else None
    titolo = m.group(2) if m else None
    if not id_piano_esterno and not titolo:
        warnings.append("ID piano e titolo non trovati")

    m = _RE_AVVISO.search(flat)
    avviso = m.group(1) if m else None
    if not avviso:
        warnings.append("Avviso non trovato")

    m = _RE_DELIBERA_PIANO.search(flat)
    delibera_data = _parse_date(m.group(1)) if m else None
    if not delibera_data:
        warnings.append("Delibera di approvazione del piano non trovata nelle premesse")

    m = _RE_SOTTOSCRIZIONE.search(flat)
    data_sottoscrizione = _parse_date(m.group(1)) if m else None
    if not data_sottoscrizione:
        warnings.append("Data di sottoscrizione (firma digitale) non trovata")

    quota_pubblica = cofinanziamento = autofinanziamento = None
    m = _RE_IMPORTI.search(flat)
    if m:
        quota_pubblica = _clean_importo(m.group(1))
        cofinanziamento = _clean_importo(m.group(2))
        autofinanziamento = _clean_importo(m.group(3))
    else:
        warnings.append("Importi A/B/C non trovati")
    costo_totale = (
        (quota_pubblica or 0) + (cofinanziamento or 0)
        if quota_pubblica is not None or cofinanziamento is not None
        else None
    )

    ente_attuatore: dict[str, Any] = {}
    m = _RE_ENTE_BLOCCO.search(flat)
    if m:
        cognome_lr, nome_lr = _split_cognome_nome(m.group(1).strip())
        luogo_nascita = m.group(2).strip()
        data_nascita = _parse_date(m.group(3))
        via_residenza = m.group(4).strip()
        comune_residenza = m.group(5).strip()
        indirizzo = m.group(6).strip()
        cap = m.group(7).strip()
        citta = m.group(8).strip()
        provincia = m.group(9).strip()
        ragione_sociale = m.group(10).strip()
        codice_fiscale = m.group(11).strip()
        partita_iva = m.group(12).strip()
        ente_attuatore = {
            "ragione_sociale": ragione_sociale,
            "codice_fiscale": codice_fiscale,
            "partita_iva": partita_iva,
            "indirizzo": indirizzo,
            "cap": cap,
            "citta": citta,
            "provincia": provincia,
            "legale_rappresentante_nome": nome_lr,
            "legale_rappresentante_cognome": cognome_lr,
            "legale_rappresentante_luogo_nascita": luogo_nascita,
            "legale_rappresentante_data_nascita": data_nascita,
            "legale_rappresentante_comune_residenza": comune_residenza,
            "legale_rappresentante_via_residenza": via_residenza,
        }
    else:
        warnings.append("Ente attuatore (Soggetto Gestore) non trovato")

    return {
        "piano": {
            "codice_fapi": None,
            "id_piano_esterno": id_piano_esterno,
            "titolo": titolo,
            "avviso": avviso,
            "delibera_numero": None,
            "delibera_data": delibera_data,
            "data_sottoscrizione": data_sottoscrizione,
            "quota_pubblica": quota_pubblica,
            "cofinanziamento": cofinanziamento,
            "autofinanziamento": autofinanziamento,
            "costo_totale": costo_totale,
        },
        "ente_attuatore": ente_attuatore,
        "aziende_beneficiarie": [],
        "codici_progetto": [],
        "warnings": warnings,
    }
