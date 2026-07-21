"""
E3.1 — search_archivio: ricerca full-text sulle 3 fonti dell'archivio avvisi.

Fonti: AvvisoRegola (SOLO stato='validata'), AvvisoConoscenza.contenuto(+tags),
AvvisoEsitoProgetto (esito+note). Dialect-aware: PostgreSQL usa tsvector
'italian' (websearch_to_tsquery + ts_rank), SQLite (questa suite) usa il
fallback ILIKE per termine con rank = numero di termini matchati. Stesso
contratto di ritorno; il fallback e' anche il degrado runtime.

I markdown puliti delle revisioni (cleaned_md_path) stanno su file, fuori
dal DB: NON sono una fonte di questa ricerca (dichiarato nel piano E3).

Il percorso tsvector reale e' coperto dal test PG-only in coda (pattern
DOM-21: skip senza un DATABASE_URL PostgreSQL dedicato).
"""

from datetime import datetime, timezone
from pathlib import Path
import os
import sys

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

from database import Base
from auth import User
import models  # noqa: F401
from services.archivio_search import RisultatoArchivio, search_archivio


@pytest.fixture(scope="function")
def db_session(tmp_path):
    db_path = tmp_path / "test_archivio_search.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def archivio(db_session):
    """Due avvisi (formazienda/fapi) con regole, conoscenza ed esito noti."""
    validator = User(
        username="validatore-e3",
        email="validatore-e3@example.com",
        hashed_password="x",
        role="admin",
    )
    db_session.add(validator)
    db_session.flush()

    avviso1 = models.Avviso(
        codice="AVV-E31-A",
        ente_erogatore="Formazienda",
        fondo="formazienda",
        numero="1/2026",
        anno=2026,
        titolo="Avviso E3.1 Formazienda",
    )
    avviso2 = models.Avviso(
        codice="AVV-E31-B",
        ente_erogatore="FAPI",
        fondo="fapi",
        numero="2/2026",
        anno=2026,
        titolo="Avviso E3.1 FAPI",
    )
    db_session.add_all([avviso1, avviso2])
    db_session.flush()

    rev1 = models.AvvisoRevisione(avviso_id=avviso1.id, numero_revisione=1, titolo="Rev 1 A")
    rev2 = models.AvvisoRevisione(avviso_id=avviso2.id, numero_revisione=1, titolo="Rev 1 B")
    db_session.add_all([rev1, rev2])
    db_session.flush()
    avviso1.revisione_corrente_id = rev1.id
    avviso2.revisione_corrente_id = rev2.id

    now = datetime.now(timezone.utc)
    regola_validata = models.AvvisoRegola(
        avviso_revisione_id=rev1.id,
        categoria="massimali",
        chiave="massimale_orario_docenza",
        valore={"tipo": "denaro", "importo": 100, "valuta": "EUR"},
        testo_originale="Il massimale orario riconosciuto per la docenza e' pari a 100,00 euro.",
        riferimento_articolo="Art. 7",
        stato="validata",
        validata_da_user_id=validator.id,
        validata_il=now,
    )
    regola_proposta = models.AvvisoRegola(
        avviso_revisione_id=rev1.id,
        categoria="massimali",
        chiave="massimale_orario_tutoraggio",
        valore={"tipo": "denaro", "importo": 30, "valuta": "EUR"},
        testo_originale="Il massimale orario per il tutoraggio e' pari a 30,00 euro.",
        riferimento_articolo="Art. 8",
        stato="proposta",
    )
    regola_avviso2 = models.AvvisoRegola(
        avviso_revisione_id=rev2.id,
        categoria="rendicontazione",
        chiave="termine_rendicontazione_finale",
        valore={"tipo": "ore", "valore": 60},
        testo_originale="La rendicontazione finale va presentata entro 60 giorni dalla chiusura.",
        riferimento_articolo="Art. 12",
        stato="validata",
        validata_da_user_id=validator.id,
        validata_il=now,
    )
    conoscenza = models.AvvisoConoscenza(
        avviso_id=avviso1.id,
        avviso_revisione_id=rev1.id,
        tipo="nota_operativa",
        contenuto="Nota operativa: per la rendicontazione serve il registro presenze firmato.",
        tags=["rendicontazione", "presenze"],
    )
    project = models.Project(name="Progetto E3.1")
    db_session.add_all(
        [regola_validata, regola_proposta, regola_avviso2, conoscenza, project]
    )
    db_session.flush()
    esito = models.AvvisoEsitoProgetto(
        avviso_id=avviso2.id,
        avviso_revisione_id=rev2.id,
        project_id=project.id,
        esito="decurtato",
        note="Decurtazione per superamento del massimale docenza in fase di rendicontazione.",
    )
    db_session.add(esito)
    db_session.commit()
    return {
        "avviso1": avviso1,
        "avviso2": avviso2,
        "rev1": rev1,
        "rev2": rev2,
        "regola_validata": regola_validata,
        "regola_proposta": regola_proposta,
        "regola_avviso2": regola_avviso2,
        "conoscenza": conoscenza,
        "esito": esito,
    }


def _regole_ids(risultati):
    return {r.regola_id for r in risultati if r.fonte == "regola"}


def test_regola_validata_trovata_proposta_esclusa(db_session, archivio):
    risultati = search_archivio(db_session, "massimale docenza")
    assert risultati, "la regola validata deve essere trovata"
    ids = _regole_ids(risultati)
    assert archivio["regola_validata"].id in ids
    assert archivio["regola_proposta"].id not in ids

    # 'tutoraggio' compare SOLO nella regola in stato proposta -> zero risultati
    assert search_archivio(db_session, "tutoraggio") == []


def test_tutte_le_fonti_raggiungibili(db_session, archivio):
    risultati = search_archivio(db_session, "rendicontazione")
    fonti = {r.fonte for r in risultati}
    assert fonti == {"regola", "conoscenza", "esito"}


def test_filtro_avviso_id(db_session, archivio):
    risultati = search_archivio(
        db_session, "rendicontazione", avviso_id=archivio["avviso1"].id
    )
    assert risultati
    assert all(r.avviso_id == archivio["avviso1"].id for r in risultati)
    assert {r.fonte for r in risultati} == {"conoscenza"}


def test_filtro_tipo_fondo(db_session, archivio):
    risultati = search_archivio(db_session, "rendicontazione", tipo_fondo="fapi")
    assert risultati
    assert all(r.avviso_id == archivio["avviso2"].id for r in risultati)
    assert {r.fonte for r in risultati} == {"regola", "esito"}


def test_estratto_contiene_testo_cercato(db_session, archivio):
    risultati = search_archivio(db_session, "registro presenze")
    assert len(risultati) == 1
    assert risultati[0].fonte == "conoscenza"
    assert "registro presenze" in risultati[0].estratto.lower()


def test_ordinamento_per_rank(db_session, archivio):
    # L'esito matcha sia 'massimale' sia 'rendicontazione'; conoscenza e
    # regola avviso2 solo 'rendicontazione' -> l'esito deve stare in testa.
    risultati = search_archivio(db_session, "massimale rendicontazione")
    assert len(risultati) >= 3
    assert risultati[0].fonte == "esito"
    ranks = [r.rank for r in risultati]
    assert ranks == sorted(ranks, reverse=True)
    assert all(r.rank > 0 for r in risultati)


def test_campi_risultato_valorizzati(db_session, archivio):
    risultati = search_archivio(db_session, "massimale docenza euro")
    regola = next(r for r in risultati if r.fonte == "regola")
    assert isinstance(regola, RisultatoArchivio)
    assert regola.avviso_id == archivio["avviso1"].id
    assert regola.avviso_titolo == "Avviso E3.1 Formazienda"
    assert regola.revisione_id == archivio["rev1"].id
    assert regola.regola_id == archivio["regola_validata"].id
    assert regola.conoscenza_id is None and regola.esito_id is None
    assert regola.riferimento_articolo == "Art. 7"

    conoscenza = next(
        r for r in search_archivio(db_session, "registro presenze")
        if r.fonte == "conoscenza"
    )
    assert conoscenza.conoscenza_id == archivio["conoscenza"].id
    assert conoscenza.regola_id is None and conoscenza.esito_id is None
    assert conoscenza.riferimento_articolo is None

    esito = next(
        r for r in search_archivio(db_session, "decurtazione")
        if r.fonte == "esito"
    )
    assert esito.esito_id == archivio["esito"].id
    assert esito.regola_id is None and esito.conoscenza_id is None


def test_query_vuota_o_corta(db_session, archivio):
    assert search_archivio(db_session, "") == []
    assert search_archivio(db_session, "   ") == []
    assert search_archivio(db_session, "ab") == []


def test_query_solo_termini_insignificanti(db_session, archivio):
    # >= 3 caratteri totali ma nessun termine utile (fallback ILIKE)
    assert search_archivio(db_session, "a e i o") == []


def test_limit_rispettato(db_session, archivio):
    risultati = search_archivio(db_session, "rendicontazione", limit=1)
    assert len(risultati) == 1


def test_nessun_match(db_session, archivio):
    assert search_archivio(db_session, "inesistente parola introvabile") == []


# ---------------------------------------------------------------------------
# NEW-037 — retrieval a due stadi (or_fallback) per le domande in linguaggio
# naturale di "chiedi all'archivio". Portabile su SQLite: il fallback OR ha lo
# stesso contratto del percorso tsvector (il caso letterale del finding, che su
# PostgreSQL da' 0 in AND, e' nel test PG-only in coda).
# ---------------------------------------------------------------------------


def test_or_fallback_domanda_naturale_recupera(db_session, archivio):
    """La domanda verbosa del finding recupera la regola docenza con
    or_fallback (prima, in AND puro, avrebbe dato 0 perche' nessun documento
    contiene "qual")."""
    domanda = "Qual e' il massimale orario per la docenza?"
    risultati = search_archivio(db_session, domanda, or_fallback=True)
    assert risultati, "la domanda in linguaggio naturale deve recuperare passaggi"
    assert archivio["regola_validata"].id in _regole_ids(risultati)


def test_or_fallback_ingaggiato_solo_se_and_vuoto(db_session, archivio):
    """Nessun singolo documento contiene sia "docenza" sia "presenze": lo stadio
    AND e' vuoto, quindi risultati non vuoti provano che il fallback OR e'
    scattato (e attraversa piu' documenti, ciascuno con un solo termine)."""
    risultati = search_archivio(db_session, "docenza presenze", or_fallback=True)
    fonti = {r.fonte for r in risultati}
    # "presenze" vive solo nella conoscenza; "docenza" solo in regola/esito:
    # comparire entrambe dimostra l'OR (l'AND non avrebbe reso nulla).
    assert "conoscenza" in fonti
    assert archivio["regola_validata"].id in _regole_ids(risultati)


def test_or_fallback_non_sballa_su_termini_assenti(db_session, archivio):
    """Il fallback OR allarga solo sui termini realmente presenti: un termine
    inesistente non fa recuperare documenti che non contengono alcun termine
    utile della domanda."""
    risultati = search_archivio(
        db_session, "docenza inesistente introvabile", or_fallback=True
    )
    # Solo i documenti con "docenza" (regola_validata, esito); mai la conoscenza
    # o la regola_avviso2 (che non contengono nessun termine della domanda).
    assert risultati
    assert all("docenza" in r.estratto.lower() or r.fonte == "esito" for r in risultati)
    assert archivio["regola_avviso2"].id not in _regole_ids(risultati)
    assert "conoscenza" not in {r.fonte for r in risultati}


def test_or_fallback_tema_assente_resta_vuoto(db_session, archivio):
    """Onesta' intatta: una domanda su un tema del tutto assente resta vuota
    (entrambi gli stadi a zero) anche con or_fallback."""
    assert (
        search_archivio(
            db_session,
            "Come funzionano le criptovalute e la blockchain?",
            or_fallback=True,
        )
        == []
    )


def test_search_keyword_puro_invariato(db_session, archivio):
    """Non-regressione: la ricerca keyword pura del tab "Cerca" (or_fallback
    di default = False) continua a funzionare."""
    risultati = search_archivio(db_session, "massimale orario docenza")
    assert risultati
    assert archivio["regola_validata"].id in _regole_ids(risultati)


# ---------------------------------------------------------------------------
# Percorso PostgreSQL reale (tsvector + indici GIN della migration 061).
# Pattern DOM-21: richiede un DATABASE_URL PostgreSQL dedicato, altrimenti skip.
# Sola lettura sul DB indicato.
# ---------------------------------------------------------------------------

PG_URL = os.getenv("ARCHIVIO_FTS_TEST_DATABASE_URL")

pg_only = pytest.mark.skipif(
    not PG_URL or not PG_URL.startswith("postgresql"),
    reason="richiede ARCHIVIO_FTS_TEST_DATABASE_URL PostgreSQL dedicato",
)


@pg_only
def test_pg_indici_fts_presenti():
    engine = create_engine(PG_URL)
    try:
        with engine.connect() as conn:
            nomi = {
                row[0]
                for row in conn.execute(text(
                    "SELECT indexname FROM pg_indexes WHERE indexname LIKE 'ix_fts_avviso_%'"
                ))
            }
        assert {
            "ix_fts_avviso_regole_validata",
            "ix_fts_avviso_conoscenze",
            "ix_fts_avviso_esiti",
        } <= nomi
    finally:
        engine.dispose()


@pg_only
def test_pg_percorso_tsvector_esegue_e_ordina():
    engine = create_engine(PG_URL)
    SessionPG = sessionmaker(bind=engine)
    session = SessionPG()
    try:
        risultati = search_archivio(session, "massimale docenza")
        assert isinstance(risultati, list)
        for r in risultati:
            assert isinstance(r, RisultatoArchivio)
            assert isinstance(r.rank, float)
            assert r.estratto
        ranks = [r.rank for r in risultati]
        assert ranks == sorted(ranks, reverse=True)
        # query corta -> [] anche su PG
        assert search_archivio(session, "ab") == []
    finally:
        session.close()
        engine.dispose()


@pg_only
def test_pg_new_037_domanda_naturale_and_zero_or_recupera():
    """NEW-037 letterale su PostgreSQL: la domanda verbosa in AND
    (websearch_to_tsquery) da' 0 risultati, mentre con or_fallback recupera i
    passaggi pertinenti. Sola lettura: crea dati in transazione e ROLLBACK.
    """
    engine = create_engine(PG_URL)
    SessionPG = sessionmaker(bind=engine)
    session = SessionPG()
    try:
        validator = User(
            username="validatore-new037",
            email="validatore-new037@example.com",
            hashed_password="x",
            role="admin",
        )
        session.add(validator)
        session.flush()
        avviso = models.Avviso(
            codice="AVV-NEW037",
            ente_erogatore="Formazienda",
            fondo="formazienda",
            numero="9/2026",
            anno=2026,
            titolo="Avviso NEW-037",
        )
        session.add(avviso)
        session.flush()
        rev = models.AvvisoRevisione(
            avviso_id=avviso.id, numero_revisione=1, titolo="Rev 1"
        )
        session.add(rev)
        session.flush()
        regola = models.AvvisoRegola(
            avviso_revisione_id=rev.id,
            categoria="massimali",
            chiave="massimale_orario_docenza",
            valore={"tipo": "denaro", "importo": 100, "valuta": "EUR"},
            testo_originale=(
                "Il massimale orario riconosciuto per la docenza e' pari a "
                "100,00 euro."
            ),
            riferimento_articolo="Art. 7",
            stato="validata",
            validata_da_user_id=validator.id,
            validata_il=datetime.now(timezone.utc),
        )
        session.add(regola)
        session.flush()

        domanda = "Qual e' il massimale orario per la docenza?"
        # AND puro (websearch_to_tsquery): 0 risultati, il bug del finding.
        assert search_archivio(session, domanda) == []
        # Due stadi (or_fallback): recupera la regola pertinente.
        recuperati = search_archivio(session, domanda, or_fallback=True)
        assert recuperati
        assert regola.id in {r.regola_id for r in recuperati if r.fonte == "regola"}
    finally:
        session.rollback()
        session.close()
        engine.dispose()
