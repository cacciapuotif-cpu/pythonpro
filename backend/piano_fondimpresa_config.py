"""Configurazione strutturale del modulo Piano Finanziario Fondimpresa."""

from copy import deepcopy

SEZIONE_LIMITS = {
    "A": {"min": 70.0, "max": None},
    "B": {"min": None, "max": None},
    "C": {"min": None, "max": 20.0},
    "D": {"min": None, "max": 10.0},
}

SEZIONE_TITLES = {
    "A": "Sezione A - Erogazione della formazione (min 70%)",
    "B": "Sezione B - Cofinanziamento aziendale",
    "C": "Sezione C - Attività preparatorie e non formative (max 20%)",
    "D": "Sezione D - Gestione del Programma (max 10%)",
}

VOICE_TEMPLATES = [
    {
        "sezione": "A",
        "voce_codice": "A1",
        "descrizione": "Docenza",
        "note_temporali": "Da avvio a conclusione erogazione attività formative",
        "supports_nominativi": True,
    },
    {
        "sezione": "A",
        "voce_codice": "A2",
        "descrizione": "Tutoraggio",
        "note_temporali": "Da avvio a conclusione erogazione attività formative",
        "supports_nominativi": True,
    },
    {
        "sezione": "A",
        "voce_codice": "A3",
        "descrizione": "Coordinamento didattico",
        "note_temporali": "Da avvio a conclusione erogazione attività formative",
        "supports_nominativi": True,
    },
    {
        "sezione": "A",
        "voce_codice": "A3b",
        "descrizione": "Comitato scientifico",
        "note_temporali": "Da avvio a conclusione erogazione attività formative",
        "supports_nominativi": True,
    },
    {
        "sezione": "A",
        "voce_codice": "A4",
        "descrizione": "Aule ed attrezzature didattiche",
        "note_temporali": "Da avvio a conclusione erogazione attività formative",
        "supports_nominativi": False,
    },
    {
        "sezione": "A",
        "voce_codice": "A5",
        "descrizione": "Materiali didattici",
        "note_temporali": "Da avvio a conclusione erogazione attività formative",
        "supports_nominativi": False,
    },
    {
        "sezione": "A",
        "voce_codice": "A6",
        "descrizione": "Materiali di consumo",
        "note_temporali": "Da avvio a conclusione erogazione attività formative",
        "supports_nominativi": False,
    },
    {
        "sezione": "A",
        "voce_codice": "A7",
        "descrizione": "Università / Partenariato - certificazione competenze",
        "note_temporali": "Da avvio a conclusione erogazione attività formative",
        "supports_nominativi": False,
    },
    {
        "sezione": "A",
        "voce_codice": "A7b",
        "descrizione": "Certificazione competenze",
        "note_temporali": "Da avvio a conclusione erogazione attività formative",
        "supports_nominativi": True,
    },
    {
        "sezione": "A",
        "voce_codice": "A8",
        "descrizione": "Viaggi e trasferte",
        "note_temporali": "Da avvio a conclusione erogazione attività formative",
        "supports_nominativi": False,
    },
    {
        "sezione": "B",
        "voce_codice": "B1",
        "descrizione": "Cofinanziamento aziendale",
        "note_temporali": "",
        "supports_nominativi": False,
    },
    {
        "sezione": "C",
        "voce_codice": "C.1.1",
        "descrizione": "Analisi della domanda",
        "note_temporali": "Da pubblicazione avviso a data conclusione attività del piano",
        "supports_nominativi": False,
    },
    {
        "sezione": "C",
        "voce_codice": "C.1.2",
        "descrizione": "Diagnosi e rilevazione dei fabbisogni formativi",
        "note_temporali": "Da pubblicazione avviso a data conclusione attività del piano",
        "supports_nominativi": False,
    },
    {
        "sezione": "C",
        "voce_codice": "C.1.5",
        "descrizione": "Definizione di metodologie e modelli di formazione continua",
        "note_temporali": "Da pubblicazione avviso a data conclusione attività del piano",
        "supports_nominativi": False,
    },
    {
        "sezione": "C",
        "voce_codice": "C.1.6",
        "descrizione": "Altre attività preparatorie e di accompagnamento",
        "note_temporali": "Da pubblicazione avviso a data conclusione attività del piano",
        "supports_nominativi": False,
    },
    {
        "sezione": "C",
        "voce_codice": "C.1.7",
        "descrizione": "Viaggi e trasferte",
        "note_temporali": "Da pubblicazione avviso a data conclusione attività del piano",
        "supports_nominativi": False,
    },
    {
        "sezione": "C",
        "voce_codice": "C.2.1",
        "descrizione": "Progettazione attività del piano",
        "note_temporali": "Da pubblicazione avviso a data conclusione attività del piano",
        "supports_nominativi": True,
    },
    {
        "sezione": "C",
        "voce_codice": "C.2.3",
        "descrizione": "Individuazione e orientamento dei partecipanti",
        "note_temporali": "Da pubblicazione avviso a data conclusione attività del piano",
        "supports_nominativi": False,
    },
    {
        "sezione": "C",
        "voce_codice": "C.2.4",
        "descrizione": "Sistema di monitoraggio e valutazione",
        "note_temporali": "Da pubblicazione avviso a data conclusione attività del piano",
        "supports_nominativi": True,
    },
    {
        "sezione": "C",
        "voce_codice": "C.2.7",
        "descrizione": "Viaggi e trasferte",
        "note_temporali": "Da pubblicazione avviso a data conclusione attività del piano",
        "supports_nominativi": False,
    },
    {
        "sezione": "D",
        "voce_codice": "D1",
        "descrizione": "Costi diretti di gestione",
        "note_temporali": "Da data ammissione a data rendicontazione",
        "supports_nominativi": True,
    },
    {
        "sezione": "D",
        "voce_codice": "D2",
        "descrizione": "Costi indiretti di gestione",
        "note_temporali": "Da data ammissione a data rendicontazione",
        "supports_nominativi": False,
    },
]


def ordered_templates():
    return deepcopy(VOICE_TEMPLATES)


def get_voice_template_map():
    return {item["voce_codice"]: item for item in VOICE_TEMPLATES}


def build_default_voci_fondimpresa():
    return [
        {
            "sezione": item["sezione"],
            "voce_codice": item["voce_codice"],
            "descrizione": item["descrizione"],
            "note_temporali": item["note_temporali"],
            "totale_voce": 0.0,
        }
        for item in VOICE_TEMPLATES
    ]
