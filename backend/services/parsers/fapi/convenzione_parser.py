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


def parse_convenzione(pdf_path: str) -> dict[str, Any]:
    """
    Parsa PDF convenzione FAPI.
    Struttura attesa:
      - Pag 1: Cod. Piano, Contributo FAPI, Cofinanziamento, Delibera, Costo Totale
      - Pag 3: Ente attuatore con P.IVA
      - Pag penultima: Allegato A — tabella progetti
      - Pag ultima: Allegato B — tabella aziende beneficiarie (NO P.IVA)
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

    # ── Pagina 1: campi piano ─────────────────────────────────────────────────
    p1 = pages_text[0] if pages_text else ""

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
    for pt in pages_text[:5]:
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

    # ── Allegato A (penultima pagina) ─────────────────────────────────────────
    codici_progetto: list[str] = []
    allegato_a_tables = pages_tables[-2] if len(pages_tables) >= 2 else []
    for table in allegato_a_tables:
        if not table:
            continue
        header = [str(c or "").strip() for c in table[0]]
        if "Codice" not in " ".join(header) and "Titolo" not in " ".join(header):
            continue
        for row in table[1:]:
            if not row or not row[0]:
                continue
            codice_raw = str(row[0]).strip()
            codice = _fix_codice(codice_raw)
            if len(codice) >= 15 and codice != _fix_codice(codice_piano or ""):
                codici_progetto.append(codice)

    # ── Allegato B (ultima pagina) ────────────────────────────────────────────
    aziende: list[dict] = []
    allegato_b_tables = pages_tables[-1] if pages_tables else []
    for table in allegato_b_tables:
        if not table:
            continue
        header = [str(c or "").strip() for c in table[0]]
        header_flat = " ".join(header)
        if "Ragione" not in header_flat and "Sociale" not in header_flat:
            continue
        for row in table[1:]:
            if not row or not row[0]:
                continue
            ragione_sociale = str(row[0]).strip()
            if not ragione_sociale or ragione_sociale.lower() in {"totale", "totali", "data"}:
                continue

            # n. partecipanti
            num_part = None
            if len(row) > 1 and row[1]:
                try:
                    num_part = int(str(row[1]).strip())
                except Exception:
                    pass

            # codice progetto
            codice_prog = None
            if len(row) > 2 and row[2]:
                codice_prog = _fix_codice(str(row[2]).strip())

            # totale (ultima colonna)
            totale = None
            for cell in reversed(row):
                if cell and "€" in str(cell):
                    totale = _clean_importo(str(cell).replace("€", ""))
                    break

            aziende.append({
                "ragione_sociale": ragione_sociale,
                "partita_iva": None,        # non presente in Allegato B
                "codice_fiscale": None,     # non presente in Allegato B
                "num_partecipanti": num_part,
                "codice_progetto": codice_prog,
                "importo": totale,
            })

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
