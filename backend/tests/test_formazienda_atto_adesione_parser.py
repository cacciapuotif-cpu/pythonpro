from pathlib import Path

from services.parsers.formazienda.atto_adesione_parser import parse_atto_adesione

CAMPIONE = Path(__file__).parent.parent.parent / "imports" / "formazienda" / "ALLEGATO E.pdf"


def test_estrae_piano_e_avviso():
    result = parse_atto_adesione(str(CAMPIONE))
    piano = result["piano"]
    assert piano["id_piano_esterno"] == "222-S2621"
    assert piano["titolo"] == "WHITE FORM"
    assert piano["avviso"] == "2/2022"


def test_trappola_data_approvazione_usa_la_delibera_non_il_piede_di_pagina():
    result = parse_atto_adesione(str(CAMPIONE))
    # Il piede di pagina ripete "Data approvazione: 03/08/2022" su ogni
    # pagina (approvazione del MODULO). La data del PIANO e' la delibera
    # citata nelle premesse: 11/06/2026.
    assert result["piano"]["delibera_data"] == "2026-06-11"
    assert result["piano"]["delibera_data"] != "2022-08-03"


def test_trappola_sottoscrizione_e_la_firma_digitale_non_l_emissione():
    result = parse_atto_adesione(str(CAMPIONE))
    # 01/07/2026 = firma PAdES; 10/08/2022 = emissione del modulo (rev. 00).
    assert result["piano"]["data_sottoscrizione"] == "2026-07-01"


def test_importi_a_b_c():
    piano = parse_atto_adesione(str(CAMPIONE))["piano"]
    assert piano["quota_pubblica"] == 55440.0
    assert piano["cofinanziamento"] == 0.0
    assert piano["autofinanziamento"] == 55440.0
    assert piano["costo_totale"] == 55440.0


def test_ente_attuatore_e_legale_rappresentante():
    ente = parse_atto_adesione(str(CAMPIONE))["ente_attuatore"]
    assert ente["ragione_sociale"] == "NEXT GROUP S.R.L."
    assert ente["partita_iva"] == "06615351217"
    assert ente["codice_fiscale"] == "06615351217"
    assert ente["citta"] == "NAPOLI"
    assert ente["cap"] == "80133"
    assert ente["legale_rappresentante_cognome"] == "CACCIAPUOTI"
    assert ente["legale_rappresentante_nome"] == "FRANCESCO"
    assert ente["legale_rappresentante_luogo_nascita"] == "NAPOLI"
    assert ente["legale_rappresentante_data_nascita"] == "1974-01-29"
    assert ente["legale_rappresentante_comune_residenza"] == "MUGNANO DI NAPOLI"


def test_nessuna_azienda_beneficiaria_mai_inventata():
    result = parse_atto_adesione(str(CAMPIONE))
    assert result["aziende_beneficiarie"] == []
    assert result["codici_progetto"] == []
