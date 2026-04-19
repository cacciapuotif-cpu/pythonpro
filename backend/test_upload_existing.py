import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Column, Integer, Table, create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from main import app
import file_upload
import models  # noqa: F401


if "users" not in Base.metadata.tables:
    Table("users", Base.metadata, Column("id", Integer, primary_key=True))


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
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


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
def client(db_session, isolated_uploads):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def existing_collaborator(client):
    collaborator_data = {
        "first_name": "Existing",
        "last_name": "User",
        "email": "existing.upload@gmail.com",
        "phone": "333-999-1111",
        "position": "Developer",
        "fiscal_code": "XSTUSR80A01H501Z",
    }
    response = client.post("/api/v1/collaborators/", json=collaborator_data)
    assert response.status_code == 200, response.text
    return response.json()


def test_upload_existing_collaborator_workflow(client, existing_collaborator):
    collaborator_id = existing_collaborator["id"]

    files = {
        "file": ("documento_test.pdf", io.BytesIO(create_test_pdf_bytes()), "application/pdf")
    }
    response = client.post(f"/api/v1/collaborators/{collaborator_id}/upload-documento", files=files)
    assert response.status_code == 200, response.text
    assert response.json()["filename"] == "documento_test.pdf"

    files = {
        "file": ("curriculum_test.pdf", io.BytesIO(create_test_pdf_bytes()), "application/pdf")
    }
    response = client.post(f"/api/v1/collaborators/{collaborator_id}/upload-curriculum", files=files)
    assert response.status_code == 200, response.text
    assert response.json()["filename"] == "curriculum_test.pdf"

    response = client.get(f"/api/v1/collaborators/{collaborator_id}")
    assert response.status_code == 200
    collaborator = response.json()
    assert collaborator["documento_identita_filename"] == "documento_test.pdf"
    assert collaborator["curriculum_filename"] == "curriculum_test.pdf"

    response = client.get(f"/api/v1/collaborators/{collaborator_id}/download-documento")
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF-1.4")

    response = client.get(f"/api/v1/collaborators/{collaborator_id}/download-curriculum")
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF-1.4")

    response = client.delete(f"/api/v1/collaborators/{collaborator_id}/delete-documento")
    assert response.status_code == 200

    response = client.delete(f"/api/v1/collaborators/{collaborator_id}/delete-curriculum")
    assert response.status_code == 200

    response = client.get(f"/api/v1/collaborators/{collaborator_id}")
    assert response.status_code == 200
    collaborator = response.json()
    assert collaborator["documento_identita_filename"] is None
    assert collaborator["curriculum_filename"] is None
