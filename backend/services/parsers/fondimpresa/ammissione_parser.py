"""Parser PDF lettera ammissione Fondimpresa."""
import re
from datetime import date

from services.parsers.base_parser import BaseDocumentParser


_MONTHS = {
    "gennaio": 1,
    "febbraio": 2,
    "marzo": 3,
    "aprile": 4,
    "maggio": 5,
    "giugno": 6,
    "luglio": 7,
    "agosto": 8,
    "settembre": 9,
    "ottobre": 10,
    "novembre": 11,
    "dicembre": 12,
}


def _clean_text(value: str | None) -> str | None:
    if not value:
        return None
    return re.sub(r"\s+", " ", value).strip(" :;\n\t")


def _clean_amount(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value.replace(".", "").replace(",", ".").strip())
    except Exception:
        return None


def _parse_italian_date(value: str | None) -> date | None:
    if not value:
        return None
    match = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", value, re.IGNORECASE)
    if not match:
        return None
    month = _MONTHS.get(match.group(2).lower())
    if not month:
        return None
    return date(int(match.group(3)), month, int(match.group(1)))


def _extract(regex: str, text: str, flags=re.IGNORECASE) -> str | None:
    match = re.search(regex, text, flags)
    return _clean_text(match.group(1)) if match else None


class AmmissioneParser(BaseDocumentParser):
    def parse(self, filepath: str) -> dict:
        warnings: list[str] = []
        try:
            import pdfplumber
        except ImportError:
            return _empty(warnings + ["pdfplumber non disponibile"])

        try:
            with pdfplumber.open(filepath) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        except Exception as exc:
            return _empty(warnings + [f"Impossibile leggere PDF: {exc}"])

        flat = re.sub(r"\s+", " ", text)

        codice = _extract(r"codice\s+(?:piano\s+)?([A-Z]{2}\d+/\d+/\d+)", flat) or _extract(r"\b([A-Z]{2}\d+/\d+/\d+)\b", flat)
        cup = _extract(r"codice\s+CUP\s+([A-Z0-9]+)", flat) or _extract(r"\bCUP\s+([A-Z0-9]{10,20})\b", flat)
        importo = _clean_amount(_extract(r"importo\s+massimo\s+di\s+[€£]\s*([\d.,]+)", flat))
        determina_raw = _extract(
            r"Determina\s+del\s+Direttore\s+Generale\s+del\s+giorno\s+(\d+\s+\w+\s+\d{4})",
            flat,
        )
        determina_data = _parse_italian_date(determina_raw)

        titolo = _extract(
            r"(?:titolo\s+(?:del\s+)?piano|piano\s+dal\s+titolo)\s*[:\-]?\s*[\"']?(.+?)(?:[\"']?\s+(?:codice|CUP|presentato|ammesso|per\s+un\s+importo)|$)",
            flat,
        )
        if titolo:
            titolo = titolo.strip("\"' ")
        if not titolo:
            for line in text.splitlines():
                if "CLICK:" in line:
                    titolo = _clean_text(line.strip("\"' "))
                    break

        soggetto = _extract(
            r"(?:Soggetto\s+Attuatore|soggetto\s+attuatore)\s*[:\-]?\s*(.+?)(?:\s+(?:codice|CUP|piano|con\s+codice|e\s+ammesso)|$)",
            flat,
        )
        if not soggetto:
            soggetto = _extract(r"(?:presentato\s+da|presentato\s+dal)\s+(.+?)(?:\s+(?:codice|CUP|piano|ammesso)|$)", flat)

        avviso = _extract(r"(?:Avviso|avviso)\s*(?:n\.?|numero)?\s*([0-9]+/[0-9]{4})", flat)

        for label, value in [
            ("codice piano", codice),
            ("CUP", cup),
            ("importo massimo", importo),
            ("determina", determina_data),
        ]:
            if not value:
                warnings.append(f"{label} non trovato nella lettera di ammissione")

        return {
            "ente": "Fondimpresa",
            "codice_piano": codice,
            "titolo_piano": titolo,
            "soggetto_attuatore": soggetto,
            "importo_totale": importo,
            "contributo_ente": importo,
            "cofinanziamento": 0.0,
            "data_approvazione": determina_data,
            "determina_numero": None,
            "determina_data": determina_data,
            "cup": cup,
            "id_piano_esterno": None,
            "avviso_numero": avviso,
            "aziende_beneficiarie": [],
            "azioni_formative": [],
            "piano_finanziario": [],
            "warnings": warnings,
        }


def _empty(warnings: list[str]) -> dict:
    return {
        "ente": "Fondimpresa",
        "codice_piano": None,
        "titolo_piano": None,
        "soggetto_attuatore": None,
        "importo_totale": None,
        "contributo_ente": None,
        "cofinanziamento": None,
        "data_approvazione": None,
        "determina_numero": None,
        "determina_data": None,
        "cup": None,
        "id_piano_esterno": None,
        "avviso_numero": None,
        "aziende_beneficiarie": [],
        "azioni_formative": [],
        "piano_finanziario": [],
        "warnings": warnings,
    }
