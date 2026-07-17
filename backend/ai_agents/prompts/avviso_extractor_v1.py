"""Prompt v1 per l'agente avviso_extractor (estrazione regole/scadenze da avvisi MD)."""

SYSTEM_PROMPT_ESTRAZIONE = (
    "Sei un estrattore di regole normative da avvisi di fondi interprofessionali italiani "
    "(Fondimpresa, Formazienda, FAPI, bandi regionali). Rispondi SOLO con un oggetto JSON valido, "
    "senza testo aggiuntivo. Non inventare valori: estrai solo cio' che e' scritto nel testo e "
    "riporta sempre la citazione esatta in 'testo_originale'. Se un dato non e' presente, ometti la voce. "
    "Formato valori regola: oggetto con campo 'tipo' tra: testo, denaro (importo, valuta), "
    "percentuale (valore), numero (valore), ore (valore), durata_giorni (valore), data (valore ISO), "
    "booleano (valore), insieme (valori), intervallo (minimo, massimo), formula (espressione)."
)

GRUPPI_CATEGORIE: dict[str, list[str]] = {
    "economiche": ["massimali", "parametri_costo"],
    "soggetti": ["destinatari", "beneficiari", "aiuti_di_stato"],
    "procedura": ["presentazione", "valutazione"],
    "gestione": ["attuazione", "rendicontazione", "delega", "variazioni"],
    "scadenze": [],
}


def build_extraction_prompt(gruppo: str, categorie: list[str], testo: str) -> str:
    if gruppo == "scadenze":
        istruzione = (
            "Estrai tutte le scadenze e finestre temporali. Rispondi con: "
            '{"scadenze": [{"tipo": "presentazione|avvio|chiusura|rendicontazione|altro", '
            '"data": "YYYY-MM-DD", "descrizione": "...", "tassativa": true/false, '
            '"testo_originale": "citazione esatta", "riferimento_articolo": "...", "confidence": 0.0-1.0}]}'
        )
    else:
        istruzione = (
            f"Estrai le regole delle categorie: {', '.join(categorie)}. Rispondi con: "
            '{"regole": [{"chiave": "snake_case", "sottocategoria": "...", '
            '"valore": {"tipo": "..."}, "unita": "...", "testo_originale": "citazione esatta", '
            '"riferimento_articolo": "...", "confidence": 0.0-1.0}]}'
        )
    return f"{istruzione}\n\nTESTO AVVISO:\n{testo}"
