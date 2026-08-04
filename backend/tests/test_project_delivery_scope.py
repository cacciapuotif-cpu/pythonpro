"""Contratto dello Step Delivery: convenzione, perimetro e caricamenti on-demand."""

from pathlib import Path
import sys
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).parent.parent))

from auth import get_current_user
from database import Base, get_db
from main import app
import models
from routers.convenzione_upload import _archivia_documento


@pytest.fixture
def db_session(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'project_delivery_scope.db'}",
        connect_args={"check_same_thread": False},
    )
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = testing_session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    def override_get_current_user():
        return type(
            "TestUser",
            (),
            {
                "id": 1,
                "username": "delivery-admin",
                "email": "delivery-admin@example.com",
                "role": "admin",
                "is_active": True,
            },
        )()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _add_project(db_session, name, ente, with_convenzione=True):
    project = models.Project(
        name=name,
        description="Progetto di test Delivery",
        status="active",
        ente_attuatore_id=ente.id if ente else None,
        data_approvazione=date(2026, 1, 10),
        data_avvio_piano=date(2026, 2, 1),
    )
    db_session.add(project)
    db_session.flush()
    if with_convenzione:
        db_session.add(models.ProjectDocumento(
            project_id=project.id,
            tipo_documento="convenzione",
            versione=1,
            file_path=f"/tmp/convenzione-{project.id}.pdf",
            file_name="convenzione.pdf",
            stato="corrente",
            source_removed=False,
        ))
    db_session.flush()
    return project


@pytest.fixture
def scenario(db_session):
    ente = models.ImplementingEntity(
        ragione_sociale="Ente da convenzione",
        partita_iva="80000000001",
        citta="Napoli",
    )
    altro_ente = models.ImplementingEntity(
        ragione_sociale="Ente estraneo",
        partita_iva="80000000002",
    )
    db_session.add_all([ente, altro_ente])
    db_session.flush()
    db_session.add(models.ImplementingEntityLocation(
        ente_id=ente.id,
        tipo="operativa",
        denominazione="Aula ente",
        citta="Napoli",
        is_active=True,
    ))

    project = _add_project(db_session, "Project in scope", ente, with_convenzione=True)
    no_convention = _add_project(db_session, "Project senza convenzione", ente, with_convenzione=False)
    other_project = _add_project(db_session, "Altro project", ente, with_convenzione=True)

    companies = [
        models.AziendaCliente(ragione_sociale="Alpha Uno Srl", partita_iva="10000000001"),
        models.AziendaCliente(ragione_sociale="Alpha Due Srl", partita_iva="10000000002"),
        models.AziendaCliente(ragione_sociale="Beta Tre Srl", partita_iva="10000000003"),
        models.AziendaCliente(ragione_sociale="Gamma Quattro Srl", partita_iva="10000000004"),
        models.AziendaCliente(ragione_sociale="Fuori Perimetro Srl", partita_iva="10000000005"),
    ]
    db_session.add_all(companies)
    db_session.flush()
    db_session.add_all([
        models.AziendaClienteProjectLink(project_id=project.id, azienda_cliente_id=company.id)
        for company in companies[:4]
    ])
    db_session.add(models.AziendaClienteProjectLink(
        project_id=other_project.id,
        azienda_cliente_id=companies[4].id,
    ))
    db_session.add(models.AziendaClienteProjectLink(
        project_id=no_convention.id,
        azienda_cliente_id=companies[0].id,
    ))
    db_session.add_all([
        models.Allievo(nome="Ada", cognome="Lovelace", azienda_cliente_id=companies[0].id),
        models.Allievo(nome="Grace", cognome="Hopper", azienda_cliente_id=companies[0].id),
        models.Allievo(nome="Edsger", cognome="Dijkstra", azienda_cliente_id=companies[4].id),
    ])
    db_session.commit()
    return {
        "ente": ente,
        "altro_ente": altro_ente,
        "project": project,
        "no_convention": no_convention,
        "other_project": other_project,
        "companies": companies,
    }


def test_atto_concessione_soddisfa_il_gate_al_pari_della_convenzione(client, db_session):
    ente = models.ImplementingEntity(ragione_sociale="Ente Formazienda", partita_iva="80000000009")
    db_session.add(ente)
    db_session.flush()
    project = models.Project(
        name="Piano Formazienda",
        ente_erogatore="Formazienda",
        ente_attuatore_id=ente.id,
        status="active",
        data_approvazione=date(2026, 1, 10),
        data_avvio_piano=date(2026, 2, 1),
    )
    db_session.add(project)
    db_session.flush()
    db_session.add(models.ProjectDocumento(
        project_id=project.id,
        tipo_documento="atto_concessione",
        versione=1,
        file_path="/tmp/atto-concessione.pdf",
        file_name="atto.pdf",
        stato="corrente",
        source_removed=False,
    ))
    db_session.commit()

    response = client.get(f"/api/v1/projects/{project.id}/delivery-context")
    assert response.status_code == 200, response.text
    assert response.json()["has_convenzione"] is True
    assert response.json()["blocked_reason"] is None


def test_delivery_context_deriva_ente_dalla_convenzione(client, scenario):
    response = client.get(f"/api/v1/projects/{scenario['project'].id}/delivery-context")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["has_convenzione"] is True
    assert body["blocked_reason"] is None
    assert body["ente_attuatore"]["id"] == scenario["ente"].id
    assert body["ente_attuatore"]["ragione_sociale"] == "Ente da convenzione"


def test_delivery_update_rifiuta_ente_diverso_dalla_convenzione(client, scenario):
    response = client.put(
        f"/api/v1/projects/{scenario['project'].id}",
        json={
            "ente_attuatore_id": scenario["altro_ente"].id,
            "azienda_ids": [scenario["companies"][0].id],
            "allievo_ids": [],
            "azienda_sedi": [],
        },
    )
    assert response.status_code == 422, response.text
    assert "non coerente con la convenzione" in response.json()["detail"]


def test_delivery_bloccata_senza_convenzione(client, scenario):
    context = client.get(
        f"/api/v1/projects/{scenario['no_convention'].id}/delivery-context"
    )
    assert context.status_code == 200, context.text
    assert context.json()["blocked_reason"] == "Collega prima la convenzione al progetto"
    assert context.json()["ente_attuatore"]["id"] == scenario["ente"].id

    listing = client.get(
        f"/api/v1/projects/{scenario['no_convention'].id}/delivery-companies"
    )
    assert listing.status_code == 422, listing.text
    assert listing.json()["detail"] == "Collega prima la convenzione al progetto"

    update = client.put(
        f"/api/v1/projects/{scenario['no_convention'].id}",
        json={
            "ente_attuatore_id": scenario["ente"].id,
            "azienda_ids": [scenario["companies"][0].id],
            "allievo_ids": [],
            "azienda_sedi": [],
        },
    )
    assert update.status_code == 422, update.text
    assert update.json()["detail"] == "Collega prima la convenzione al progetto"


def test_delivery_companies_esclude_fuori_perimetro_e_altro_progetto(client, scenario):
    response = client.get(
        f"/api/v1/projects/{scenario['project'].id}/delivery-companies"
    )
    assert response.status_code == 200, response.text
    ids = {item["id"] for item in response.json()["items"]}
    assert ids == {company.id for company in scenario["companies"][:4]}
    assert scenario["companies"][4].id not in ids


def test_delivery_companies_ricerca_e_paginazione_server_side(client, scenario):
    first = client.get(
        f"/api/v1/projects/{scenario['project'].id}/delivery-companies",
        params={"q": "Alpha", "limit": 1, "offset": 0},
    )
    assert first.status_code == 200, first.text
    assert first.json()["total"] == 2
    assert len(first.json()["items"]) == 1
    assert first.json()["has_more"] is True

    by_vat = client.get(
        f"/api/v1/projects/{scenario['project'].id}/delivery-companies",
        params={"q": "10000000003", "limit": 20, "offset": 0},
    )
    assert by_vat.status_code == 200, by_vat.text
    assert [item["ragione_sociale"] for item in by_vat.json()["items"]] == ["Beta Tre Srl"]


def test_delivery_company_payload_non_contiene_allievi_o_conteggi(client, scenario):
    response = client.get(
        f"/api/v1/projects/{scenario['project'].id}/delivery-companies",
        params={"limit": 20},
    )
    assert response.status_code == 200, response.text
    for item in response.json()["items"]:
        lowered_keys = {key.lower() for key in item}
        assert not any("alliev" in key for key in lowered_keys)
        assert not any("student" in key for key in lowered_keys)
        assert lowered_keys == {"id", "ragione_sociale", "partita_iva", "sedi_operative"}


def test_allievi_sono_on_demand_e_solo_per_azienda_in_perimetro(client, scenario):
    company = scenario["companies"][0]
    response = client.get(
        f"/api/v1/projects/{scenario['project'].id}/delivery-companies/{company.id}/students"
    )
    assert response.status_code == 200, response.text
    assert {item["nome"] for item in response.json()["items"]} == {"Ada", "Grace"}

    outside = client.get(
        f"/api/v1/projects/{scenario['project'].id}/delivery-companies/{scenario['companies'][4].id}/students"
    )
    assert outside.status_code == 404, outside.text


def test_scala_500_aziende_payload_dipende_solo_dal_perimetro(client, db_session):
    ente = models.ImplementingEntity(
        ragione_sociale="Ente scala",
        partita_iva="90000000001",
    )
    db_session.add(ente)
    db_session.flush()
    project = _add_project(db_session, "Project scala", ente, with_convenzione=True)
    in_scope = [models.AziendaCliente(ragione_sociale=f"Scope {index:03d}") for index in range(20)]
    db_session.add_all(in_scope)
    db_session.flush()
    db_session.add_all([
        models.AziendaClienteProjectLink(project_id=project.id, azienda_cliente_id=company.id)
        for company in in_scope
    ])
    db_session.commit()

    before = client.get(f"/api/v1/projects/{project.id}/delivery-companies")
    assert before.status_code == 200, before.text
    assert len(before.json()["items"]) == 20
    before_payload_size = len(before.content)

    outside = [models.AziendaCliente(ragione_sociale=f"Outside {index:03d}") for index in range(480)]
    db_session.add_all(outside)
    db_session.commit()

    after = client.get(f"/api/v1/projects/{project.id}/delivery-companies")
    assert after.status_code == 200, after.text
    assert len(after.json()["items"]) == 20
    assert after.json()["total"] == 20
    assert len(after.content) == before_payload_size


def test_formulario_non_sovrascrive_il_path_della_convenzione(db_session, scenario, tmp_path):
    project = scenario["project"]
    project.convenzione_file_path = "/uploads/convenzione-vera.pdf"
    formulario = tmp_path / "formulario.pdf"
    formulario.write_bytes(b"formulario")

    _archivia_documento(
        db_session,
        project=project,
        preview={"original_filename": "formulario.pdf", "mime_type": "application/pdf"},
        file_path=str(formulario),
        tipo_documento="formulario",
        current_user=type("TestUser", (), {"id": None})(),
    )

    assert project.convenzione_file_path == "/uploads/convenzione-vera.pdf"
    documento = db_session.query(models.ProjectDocumento).filter(
        models.ProjectDocumento.project_id == project.id,
        models.ProjectDocumento.tipo_documento == "formulario",
    ).one()
    assert documento.file_path == str(formulario)
