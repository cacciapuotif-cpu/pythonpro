def test_classe_dimensionale_e_soggetto_delegato_esistono_nello_schema():
    import models
    assert hasattr(models.AziendaCliente, "classe_dimensionale")
    assert hasattr(models, "ProjectSoggettoDelegato")
    delegato = models.ProjectSoggettoDelegato(
        project_id=1, ragione_sociale="Test", importo=100.0, percentuale=10.0,
    )
    assert delegato.ragione_sociale == "Test"
