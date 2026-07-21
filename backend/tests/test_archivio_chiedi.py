"""E3.2 — endpoint /api/v1/archivio/{search,chiedi} + orchestrazione "chiedi".

Copre le tre regole di onesta' non negoziabili con test espliciti:

1. retrieval vuoto -> stato="non_presente", risposta=None, **LLM MAI chiamato**
   (assert sul mock non invocato);
2. citazione fuori dal retrieval -> risposta scartata -> stato="degradato"
   (validazione server-side degli id citati);
3. LLM giu'/disabilitato (call_ollama_json solleva) -> stato="degradato" con i
   soli risultati di ricerca. La ricerca funziona sempre.

Piu' il caso felice (citazioni valide -> stato="ok") e la matrice RBAC (i 3
ruoli raggiungono search E chiedi, pattern test_rbac_download_endpoints.py con
RBAC_ENFORCE=True monkeypatchato).
"""

from datetime import datetime, timezone
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app
from database import Base, get_db
import auth
from auth import User, UserRole, get_current_user
import models  # noqa: F401 - registra i modelli sul Base
import services.archivio_chiedi as archivio_chiedi
from services.archivio_chiedi import chiedi_archivio


ALL_ROLES = (UserRole.ADMIN.value, UserRole.OPERATORE.value, UserRole.CONSULTAZIONE.value)


# ------------------------------------------------------------------
# Fixture DB + dati archivio (le fonti reali sono vuote — NEW-036 —
# quindi il test crea i propri dati per avere retrieval non vuoto).
# ------------------------------------------------------------------

@pytest.fixture(scope="function")
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def archivio(db_session):
    """Un avviso validato con una regola pertinente a 'massimale docenza'."""
    validator = User(
        username="validatore-e32",
        email="validatore-e32@example.com",
        hashed_password="x",
        role="admin",
    )
    db_session.add(validator)
    db_session.flush()

    avviso = models.Avviso(
        codice="AVV-E32-A",
        ente_erogatore="Formazienda",
        fondo="formazienda",
        numero="1/2026",
        anno=2026,
        titolo="Avviso E3.2 Formazienda",
    )
    db_session.add(avviso)
    db_session.flush()

    rev = models.AvvisoRevisione(avviso_id=avviso.id, numero_revisione=1, titolo="Rev 1")
    db_session.add(rev)
    db_session.flush()
    avviso.revisione_corrente_id = rev.id

    regola = models.AvvisoRegola(
        avviso_revisione_id=rev.id,
        categoria="massimali",
        chiave="massimale_orario_docenza",
        valore={"tipo": "denaro", "importo": 100, "valuta": "EUR"},
        testo_originale="Il massimale orario riconosciuto per la docenza e' pari a 100,00 euro.",
        riferimento_articolo="Art. 7",
        stato="validata",
        validata_da_user_id=validator.id,
        validata_il=datetime.now(timezone.utc),
    )
    db_session.add(regola)
    db_session.commit()
    db_session.refresh(regola)
    return {"avviso": avviso, "rev": rev, "regola": regola}


# ------------------------------------------------------------------
# Caso 1 — risposta citata: mock LLM con citazioni valide -> stato="ok"
# ------------------------------------------------------------------

def test_chiedi_risposta_citata_ok(db_session, archivio, monkeypatch):
    regola_id = archivio["regola"].id
    mock_llm = Mock(return_value={
        "risposta": "Il massimale orario per la docenza e' 100,00 euro.",
        "citazioni": [f"regola:{regola_id}"],
    })
    monkeypatch.setattr(archivio_chiedi, "call_ollama_json", mock_llm)

    esito = chiedi_archivio(db_session, "massimale docenza")

    assert esito.stato == "ok"
    assert esito.risposta and "100" in esito.risposta
    assert mock_llm.call_count == 1
    # Citazione ancorata al passaggio realmente recuperato.
    assert [c.regola_id for c in esito.citazioni] == [regola_id]
    assert esito.risultati, "i risultati di ricerca accompagnano sempre la risposta"


# ------------------------------------------------------------------
# Caso 1b (NEW-037) — domanda in linguaggio naturale verbosa: il retrieval a
# due stadi (or_fallback) la recupera e l'LLM viene interpellato. Prima, la
# domanda grezza in AND (websearch_to_tsquery) su PG dava 0 -> non_presente.
# ------------------------------------------------------------------

def test_chiedi_domanda_naturale_recupera_e_interpella_llm(db_session, archivio, monkeypatch):
    regola_id = archivio["regola"].id
    mock_llm = Mock(return_value={
        "risposta": "Il massimale orario per la docenza e' 100,00 euro.",
        "citazioni": [f"regola:{regola_id}"],
    })
    monkeypatch.setattr(archivio_chiedi, "call_ollama_json", mock_llm)

    esito = chiedi_archivio(db_session, "Qual e' il massimale orario per la docenza?")

    assert esito.stato == "ok"
    assert mock_llm.call_count == 1, "la domanda NL deve recuperare passaggi e interpellare l'LLM"
    assert [c.regola_id for c in esito.citazioni] == [regola_id]


def test_chiedi_domanda_naturale_tema_assente_non_presente(db_session, archivio, monkeypatch):
    """Onesta' intatta con or_fallback: tema del tutto assente -> non_presente,
    LLM mai interpellato."""
    mock_llm = Mock(return_value={"risposta": "x", "citazioni": []})
    monkeypatch.setattr(archivio_chiedi, "call_ollama_json", mock_llm)

    esito = chiedi_archivio(db_session, "Come funzionano criptovalute e blockchain?")

    assert esito.stato == "non_presente"
    assert esito.risultati == []
    mock_llm.assert_not_called()


# ------------------------------------------------------------------
# Caso 2 — non_presente: retrieval vuoto, LLM MAI chiamato
# ------------------------------------------------------------------

def test_chiedi_non_presente_llm_non_invocato(db_session, archivio, monkeypatch):
    mock_llm = Mock(return_value={"risposta": "x", "citazioni": []})
    monkeypatch.setattr(archivio_chiedi, "call_ollama_json", mock_llm)

    # Termine assente dall'archivio -> retrieval vuoto.
    esito = chiedi_archivio(db_session, "criptovalute blockchain inesistente")

    assert esito.stato == "non_presente"
    assert esito.risposta is None
    assert esito.citazioni == []
    assert esito.risultati == []
    mock_llm.assert_not_called()


# ------------------------------------------------------------------
# Caso 3 — degradato per LLM error: call_ollama_json solleva
# ------------------------------------------------------------------

def test_chiedi_degradato_llm_error(db_session, archivio, monkeypatch):
    def _boom(*args, **kwargs):
        raise RuntimeError("Provider LLM non abilitato")

    mock_llm = Mock(side_effect=_boom)
    monkeypatch.setattr(archivio_chiedi, "call_ollama_json", mock_llm)

    esito = chiedi_archivio(db_session, "massimale docenza")

    assert esito.stato == "degradato"
    assert esito.risposta is None
    assert esito.citazioni == []
    # La ricerca funziona sempre: i risultati ci sono comunque.
    assert esito.risultati, "il degrado mantiene i risultati di ricerca"
    assert mock_llm.call_count == 1


# ------------------------------------------------------------------
# Caso 4 — citazione fuori retrieval scartata -> degradato
# ------------------------------------------------------------------

def test_chiedi_citazione_fuori_retrieval_scartata(db_session, archivio, monkeypatch):
    # L'LLM cita un id NON presente nel retrieval: la risposta va scartata.
    mock_llm = Mock(return_value={
        "risposta": "Il massimale e' 999 euro secondo un articolo inventato.",
        "citazioni": ["regola:999999"],
    })
    monkeypatch.setattr(archivio_chiedi, "call_ollama_json", mock_llm)

    esito = chiedi_archivio(db_session, "massimale docenza")

    assert esito.stato == "degradato"
    assert esito.risposta is None, "risposta con citazione fuori retrieval scartata"
    assert esito.citazioni == []
    assert esito.risultati, "restano i soli risultati di ricerca"
    assert mock_llm.call_count == 1


# ------------------------------------------------------------------
# Caso 5 — RBAC: i 3 ruoli raggiungono search E chiedi (HTTP, enforce on)
# ------------------------------------------------------------------

@pytest.fixture(scope="function")
def users_by_role(db_session):
    users = {}
    for role in ALL_ROLES:
        user = User(
            username=f"archivio_{role}",
            email=f"archivio_{role}@example.com",
            hashed_password="x",
            role=role,
            is_active=True,
        )
        db_session.add(user)
        users[role] = user
    db_session.commit()
    for user in users.values():
        db_session.refresh(user)
    return users


@pytest.fixture(scope="function")
def client(db_session, monkeypatch):
    monkeypatch.setattr(auth, "RBAC_ENFORCE", True)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.mark.parametrize("role", ALL_ROLES)
def test_rbac_search_tre_ruoli_200(client, users_by_role, role):
    app.dependency_overrides[get_current_user] = lambda: users_by_role[role]
    resp = client.get("/api/v1/archivio/search", params={"q": "massimale docenza"})
    assert resp.status_code == 200, (
        f"ruolo {role} doveva passare il gate RBAC su GET /search, "
        f"ottenuto {resp.status_code}: {resp.text[:200]}"
    )
    assert isinstance(resp.json(), list)


@pytest.mark.parametrize("role", ALL_ROLES)
def test_rbac_chiedi_tre_ruoli_200(client, users_by_role, role, monkeypatch):
    # Il POST /chiedi e' una query di lettura: i 3 ruoli devono raggiungerlo.
    # Provider LLM non configurato in test -> degrado onesto, ma il gate RBAC
    # deve comunque lasciare passare (mai 401/403).
    app.dependency_overrides[get_current_user] = lambda: users_by_role[role]
    resp = client.post(
        "/api/v1/archivio/chiedi",
        json={"domanda": "massimale docenza"},
    )
    assert resp.status_code == 200, (
        f"ruolo {role} doveva passare il gate RBAC su POST /chiedi, "
        f"ottenuto {resp.status_code}: {resp.text[:200]}"
    )
    assert resp.json()["stato"] in ("ok", "non_presente", "degradato")


# ------------------------------------------------------------------
# Matrice RBAC pura (senza HTTP): conferma la decisione per ogni ruolo.
# ------------------------------------------------------------------

@pytest.mark.parametrize("role", ALL_ROLES)
def test_matrice_rbac_search_e_chiedi(role):
    assert auth.rbac_decision_for("GET", "/api/v1/archivio/search", role)["would_status"] == 200
    assert auth.rbac_decision_for("POST", "/api/v1/archivio/chiedi", role)["would_status"] == 200
