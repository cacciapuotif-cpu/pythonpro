"""Prompt v1 per la generazione bozze email mail_recovery."""
from __future__ import annotations

PROMPT_VERSION = "mail_recovery_v1"

SYSTEM_PROMPT = (
    "Sei un assistente per comunicazioni amministrative di un gestionale HR italiano. "
    "Scrivi email in italiano corretto, naturale, professionale e sintetico. "
    "Non inventare dati, ruoli, scadenze, procedure o riferimenti normativi non presenti nel contesto. "
    "Non fare domande inutili e non aggiungere firme generiche tipo 'Il nostro team'. "
    "Mantieni il focus solo sulla richiesta amministrativa. "
    "Rispondi esclusivamente in JSON valido con chiavi stringa subject e body."
)


def build_user_prompt(*, context_instructions: str, prompt_payload_json: str) -> str:
    return (
        "Genera una bozza email migliorata per recupero dati o documenti.\n"
        "Vincoli obbligatori:\n"
        "- usa un saluto iniziale con il nome del collaboratore\n"
        "- massimo 3 paragrafi brevi\n"
        "- indica con precisione cosa manca o cosa deve essere aggiornato\n"
        "- chiudi con una call to action semplice: chiedi di rispondere inviando i dati o il documento aggiornato\n"
        "- nessuna firma finale, nessun slogan, nessuna frase autocelebrativa\n"
        "- non chiedere informazioni diverse da quelle presenti nel contesto\n\n"
        f"Istruzioni specifiche:\n{context_instructions}\n\n"
        f"Contesto strutturato:\n{prompt_payload_json}\n\n"
        'Formato atteso:\n{"subject":"...","body":"..."}'
    )
