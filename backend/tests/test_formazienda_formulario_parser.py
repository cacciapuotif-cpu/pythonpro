from pathlib import Path

from services.parsers.formazienda.formulario_parser import parse_formulario

CAMPIONE = Path(__file__).parent.parent.parent / "imports" / "formazienda" / "ALLEGATO A.pdf"


def test_titolo_e_tipologia_piano():
    result = parse_formulario(str(CAMPIONE))
    assert result["piano"]["titolo"] == "WHITE FORM"
    assert result["piano"]["tipologia"] == "Territoriale"


def test_soggetto_gestore_non_e_beneficiaria():
    result = parse_formulario(str(CAMPIONE))
    gestore = result["soggetto_gestore"]
    assert gestore["ragione_sociale"] == "NEXT GROUP S.R.L."
    assert gestore["partita_iva"] == "06615351217"
    assert gestore["legale_rappresentante_cognome"] == "CACCIAPUOTI"
    nomi_beneficiarie = [imp.get("ragione_sociale") for imp in result["imprese_beneficiarie"]]
    assert "NEXT GROUP S.R.L." not in nomi_beneficiarie


def test_soggetto_delegato_con_importo_e_percentuale():
    delegato = parse_formulario(str(CAMPIONE))["soggetto_delegato"]
    assert delegato["ragione_sociale"] == "A.M.D. S.R.L."
    assert delegato["partita_iva"] == "06296751214"
    assert delegato["importo"] == 14000.0
    assert delegato["percentuale"] == 25.25


def test_soggetti_partner_vuoto_non_fallisce():
    result = parse_formulario(str(CAMPIONE))
    assert result["soggetti_partner"] == []
