"""Prompt versionato per procedure da vademecum."""
SYSTEM_PROMPT = (
    "Sei un estrattore di procedure operative per formazione finanziata italiana. "
    "Rispondi solo JSON valido, non inventare, conserva la citazione originale."
)
def build_prompt(text: str) -> str:
    return ('Estrai voci checklist nel formato {"voci":[{"fase":"presentazione|avvio|gestione|rendicontazione",'
            '"titolo":"...","descrizione":"...","tipo_contenuto":"attivita_semplice|scadenza_relativa|documento",'
            '"offset_giorni":null,"ancora":null,"tipo_documento":null,"testo_originale":"...",'
            '"riferimento_articolo":null,"confidence":0.0}]}\n\nTESTO:\n' + text)
