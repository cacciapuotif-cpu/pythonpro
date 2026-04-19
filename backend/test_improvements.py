import sqlite3
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Column, Integer, Table, create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backup_manager import BackupManager
from database import Base, get_db
from error_handler import ErrorHandler, GestionaleException, SafeTransaction
from main import app
from validators import InputSanitizer, EnhancedCollaboratorCreate
import models  # noqa: F401

try:
    from performance_monitor import PerformanceMonitor
except ModuleNotFoundError:
    PerformanceMonitor = None


if "users" not in Base.metadata.tables:
    Table("users", Base.metadata, Column("id", Integer, primary_key=True))


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
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


class TestErrorHandling:
    def test_database_error_handling(self):
        error = OperationalError("Connection failed", None, None)
        response = ErrorHandler.handle_database_error(error)

        assert response.status_code == 503
        assert b"DB_UNAVAILABLE" in response.body

    def test_safe_transaction(self, db_session):
        with SafeTransaction(db_session) as transaction:
            collaborator = models.Collaborator(
                first_name="Test",
                last_name="User",
                email="safe.transaction@gmail.com",
                phone="1234567890",
                fiscal_code="TSTUSR80A01H501Z",
            )
            db_session.add(collaborator)
            transaction.commit()

        saved = db_session.query(models.Collaborator).filter(
            models.Collaborator.email == "safe.transaction@gmail.com"
        ).first()
        assert saved is not None

    def test_gestionale_exception(self):
        exc = GestionaleException(
            "Test error",
            error_code="TEST_ERROR",
            details={"field": "test_field"},
        )

        assert exc.message == "Test error"
        assert exc.error_code == "TEST_ERROR"
        assert exc.details["field"] == "test_field"


class TestInputValidation:
    def test_string_sanitization(self):
        dirty_string = "<script>alert('xss')</script>Hello World"
        clean_string = InputSanitizer.sanitize_string(dirty_string)
        assert "<script>" not in clean_string
        assert "Hello World" in clean_string

        long_string = "a" * 300
        limited_string = InputSanitizer.sanitize_string(long_string, max_length=100)
        assert len(limited_string) == 100

    def test_email_validation(self):
        valid_email = InputSanitizer.sanitize_email("mario.rossi@gmail.com")
        assert valid_email == "mario.rossi@gmail.com"

        with pytest.raises(ValueError):
            InputSanitizer.sanitize_email("invalid-email")

    def test_phone_validation(self):
        valid_phone = InputSanitizer.sanitize_phone("+39 123 456 7890")
        assert valid_phone == "+39 123 456 7890"

        cleaned_phone = InputSanitizer.sanitize_phone("123-456-7890 ext.123")
        assert "ext" not in cleaned_phone

    def test_fiscal_code_validation(self):
        valid_cf = InputSanitizer.sanitize_fiscal_code("rssmra85t10a562s")
        assert len(valid_cf) == 16
        assert valid_cf.isupper()

        with pytest.raises(ValueError):
            InputSanitizer.sanitize_fiscal_code("invalid")

    def test_enhanced_collaborator_validation(self):
        valid_data = {
            "first_name": "Mario",
            "last_name": "Rossi",
            "email": "mario.rossi@gmail.com",
            "phone": "+39 123 456 7890",
            "fiscal_code": "RSSMRA85T10A562S",
        }

        collaborator = EnhancedCollaboratorCreate(**valid_data)
        assert collaborator.first_name == "Mario"
        assert collaborator.email == "mario.rossi@gmail.com"

        with pytest.raises(ValueError):
            EnhancedCollaboratorCreate(**{**valid_data, "email": "invalid-email"})


class TestBackupSystem:
    def test_backup_creation_and_verification(self, tmp_path):
        db_path = tmp_path / "test_gestionale.db"
        backup_dir = tmp_path / "test_backups"

        with sqlite3.connect(db_path) as conn:
            conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, name TEXT)")
            conn.execute("INSERT INTO sample (name) VALUES ('alpha')")
            conn.commit()

        backup_mgr = BackupManager(str(db_path), str(backup_dir))
        backup_path = backup_mgr.create_backup("test")

        assert backup_path is not None
        assert Path(backup_path).exists()
        assert zipfile.is_zipfile(backup_path)
        assert backup_mgr.verify_backup_integrity(backup_path) is True

    def test_backup_listing(self, tmp_path):
        db_path = tmp_path / "test_gestionale.db"
        backup_dir = tmp_path / "test_backups"

        with sqlite3.connect(db_path) as conn:
            conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, name TEXT)")
            conn.commit()

        backup_mgr = BackupManager(str(db_path), str(backup_dir))
        assert backup_mgr.create_backup("test1") is not None
        assert backup_mgr.create_backup("test2") is not None

        backups = backup_mgr.list_backups()
        assert len(backups) >= 2


@pytest.mark.skipif(PerformanceMonitor is None, reason="psutil/performance monitor non disponibile nel container")
class TestPerformanceMonitoring:
    def test_performance_monitor_initialization(self):
        monitor = PerformanceMonitor()
        assert monitor.max_history == 1000
        assert len(monitor.metrics_history) == 0

    def test_request_recording(self):
        monitor = PerformanceMonitor()
        monitor.record_request("/test", "GET", 150.5, 200)
        monitor.record_request("/test", "POST", 250.0, 201)
        monitor.record_request("/error", "GET", 100.0, 500)

        endpoints = monitor.get_endpoint_metrics()
        assert len(endpoints) >= 2
        assert monitor.error_count == 1


class TestAPIEndpoints:
    def test_create_collaborator_with_validation(self, client):
        collaborator_data = {
            "first_name": "Mario",
            "last_name": "Rossi",
            "email": "mario.test@gmail.com",
            "phone": "+39 123 456 7890",
            "fiscal_code": "RSSMRA80A01H501Z",
        }

        response = client.post("/api/v1/collaborators/", json=collaborator_data)
        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "Mario"
        assert data["email"] == "mario.test@gmail.com"

    def test_create_collaborator_duplicate_email(self, client):
        collaborator_data = {
            "first_name": "Luigi",
            "last_name": "Verdi",
            "email": "dupe.test@gmail.com",
            "phone": "+39 987 654 3210",
            "fiscal_code": "VRDLGU80A01H501Z",
        }
        first = client.post("/api/v1/collaborators/", json=collaborator_data)
        assert first.status_code == 200

        duplicate = {
            **collaborator_data,
            "fiscal_code": "VRDLGU80A01H501X",
        }
        response = client.post("/api/v1/collaborators/", json=duplicate)
        assert response.status_code == 409

    def test_invalid_email_format(self, client):
        collaborator_data = {
            "first_name": "Test",
            "last_name": "User",
            "email": "invalid-email-format",
            "phone": "+39 123 456 7890",
            "fiscal_code": "TSTUSR80A01H501Z",
        }

        response = client.post("/api/v1/collaborators/", json=collaborator_data)
        assert response.status_code == 422

    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data


class TestSystemIntegration:
    def test_full_collaborator_lifecycle(self, client):
        collaborator_data = {
            "first_name": "Integration",
            "last_name": "Test",
            "email": "integration.test@gmail.com",
            "phone": "+39 111 222 3333",
            "fiscal_code": "NTGTST80A01H501Z",
        }

        create_response = client.post("/api/v1/collaborators/", json=collaborator_data)
        assert create_response.status_code == 200
        collaborator_id = create_response.json()["id"]

        get_response = client.get(f"/api/v1/collaborators/{collaborator_id}")
        assert get_response.status_code == 200
        assert get_response.json()["email"] == "integration.test@gmail.com"

        update_data = {"phone": "+39 999 888 7777"}
        update_response = client.put(f"/api/v1/collaborators/{collaborator_id}", json=update_data)
        assert update_response.status_code == 200
        assert update_response.json()["phone"] == "+39 999 888 7777"

        delete_response = client.delete(f"/api/v1/collaborators/{collaborator_id}")
        assert delete_response.status_code == 200

        active_list = client.get("/api/v1/collaborators/?active_only=true")
        assert active_list.status_code == 200
        assert active_list.json() == []
