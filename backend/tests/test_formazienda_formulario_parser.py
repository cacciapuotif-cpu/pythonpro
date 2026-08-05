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


def test_quattordici_imprese_beneficiarie_con_dati_reali():
    imprese = parse_formulario(str(CAMPIONE))["imprese_beneficiarie"]
    assert len(imprese) == 14
    ragioni = {imp["ragione_sociale"] for imp in imprese}
    assert "PAKI UNITED FOREVER S.R.L.S." in ragioni
    assert "NEXT GROUP S.R.L." not in ragioni
    assert "A.M.D. S.R.L." not in ragioni

    paki = next(imp for imp in imprese if imp["ragione_sociale"] == "PAKI UNITED FOREVER S.R.L.S.")
    assert paki["partita_iva"] == "08951911216"
    assert paki["codice_fiscale"] == "08951911216"
    assert paki["matricola_inps"] == "5138462742"
    assert paki["codice_ateco"] == "38.21.40"
    assert paki["classe_dimensionale"] == "micro"
    assert paki["regime_aiuti"] == "de_minimis"
    assert paki["legale_rappresentante_cognome"] == "IACOMINO"
    assert paki["numero_dipendenti_totale"] == 6


def test_ditta_individuale_cf_personale_diverso_da_piva():
    imprese = parse_formulario(str(CAMPIONE))["imprese_beneficiarie"]
    pama = next(imp for imp in imprese if imp["ragione_sociale"] == "PAMA DI GUARRACINO MARIANNA")
    assert pama["codice_fiscale"] == "GRRMNN01C70C291M"
    assert pama["partita_iva"] == "04800950612"
    assert pama["codice_fiscale"] != pama["partita_iva"]


def test_campi_vuoti_non_fanno_fallire_il_parser():
    imprese = parse_formulario(str(CAMPIONE))["imprese_beneficiarie"]
    paki = next(imp for imp in imprese if imp["ragione_sociale"] == "PAKI UNITED FOREVER S.R.L.S.")
    assert paki["telefono"] is None
    assert paki["ccnl"] is None
    assert paki["welfare"] is None


def test_progetto_formativo_ore_edizioni_e_modalita():
    progetti = parse_formulario(str(CAMPIONE))["progetti_formativi"]
    assert len(progetti) == 1
    progetto = progetti[0]
    assert progetto["titolo"] == "OPERATORE SEGRETARIALE"
    assert progetto["ore_formazione"] == 24.0
    assert progetto["edizioni"] == 14
    assert progetto["modalita_attuazione"] == [
        {"tipo": "aula", "ore": 14.0, "percentuale": 58.33},
        {"tipo": "training_on_job", "ore": 10.0, "percentuale": 41.67},
    ]


def test_quadratura_costo_progetto():
    progetto = parse_formulario(str(CAMPIONE))["progetti_formativi"][0]
    # 14 edizioni x 3.960,00 = 55.440,00 = totale dichiarato
    assert progetto["quadratura_costo_ok"] is True


def test_macrovoci_e_quadratura():
    riepilogo = parse_formulario(str(CAMPIONE))["riepilogo"]
    macrovoci = {m["codice"]: m for m in riepilogo["macrovoci"]}
    assert macrovoci["A"]["importo"] == 11088.0
    assert macrovoci["A"]["limite_max_pct"] == 20
    assert macrovoci["C"]["limite_max_pct"] == 30
    assert riepilogo["quadratura_macrovoci_ok"] is True
    assert riepilogo["quadratura_finanziamento_per_impresa_ok"] is True


def test_quattordici_finanziamenti_per_impresa_per_associare_le_edizioni():
    righe = parse_formulario(str(CAMPIONE))["riepilogo"]["finanziamenti_per_impresa"]
    assert len(righe) == 14
    assert {riga["finanziamento"] for riga in righe} == {3960.0}
    pama = next(riga for riga in righe if riga["ragione_sociale"] == "PAMA DI GUARRACINO")
    assert pama["identificativo_fiscale"] == "GRRMNN01C70C291M"
    assert pama["cofinanziamento"] == 0.0


def test_cronoprogramma_mese_anno_senza_giorno():
    cronoprogramma = parse_formulario(str(CAMPIONE))["riepilogo"]["cronoprogramma"]
    assert cronoprogramma["durata_giorni"] == 180
    avvio = next(a for a in cronoprogramma["attivita"] if a["nome"] == "Avvio Piano Formativo")
    assert avvio == {"nome": "Avvio Piano Formativo", "mese": 5, "anno": 2026}
    # Nessun giorno inventato: la chiave "giorno" non deve esistere.
    assert "giorno" not in avvio
