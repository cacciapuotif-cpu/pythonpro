from io import BytesIO
from types import SimpleNamespace

import pdfplumber
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from reportlab import rl_config
from reportlab.pdfgen import canvas
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import file_upload
import models
import schemas
from auth import User, get_current_user
from contract_generator import ContractGenerator
from database import Base, get_db
from routers.implementing_entities import router
from routers.projects import router as projects_router
from routers.sprint7 import router as sprint7_router
from services.entity_printing import generate_print_preview, select_bank_account, select_location


@pytest.fixture()
def ux2_api():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = TestingSession()

    users = {
        role: User(
            username=f"ux2-{role}",
            email=f"ux2-{role}@example.com",
            hashed_password="not-used",
            full_name=f"UX2 {role}",
            role=role,
            is_active=True,
        )
        for role in ("admin", "operatore", "consultazione")
    }
    db.add_all(users.values())
    entity = models.ImplementingEntity(
        ragione_sociale="Ente UX2 Srl",
        partita_iva="12345678901",
        indirizzo="Via Storica 1",
        cap="80100",
        citta="Napoli",
        provincia="NA",
        nazione="IT",
        email="info@example.com",
    )
    db.add(entity)
    db.commit()
    for user in users.values():
        db.refresh(user)
    db.refresh(entity)

    role_state = {"role": "admin"}
    app = FastAPI()
    app.include_router(router)
    app.include_router(projects_router)
    app.include_router(sprint7_router)

    def override_db():
        yield db

    def override_user():
        return users[role_state["role"]]

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user

    with TestClient(app) as client:
        yield client, db, entity, role_state

    db.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_location_crud_and_unique_legal_primary_constraints(ux2_api):
    client, _, entity, _ = ux2_api
    legal = {
        "tipo": "legale",
        "denominazione": "Sede legale",
        "indirizzo": "Via Nuova 2",
        "cap": "80100",
        "citta": "Napoli",
        "provincia": "NA",
        "nazione": "IT",
        "is_principale": True,
        "is_active": True,
    }
    created = client.post(f"/api/v1/entities/{entity.id}/locations", json=legal)
    assert created.status_code == 201, created.text
    location_id = created.json()["id"]

    duplicate_legal = client.post(
        f"/api/v1/entities/{entity.id}/locations",
        json={**legal, "denominazione": "Seconda legale", "is_principale": False},
    )
    assert duplicate_legal.status_code == 409

    duplicate_primary = client.post(
        f"/api/v1/entities/{entity.id}/locations",
        json={**legal, "tipo": "operativa", "denominazione": "Operativa principale"},
    )
    assert duplicate_primary.status_code == 409

    updated = client.put(
        f"/api/v1/entities/{entity.id}/locations/{location_id}",
        json={"telefono": "+39 081 1234567"},
    )
    assert updated.status_code == 200
    assert updated.json()["telefono"] == "+39 081 1234567"

    accreditation_start = client.put(
        f"/api/v1/entities/{entity.id}/locations/{location_id}",
        json={"accreditamento_data": "2026-06-01"},
    )
    assert accreditation_start.status_code == 200
    invalid_partial_expiry = client.put(
        f"/api/v1/entities/{entity.id}/locations/{location_id}",
        json={"accreditamento_scadenza": "2026-05-31"},
    )
    assert invalid_partial_expiry.status_code == 422
    assert "precedere" in invalid_partial_expiry.json()["detail"]

    deactivated = client.delete(f"/api/v1/entities/{entity.id}/locations/{location_id}")
    assert deactivated.status_code == 200
    rows = client.get(f"/api/v1/entities/{entity.id}/locations").json()
    assert rows[0]["is_active"] is False
    assert rows[0]["dismessa_dal"] is not None


def test_account_crud_iban_validation_masking_role_and_audit(ux2_api):
    client, db, entity, role_state = ux2_api
    payload = {
        "banca": "West Bank",
        "agenzia": "London",
        "iban": "GB82 WEST 1234 5698 7654 32",
        "bic_swift": "DABAIE2D",
        "intestatario": "Ente UX2 Srl",
        "is_predefinito": True,
        "is_active": True,
    }
    created = client.post(f"/api/v1/entities/{entity.id}/accounts", json=payload)
    assert created.status_code == 201, created.text
    body = created.json()
    account_id = body["id"]
    assert body["iban"] is None
    assert body["iban_masked"].endswith("5432")
    assert "GB82WEST12345698765432" not in str(body)

    invalid = client.post(
        f"/api/v1/entities/{entity.id}/accounts",
        json={**payload, "iban": "IT00INVALID"},
    )
    assert invalid.status_code == 422

    duplicate_default = client.post(
        f"/api/v1/entities/{entity.id}/accounts",
        json={**payload, "iban": "DE89370400440532013000"},
    )
    assert duplicate_default.status_code == 409

    listed = client.get(f"/api/v1/entities/{entity.id}/accounts")
    assert listed.status_code == 200
    assert listed.json()[0]["iban"] is None
    detail = client.get(f"/api/v1/entities/{entity.id}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["conti_correnti"][0]["iban"] is None
    assert "GB82WEST12345698765432" not in detail.text
    entity_list = client.get("/api/v1/entities/")
    assert entity_list.status_code == 200
    assert "GB82WEST12345698765432" not in entity_list.text

    # Regressione sicurezza: il super-context progetti usava un serializer
    # diverso e poteva esporre sia l'IBAN legacy sia quello annidato.
    entity.iban = "GB82WEST12345698765432"
    project = models.Project(name="Progetto context UX2", status="active", ente_attuatore=entity)
    db.add(project)
    db.commit()
    db.refresh(project)
    role_state["role"] = "consultazione"
    full_context = client.get(f"/api/v1/projects/{project.id}/full-context")
    assert full_context.status_code == 200, full_context.text
    assert "GB82WEST12345698765432" not in full_context.text
    context_entity = full_context.json()["implementing_entity"]
    assert context_entity["iban"].endswith("5432")
    assert context_entity["conti_correnti"][0]["iban"] is None
    assert context_entity["conti_correnti"][0]["iban_masked"].endswith("5432")

    denied = client.get(f"/api/v1/entities/{entity.id}/accounts/{account_id}/iban")
    assert denied.status_code == 403

    role_state["role"] = "operatore"
    revealed = client.get(f"/api/v1/entities/{entity.id}/accounts/{account_id}/iban")
    assert revealed.status_code == 200
    assert revealed.json()["iban"] == "GB82WEST12345698765432"

    audit_rows = db.query(models.SecurityAuditLog).filter(
        models.SecurityAuditLog.azione == "iban_reveal"
    ).order_by(models.SecurityAuditLog.id).all()
    assert [row.esito for row in audit_rows] == ["denied", "success"]
    assert all("GB82WEST12345698765432" not in (row.dati_dopo or "") for row in audit_rows)

    role_state["role"] = "admin"
    updated = client.put(
        f"/api/v1/entities/{entity.id}/accounts/{account_id}",
        json={
            "note": "Conto fondi",
            "banca": "West Bank Europe",
            "bic_swift": "dabaie2d",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["note"] == "Conto fondi"
    assert updated.json()["bic_swift"] == "DABAIE2D"
    invalid_bic_update = client.put(
        f"/api/v1/entities/{entity.id}/accounts/{account_id}",
        json={"bic_swift": "INVALID!"},
    )
    assert invalid_bic_update.status_code == 422
    assert client.delete(f"/api/v1/entities/{entity.id}/accounts/{account_id}").status_code == 200


@pytest.mark.parametrize(
    "value,valid",
    [
        ("https://www.example.org", True),
        ("http://example.org/path", True),
        ("javascript:alert(1)", False),
        ("example.org", False),
    ],
)
def test_website_and_extensible_social_url_validation(value, valid):
    data = {
        "ragione_sociale": "Ente",
        "partita_iva": "12345678901",
        "sito_web": value,
        "social_links": [{"platform": "Mastodon", "url": value}],
    }
    if valid:
        model = schemas.ImplementingEntityCreate(**data)
        assert model.social_links[0].platform == "Mastodon"
    else:
        with pytest.raises(ValueError):
            schemas.ImplementingEntityCreate(**data)


def test_default_location_and_account_selection(ux2_api):
    _, db, entity, _ = ux2_api
    legal = models.ImplementingEntityLocation(
        ente_id=entity.id,
        tipo="legale",
        denominazione="Legale",
        is_active=True,
        is_principale=False,
    )
    operational = models.ImplementingEntityLocation(
        ente_id=entity.id,
        tipo="operativa",
        denominazione="Operativa",
        is_active=True,
        is_principale=True,
    )
    account = models.ImplementingEntityBankAccount(
        ente_id=entity.id,
        iban="DE89370400440532013000",
        intestatario="Ente UX2 Srl",
        is_predefinito=True,
        is_active=True,
    )
    db.add_all([legal, operational, account])
    db.commit()
    db.refresh(entity)
    assert select_location(entity).id == legal.id
    assert select_location(entity, operational.id).id == operational.id
    assert select_bank_account(entity).id == account.id


def test_existing_contract_pipeline_uses_selected_entity_location_and_account(ux2_api):
    client, db, entity, _ = ux2_api
    location = models.ImplementingEntityLocation(
        ente_id=entity.id,
        tipo="legale",
        denominazione="Sede Fondo Selezionata",
        indirizzo="Via Fondo 9",
        citta="Roma",
        nazione="IT",
        is_principale=True,
        is_active=True,
    )
    account = models.ImplementingEntityBankAccount(
        ente_id=entity.id,
        iban="DE89370400440532013000",
        intestatario="Ente UX2 Srl",
        is_predefinito=True,
        is_active=True,
    )
    collaborator = models.Collaborator(
        first_name="Ada",
        last_name="Lovelace",
        email="ada.ux2@example.com",
        fiscal_code="LVLDAX80A01H501Q",
    )
    project = models.Project(
        name="Progetto UX2",
        status="active",
        ente_attuatore=entity,
    )
    assignment = models.Assignment(
        collaborator=collaborator,
        project=project,
        role="Docente",
        assigned_hours=10,
        completed_hours=0,
        hourly_rate=50,
        start_date=__import__("datetime").datetime(2026, 1, 1),
        end_date=__import__("datetime").datetime(2026, 3, 31),
        contract_type="occasionale",
        is_active=True,
    )
    template = models.ContractTemplate(
        nome_template="UX2 route",
        tipo_contratto="occasionale",
        contenuto_html=(
            "<p>Sede: {{ ente_sede_denominazione }}</p>"
            "<p>Conto: {{ ente_conto_iban }}</p>"
        ),
        is_default=True,
        is_active=True,
    )
    db.add_all([location, account, collaborator, project, assignment, template])
    db.commit()
    db.refresh(location)
    db.refresh(account)
    db.refresh(assignment)

    response = client.get(
        f"/api/v1/assignments/{assignment.id}/contract",
        params={"sede_id": location.id, "conto_corrente_id": account.id},
    )
    assert response.status_code == 200, response.text
    with pdfplumber.open(BytesIO(response.content)) as document:
        text = "\n".join(page.extract_text() or "" for page in document.pages)
    assert "Sede Fondo Selezionata" in text
    assert "DE89370400440532013000" in text


def _reference_contract_data():
    return {
        "contract_type": "occasionale",
        "collaborator_name": "Mario Rossi",
        "collaborator_fiscal_code": "RSSMRA80A01F839X",
        "collaborator_birthplace": "Napoli",
        "collaborator_birthdate": "1980-01-01",
        "collaborator_address": "Via Roma 1, Napoli",
        "project_name": "Progetto riferimento",
        "role": "Docente",
        "assigned_hours": 10,
        "hourly_rate": 50,
        "start_date": "2026-01-01",
        "end_date": "2026-03-31",
        "ente_attuatore": "Ente riferimento",
        "ente_attuatore_piva": "12345678901",
        "ente_attuatore_indirizzo": "Via Ente 1",
    }


def test_empty_print_configuration_is_byte_identical_to_legacy_contract():
    previous_invariant = rl_config.invariant
    rl_config.invariant = 1
    try:
        legacy = ContractGenerator().generate_contract(_reference_contract_data()).getvalue()
        disabled = ContractGenerator().generate_contract(
            _reference_contract_data(),
            ente_print_config=SimpleNamespace(print_config_enabled=False),
        ).getvalue()
    finally:
        rl_config.invariant = previous_invariant
    assert disabled == legacy


def test_letterhead_and_footer_are_applied_to_generated_preview(tmp_path, monkeypatch):
    monkeypatch.setattr(file_upload, "UPLOAD_DIR", tmp_path)
    letterhead = tmp_path / "letterhead.png"
    Image.new("RGB", (595, 842), color=(235, 245, 255)).save(letterhead)
    entity = SimpleNamespace(
        ragione_sociale="Ente Preview",
        partita_iva="12345678901",
        indirizzo_completo="Via Preview 1",
        logo_path=None,
        letterhead_path="letterhead.png",
        print_margin_top_mm=28,
        print_margin_bottom_mm=22,
        print_margin_left_mm=18,
        print_margin_right_mm=18,
        print_logo_width_mm=40,
        print_logo_height_mm=20,
        print_logo_x_mm=20,
        print_logo_y_mm=8,
        print_letterhead_pages="all",
        print_footer="Piè di pagina UX-2",
    )
    pdf = generate_print_preview(entity).getvalue()
    assert pdf.startswith(b"%PDF-")
    with pdfplumber.open(BytesIO(pdf)) as document:
        text = "\n".join(page.extract_text() or "" for page in document.pages)
        assert len(document.pages) >= 2
        assert "Anteprima configurazione di stampa" in text
        assert "Piè di pagina UX-2" in text

    pdf_letterhead = tmp_path / "letterhead.pdf"
    background = canvas.Canvas(str(pdf_letterhead))
    background.setFillColorRGB(0.9, 0.95, 1)
    background.rect(0, 0, 595, 842, fill=1, stroke=0)
    background.save()
    entity.letterhead_path = "letterhead.pdf"
    pdf_background_preview = generate_print_preview(entity).getvalue()
    assert pdf_background_preview.startswith(b"%PDF-")
    with pdfplumber.open(BytesIO(pdf_background_preview)) as document:
        assert len(document.pages) >= 2


def test_svg_logo_is_rejected_before_it_can_break_pdf_rendering():
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"></svg>'
    assert ".svg" not in file_upload.ALLOWED_ENTITY_LOGO_EXTENSIONS
    assert not file_upload.validate_file_signature(
        "logo.svg",
        svg,
        file_upload.ALLOWED_ENTITY_LOGO_EXTENSIONS,
    )
