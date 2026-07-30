"""S5: pacchetto rendicontazione operativo e isolato per azienda."""

import io
import zipfile
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import auth
import models
from auth import get_current_user
from database import Base, get_db
from main import app
from services import rendicontazione


@pytest.fixture()
def db_session(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'rendicontazione.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def seeded_project(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(rendicontazione, "UPLOAD_BASE", str(tmp_path))
    avviso = models.Avviso(
        codice="FAPI-TEST",
        ente_erogatore="FAPI",
        fondo="fapi",
        numero="1",
        anno=2026,
        titolo="Avviso test",
        stato="attivo",
    )
    project = models.Project(
        name="Progetto rendicontazione",
        status="active",
        ente_erogatore="Formazienda legacy",
        avviso="Legacy",
        avviso_rel=avviso,
    )
    acme = models.AziendaCliente(ragione_sociale="ACME Srl", partita_iva="12345678901")
    beta = models.AziendaCliente(ragione_sociale="BETA Srl", partita_iva="12345678902")
    db_session.add_all([project, acme, beta])
    db_session.flush()
    db_session.add_all([
        models.AziendaClienteProjectLink(
            project_id=project.id,
            azienda_cliente_id=acme.id,
            regime_aiuto="esenzione",
        ),
        models.AziendaClienteProjectLink(
            project_id=project.id,
            azienda_cliente_id=beta.id,
            regime_aiuto="esenzione",
        ),
    ])
    allievo_acme = models.Allievo(nome="Ada", cognome="Acme", azienda_cliente_id=acme.id)
    allievo_beta = models.Allievo(nome="Bruno", cognome="Beta", azienda_cliente_id=beta.id)
    db_session.add_all([allievo_acme, allievo_beta])
    db_session.flush()
    (tmp_path / "acme.pdf").write_bytes(b"acme-payroll")
    (tmp_path / "beta.pdf").write_bytes(b"beta-payroll")
    db_session.add_all([
        models.DatiRetributivi(
            project_id=project.id,
            allievo_id=allievo_acme.id,
            busta_paga_path="acme.pdf",
        ),
        models.DatiRetributivi(
            project_id=project.id,
            allievo_id=allievo_beta.id,
            busta_paga_path="beta.pdf",
        ),
    ])
    db_session.commit()
    return project, allievo_acme, allievo_beta


def _zip_names(content):
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        return set(archive.namelist()), archive.read("00_MANIFEST.txt").decode("utf-8")


def test_service_usa_fondo_fk_e_isola_buste_paga_per_azienda(db_session, seeded_project):
    project, allievo_acme, allievo_beta = seeded_project

    content, filename = rendicontazione.genera_pacchetto_rendicontazione(db_session, project.id)
    names, manifest = _zip_names(content)

    assert filename.startswith("rendicontazione_Progetto_rendicontazione_")
    assert "04_fondo_fapi/relazione_beneficiario.txt" in names
    assert "Fondo: FAPI" in manifest
    acme_payroll = f"03_beneficiari/ACME_Srl/buste_paga/busta_{allievo_acme.id}.pdf"
    beta_payroll = f"03_beneficiari/BETA_Srl/buste_paga/busta_{allievo_beta.id}.pdf"
    assert acme_payroll in names
    assert beta_payroll in names
    assert f"03_beneficiari/ACME_Srl/buste_paga/busta_{allievo_beta.id}.pdf" not in names
    assert f"03_beneficiari/BETA_Srl/buste_paga/busta_{allievo_acme.id}.pdf" not in names
    assert all(not name.startswith("/") and ".." not in name.split("/") for name in names)


def test_componenti_zip_non_consentono_path_traversal():
    assert rendicontazione._safe_zip_component("../ACME\\evil") == "ACME_evil"


def test_fondo_legacy_resta_supportato_senza_fk(db_session):
    project = models.Project(
        name="Legacy",
        status="active",
        ente_erogatore="Formazienda",
    )
    db_session.add(project)
    db_session.commit()

    content, _ = rendicontazione.genera_pacchetto_rendicontazione(db_session, project.id)
    names, _ = _zip_names(content)

    assert "04_fondo_formazienda/formup/formup_4_rendiconto.txt" in names


@pytest.mark.parametrize("role,expected", [("admin", 200), ("operatore", 200), ("consultazione", 403)])
def test_endpoint_rbac_e_download(db_session, seeded_project, role, expected, monkeypatch):
    project, _, _ = seeded_project
    monkeypatch.setattr(auth, "RBAC_ENFORCE", True)

    def override_db():
        yield db_session

    def override_user():
        return type(
            "User",
            (),
            {"id": 1, "username": f"test-{role}", "role": role, "is_active": True},
        )()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    try:
        with TestClient(app) as client:
            response = client.post(f"/api/v1/reporting/projects/{project.id}/rendicontazione")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == expected
    if expected == 200:
        assert response.headers["content-type"] == "application/zip"
        assert "attachment;" in response.headers["content-disposition"]


def test_progetto_inesistente_404(db_session):
    with pytest.raises(ValueError, match="Progetto non trovato"):
        rendicontazione.genera_pacchetto_rendicontazione(db_session, 999_999)
