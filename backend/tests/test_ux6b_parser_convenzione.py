"""UX-6b — la posizione delle pagine non è un contratto del PDF FAPI."""

import sys
from types import SimpleNamespace

from services.parsers.fapi.convenzione_parser import (
    _estrai_allegati,
    parse_convenzione,
)


def test_allegato_c_dopo_le_tabelle_non_rompe_codici_e_beneficiarie():
    allegato_a = [[
        [
            "Codice\nProgetto", "Titolo", "Ore\nForm.", "n.\nPart.",
            "Contributo\nFAPI", "Cofinanz.", "Finanz.\nTotale",
        ],
        [
            "20250611CMI\nA00101", "PG01", "40", "9",
            "€6.917,65", "€2.964,71", "€9.882,36",
        ],
    ]]
    allegato_b = [[
        [
            "Ragione Sociale", "n.\nPartec.", "Codice Progetto",
            "Finanz.", "Cofinanz.", "Totale",
        ],
        [
            "Power Impianti srl", "9", "20250611CMIA00101",
            "€6.917,65", "€2.964,71", "€9.882,36",
        ],
    ]]
    allegato_c = [[
        ["ragione Sociale", "codice Fiscale", "", "Descrizione"],
        ["Power Impianti srl", "09326361210", "CUP", "G64D26000610003"],
    ]]

    codici, aziende = _estrai_allegati(
        [[], allegato_a, allegato_b, allegato_c],
        "20250611CMIA001",
    )

    assert codici == ["20250611CMIA00101"]
    assert aziende == [{
        "ragione_sociale": "Power Impianti srl",
        "partita_iva": None,
        "codice_fiscale": None,
        "num_partecipanti": 9,
        "codice_progetto": "20250611CMIA00101",
        "importo": 9882.36,
    }]


def test_pagine_firma_vuote_non_nascondono_piano_ed_ente(monkeypatch):
    class Pagina:
        def __init__(self, testo):
            self.testo = testo

        def extract_text(self):
            return self.testo

        def extract_tables(self):
            return []

    class Pdf:
        pages = [
            Pagina(""),
            Pagina(""),
            Pagina(
                "Cod. Piano: 20250611CMIA001\n"
                "Contributo FAPI: €35.869,42\n"
                "Cofinanziamento €15.372,61\n"
                "Delibera C.d.A./Determin. Presid. n 7 del 24/03/2026\n"
                "Costo Totale: €51.242,03"
            ),
            Pagina(""),
            Pagina(""),
            Pagina(
                "NEXT GROUP SRL, con sede legale in Via S.Aspreno 13, "
                "Napoli (Napoli), C.F./P.IVA 06615351217"
            ),
        ]

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    monkeypatch.setitem(
        sys.modules,
        "pdfplumber",
        SimpleNamespace(open=lambda _path: Pdf()),
    )

    result = parse_convenzione("firmato.pdf")

    assert result["piano"] == {
        "codice_fapi": "20250611CMIA001",
        "titolo": None,
        "delibera_numero": "7",
        "delibera_data": "2026-03-24",
        "costo_totale": 51242.03,
        "contributo_ente": 35869.42,
        "cofinanziamento": 15372.61,
    }
    assert result["ente_attuatore"] == {
        "ragione_sociale": "NEXT GROUP SRL",
        "partita_iva": "06615351217",
    }
