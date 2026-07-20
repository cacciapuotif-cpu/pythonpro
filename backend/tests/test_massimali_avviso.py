"""
E1.3 (piano) / E1.4 (numerazione utente) — Massimali con precedenza regola
avviso validata.

Precedenza: AvvisoRegola con stato='validata' sulla revisione del piano
(categoria 'massimali'/'parametri_costo', chiave che matcha docenza/tutoraggio)
vince sul MassimaleFondo generico. Il 422 cita fonte e riferimento articolo.
Formato valore non interpretabile -> warning + fallback al fondo (MAI limiti
inventati).
"""

from decimal import Decimal
from pathlib import Path
import logging
import sys
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app
from database import Base, get_db
from auth import User, get_current_user
import models  # noqa: F401


@pytest.fixture(scope="function")
def db_session(tmp_path):
    db_path = tmp_path / "test_massimali_avviso.db"
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


@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        yield db_session

    def override_get_current_user():
        return type(
            "TestUser",
            (),
            {
                "id": 1,
                "username": "test-admin",
                "email": "test-admin@example.com",
                "role": "admin",
                "is_active": True,
            },
        )()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def base(db_session):
    """Progetto + avviso/revisione + piano fondimpresa 2026 agganciato alla
    revisione, con MassimaleFondo docenza=100 e tutoraggio=70."""
    validator = User(
        username="validatore",
        email="validatore@example.com",
        hashed_password="x",
        role="admin",
    )
    db_session.add(validator)
    db_session.flush()

    project = models.Project(
        name="Progetto E1.4",
        description="t",
        status="active",
        start_date=datetime(2026, 7, 1),
        end_date=datetime(2026, 7, 31),
    )
    db_session.add(project)
    db_session.flush()

    avviso = models.Avviso(
        codice="AVV-E14",
        ente_erogatore="Fondimpresa",
        fondo="fondimpresa",
        numero="1/2026",
        anno=2026,
        titolo="Avviso E1.4",
    )
    db_session.add(avviso)
    db_session.flush()

    revisione = models.AvvisoRevisione(
        avviso_id=avviso.id,
        numero_revisione=1,
        titolo="Avviso E1.4 rev 1",
    )
    db_session.add(revisione)
    db_session.flush()
    avviso.revisione_corrente_id = revisione.id

    piano = models.PianoFinanziario(
        progetto_id=project.id,
        anno=2026,
        nome="Piano E1.4",
        ente_erogatore="Fondimpresa",
        tipo_fondo="fondimpresa",
        budget_totale=100000.0,
        data_inizio=datetime(2026, 7, 1),
        data_fine=datetime(2026, 7, 31),
        stato="in_corso",
        avviso_pf_id=avviso.id,
        avviso_revisione_id=revisione.id,
    )
    massimale = models.MassimaleFondo(
        tipo_fondo="fondimpresa",
        anno=2026,
        massimale_orario_docenza=100,
        massimale_orario_tutoraggio=70,
    )
    db_session.add_all([piano, massimale])
    db_session.commit()
    return project, avviso, revisione, piano


def _regola(revisione, *, chiave, valore, stato="validata", categoria="massimali",
            riferimento_articolo="Art. 12", testo_originale="Il costo orario della docenza non può superare 80 euro."):
    validazione = {}
    if stato == "validata":
        # ck_avviso_regole_validazione_completa: validata richiede chi e quando
        validazione = {
            "validata_da_user_id": 1,
            "validata_il": datetime(2026, 7, 1, 10, 0, 0),
        }
    return models.AvvisoRegola(
        avviso_revisione_id=revisione.id,
        categoria=categoria,
        chiave=chiave,
        valore=valore,
        tipo_valore="oggetto",
        testo_originale=testo_originale,
        riferimento_articolo=riferimento_articolo,
        stato=stato,
        **validazione,
    )


def _voce_payload(piano, tariffa, categoria="docenza"):
    return {
        "piano_id": piano.id,
        "categoria": categoria,
        "descrizione": f"Voce {categoria}",
        "tariffa_oraria": tariffa,
    }


def test_precedenza_regola_avviso_su_massimale_fondo(client, db_session, base):
    """Fondo docenza=100, regola validata docenza=80: la voce a 90 va bloccata
    citando la regola avviso (senza regola sarebbe passata)."""
    project, avviso, revisione, piano = base
    db_session.add(_regola(
        revisione,
        chiave="costo_orario_docenza",
        valore={"tipo": "denaro", "importo": 80, "valuta": "EUR"},
    ))
    db_session.commit()

    r = client.post(f"/api/v1/piani-finanziari/{piano.id}/voci", json=_voce_payload(piano, 90.0))
    assert r.status_code == 422, r.text
    detail = r.json()["detail"]
    assert "Art. 12" in detail
    assert db_session.query(models.VocePianoFinanziario).count() == 0


def test_fallback_massimale_fondo_senza_regola(client, db_session, base):
    """Senza regole avviso vale il MassimaleFondo come oggi: 90 passa (fondo
    100), 110 viene bloccata citando il massimale fondo."""
    project, avviso, revisione, piano = base

    ok = client.post(f"/api/v1/piani-finanziari/{piano.id}/voci", json=_voce_payload(piano, 90.0))
    assert ok.status_code == 201, ok.text

    ko = client.post(f"/api/v1/piani-finanziari/{piano.id}/voci", json=_voce_payload(piano, 110.0))
    assert ko.status_code == 422, ko.text
    assert "massimale fondo" in ko.json()["detail"].lower()


def test_regola_non_validata_ignorata(client, db_session, base):
    """Regola in stato 'proposta' non ha effetto: vale il fondo (100)."""
    project, avviso, revisione, piano = base
    db_session.add(_regola(
        revisione,
        chiave="costo_orario_docenza",
        valore={"tipo": "denaro", "importo": 80, "valuta": "EUR"},
        stato="proposta",
    ))
    db_session.commit()

    r = client.post(f"/api/v1/piani-finanziari/{piano.id}/voci", json=_voce_payload(piano, 90.0))
    assert r.status_code == 201, r.text


def test_422_cita_articolo(client, db_session, base):
    """Il detail del 422 da regola cita il riferimento articolo e la fonte
    'regola avviso'."""
    project, avviso, revisione, piano = base
    db_session.add(_regola(
        revisione,
        chiave="massimale_orario_tutoraggio",
        valore={"tipo": "denaro", "importo": 50, "valuta": "EUR"},
        categoria="parametri_costo",
        riferimento_articolo="Art. 7 comma 2",
    ))
    db_session.commit()

    r = client.post(
        f"/api/v1/piani-finanziari/{piano.id}/voci",
        json=_voce_payload(piano, 60.0, categoria="tutoraggio"),
    )
    assert r.status_code == 422, r.text
    detail = r.json()["detail"]
    assert "regola avviso" in detail.lower()
    assert "Art. 7 comma 2" in detail


def test_valore_non_interpretabile_fallback(client, db_session, base, caplog):
    """Valore JSON non interpretabile come limite numerico: warning + fallback
    al MassimaleFondo, MAI limiti inventati."""
    project, avviso, revisione, piano = base
    db_session.add(_regola(
        revisione,
        chiave="costo_orario_docenza",
        valore={"tipo": "testo", "valore": "costo congruo secondo mercato"},
    ))
    db_session.commit()

    with caplog.at_level(logging.WARNING, logger="services.massimali"):
        ok = client.post(f"/api/v1/piani-finanziari/{piano.id}/voci", json=_voce_payload(piano, 90.0))
    assert ok.status_code == 201, ok.text
    assert any("non interpretabile" in rec.message for rec in caplog.records), (
        "warning per valore regola non interpretabile assente"
    )

    ko = client.post(f"/api/v1/piani-finanziari/{piano.id}/voci", json=_voce_payload(piano, 110.0))
    assert ko.status_code == 422, ko.text
    assert "massimale fondo" in ko.json()["detail"].lower()


@pytest.mark.parametrize(
    "valore",
    [
        {"tipo": "denaro", "importo": 80, "valuta": "EUR"},  # forma canonica estrattore
        {"importo": 80},
        {"valore": 80},
        80,
        "80",
    ],
    ids=["denaro_canonico", "dict_importo", "dict_valore", "scalare_int", "scalare_str"],
)
def test_forme_valore_interpretate(client, db_session, base, valore):
    """Tutte le forme note del JSON `valore` producono lo stesso limite 80."""
    project, avviso, revisione, piano = base
    db_session.add(_regola(revisione, chiave="costo_orario_docenza", valore=valore))
    db_session.commit()

    ko = client.post(f"/api/v1/piani-finanziari/{piano.id}/voci", json=_voce_payload(piano, 90.0))
    assert ko.status_code == 422, ko.text
    assert "80" in ko.json()["detail"]

    ok = client.post(f"/api/v1/piani-finanziari/{piano.id}/voci", json=_voce_payload(piano, 75.0))
    assert ok.status_code == 201, ok.text


def test_servizio_ritorna_fonte_e_limite(db_session, base):
    """Contratto del servizio puro: MassimaleEffettivo con fonte regola_avviso
    quando la regola vince, massimale_fondo altrimenti."""
    from services.massimali import get_massimale_effettivo

    project, avviso, revisione, piano = base
    db_session.add(_regola(
        revisione,
        chiave="costo_orario_docenza",
        valore={"tipo": "denaro", "importo": 80, "valuta": "EUR"},
    ))
    db_session.commit()

    docenza = get_massimale_effettivo(db_session, piano, "docenza")
    assert docenza is not None
    assert docenza.limite == Decimal("80")
    assert docenza.fonte == "regola_avviso"
    assert docenza.riferimento_articolo == "Art. 12"
    assert docenza.testo_originale

    tutoraggio = get_massimale_effettivo(db_session, piano, "tutoraggio")
    assert tutoraggio is not None
    assert tutoraggio.limite == Decimal("70")
    assert tutoraggio.fonte == "massimale_fondo"
    assert tutoraggio.riferimento_articolo is None

    assert get_massimale_effettivo(db_session, piano, "coordinamento") is None
