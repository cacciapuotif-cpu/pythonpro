"""
DOM-05 — Regole percentuali incompatibili (GATE W1.2, decisione confermata).

Due regole convivevano sulle stesse macrovoci:
- MACROVOCE_LIMITS (Formazienda): A<=20 / B<=50 / C<=30 — alert nel riepilogo;
- validate_sezioni_percentuali: A>=70 / C<=20 / D<=10 — BLOCCANTE (422) su
  create/update/delete voce, per giunta validata dopo il commit (DOM-06).

Inconciliabili (A<=20 vs A>=70): su piani costruiti col template standard
(docenza in macrovoce B) la regola bloccante interdiceva OGNI aggiunta voce
via API e corrompeva il piano (voce persistita + errore al client, D4 S3.4).

Decisione (GATE W1.2): la regola A>=70 appartiene a un altro schema di fondo
e viene rimossa; resta 20/50/30 come regola Formazienda alert-only in
costruzione; il blocco scatterà alla transizione di stato (Wave 2.2);
i limiti diventano funzione di tipo_fondo (get_macrovoce_limits).
"""

from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app
from database import Base, get_db
from auth import get_current_user
import models  # noqa: F401


@pytest.fixture(scope="function")
def db_session(tmp_path):
    db_path = tmp_path / "test_dom05.db"
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
def piano_solo_docenza(db_session):
    """Piano realistico: tutto il preventivo in macrovoce B (docenza).

    Con la regola bloccante A>=70 questo piano era immodificabile via API.
    """
    project = models.Project(name="Progetto DOM-05", description="t", status="active")
    db_session.add(project)
    db_session.commit()

    piano = models.PianoFinanziario(
        progetto_id=project.id,
        anno=2026,
        nome="Piano DOM-05",
        ente_erogatore="Formazienda",
        budget_totale=10000.0,
        stato="in_corso",
    )
    db_session.add(piano)
    db_session.commit()

    voce_b = models.VocePianoFinanziario(
        piano_id=piano.id,
        macrovoce="B",
        voce_codice="B.2",
        descrizione="Docenza",
        importo_preventivo=2400.0,
        importo_consuntivo=840.0,
    )
    db_session.add(voce_b)
    db_session.commit()
    return piano


class TestNessunBloccoPercentualeInCostruzione:
    def test_aggiunta_voce_su_piano_solo_docenza_permessa(self, client, db_session, piano_solo_docenza):
        """D4 S3.4: prima 422 'Sezione A fuori limite: 0.00% < 70%' con voce
        comunque persistita. Ora: la voce si aggiunge e basta."""
        response = client.post(
            f"/api/v1/piani-finanziari/{piano_solo_docenza.id}/voci",
            json={
                "piano_id": piano_solo_docenza.id,
                "descrizione": "Tutor aula",
                "importo_preventivo": 500.0,
            },
        )
        assert response.status_code == 201, response.text
        voce_id = response.json()["id"]
        salvata = db_session.query(models.VocePianoFinanziario).filter_by(id=voce_id).first()
        assert salvata is not None

    def test_update_voce_senza_blocco_percentuale(self, client, piano_solo_docenza, db_session):
        voce = db_session.query(models.VocePianoFinanziario).filter_by(
            piano_id=piano_solo_docenza.id
        ).first()
        response = client.put(
            f"/api/v1/piani-finanziari/{piano_solo_docenza.id}/voci/{voce.id}",
            json={"importo_preventivo": 3000.0},
        )
        assert response.status_code == 200, response.text

    def test_delete_voce_senza_blocco_percentuale(self, client, piano_solo_docenza, db_session):
        voce = db_session.query(models.VocePianoFinanziario).filter_by(
            piano_id=piano_solo_docenza.id
        ).first()
        response = client.delete(
            f"/api/v1/piani-finanziari/{piano_solo_docenza.id}/voci/{voce.id}"
        )
        assert response.status_code == 200, response.text


class TestAlertFormaziendaRestano:
    def test_riepilogo_segnala_macrovoce_b_oltre_limite(self, client, piano_solo_docenza):
        """La regola Formazienda 20/50/30 resta come alert nel riepilogo."""
        response = client.get(
            f"/api/v1/piani-finanziari/{piano_solo_docenza.id}/riepilogo"
        )
        assert response.status_code == 200, response.text
        alerts = response.json().get("alerts") or []
        codes = {a.get("code") for a in alerts}
        assert "macrovoce_b_over_limit" in codes


class TestLimitiPerFondo:
    def test_limiti_formazienda(self):
        from piano_finanziario_config import get_macrovoce_limits

        limits = get_macrovoce_limits("formazienda")
        assert limits == {"A": 20.0, "B": 50.0, "C": 30.0, "D": None}

    def test_fondo_sconosciuto_usa_default_formazienda(self):
        """Finché la tassonomia per-fondo non è popolata (Wave 2.3), i piani
        'altro' mantengono il comportamento attuale: alert Formazienda."""
        from piano_finanziario_config import get_macrovoce_limits

        assert get_macrovoce_limits("altro") == get_macrovoce_limits("formazienda")
        assert get_macrovoce_limits(None) == get_macrovoce_limits("formazienda")

    def test_regola_bloccante_a70_eliminata(self):
        """La regola A>=70/C<=20/D<=10 (schema di altro fondo) non esiste più."""
        import piano_finanziario_config as cfg

        assert not hasattr(cfg, "validate_sezioni_percentuali")
