"""Parser PDF per convenzioni FAPI — basato sulla struttura reale del documento."""
import re
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── regex pagina 1 ────────────────────────────────────────────────────────────

_RE_CODICE_PIANO = re.compile(r"Cod\.?\s*Piano\s*:\s*([A-Z0-9]{10,20})", re.IGNORECASE)
_RE_CONTRIBUTO_FAPI = re.compile(r"Contributo\s+FAPI\s*:\s*€\s*([\d.,]+)", re.IGNORECASE)
_RE_COFINANZIAMENTO = re.compile(r"Cofinanziamento\s*[:\s]*€\s*([\d.,]+)", re.IGNORECASE)
_RE_COSTO_TOTALE = re.compile(r"Costo\s+Totale\s*:\s*€\s*([\d.,]+)", re.IGNORECASE)
_RE_DELIBERA = re.compile(
    r"Delibera\s+C\.d\.A\./Determin\.\s*Presid\.\s*n\s*(\d+)\s+del\s+(\d{1,2}/\d{1,2}/\d{4})",
    re.IGNORECASE,
)

# ── regex pagina 3 (ente attuatore) ───────────────────────────────────────────
# Cerca "RAGIONE SOCIALE, con sede legale ... C.F./P.IVA XXXXXXXXXXX"
# Il pattern con "C.F./P.IVA" (con slash) identifica il soggetto attuatore
_RE_ENTE_PIVA = re.compile(
    r"([A-Z][A-Z0-9À-ÿ\s\.,&'\-]{2,60}?),\s*con\s+sede\s+legale\s+in\s+[^,]+,[^,]+,\s*C\.F\./P\.IVA\s+(\d{11})",
    re.IGNORECASE,
)


def _clean_importo(raw: str) -> float | None:
    try:
        return float(raw.strip().replace(".", "").replace(",", "."))
    except Exception:
        return None


def _parse_date(raw: str) -> str | None:
    try:
        parts = re.split(r"[/\-\.]", raw.strip())
        if len(parts) == 3:
            d, m, y = parts
            if len(y) == 2:
                y = "20" + y
            return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    except Exception:
        pass
    return None


def _fix_codice(raw: str) -> str:
    """Join newlines within codice progetto: '20250611CMI\nA00101' → '20250611CMIA00101'."""
    return raw.replace("\n", "").replace(" ", "").upper()


def _header_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _estrai_allegati(
    pages_tables: list[list[list[list[Any]]]],
    codice_piano: str | None,
) -> tuple[list[str], list[dict]]:
    """Trova Allegato A/B dalle intestazioni, anche con allegati successivi.

    Le convenzioni possono contenere un Allegato C dopo le due tabelle utili:
    affidarsi a "penultima/ultima pagina" trasforma allora nomi di aziende in
    codici progetto e perde tutte le beneficiarie.
    """
    codici: list[str] = []
    aziende: list[dict] = []
    for page_tables in pages_tables:
        for table in page_tables or []:
            if not table or not table[0]:
                continue
            headers = [_header_key(cell) for cell in table[0]]
            codice_idx = next(
                (i for i, value in enumerate(headers) if "codiceprogetto" in value),
                None,
            )
            titolo_idx = next(
                (i for i, value in enumerate(headers) if value == "titolo"),
                None,
            )
            ragione_idx = next(
                (i for i, value in enumerate(headers) if "ragionesociale" in value),
                None,
            )
            partecipanti_idx = next(
                (i for i, value in enumerate(headers) if "partec" in value),
                None,
            )
            totale_idx = next(
                (i for i, value in enumerate(headers) if value.endswith("totale")),
                None,
            )

            if codice_idx is not None and titolo_idx is not None:
                for row in table[1:]:
                    if len(row) <= codice_idx or not row[codice_idx]:
                        continue
                    codice = _fix_codice(str(row[codice_idx]))
                    if (
                        15 <= len(codice) <= 24
                        and codice.isalnum()
                        and codice != _fix_codice(codice_piano or "")
                        and codice not in codici
                    ):
                        codici.append(codice)

            if (
                ragione_idx is not None
                and codice_idx is not None
                and partecipanti_idx is not None
            ):
                for row in table[1:]:
                    if len(row) <= ragione_idx or not row[ragione_idx]:
                        continue
                    ragione_sociale = str(row[ragione_idx]).strip()
                    if ragione_sociale.lower() in {"totale", "totali", "data"}:
                        continue
                    num_part = None
                    if len(row) > partecipanti_idx and row[partecipanti_idx]:
                        try:
                            num_part = int(str(row[partecipanti_idx]).strip())
                        except (TypeError, ValueError):
                            pass
                    codice_progetto = None
                    if len(row) > codice_idx and row[codice_idx]:
                        codice_progetto = _fix_codice(str(row[codice_idx]))
                    totale = None
                    if totale_idx is not None and len(row) > totale_idx and row[totale_idx]:
                        totale = _clean_importo(str(row[totale_idx]).replace("€", ""))
                    aziende.append({
                        "ragione_sociale": ragione_sociale,
                        "partita_iva": None,
                        "codice_fiscale": None,
                        "num_partecipanti": num_part,
                        "codice_progetto": codice_progetto,
                        "importo": totale,
                    })
    return codici, aziende


def parse_convenzione(pdf_path: str) -> dict[str, Any]:
    """
    Parsa PDF convenzione FAPI.
    Struttura attesa:
      - Pag 1: Cod. Piano, Contributo FAPI, Cofinanziamento, Delibera, Costo Totale
      - Pag 3: Ente attuatore con P.IVA
      - Allegato A: tabella progetti, riconosciuta dalle intestazioni
      - Allegato B: tabella aziende beneficiarie, riconosciuta dalle
        intestazioni (può essere seguita da Allegato C)
    """
    warnings: list[str] = []

    try:
        import pdfplumber
    except ImportError:
        return {"piano": {}, "ente_attuatore": {}, "aziende_beneficiarie": [], "codici_progetto": [], "warnings": ["pdfplumber non disponibile"]}

    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages_text = [p.extract_text() or "" for p in pdf.pages]
            pages_tables = [p.extract_tables() for p in pdf.pages]
    except Exception as exc:
        return {"piano": {}, "ente_attuatore": {}, "aziende_beneficiarie": [], "codici_progetto": [], "warnings": [f"Impossibile leggere PDF: {exc}"]}

    full_text = "\n".join(pages_text)

    # Le firme digitali possono anteporre pagine senza testo: cerchiamo nel
    # documento, non nell'indice fisico della prima pagina.
    p1 = full_text

    m = _RE_CODICE_PIANO.search(p1)
    codice_piano = m.group(1).strip() if m else None
    if not codice_piano:
        warnings.append("Codice piano non trovato")

    m = _RE_DELIBERA.search(p1)
    delibera_numero = m.group(1) if m else None
    delibera_data = _parse_date(m.group(2)) if m else None
    if not delibera_numero:
        warnings.append("Delibera CdA non trovata in pagina 1")

    m = _RE_CONTRIBUTO_FAPI.search(p1)
    contributo_ente = _clean_importo(m.group(1)) if m else None

    m = _RE_COFINANZIAMENTO.search(p1)
    cofinanziamento = _clean_importo(m.group(1)) if m else None

    m = _RE_COSTO_TOTALE.search(p1)
    costo_totale = _clean_importo(m.group(1)) if m else None

    # ── Ente attuatore (pagina 3 o prima che lo contiene) ────────────────────
    # Cerca "RAGIONE SOCIALE, con sede legale ... C.F./P.IVA XXXXXXXXXXX" su una sola riga
    ente_ragione = None
    ente_piva = None
    _re_ente_line = re.compile(
        r"^(.+?),\s*con\s+sede\s+legale\s+in\s+.+C\.F\./P\.IVA\s+(\d{11})",
        re.IGNORECASE,
    )
    for pt in pages_text:
        for line in pt.splitlines():
            m = _re_ente_line.match(line.strip())
            if m:
                ente_ragione = m.group(1).strip()
                ente_piva = m.group(2)
                break
        if ente_piva:
            break
    if not ente_piva:
        warnings.append("P.IVA ente attuatore non trovata")

    codici_progetto, aziende = _estrai_allegati(pages_tables, codice_piano)

    if not aziende:
        warnings.append("Nessuna azienda estratta dall'Allegato B")
    if not codici_progetto:
        warnings.append("Nessun codice progetto estratto dall'Allegato A")

    return {
        "piano": {
            "codice_fapi": codice_piano,
            "titolo": None,   # non presente in convenzione, viene dal formulario
            "delibera_numero": delibera_numero,
            "delibera_data": delibera_data,
            "costo_totale": costo_totale,
            "contributo_ente": contributo_ente,
            "cofinanziamento": cofinanziamento,
        },
        "ente_attuatore": {
            "ragione_sociale": ente_ragione,
            "partita_iva": ente_piva,
        },
        "aziende_beneficiarie": aziende,
        "codici_progetto": codici_progetto,
        "warnings": warnings,
    }
