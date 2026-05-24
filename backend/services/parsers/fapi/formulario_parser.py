"""Parser PDF per formulari FAPI — basato sulla struttura reale del documento."""
import re
import logging
from typing import Any

logger = logging.getLogger(__name__)

_RE_CODICE_FAPI_LUNGO = re.compile(r"(20\d{6}[A-Z]{4}\d{5})")   # es 20250611CMIA00101
_RE_CF_PERSONA = re.compile(r"\b([A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z])\b", re.IGNORECASE)
_RE_PIVA = re.compile(r"\b(\d{11})\b")

_MODALITA_MAP = {
    "training on-the-job": "training_on_job",
    "training on the job": "training_on_job",
    "aula": "aula",
    "ambienti strutturati": "aula",
    "fad sincrona": "fad_sincrona",
    "fad - sincrona": "fad_sincrona",
    "fad asincrona": "fad_asincrona",
    "analisi organizzativa": "propedeutica",
    "analisi dei fabbisogni": "propedeutica",
    "analisi fabbisogni": "propedeutica",
    "attività propedeutica": "propedeutica",
}

_REGIME_AIUTO_MAP = {
    "regolamento (ce) n. 651/2014 (esenzione)": "esenzione",
    "regolamento (ce) n. 1407/2013 (de minimis)": "de_minimis",
    "regolamento (ce) n. 1408/2013 (de minimis)": "de_minimis",
}


def _map_modalita(raw: str) -> str:
    rl = raw.lower().strip()
    for key, val in _MODALITA_MAP.items():
        if key in rl:
            return val
    return "aula"


def _clean_cell(cell) -> str:
    return re.sub(r"\s+", " ", str(cell or "").replace("\n", " ")).strip()


def _clean_code(cell) -> str | None:
    value = re.sub(r"\s+", "", str(cell or "")).upper()
    return value or None


def _clean_email(cell) -> str | None:
    value = re.sub(r"\s+", "", str(cell or "")).lower()
    return value or None


def _clean_natura_giuridica(cell) -> str | None:
    value = _clean_cell(cell)
    compact = value.replace(" ", "").upper()
    if compact == "ASSOCIAZIONE":
        return "ASSOCIAZIONE"
    return value or None


def _clean_int(cell) -> int | None:
    value = _clean_cell(cell)
    if not value:
        return None
    try:
        return int(float(value.replace(",", ".")))
    except Exception:
        return None


def _map_regime_aiuto(raw: str | None) -> str | None:
    if not raw:
        return None
    normalized = _clean_cell(raw).lower()
    for label, value in _REGIME_AIUTO_MAP.items():
        if label in normalized:
            return value
    if "esenzione" in normalized:
        return "esenzione"
    if "de minimis" in normalized:
        return "de_minimis"
    return None


def _table_header(table: list) -> list[str]:
    if not table:
        return []
    return [_clean_cell(c).lower() for c in table[0]]


def _is_table(table: list, *needles: str) -> bool:
    header = " ".join(_table_header(table))
    return all(needle.lower() in header for needle in needles)


def _merge_azienda(existing: dict, detail: dict) -> bool:
    changed = False
    for key, value in detail.items():
        if value in (None, ""):
            continue
        if not existing.get(key):
            existing[key] = value
            changed = True
    return changed


def _clean_ore(cell) -> float | None:
    s = _clean_cell(cell)
    try:
        return float(s.replace(",", "."))
    except Exception:
        return None


def _is_moduli_header(row: list) -> tuple[bool, str]:
    """Ritorna (is_header, tipo) dove tipo = 'formativa' | 'propedeutica'."""
    if not row:
        return False, ""
    cells = [_clean_cell(c).lower() for c in row]
    has_titolo = any("titolo" in c for c in cells)
    has_ore = any(c == "ore" for c in cells)
    has_modalita = any("modalit" in c for c in cells)
    if not (has_titolo and has_ore and has_modalita):
        return False, ""
    has_tipo = any(c == "tipo" for c in cells)
    has_tematica = any("tematica" in c for c in cells)
    if has_tipo:
        return True, "propedeutica"
    if has_tematica:
        return True, "formativa"
    return True, "formativa"


def _parse_moduli_rows(table: list, tipo_attivita: str, codice_pg: str | None) -> list[dict]:
    """Parse righe moduli da tabella (header escluso, skip Totali)."""
    moduli = []
    for row in table[1:]:
        if not row:
            continue
        titolo = _clean_cell(row[0])
        if not titolo or titolo.lower() in {"totali", "totale"}:
            continue
        if len(titolo) < 3:
            continue

        # col 1: tematica o tipo
        materia = _clean_cell(row[1]) if len(row) > 1 else ""
        # col 2: modalità
        modalita_raw = _clean_cell(row[2]) if len(row) > 2 else ""
        # col 3: obiettivo
        obiettivo = _clean_cell(row[3]) if len(row) > 3 else ""
        # col 4: ore
        ore = _clean_ore(row[4]) if len(row) > 4 else None

        modalita = _map_modalita(modalita_raw)
        if tipo_attivita == "propedeutica":
            modalita_eff = modalita  # es propedeutica, fad_sincrona, ecc.
        else:
            modalita_eff = modalita

        moduli.append({
            "codice_progetto_fapi": codice_pg,
            "titolo_modulo": titolo,
            "materia": materia or None,
            "modalita_erogazione": modalita_eff,
            "tipo_attivita": tipo_attivita,
            "ore_previste": ore,
            "obiettivo": obiettivo or None,
        })
    return moduli


def _extract_titolo_piano(page_text: str) -> str | None:
    """Estrae titolo piano da pagina 1 formulario (linea prima del codice piano)."""
    lines = [l.strip() for l in page_text.splitlines() if l.strip()]
    codice_re = re.compile(r"20\d{6}[A-Z]{4}\d{3}")
    for i, line in enumerate(lines):
        if codice_re.search(line) and i > 0:
            candidate = lines[i - 1]
            # il titolo è tutto maiuscolo e abbastanza lungo
            if candidate.isupper() and len(candidate) > 3:
                return candidate
    return None


def _extract_beneficiarie_summary(page_text: str) -> list[dict]:
    """
    Estrae la tabella riepilogativa "2.2 Beneficiarie":
    Ragione Sociale | codice Fiscale | matricola INPS
    """
    aziende = []
    if "2.2 Beneficiarie" not in page_text and "2.2. Beneficiarie" not in page_text:
        return aziende

    lines = page_text.splitlines()
    in_section = False
    for line in lines:
        line = line.strip()
        if "2.2 Beneficiarie" in line or "2.2. Beneficiarie" in line:
            in_section = True
            continue
        if not in_section:
            continue
        if line.startswith("SEZIONE") or (line.startswith("2.") and "Beneficiar" not in line):
            break
        # riga dati: ha CF o P.IVA
        cf_m = _RE_CF_PERSONA.search(line)
        piva_m = _RE_PIVA.search(line)
        if not cf_m and not piva_m:
            continue

        # estrai ragione sociale (tutto prima del CF/PIVA)
        pos = cf_m.start() if cf_m else piva_m.start()
        ragione_sociale = line[:pos].strip()
        if not ragione_sociale:
            continue

        cf = cf_m.group(1).upper() if cf_m else None
        piva_raw = piva_m.group(1) if piva_m else None

        # se CF è di persona fisica, P.IVA è quella successiva nel testo (se presente)
        piva = None
        if piva_raw:
            if cf and piva_raw == cf:
                pass  # CF numerico (società) == P.IVA
            elif len(piva_raw) == 11 and piva_raw.isdigit():
                piva = piva_raw

        # per società (CF numerico), CF = P.IVA
        if cf and re.match(r"^\d{11}$", cf):
            piva = cf
            cf = None

        aziende.append({
            "ragione_sociale": ragione_sociale,
            "codice_fiscale": cf,
            "partita_iva": piva,
        })

    return aziende


def _extract_beneficiaria_detail(page_text: str, tables: list | None = None) -> dict | None:
    """
    Estrae dettaglio da pagina SEZIONE 2.2 ANAGRAFICA BENEFICIARIA:
    Ragione Sociale | Natura Giuridica | Codice Fiscale | Partita Iva | Tipo
    """
    if "SEZIONE 2.2" not in page_text and "2.2.1" not in page_text:
        return None

    result: dict[str, Any] = {
        "ragione_sociale": None,
        "natura_giuridica": None,
        "codice_fiscale": None,
        "partita_iva": None,
        "tipo": None,
        "settore_codice": None,
        "settore_descrizione": None,
        "sede_legale_indirizzo": None,
        "sede_legale_cap": None,
        "sede_legale_comune": None,
        "sede_legale_provincia": None,
        "sede_operativa_indirizzo": None,
        "sede_operativa_cap": None,
        "sede_operativa_comune": None,
        "sede_operativa_provincia": None,
        "legale_rappresentante_nome": None,
        "legale_rappresentante_cf": None,
        "legale_rappresentante_telefono": None,
        "legale_rappresentante_email": None,
        "matricola_inps": None,
        "anno_adesione": None,
        "regime_aiuto": None,
        "num_dipendenti": None,
        "ccnl_prevalente": None,
    }

    for table in tables or []:
        if not table or len(table) < 2:
            continue

        if _is_table(table, "ragione sociale", "partita iva", "tipo"):
            row = table[1]
            result.update({
                "ragione_sociale": _clean_cell(row[0]) if len(row) > 0 else None,
                "natura_giuridica": _clean_natura_giuridica(row[1]) if len(row) > 1 else None,
                "codice_fiscale": _clean_code(row[2]) if len(row) > 2 else None,
                "partita_iva": _clean_code(row[3]) if len(row) > 3 else None,
                "tipo": _clean_cell(row[4]) if len(row) > 4 else None,
            })
            if result["codice_fiscale"] and result["codice_fiscale"].isdigit():
                result["codice_fiscale"] = None

        elif _is_table(table, "matricola inps", "anno adesione"):
            row = table[1]
            result["matricola_inps"] = _clean_cell(row[0]) if len(row) > 0 else None
            result["anno_adesione"] = _clean_cell(row[1]) if len(row) > 1 else None

        elif _is_table(table, "regime aiuti"):
            result["regime_aiuto"] = _map_regime_aiuto(table[1][0] if table[1] else None)

        elif _is_table(table, "codice", "settore"):
            row = table[1]
            result["settore_codice"] = _clean_cell(row[0]) if len(row) > 0 else None
            result["settore_descrizione"] = _clean_cell(row[1]) if len(row) > 1 else None

        elif _is_table(table, "sede di piano", "indirizzo", "comune"):
            for row in table[1:]:
                tipo_sede = _clean_cell(row[0]).lower() if row else ""
                if tipo_sede not in {"legale", "operativa"}:
                    continue
                prefix = "sede_legale" if tipo_sede == "legale" else "sede_operativa"
                result[f"{prefix}_indirizzo"] = _clean_cell(row[1]) if len(row) > 1 else None
                result[f"{prefix}_cap"] = _clean_cell(row[2]) if len(row) > 2 else None
                result[f"{prefix}_comune"] = _clean_cell(row[4]) if len(row) > 4 else None
                result[f"{prefix}_provincia"] = _clean_cell(row[5]) if len(row) > 5 else None

        elif _is_table(table, "rappresentante legale", "codice fiscale"):
            row = table[1]
            result["legale_rappresentante_nome"] = _clean_cell(row[0]) if len(row) > 0 else None
            result["legale_rappresentante_cf"] = _clean_code(row[1]) if len(row) > 1 else None
            result["legale_rappresentante_telefono"] = _clean_cell(row[2]) if len(row) > 2 else None
            result["legale_rappresentante_email"] = _clean_email(row[4]) if len(row) > 4 else None

        elif _is_table(table, "ccnl prevalente", "dipendenti"):
            row = table[1]
            result["ccnl_prevalente"] = _clean_cell(row[0]) if len(row) > 0 else None
            result["num_dipendenti"] = _clean_int(row[1]) if len(row) > 1 else None

    if not result["ragione_sociale"]:
        cf_m = _RE_CF_PERSONA.search(page_text)
        piva_ms = list(_RE_PIVA.finditer(page_text))
        if not cf_m and not piva_ms:
            return None
        result["codice_fiscale"] = cf_m.group(1).upper() if cf_m else None
        for m in piva_ms:
            candidate = m.group(1)
            if len(candidate) == 11 and candidate.isdigit():
                result["partita_iva"] = candidate
                break

    return result if result.get("ragione_sociale") else None


def parse_formulario(pdf_path: str) -> dict[str, Any]:
    """
    Parsa formulario FAPI.
    Struttura:
    - Pag 1: SEZIONE 1 con titolo piano e codice
    - Pag 3: 2.2 Beneficiarie (riepilogo con CF/P.IVA)
    - Pag 5,7,9,11,13: SEZIONE 2.2 ANAGRAFICA BENEFICIARIA individuale
    - Pag con Codice Fapi table: identifica progetto corrente
    - Tab con Titolo|Tematica|Modalità|Obiettivo|Ore → formativa
    - Tab con Titolo|Tipo|Modalità|Obiettivo|Ore → propedeutica

    Ritorna: titolo_piano, codice_piano, aziende_beneficiarie, tutti_moduli, progetti, warnings
    """
    warnings: list[str] = []

    try:
        import pdfplumber
    except ImportError:
        return {"titolo_piano": None, "tutti_moduli": [], "aziende_beneficiarie": [], "progetti": {}, "warnings": ["pdfplumber non disponibile"]}

    titolo_piano: str | None = None
    codice_piano: str | None = None
    tutti_moduli: list[dict] = []
    progetti: dict[str, dict] = {}
    aziende_beneficiarie: list[dict] = []
    current_codice_pg: str | None = None

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                try:
                    text = page.extract_text() or ""
                    tables = page.extract_tables()
                except Exception as exc:
                    warnings.append(f"Pagina {i+1} non leggibile: {exc}")
                    continue

                # ── Pagina 1: titolo e codice piano ───────────────────────────────
                if i == 0:
                    titolo_piano = _extract_titolo_piano(text)
                    m = re.search(r"(20\d{6}[A-Z]{4}\d{3})\b", text)
                    if m:
                        codice_piano = m.group(1)

                # ── Sezione 2.2 Beneficiarie (riepilogo) ─────────────────────────
                if "2.2 Beneficiarie" in text or "2.2. Beneficiarie" in text:
                    azs = _extract_beneficiarie_summary(text)
                    for az in azs:
                        existing = next((a for a in aziende_beneficiarie if a["ragione_sociale"] == az["ragione_sociale"]), None)
                        if not existing:
                            aziende_beneficiarie.append(az)

                # ── Sezione 2.2 individuale (P.IVA dettaglio) ─────────────────────
                if "SEZIONE 2.2" in text or "2.2.1" in text:
                    detail = _extract_beneficiaria_detail(text, tables)
                    if detail and detail.get("ragione_sociale"):
                        existing = next((a for a in aziende_beneficiarie if a["ragione_sociale"] == detail["ragione_sociale"]), None)
                        if existing:
                            _merge_azienda(existing, detail)
                        else:
                            aziende_beneficiarie.append(detail)

                # ── Track codice FAPI corrente da tabelle "Codice Fapi" ───────────
                for table in tables:
                    if not table or not table[0]:
                        continue
                    first_cell = _clean_cell(table[0][0])
                    if first_cell == "Codice Fapi" and len(table) > 1:
                        raw = _clean_cell(table[1][0])
                        m = _RE_CODICE_FAPI_LUNGO.search(raw)
                        if m:
                            code = m.group(1)
                            # codici progetto hanno 5 cifre finali (es 20250611CMIA00101, len=17)
                            # codici piano hanno 3 cifre finali (es 20250611CMIA001, len=15)
                            if len(code) == 17:
                                current_codice_pg = code

                # ── Tabelle moduli ────────────────────────────────────────────────
                for table in tables:
                    if not table:
                        continue
                    is_mod, tipo = _is_moduli_header(table[0])
                    if not is_mod:
                        continue
                    moduli = _parse_moduli_rows(table, tipo, current_codice_pg)
                    for mod in moduli:
                        pg = mod["codice_progetto_fapi"] or "UNKNOWN"
                        if pg not in progetti:
                            progetti[pg] = {"formativa": [], "propedeutica": []}
                        progetti[pg][tipo].append(mod)
                        tutti_moduli.append(mod)

    except Exception as exc:
        warnings.append(f"Errore durante parsing PDF: {exc}")

    if not titolo_piano:
        warnings.append("Titolo piano non trovato")
    if not tutti_moduli:
        warnings.append("Nessun modulo formativo estratto")
    if not aziende_beneficiarie:
        warnings.append("Nessuna azienda beneficiaria estratta dalla sezione 2.2")

    azienda_keys = [
        "ragione_sociale", "natura_giuridica", "codice_fiscale", "partita_iva", "tipo",
        "settore_codice", "settore_descrizione",
        "sede_legale_indirizzo", "sede_legale_cap", "sede_legale_comune", "sede_legale_provincia",
        "sede_operativa_indirizzo", "sede_operativa_cap", "sede_operativa_comune", "sede_operativa_provincia",
        "legale_rappresentante_nome", "legale_rappresentante_cf",
        "legale_rappresentante_telefono", "legale_rappresentante_email",
        "matricola_inps", "anno_adesione", "regime_aiuto", "num_dipendenti", "ccnl_prevalente",
    ]
    for azienda in aziende_beneficiarie:
        for key in azienda_keys:
            azienda.setdefault(key, None)

    return {
        "titolo_piano": titolo_piano,
        "codice_piano": codice_piano,
        "aziende_beneficiarie": aziende_beneficiarie,
        "tutti_moduli": tutti_moduli,
        "progetti": progetti,
        "warnings": warnings,
    }
