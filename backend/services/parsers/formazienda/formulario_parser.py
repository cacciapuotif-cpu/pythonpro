"""Parser PDF per il Formulario di candidatura Formazienda (Allegato A).

Complementare all'Atto di adesione (Allegato E): l'Allegato E porta l'ente
e gli importi approvati, l'Allegato A porta le imprese beneficiarie, il
progetto formativo e le macrovoci di dettaglio. Nessuno dei due basta da
solo (vedi atto_adesione_parser.py per le trappole sulle date, identiche
qui: il piede di pagina "Data approvazione" e' del MODULO, non del piano).
"""
import re
from typing import Any

_RE_PIEDE_PAGINA = re.compile(
    r"Data approvazione: \d{1,2}/\d{1,2}/\d{4} Rev\. \d+ Pagina \d+ di \d+\n?Fondo Formazienda\n?"
)
_RE_INTESTAZIONE_PAGINA = re.compile(
    r"Fondo Formazienda AVV\s*\d+/\d{4}_All [AE]_\d+\n?"
    r"Redazione: Fondo Formazienda Pag\. \d+/\d+\n?"
    r"Allegato [AE] - (?:Atto di adesione|Formulario di candidatura) Rev\. \d+ \d{1,2}/\d{1,2}/\d{4}\n?"
)

_RE_TITOLO_PIANO = re.compile(r"I\.1\.\s*Titolo Piano Formativo\s*\n(.+)")
_RE_TIPOLOGIA_PIANO = re.compile(r"I\.2\.\s*Tipologia Piano Formativo\s*\n(.+)")
_RE_TEMATICHE = re.compile(r"I\.3\.\s*Tematiche di intervento\s*\n((?:•.+\n?)+)")

_RE_ANAGRAFICA = re.compile(
    r"Ragione sociale\s+(.+?)\s*\n"
    r"Sede legale in\s+(.+?)\s+Cap\s+(\d{5})\s+Citt[aà]\s+(.+?)\s+Prov\.\s+(\S+)\s*\n"
    r"Tel\.\s*(\S*)\s*\n"
    r"eMail\s*(\S*)\s*Pec\s*(\S*)\s*\n"
    r"Codice Fiscale\s+(\S+)\s+Partita IVA\s+(\d{11})\s*\n",
    re.IGNORECASE,
)
# Non sempre adiacente a Codice Fiscale/Partita IVA: nei blocchi impresa di
# Sezione 2 ci sono Matricola Inps e Codice Ateco in mezzo. Cercato altrove
# nel blocco, non incatenato alla sequenza precedente.
_RE_LEGALE_RAPPRESENTANTE = re.compile(
    r"Legale rappresentante\s*\([^)]*\)\s*:\s*(.+?)\s*\n", re.IGNORECASE,
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
    m_legale = _RE_LEGALE_RAPPRESENTANTE.search(testo)
    legale = m_legale.group(1).strip() if m_legale else ""
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


_RE_MATRICOLA = re.compile(r"Matricola/e Inps\s+(\S+)")
_RE_ATECO = re.compile(r"Codice Ateco\(Istat \d{4}\)\s+(\S+)")
_RE_STATO_ADESIONE = re.compile(
    r"Aderente a Formazienda dal\s+(\d{1,2}/\d{1,2}/\d{4})\s*-\s*periodo di competenza:\s*(\S+)",
)
_RE_DESCRIZIONE_IMPRESA = re.compile(
    r"II\.5\.[^\n]*\nDescrivere[^\n]*\n(.*?)(?=II\.6\.)", re.DOTALL,
)
_RE_FABBISOGNO = re.compile(
    r"II\.10\.[^\n]*\nDescrivere[^\n]*\n(.*?)(?=Data approvazione:|===|\Z)", re.DOTALL,
)
_RE_CCNL_BODY = re.compile(
    r"II\.6\.[^\n]*\nIndicare[^\n]*\n(.*?)(?=II\.7\.)", re.DOTALL,
)
_RE_WELFARE_BODY = re.compile(
    r"II\.9\.[^\n]*\nSpecificare[^\n]*\n(.*?)(?=II\.10\.)", re.DOTALL,
)
_RE_DIPENDENTI = re.compile(
    r"Numero totale dipendenti:\s*(\d+)\s*"
    r"Di cui maschi:\s*(\d+)\s*"
    r"Di cui femmine:\s*(\d+)\s*"
    r"Di cui con disabilit[aà][^:]*:\s*(\d+)",
)


def _classe_dimensionale(blocco: str) -> str | None:
    for etichetta, chiave in (("☑ Micro", "micro"), ("☑ Piccola", "piccola"),
                              ("☑ Media", "media"), ("☑ Grande", "grande")):
        if etichetta in blocco:
            return chiave
    return None


def _regime_aiuti(blocco: str) -> str | None:
    idx_651 = blocco.find("651/2014")
    idx_minimis = blocco.find("de minimis")
    if idx_651 != -1:
        # Il checkbox del regime 651/2014 sta sulla riga precedente al testo
        # dell'articolo (trappola di layout: checkbox prima dell'etichetta
        # completa, che va a capo). Cerca "☑" prima di "651/2014" nello stesso
        # paragrafo, non altrove nel blocco.
        finestra = blocco[max(0, idx_651 - 80):idx_651]
        if "☑" in finestra:
            return "aiuti_stato_formazione_651_2014"
    if idx_minimis != -1:
        finestra = blocco[idx_minimis:idx_minimis + 80]
        if "☑" in finestra:
            return "de_minimis"
    return None


def _rsa_rsu(blocco: str) -> bool | None:
    idx = blocco.find("Presenza RSA/RSU")
    if idx == -1:
        return None
    finestra = blocco[idx:idx + 60]
    if re.search(r"☑\s*S[iì]", finestra):
        return True
    if re.search(r"☑\s*No", finestra):
        return False
    return None


def _clean_testo_libero(raw: str | None) -> str | None:
    if raw is None:
        return None
    testo = raw.strip()
    if not testo or testo.startswith("II."):
        return None
    return testo


def _parse_imprese_beneficiarie(sezione2: str, warnings: list[str]) -> list[dict[str, Any]]:
    # I blocchi si riconoscono dalla ripetizione di "II.1. Anagrafica impresa",
    # non da un'intestazione univoca (trappola #3): ogni impresa riusa la
    # stessa numerazione II.1...II.10.
    marcatori = [m.start() for m in re.finditer(r"II\.1\.\s*Anagrafica impresa", sezione2)]
    blocchi = [
        sezione2[inizio: (marcatori[i + 1] if i + 1 < len(marcatori) else len(sezione2))]
        for i, inizio in enumerate(marcatori)
    ]

    imprese = []
    for blocco in blocchi:
        anagrafica = _parse_anagrafica_blocco(blocco)
        if not anagrafica:
            warnings.append("Blocco impresa non riconosciuto in Sezione 2 (anagrafica illeggibile)")
            continue
        m = _RE_MATRICOLA.search(blocco)
        anagrafica["matricola_inps"] = m.group(1) if m else None
        m = _RE_ATECO.search(blocco)
        anagrafica["codice_ateco"] = m.group(1) if m else None
        anagrafica["classe_dimensionale"] = _classe_dimensionale(blocco)
        anagrafica["regime_aiuti"] = _regime_aiuti(blocco)
        anagrafica["rsa_rsu"] = _rsa_rsu(blocco)

        m = _RE_STATO_ADESIONE.search(blocco)
        if m:
            d, mo, y = m.group(1).split("/")
            anagrafica["stato_adesione_data"] = f"{y}-{mo.zfill(2)}-{d.zfill(2)}"
            anagrafica["stato_adesione_periodo"] = m.group(2)
        else:
            anagrafica["stato_adesione_data"] = None
            anagrafica["stato_adesione_periodo"] = None

        m = _RE_CCNL_BODY.search(blocco)
        anagrafica["ccnl"] = _clean_testo_libero(m.group(1)) if m else None
        m = _RE_WELFARE_BODY.search(blocco)
        anagrafica["welfare"] = _clean_testo_libero(m.group(1)) if m else None

        m = _RE_DIPENDENTI.search(blocco)
        if m:
            anagrafica["numero_dipendenti_totale"] = int(m.group(1))
            anagrafica["numero_dipendenti_maschi"] = int(m.group(2))
            anagrafica["numero_dipendenti_femmine"] = int(m.group(3))
            anagrafica["numero_dipendenti_disabili"] = int(m.group(4))
        else:
            anagrafica["numero_dipendenti_totale"] = None
            anagrafica["numero_dipendenti_maschi"] = None
            anagrafica["numero_dipendenti_femmine"] = None
            anagrafica["numero_dipendenti_disabili"] = None

        m = _RE_DESCRIZIONE_IMPRESA.search(blocco)
        descrizione = _clean_testo_libero(m.group(1).replace("\n", " ")) if m else None
        # Trappola #8: dati spazzatura (es. una sola lettera) non scartano
        # l'impresa, ma vanno segnalati per verifica.
        anagrafica["descrizione_impresa"] = descrizione
        anagrafica["descrizione_impresa_da_verificare"] = bool(
            descrizione is not None and len(descrizione.strip()) < 15
        )
        if anagrafica["descrizione_impresa_da_verificare"]:
            warnings.append(
                f"Descrizione impresa da verificare per {anagrafica['ragione_sociale']}: troppo corta"
            )

        m = _RE_FABBISOGNO.search(blocco)
        anagrafica["fabbisogno_formativo"] = (
            _clean_testo_libero(m.group(1).replace("\n", " ")) if m else None
        )

        imprese.append(anagrafica)

    if not imprese:
        warnings.append("Nessuna impresa beneficiaria trovata in Sezione 2")
    return imprese


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
    # Il piede/intestazione di pagina si ripete a ogni cambio pagina e finisce
    # dentro le sezioni a testo libero che attraversano un salto pagina
    # (es. II.6/II.9/II.10): va rimosso prima di qualunque estrazione, non
    # trattato come contenuto del campo.
    full_text = _RE_PIEDE_PAGINA.sub("", full_text)
    full_text = _RE_INTESTAZIONE_PAGINA.sub("", full_text)

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

    idx_sezione3 = full_text.find("Sezione 3.")
    sezione2 = full_text[idx_sezione2:idx_sezione3] if idx_sezione2 != -1 and idx_sezione3 != -1 else ""
    imprese_beneficiarie = _parse_imprese_beneficiarie(sezione2, warnings)

    return {
        "piano": piano,
        "soggetto_gestore": soggetto_gestore,
        "soggetto_delegato": soggetto_delegato,
        "soggetti_partner": soggetti_partner,
        "imprese_beneficiarie": imprese_beneficiarie,
        "progetti_formativi": [],
        "riepilogo": {},
        "warnings": warnings,
    }
