"""
Script per inizializzare i template base dei piani finanziari.

Eseguire:
    docker compose exec backend python scripts/init_templates.py
"""

import json

from database import SessionLocal
from models import TemplatePianoFinanziario


def init_templates():
    db = SessionLocal()
    try:
        templates = [
            {
                "codice": "FORMAZIENDA_STD",
                "nome": "Template Standard Formazienda",
                "tipo_fondo": "formazienda",
                "versione": "1.0",
                "descrizione": "Template per piani finanziati da Formazienda",
                "categorie_spesa": json.dumps([
                    "docenza",
                    "tutoraggio",
                    "coordinamento",
                    "progettazione",
                    "materiali",
                    "aula",
                    "altro",
                ]),
                "percentuale_max_docenza": 80.0,
                "percentuale_max_coordinamento": 10.0,
                "ore_minime_corso": 8,
                "ore_massime_corso": 120,
            },
            {
                "codice": "FAPI_STD",
                "nome": "Template Standard FAPI",
                "tipo_fondo": "fapi",
                "versione": "1.0",
                "descrizione": "Template per piani finanziati da FAPI",
                "categorie_spesa": json.dumps([
                    "docenza",
                    "tutoraggio",
                    "coordinamento",
                    "materiali_didattici",
                    "aula",
                    "viaggi",
                    "altro",
                ]),
                "percentuale_max_docenza": 70.0,
                "percentuale_max_coordinamento": 15.0,
                "ore_minime_corso": 16,
                "ore_massime_corso": 200,
            },
            {
                "codice": "FONDIMPRESA_STD",
                "nome": "Template Standard Fondimpresa",
                "tipo_fondo": "fondimpresa",
                "versione": "1.0",
                "descrizione": "Template per piani finanziati da Fondimpresa",
                "categorie_spesa": json.dumps([
                    "docenza",
                    "tutoraggio",
                    "coordinamento",
                    "progettazione",
                    "materiali",
                    "attrezzature",
                    "aula",
                    "viaggi",
                    "certificazioni",
                    "altro",
                ]),
                "percentuale_max_docenza": 100.0,
                "percentuale_max_coordinamento": 20.0,
                "ore_minime_corso": 4,
                "ore_massime_corso": 250,
            },
        ]

        for template_data in templates:
            existing = db.query(TemplatePianoFinanziario).filter(
                TemplatePianoFinanziario.codice == template_data["codice"]
            ).first()
            if existing:
                print(f"SKIP {template_data['codice']}: gia presente")
                continue

            db.add(TemplatePianoFinanziario(**template_data))
            print(f"OK {template_data['codice']}")

        db.commit()
        print("Inizializzazione template completata")
    finally:
        db.close()


if __name__ == "__main__":
    init_templates()
