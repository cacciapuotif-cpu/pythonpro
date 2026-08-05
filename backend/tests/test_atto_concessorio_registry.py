from services.atto_concessorio_registry import for_ente_erogatore, fornisce_aziende_beneficiarie


def test_fapi_fornisce_aziende():
    voce = for_ente_erogatore("FAPI")
    assert voce.tipo_documento == "convenzione"
    assert voce.fornisce_aziende_beneficiarie is True
    assert fornisce_aziende_beneficiarie("FAPI") is True


def test_formazienda_non_fornisce_aziende():
    voce = for_ente_erogatore("Formazienda")
    assert voce.tipo_documento == "atto_concessione"
    assert voce.etichetta_atto == "Atto di adesione (Allegato E)"
    assert voce.etichetta_formulario == "Formulario (Allegato A)"
    assert voce.etichetta_codice_progetto == "Codice pratica Formazienda"
    assert voce.fornisce_ente_attuatore is True
    assert voce.fornisce_aziende_beneficiarie is False
    assert fornisce_aziende_beneficiarie("Formazienda") is False


def test_fondo_sconosciuto_o_assente_resta_prudente():
    # Nessuna dichiarazione = comportamento FAPI-like (perimetro), mai il contrario:
    # allargare l'accesso di default sarebbe la regressione pericolosa.
    assert fornisce_aziende_beneficiarie(None) is True
    assert fornisce_aziende_beneficiarie("Ente Mai Visto") is True


def test_fondo_sconosciuto_ha_etichette_generiche():
    # Un fondo non censito deve comunque restituire etichette utilizzabili in UI,
    # mai None/KeyError: e' esattamente il caso "vista funziona senza rompersi".
    voce = for_ente_erogatore("Ente Mai Visto")
    assert voce.etichetta_atto == "Convenzione"
    assert voce.etichetta_formulario == "Formulario"
    assert voce.etichetta_piano_finanziario == "Piano finanziario"
    assert voce.etichetta_codice_progetto == "Codice progetto"


def test_fondimpresa_struttura_predisposta_non_attivata():
    voce = for_ente_erogatore("Fondimpresa")
    assert voce.tipo_documento == "atto_concessione"
    assert voce.fornisce_aziende_beneficiarie is False
