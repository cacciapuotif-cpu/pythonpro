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


_RE_PROGETTO_TITOLO = re.compile(r"Titolo\s+(.+?)\s*\nTipologia formativa")
_RE_PROGETTO_TEMATICA = re.compile(r"Tematica\s+(.+)")
_RE_PROGETTO_ORE = re.compile(r"n\.\s*ore di formazione\s*\n(\d+(?:[.,]\d+)?)\s*ore")
_RE_PROGETTO_EDIZIONI = re.compile(r"n\.\s*edizioni\s+(\d+)")
_RE_SOGGETTO_EROGATORE = re.compile(r"Soggetto Erogatore\s+Ragione sociale:\s*(.+)")
_RE_REGIONI = re.compile(r"Regioni:\s*(.+)")
_RE_PROVINCE = re.compile(r"Province:\s*(.+)")
_RE_MODALITA_RIGHE = re.compile(
    r"(Aula|Training on the job)\s+(\d+(?:[.,]\d+)?)\s+(\d+(?:[.,]\d+)?)\s*%",
)
_RE_COSTO_PROGETTO = re.compile(
    r"Costo del progetto.*?\n(?:.*\n)*?(\d+)\s+(\d+)\s+([\d.,]+)\s*€\s*\n"
    r"Totale\s+(\d+)\s+\d+\s+([\d.,]+)\s*€",
)

_RE_CRONO_DURATA = re.compile(r"Durata in giorni del\s+(\d+)\s*\nPiano Formativo")
_RE_CRONO_ATTIVITA = re.compile(
    r"(Avvio Piano Formativo|Gestione Piano Formativo|Chiusura Piano Formativo|"
    r"Presentazione Rendicontazione)\s+(\d{2})\s+(\d{4})",
)
_RE_MACROVOCE_TOTALE = re.compile(
    r"Totale Macrovoce ([ABCD])\.\s+([\d.,]+)\s*€\s+(\d+(?:[.,]\d+)?)\s*%",
)
_RE_MACROVOCE_LIMITE = {
    "A": re.compile(r"Macrovoce A\..*?max\s*(\d+)%", re.DOTALL),
    "C": re.compile(r"Macrovoce C\..*?max\s*(\d+)%", re.DOTALL),
}
_RE_FINANZIAMENTO_TOTALE_PROGETTI = re.compile(r"TOTALE\s+([\d.,]+)\s*€")
_RE_DESTINATARI_TOTALE = re.compile(r"4\.3\..*?TOTALE\s+(\d+)", re.DOTALL)
_RE_COSTO_COMPLESSIVO = re.compile(r"Costo complessivo del Piano Formativo\s+([\d.,]+)\s*€")
_RE_QUOTA_PUBBLICA = re.compile(r"Quota finanziamento pubblico\s+([\d.,]+)\s*€")
_RE_QUOTA_PRIVATA = re.compile(r"Quota cofinanziamento privato\s+([\d.,]+)\s*€")
_RE_RIEPILOGO_IMPRESA_RIGA = re.compile(
    r"([A-Z0-9À-Ü][A-Z0-9À-Ü .&'\-]+?)\s+([A-Z0-9]{11,16})\s+(Micro|Piccola|Media|Grande)\s+"
    r"([\d.,]+)\s*€\s+([\d.,]+)\s*€",
)
_RE_TOTALE_PREVENTIVO = re.compile(r"Totale preventivo\s+([\d.,]+)\s*€")
_RE_CONTRIBUTO_RICHIESTO = re.compile(r"Contributo richiesto\s+([\d.,]+)\s*€")
_RE_COFINANZIAMENTO_FINALE = re.compile(r"Cofinanziamento\s+([\d.,]+)\s*€\s*Data")


def _quadra(a: float | None, b: float | None, tolleranza: float = 0.5) -> bool:
    if a is None or b is None:
        return False
    return abs(a - b) <= tolleranza


def _parse_progetti_formativi(sezione3: str, warnings: list[str]) -> list[dict[str, Any]]:
    marcatori = [m.start() for m in re.finditer(r"Progetto Formativo n\.", sezione3)]
    blocchi = [
        sezione3[inizio: (marcatori[i + 1] if i + 1 < len(marcatori) else len(sezione3))]
        for i, inizio in enumerate(marcatori)
    ]

    progetti = []
    for blocco in blocchi:
        numero_match = re.search(r"Progetto Formativo n\.\s*\n?(\d+)", blocco)
        m_titolo = _RE_PROGETTO_TITOLO.search(blocco)
        m_ore = _RE_PROGETTO_ORE.search(blocco)
        m_edizioni = _RE_PROGETTO_EDIZIONI.search(blocco)
        m_erogatore = _RE_SOGGETTO_EROGATORE.search(blocco)
        m_regioni = _RE_REGIONI.search(blocco)
        m_province = _RE_PROVINCE.search(blocco)
        m_tematica = _RE_PROGETTO_TEMATICA.search(blocco)

        modalita_attuazione = [
            {
                "tipo": "aula" if riga[0] == "Aula" else "training_on_job",
                "ore": float(riga[1].replace(",", ".")),
                "percentuale": float(riga[2].replace(",", ".")),
            }
            for riga in _RE_MODALITA_RIGHE.findall(blocco)
        ]

        m_costo = _RE_COSTO_PROGETTO.search(blocco)
        if m_costo:
            edizioni_riga = int(m_costo.group(1))
            partecipanti_minimo = int(m_costo.group(2))
            finanziamento_edizione = float(m_costo.group(3).replace(".", "").replace(",", "."))
            totale = float(m_costo.group(5).replace(".", "").replace(",", "."))
            costo = {
                "costo_numero_edizioni": edizioni_riga,
                "costo_partecipanti_minimo": partecipanti_minimo,
                "costo_finanziamento_per_edizione": finanziamento_edizione,
                "costo_totale": totale,
                "quadratura_costo_ok": _quadra(edizioni_riga * finanziamento_edizione, totale),
            }
        else:
            warnings.append("Costo del progetto non trovato o non quadrato (Sezione 3)")
            costo = {
                "costo_numero_edizioni": None, "costo_partecipanti_minimo": None,
                "costo_finanziamento_per_edizione": None, "costo_totale": None,
                "quadratura_costo_ok": False,
            }

        progetti.append({
            "numero": numero_match.group(1) if numero_match else None,
            "titolo": m_titolo.group(1).strip() if m_titolo else None,
            "tematica": m_tematica.group(1).strip() if m_tematica else None,
            "ore_formazione": float(m_ore.group(1).replace(",", ".")) if m_ore else None,
            "edizioni": int(m_edizioni.group(1)) if m_edizioni else None,
            "soggetto_erogatore": m_erogatore.group(1).strip() if m_erogatore else None,
            "regioni": [r.strip() for r in m_regioni.group(1).split(",")] if m_regioni else [],
            "province": [p.strip() for p in m_province.group(1).split(",")] if m_province else [],
            "modalita_attuazione": modalita_attuazione,
            **costo,
        })

    if not progetti:
        warnings.append("Nessun progetto formativo trovato in Sezione 3")
    return progetti


def _parse_riepilogo(sezione4: str, warnings: list[str]) -> dict[str, Any]:
    m = _RE_FINANZIAMENTO_TOTALE_PROGETTI.search(sezione4)
    finanziamento_totale = _clean_importo(m.group(1)) if m else None

    m = _RE_DESTINATARI_TOTALE.search(sezione4)
    destinatari_totale = int(m.group(1)) if m else None

    m = _RE_COSTO_COMPLESSIVO.search(sezione4)
    costo_complessivo = _clean_importo(m.group(1)) if m else None
    m = _RE_QUOTA_PUBBLICA.search(sezione4)
    quota_pubblica = _clean_importo(m.group(1)) if m else None
    m = _RE_QUOTA_PRIVATA.search(sezione4)
    quota_privata = _clean_importo(m.group(1)) if m else None

    cronoprogramma = {"durata_giorni": None, "attivita": []}
    m = _RE_CRONO_DURATA.search(sezione4)
    if m:
        cronoprogramma["durata_giorni"] = int(m.group(1))
    cronoprogramma["attivita"] = [
        {"nome": nome, "mese": int(mese), "anno": int(anno)}
        for nome, mese, anno in _RE_CRONO_ATTIVITA.findall(sezione4)
    ]
    if not cronoprogramma["attivita"]:
        warnings.append("Cronoprogramma non trovato in Sezione 4.5")

    macrovoci = []
    for codice, importo_raw, pct_raw in _RE_MACROVOCE_TOTALE.findall(sezione4):
        limite = None
        pattern_limite = _RE_MACROVOCE_LIMITE.get(codice)
        if pattern_limite:
            m_limite = pattern_limite.search(sezione4)
            limite = int(m_limite.group(1)) if m_limite else None
        macrovoci.append({
            "codice": codice,
            "importo": _clean_importo(importo_raw),
            "percentuale": _clean_pct(pct_raw),
            "limite_max_pct": limite,
        })
    # ``findall`` puo' incontrare piu' occorrenze dello stesso codice se il
    # documento ripete la riga "Totale Macrovoce X." su piu' righe di
    # rendering: dedup per codice tenendo l'ultima (quella con percentuale
    # valorizzata), che nel campione e' sempre quella corretta.
    macrovoci_per_codice: dict[str, dict[str, Any]] = {}
    for voce in macrovoci:
        macrovoci_per_codice[voce["codice"]] = voce
    macrovoci = [macrovoci_per_codice[c] for c in ("A", "B", "C", "D") if c in macrovoci_per_codice]

    m = _RE_TOTALE_PREVENTIVO.search(sezione4)
    totale_preventivo = _clean_importo(m.group(1)) if m else None
    m = _RE_CONTRIBUTO_RICHIESTO.search(sezione4)
    contributo_richiesto = _clean_importo(m.group(1)) if m else None
    m = _RE_COFINANZIAMENTO_FINALE.search(sezione4)
    cofinanziamento = _clean_importo(m.group(1)) if m else None

    somma_macrovoci = sum(v["importo"] for v in macrovoci if v["importo"] is not None) or None
    quadratura_macrovoci_ok = _quadra(somma_macrovoci, totale_preventivo)
    if not quadratura_macrovoci_ok:
        warnings.append(
            f"Le macrovoci (totale {somma_macrovoci}) non quadrano col preventivo totale ({totale_preventivo})"
        )

    finanziamenti_per_impresa = [
        {
            "ragione_sociale": ragione_sociale.strip(),
            "identificativo_fiscale": identificativo.strip(),
            "classe_dimensionale": classe_dimensionale.lower(),
            "finanziamento": _clean_importo(finanziamento),
            "cofinanziamento": _clean_importo(cofinanziamento),
        }
        for ragione_sociale, identificativo, classe_dimensionale, finanziamento, cofinanziamento
        in _RE_RIEPILOGO_IMPRESA_RIGA.findall(sezione4)
    ]
    somma_per_impresa = sum(
        riga["finanziamento"] or 0 for riga in finanziamenti_per_impresa
    ) or None
    quadratura_finanziamento_per_impresa_ok = _quadra(somma_per_impresa, costo_complessivo)
    if not quadratura_finanziamento_per_impresa_ok:
        warnings.append(
            f"La somma dei finanziamenti per impresa ({somma_per_impresa}) non coincide "
            f"col costo complessivo ({costo_complessivo})"
        )

    return {
        "finanziamento_totale": finanziamento_totale,
        "destinatari_totale": destinatari_totale,
        "costo_complessivo": costo_complessivo,
        "quota_pubblica": quota_pubblica,
        "quota_privata": quota_privata,
        "cronoprogramma": cronoprogramma,
        "macrovoci": macrovoci,
        "totale_preventivo": totale_preventivo,
        "contributo_richiesto": contributo_richiesto,
        "cofinanziamento": cofinanziamento,
        "finanziamenti_per_impresa": finanziamenti_per_impresa,
        "quadratura_macrovoci_ok": quadratura_macrovoci_ok,
        "quadratura_finanziamento_per_impresa_ok": quadratura_finanziamento_per_impresa_ok,
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
    idx_sezione4 = full_text.find("Sezione 4.")
    sezione2 = full_text[idx_sezione2:idx_sezione3] if idx_sezione2 != -1 and idx_sezione3 != -1 else ""
    sezione3 = full_text[idx_sezione3:idx_sezione4] if idx_sezione3 != -1 and idx_sezione4 != -1 else ""
    sezione4 = full_text[idx_sezione4:] if idx_sezione4 != -1 else ""
    imprese_beneficiarie = _parse_imprese_beneficiarie(sezione2, warnings)
    progetti_formativi = _parse_progetti_formativi(sezione3, warnings)
    riepilogo = _parse_riepilogo(sezione4, warnings)

    return {
        "piano": piano,
        "soggetto_gestore": soggetto_gestore,
        "soggetto_delegato": soggetto_delegato,
        "soggetti_partner": soggetti_partner,
        "imprese_beneficiarie": imprese_beneficiarie,
        "progetti_formativi": progetti_formativi,
        "riepilogo": riepilogo,
        "warnings": warnings,
    }
