"""
E2E catena contratto: anagrafica -> progetto/assegnazione -> documenti
obbligatori -> upload+valida via API -> trigger reale contract_agent ->
accept umano -> GET generate_url -> PDF valido con dati del collaboratore.

Nessun mock del collector: il trigger e' quello reale
(POST /api/v1/documenti-richiesti/{id}/valida -> run_agent_workflow,
vedi routers/documenti_richiesti.py::_trigger_contract_agent_for_document).
"""
import io
import json
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from pdfminer.high_level import extract_text

from main import app
from database import Base, get_db
import auth
from auth import get_current_user, User
import file_upload
import models  # noqa: F401


def create_test_pdf_bytes() -> bytes:
    return b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /Resources 4 0 R /MediaBox [0 0 612 792] /Contents 5 0 R >>
endobj
4 0 obj
<< /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >>
endobj
5 0 obj
<< /Length 44 >>
stream
BT
/F1 12 Tf
100 700 Td
(Test Document) Tj
ET
endstream
endobj
xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000230 00000 n
0000000329 00000 n
trailer
<< /Size 6 /Root 1 0 R >>
startxref
423
%%EOF
"""


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


@pytest.fixture(scope="function")
def admin_user(db_session):
    user = User(
        username="admin_e2e",
        email="admin_e2e@example.com",
        hashed_password="x",
        role="admin",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def isolated_uploads(tmp_path, monkeypatch):
    upload_dir = tmp_path / "uploads"
    monkeypatch.setattr(file_upload, "UPLOAD_DIR", upload_dir)
    monkeypatch.setattr(file_upload, "DOCUMENTS_DIR", upload_dir / "documents")
    monkeypatch.setattr(file_upload, "CURRICULUM_DIR", upload_dir / "curriculum")
    monkeypatch.setattr(file_upload, "ENTITY_LOGOS_DIR", upload_dir / "entity_logos")
    file_upload.setup_upload_directories()
    return upload_dir


@pytest.fixture(scope="function")
def client(db_session, admin_user, isolated_uploads):
    def override_get_db():
        yield db_session

    def override_get_current_user():
        return admin_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _crea_template_contratto(db_session):
    """Template deterministico con i placeholder usati da genera_contratto
    (sprint7.py:214-240), cosi' l'estrazione testo del PDF e' garantita
    anche senza il fallback ContractGenerator.generate_contract."""
    template = models.ContractTemplate(
        nome_template="Template E2E Occasionale",
        tipo_contratto="occasionale",
        contenuto_html=(
            "<p>Incarico di «RUOLO_PROGETTUALE» conferito a «NOME» «COGNOME», "
            "codice fiscale «CODICE_FISCALE», per «ORE» ore complessive "
            "al costo unitario di «COSTO_UNITARIO» euro/ora.</p>"
        ),
        is_default=True,
        is_active=True,
    )
    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)
    return template


def _crea_catena_base(client):
    ente = client.post("/api/v1/entities/", json={
        "ragione_sociale": "Ente Attuatore E2E SRL",
        "partita_iva": "12345678901",
    })
    assert ente.status_code in (200, 201), ente.text
    ente = ente.json()

    collab = client.post("/api/v1/collaborators/", json={
        "first_name": "Mario",
        "last_name": "Rossi",
        "email": "mario.rossi.e2e@gmail.com",
        "fiscal_code": "RSSMRA80A01H501U",
    })
    assert collab.status_code in (200, 201), collab.text
    collab = collab.json()

    project = client.post("/api/v1/projects/", json={
        "name": "Progetto E2E Catena Contratto",
        "ente_attuatore_id": ente["id"],
    })
    assert project.status_code in (200, 201), project.text
    project = project.json()

    start_date = datetime.now()
    end_date = start_date + timedelta(days=90)
    assignment = client.post("/api/v1/assignments/", json={
        "collaborator_id": collab["id"],
        "project_id": project["id"],
        "role": "docenza",
        "assigned_hours": 40,
        "hourly_rate": 60.0,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "contract_type": "occasionale",
    })
    assert assignment.status_code in (200, 201), assignment.text
    assignment = assignment.json()

    return ente, collab, project, assignment


def test_catena_contratto_completa(client, db_session, admin_user):
    _crea_template_contratto(db_session)
    ente, collab, project, assignment = _crea_catena_base(client)

    # 3. documenti obbligatori
    doc_ids = []
    for tipo in ["documento_identita", "codice_fiscale"]:
        r = client.post("/api/v1/documenti-richiesti/", json={
            "collaboratore_id": collab["id"],
            "tipo_documento": tipo,
            "obbligatorio": True,
        })
        assert r.status_code == 201, r.text
        doc_ids.append(r.json()["id"])

    # 4. upload + valida come farebbe l'operatore
    for doc_id in doc_ids:
        up = client.post(
            f"/api/v1/documenti-richiesti/{doc_id}/upload",
            files={"file": ("doc.pdf", io.BytesIO(create_test_pdf_bytes()), "application/pdf")},
        )
        assert up.status_code == 200, up.text
        ok = client.post(
            f"/api/v1/documenti-richiesti/{doc_id}/valida",
            json={"validato_da": "admin_test"},
        )
        assert ok.status_code == 200, ok.text

    # 5. trigger REALE: la valida dell'ultimo doc ha lanciato contract_agent
    # (POST .../valida -> _trigger_contract_agent_for_document -> run_agent_workflow)
    pend = client.get("/api/v1/agents/suggestions/pending")
    assert pend.status_code == 200, pend.text
    pend = pend.json()
    contract = [
        s for s in pend
        if s["suggestion_type"] == "contract_ready" and s["entity_id"] == assignment["id"]
    ]
    assert len(contract) == 1, pend
    sugg = contract[0]
    payload = json.loads(sugg["payload"])
    assert payload["generate_url"] == f"/api/v1/assignments/{assignment['id']}/contract"

    # run tracciato (non chiamata diretta al collector)
    runs = client.get("/api/v1/agents/runs/", params={"agent_type": "contract_agent"})
    assert runs.status_code == 200, runs.text
    runs = runs.json()
    assert any(r["id"] == sugg["run_id"] for r in runs)

    # 6. apply umano
    acc = client.post(
        f"/api/v1/agents/suggestions/{sugg['id']}/accept",
        json={"action": "accepted", "reviewed_by_user_id": admin_user.id},
    )
    assert acc.status_code == 200, acc.text
    assert acc.json()["status"] == "approved"

    # 7. generazione dall'endpoint reale
    pdf = client.get(payload["generate_url"])
    assert pdf.status_code == 200, pdf.text
    assert pdf.headers["content-type"].startswith("application/pdf")
    assert pdf.content.startswith(b"%PDF")
    assert len(pdf.content) > 1000

    # 8. asserzioni finali sul contenuto: pdfminer estrae davvero il testo
    testo = extract_text(io.BytesIO(pdf.content))
    assert "Rossi" in testo and "Mario" in testo
    assert "docenza" in testo.lower()
    assert "40" in testo            # ore
    assert "60" in testo            # tariffa oraria

    # stato pratica coerente
    sugg_after = client.get(f"/api/v1/agents/suggestions/{sugg['id']}")
    assert sugg_after.status_code == 200, sugg_after.text
    sugg_after = sugg_after.json()
    assert sugg_after["status"] != "pending"
    # audit trail: run + review action registrati
    assert sugg_after["review_actions"], "review action assente"


def test_accept_diretto_idempotente_su_suggestion_gia_revisionata(client, db_session, admin_user):
    """NEW-023 (review R0 su E2.1, finding I-1): il ramo approve diretto per
    suggerimenti non-collaboratore non aveva guardia di stato — un doppio
    accept duplicava le AgentReviewAction e un accept su una suggestion
    'rejected' la riportava 'approved'. Il secondo accept deve rispondere 400
    lasciando stato e review_actions invariati."""
    _crea_template_contratto(db_session)
    ente, collab, project, assignment = _crea_catena_base(client)

    for tipo in ["documento_identita", "codice_fiscale"]:
        r = client.post("/api/v1/documenti-richiesti/", json={
            "collaboratore_id": collab["id"],
            "tipo_documento": tipo,
            "obbligatorio": True,
        })
        assert r.status_code == 201, r.text
        doc_id = r.json()["id"]
        up = client.post(
            f"/api/v1/documenti-richiesti/{doc_id}/upload",
            files={"file": ("doc.pdf", io.BytesIO(create_test_pdf_bytes()), "application/pdf")},
        )
        assert up.status_code == 200, up.text
        ok = client.post(
            f"/api/v1/documenti-richiesti/{doc_id}/valida",
            json={"validato_da": "admin_test"},
        )
        assert ok.status_code == 200, ok.text

    pend = client.get("/api/v1/agents/suggestions/pending").json()
    contract = [
        s for s in pend
        if s["suggestion_type"] == "contract_ready" and s["entity_id"] == assignment["id"]
    ]
    assert len(contract) == 1, pend
    sugg = contract[0]

    # primo accept: ok
    acc1 = client.post(
        f"/api/v1/agents/suggestions/{sugg['id']}/accept",
        json={"action": "accepted", "reviewed_by_user_id": admin_user.id},
    )
    assert acc1.status_code == 200, acc1.text
    assert acc1.json()["status"] == "approved"
    review_actions_dopo_primo = acc1.json()["review_actions"]
    assert len(review_actions_dopo_primo) == 1, review_actions_dopo_primo

    # secondo accept: 400, nessuna mutazione
    acc2 = client.post(
        f"/api/v1/agents/suggestions/{sugg['id']}/accept",
        json={"action": "accepted", "reviewed_by_user_id": admin_user.id},
    )
    assert acc2.status_code == 400, acc2.text
    assert "revisionat" in acc2.json()["detail"].lower()

    dopo = client.get(f"/api/v1/agents/suggestions/{sugg['id']}")
    assert dopo.status_code == 200, dopo.text
    dopo = dopo.json()
    assert dopo["status"] == "approved"
    assert len(dopo["review_actions"]) == len(review_actions_dopo_primo)


def _crea_doc_richiesto(client, collaboratore_id, tipo):
    r = client.post("/api/v1/documenti-richiesti/", json={
        "collaboratore_id": collaboratore_id,
        "tipo_documento": tipo,
        "obbligatorio": True,
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _upload_doc(client, doc_id, data_scadenza=None):
    data = {}
    if data_scadenza is not None:
        data["data_scadenza"] = data_scadenza
    up = client.post(
        f"/api/v1/documenti-richiesti/{doc_id}/upload",
        files={"file": ("doc.pdf", io.BytesIO(create_test_pdf_bytes()), "application/pdf")},
        data=data,
    )
    assert up.status_code == 200, up.text
    return up.json()


def _valida_doc(client, doc_id):
    ok = client.post(
        f"/api/v1/documenti-richiesti/{doc_id}/valida",
        json={"validato_da": "admin_test"},
    )
    assert ok.status_code == 200, ok.text
    return ok.json()


def _pending_contract_ready(client, assignment_id):
    pend = client.get("/api/v1/agents/suggestions/pending")
    assert pend.status_code == 200, pend.text
    return [
        s for s in pend.json()
        if s["suggestion_type"] == "contract_ready" and s["entity_id"] == assignment_id
    ]


def test_documento_mancante_nessuna_suggestion(client, db_session):
    """E2.2: doc obbligatorio mai caricato -> la valida degli altri non
    produce alcuna suggestion contract_ready per l'assignment."""
    _crea_template_contratto(db_session)
    ente, collab, project, assignment = _crea_catena_base(client)

    doc1 = _crea_doc_richiesto(client, collab["id"], "documento_identita")
    _crea_doc_richiesto(client, collab["id"], "codice_fiscale")  # mai caricato

    # upload + valida SOLO del primo: il trigger reale parte ma la pratica
    # e' incompleta.
    _upload_doc(client, doc1)
    _valida_doc(client, doc1)

    assert _pending_contract_ready(client, assignment["id"]) == []


def test_documento_non_validato_nessuna_suggestion(client, db_session):
    """E2.2: tutti i doc caricati ma nessuno validato (stato 'caricato') ->
    il run manuale reale dell'agente non produce suggestion contract_ready."""
    _crea_template_contratto(db_session)
    ente, collab, project, assignment = _crea_catena_base(client)

    for tipo in ["documento_identita", "codice_fiscale"]:
        doc_id = _crea_doc_richiesto(client, collab["id"], tipo)
        doc = _upload_doc(client, doc_id)
        assert doc["stato"] == "caricato", doc

    # nessuna valida => nessun trigger automatico: run manuale via endpoint
    # reale POST /api/v1/agents/{agent_type}/run (routers/agents.py).
    run = client.post("/api/v1/agents/contract_agent/run")
    assert run.status_code == 200, run.text
    run = run.json()
    assert run["status"] == "completed", run
    assert [
        s for s in run["suggestions"] if s["suggestion_type"] == "contract_ready"
    ] == []

    assert _pending_contract_ready(client, assignment["id"]) == []


def test_documento_scaduto_pratica_non_completa(client, db_session):
    """E2.2 / NEW-027: un documento obbligatorio validato ma con
    data_scadenza passata NON deve rendere completa la pratica: nessuna
    suggestion contract_ready deve essere proposta."""
    _crea_template_contratto(db_session)
    ente, collab, project, assignment = _crea_catena_base(client)

    scadenza_passata = (datetime.now() - timedelta(days=30)).isoformat()

    doc1 = _crea_doc_richiesto(client, collab["id"], "documento_identita")
    doc = _upload_doc(client, doc1, data_scadenza=scadenza_passata)
    assert doc["data_scadenza"] is not None, doc
    _valida_doc(client, doc1)

    doc2 = _crea_doc_richiesto(client, collab["id"], "codice_fiscale")
    _upload_doc(client, doc2)
    _valida_doc(client, doc2)  # trigger reale sull'ultima valida

    assert _pending_contract_ready(client, assignment["id"]) == [], (
        "Pratica considerata completa nonostante un documento obbligatorio "
        "sia scaduto (data_scadenza passata)"
    )


def test_contract_endpoint_richiede_autenticazione(client, db_session, admin_user):
    """RBAC: il download del contratto deve richiedere un utente autenticato
    (NEW-022: verifica che l'endpoint non sia accessibile senza credenziali)."""
    _crea_template_contratto(db_session)
    ente, collab, project, assignment = _crea_catena_base(client)

    # Rimuovo l'override di get_current_user per simulare una richiesta reale
    # senza token: se l'endpoint fosse privo di dipendenza auth, risponderebbe 200.
    del app.dependency_overrides[get_current_user]
    resp = client.get(f"/api/v1/assignments/{assignment['id']}/contract")

    assert resp.status_code in (401, 403), (
        f"Endpoint contratto raggiungibile senza autenticazione: {resp.status_code} {resp.text}"
    )


def test_contract_endpoint_nega_consultazione(client, db_session, monkeypatch):
    """RBAC: un utente 'consultazione' non deve poter scaricare il contratto
    firmato (contiene PII: codice fiscale, indirizzo, compenso).

    M-2 (review R0): l'enforcement non deve dipendere dall'env RBAC_ENFORCE
    del container — lo forziamo esplicitamente come in
    test_assignments_features.py."""
    monkeypatch.setattr(auth, "RBAC_ENFORCE", True)
    _crea_template_contratto(db_session)
    ente, collab, project, assignment = _crea_catena_base(client)

    consultazione_user = User(
        username="consultazione_e2e",
        email="consultazione_e2e@example.com",
        hashed_password="x",
        role="consultazione",
        is_active=True,
    )
    db_session.add(consultazione_user)
    db_session.commit()
    db_session.refresh(consultazione_user)

    app.dependency_overrides[get_current_user] = lambda: consultazione_user
    resp = client.get(f"/api/v1/assignments/{assignment['id']}/contract")

    assert resp.status_code == 403, f"Atteso 403 per ruolo consultazione, ottenuto {resp.status_code}: {resp.text}"
