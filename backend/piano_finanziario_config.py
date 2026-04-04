"""Configurazione strutturale del modulo Piano Finanziario Formazienda."""

from copy import deepcopy

MACROVOCE_LIMITS = {
    "A": 20.0,
    "B": 50.0,
    "C": 30.0,
    "D": None,
}

MACROVOCE_TITLES = {
    "A": "Macrovoce A - Progettazione della formazione (max 20%)",
    "B": "Macrovoce B - Erogazione della formazione (max 50%)",
    "C": "Macrovoce C - Gestione e amministrazione (max 30%)",
    "D": "Macrovoce D - Costo del personale in formazione (solo cofinanziamento)",
}

VOICE_TEMPLATES = [
    {"macrovoce": "A", "voce_codice": "A.1", "descrizione": "Progettazione esecutiva", "is_dynamic": False},
    {"macrovoce": "A", "voce_codice": "A.2", "descrizione": "Rilevazione fabbisogni", "is_dynamic": False},
    {"macrovoce": "A", "voce_codice": "A.3", "descrizione": "Promozione", "is_dynamic": False},
    {"macrovoce": "A", "voce_codice": "A.4", "descrizione": "Monitoraggio e valutazione", "is_dynamic": False},
    {"macrovoce": "A", "voce_codice": "A.5", "descrizione": "Diffusione", "is_dynamic": False},
    {"macrovoce": "A", "voce_codice": "A.6", "descrizione": "Viaggi e trasferte", "is_dynamic": False},
    {"macrovoce": "A", "voce_codice": "A.7", "descrizione": "Altro", "is_dynamic": False},
    {"macrovoce": "B", "voce_codice": "B.1", "descrizione": "Coordinamento", "is_dynamic": False},
    {"macrovoce": "B", "voce_codice": "B.2", "descrizione": "Docenza", "is_dynamic": True},
    {"macrovoce": "B", "voce_codice": "B.3", "descrizione": "Tutor", "is_dynamic": True},
    {"macrovoce": "B", "voce_codice": "B.4", "descrizione": "Materiali didattici", "is_dynamic": False},
    {"macrovoce": "B", "voce_codice": "B.5", "descrizione": "Materiali di consumo", "is_dynamic": False},
    {"macrovoce": "B", "voce_codice": "B.6", "descrizione": "Aule didattiche", "is_dynamic": False},
    {"macrovoce": "B", "voce_codice": "B.7", "descrizione": "Attrezzature", "is_dynamic": False},
    {"macrovoce": "B", "voce_codice": "B.8", "descrizione": "Certificazione delle competenze", "is_dynamic": False},
    {"macrovoce": "B", "voce_codice": "B.9", "descrizione": "Viaggi e trasferte", "is_dynamic": False},
    {"macrovoce": "B", "voce_codice": "B.10", "descrizione": "Altro", "is_dynamic": False},
    {"macrovoce": "C", "voce_codice": "C.1", "descrizione": "Designer", "is_dynamic": False},
    {"macrovoce": "C", "voce_codice": "C.2", "descrizione": "Personale amministrativo", "is_dynamic": False},
    {"macrovoce": "C", "voce_codice": "C.3", "descrizione": "Rendicontazione", "is_dynamic": False},
    {"macrovoce": "C", "voce_codice": "C.4", "descrizione": "Revisione dei conti", "is_dynamic": False},
    {"macrovoce": "C", "voce_codice": "C.5", "descrizione": "Fidejussione", "is_dynamic": False},
    {"macrovoce": "C", "voce_codice": "C.6", "descrizione": "Costi generali e amministrativi (forfait)", "is_dynamic": False},
    {"macrovoce": "C", "voce_codice": "C.7", "descrizione": "Viaggi e trasferte", "is_dynamic": False},
    {"macrovoce": "C", "voce_codice": "C.8", "descrizione": "Altro", "is_dynamic": False},
    {"macrovoce": "D", "voce_codice": "D.1", "descrizione": "Retribuzione ed oneri del personale", "is_dynamic": False},
    {"macrovoce": "D", "voce_codice": "D.2", "descrizione": "Assicurazioni", "is_dynamic": False},
    {"macrovoce": "D", "voce_codice": "D.3", "descrizione": "Rimborsi viaggi e trasferte", "is_dynamic": False},
    {"macrovoce": "D", "voce_codice": "D.4", "descrizione": "Altro", "is_dynamic": False},
]


def get_voice_template_map():
    return {item["voce_codice"]: item for item in VOICE_TEMPLATES}


def is_dynamic_voice(voce_codice: str) -> bool:
    template = get_voice_template_map().get(voce_codice)
    return bool(template and template["is_dynamic"])


def build_default_voci():
    rows = []
    for template in VOICE_TEMPLATES:
        if template["is_dynamic"]:
            continue
        rows.append({
            "macrovoce": template["macrovoce"],
            "voce_codice": template["voce_codice"],
            "descrizione": template["descrizione"],
            "progetto_label": None,
            "edizione_label": None,
            "ore": 0.0,
            "importo_consuntivo": 0.0,
            "importo_preventivo": 0.0,
            "importo_presentato": 0.0,
        })
    return rows


def ordered_templates():
    return deepcopy(VOICE_TEMPLATES)
