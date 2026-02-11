# Test suite per verificare i miglioramenti implementati
import pytest
import asyncio
import time
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

# Importa i moduli da testare
from main import app
from database import Base, get_db
from error_handler import ErrorHandler, GestionaleException, SafeTransaction
from validators import (
    InputSanitizer, EnhancedCollaboratorCreate,
    EnhancedProjectCreate, EnhancedAttendanceCreate
)
from backup_manager import BackupManager
from performance_monitor import PerformanceMonitor
import models
import crud

# Database di test in memoria
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_gestionale.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Setup test database
Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

class TestErrorHandling:
    """Test per il sistema di gestione errori"""

    def test_database_error_handling(self):
        """Test gestione errori database"""
        from sqlalchemy.exc import OperationalError

        # Simula errore operazionale database
        error = OperationalError("Connection failed", None, None)
        response = ErrorHandler.handle_database_error(error)

        assert response.status_code == 503
        assert "Database connection issues" in str(response.body) or "Service temporarily unavailable" in str(response.body)

    def test_safe_transaction(self):
        """Test transazioni sicure"""
        db = TestingSessionLocal()

        try:
            with SafeTransaction(db) as transaction:
                # Operazione che dovrebbe andare a buon fine
                collaborator_data = {
                    "first_name": "Test",
                    "last_name": "User",
                    "email": "test@example.com",
                    "phone": "1234567890"
                }

                collaborator = models.Collaborator(**collaborator_data)
                db.add(collaborator)
                transaction.commit()

                # Verifica che sia stato salvato
                saved = db.query(models.Collaborator).filter(
                    models.Collaborator.email == "test@example.com"
                ).first()
                assert saved is not None

        finally:
            # Cleanup
            db.query(models.Collaborator).filter(
                models.Collaborator.email == "test@example.com"
            ).delete()
            db.commit()
            db.close()

    def test_gestionale_exception(self):
        """Test eccezioni personalizzate"""
        exc = GestionaleException(
            "Test error",
            error_code="TEST_ERROR",
            details={"field": "test_field"}
        )

        assert exc.message == "Test error"
        assert exc.error_code == "TEST_ERROR"
        assert exc.details["field"] == "test_field"

class TestInputValidation:
    """Test per validazione e sanitizzazione input"""

    def test_string_sanitization(self):
        """Test sanitizzazione stringhe"""
        # Test rimozione HTML
        dirty_string = "<script>alert('xss')</script>Hello World"
        clean_string = InputSanitizer.sanitize_string(dirty_string)
        assert "<script>" not in clean_string
        assert "Hello World" in clean_string

        # Test limite lunghezza
        long_string = "a" * 300
        limited_string = InputSanitizer.sanitize_string(long_string, max_length=100)
        assert len(limited_string) == 100

    def test_email_validation(self):
        """Test validazione email"""
        # Email valida
        valid_email = InputSanitizer.sanitize_email("  Test@Example.COM  ")
        assert valid_email == "test@example.com"

        # Email invalida
        with pytest.raises(ValueError):
            InputSanitizer.sanitize_email("invalid-email")

    def test_phone_validation(self):
        """Test validazione telefono"""
        # Telefono valido
        valid_phone = InputSanitizer.sanitize_phone("+39 123 456 7890")
        assert valid_phone == "+39 123 456 7890"

        # Telefono con caratteri speciali
        cleaned_phone = InputSanitizer.sanitize_phone("123-456-7890 ext.123")
        assert "ext" not in cleaned_phone

    def test_fiscal_code_validation(self):
        """Test validazione codice fiscale"""
        # Codice fiscale valido
        valid_cf = InputSanitizer.sanitize_fiscal_code("rssmra85t10a562s")
        assert len(valid_cf) == 16
        assert valid_cf.isupper()

        # Codice fiscale invalido
        with pytest.raises(ValueError):
            InputSanitizer.sanitize_fiscal_code("invalid")

    def test_enhanced_collaborator_validation(self):
        """Test validazione collaboratore avanzata"""
        # Dati validi
        valid_data = {
            "first_name": "Mario",
            "last_name": "Rossi",
            "email": "mario.rossi@example.com",
            "phone": "+39 123 456 7890",
            "fiscal_code": "RSSMRA85T10A562S"
        }

        collaborator = EnhancedCollaboratorCreate(**valid_data)
        assert collaborator.first_name == "Mario"
        assert collaborator.email == "mario.rossi@example.com"

        # Email invalida
        with pytest.raises(ValueError):
            EnhancedCollaboratorCreate(**{**valid_data, "email": "invalid-email"})

class TestBackupSystem:
    """Test per sistema di backup"""

    def test_backup_creation(self):
        """Test creazione backup"""
        backup_mgr = BackupManager("./test_gestionale.db", "./test_backups")

        # Crea backup
        backup_path = backup_mgr.create_backup("test")
        assert backup_path is not None

        # Verifica esistenza file
        from pathlib import Path
        assert Path(backup_path).exists()

    def test_backup_listing(self):
        """Test lista backup"""
        backup_mgr = BackupManager("./test_gestionale.db", "./test_backups")

        # Crea alcuni backup
        backup_mgr.create_backup("test1")
        backup_mgr.create_backup("test2")

        # Lista backup
        backups = backup_mgr.list_backups()
        assert len(backups) >= 2

    def test_backup_verification(self):
        """Test verifica integrità backup"""
        backup_mgr = BackupManager("./test_gestionale.db", "./test_backups")

        # Crea backup
        backup_path = backup_mgr.create_backup("test_verify")
        assert backup_path is not None

        # Verifica integrità
        is_valid = backup_mgr.verify_backup_integrity(backup_path)
        assert is_valid

class TestPerformanceMonitoring:
    """Test per monitoraggio performance"""

    def test_performance_monitor_initialization(self):
        """Test inizializzazione monitor"""
        monitor = PerformanceMonitor()
        assert monitor.max_history == 1000
        assert len(monitor.metrics_history) == 0

    def test_request_recording(self):
        """Test registrazione richieste"""
        monitor = PerformanceMonitor()

        # Registra alcune richieste
        monitor.record_request("/test", "GET", 150.5, 200)
        monitor.record_request("/test", "POST", 250.0, 201)
        monitor.record_request("/error", "GET", 100.0, 500)

        # Verifica metriche endpoint
        endpoints = monitor.get_endpoint_metrics()
        assert len(endpoints) >= 2

        # Verifica conteggio errori
        assert monitor.error_count == 1

    def test_performance_metrics_collection(self):
        """Test raccolta metriche"""
        monitor = PerformanceMonitor()

        # Avvia monitoraggio per poco tempo
        monitor.start_monitoring(interval=1)
        time.sleep(2)
        monitor.stop_monitoring()

        # Verifica che abbia raccolto metriche
        current = monitor.get_current_metrics()
        assert "current" in current
        assert current["current"]["cpu_percent"] >= 0

class TestAPIEndpoints:
    """Test per endpoint API migliorati"""

    def test_create_collaborator_with_validation(self):
        """Test creazione collaboratore con validazione"""
        collaborator_data = {
            "first_name": "Mario",
            "last_name": "Rossi",
            "email": "mario.test@example.com",
            "phone": "+39 123 456 7890"
        }

        response = client.post("/collaborators/", json=collaborator_data)
        assert response.status_code == 200

        # Verifica dati salvati
        data = response.json()
        assert data["first_name"] == "Mario"
        assert data["email"] == "mario.test@example.com"

    def test_create_collaborator_duplicate_email(self):
        """Test prevenzione email duplicate"""
        collaborator_data = {
            "first_name": "Luigi",
            "last_name": "Verdi",
            "email": "mario.test@example.com",  # Email già usata nel test precedente
            "phone": "+39 987 654 3210"
        }

        response = client.post("/collaborators/", json=collaborator_data)
        assert response.status_code == 400

    def test_invalid_email_format(self):
        """Test email con formato invalido"""
        collaborator_data = {
            "first_name": "Test",
            "last_name": "User",
            "email": "invalid-email-format",
            "phone": "+39 123 456 7890"
        }

        response = client.post("/collaborators/", json=collaborator_data)
        assert response.status_code == 422  # Validation error

    def test_health_endpoint(self):
        """Test endpoint di health check"""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "timestamp" in data

class TestSystemIntegration:
    """Test di integrazione sistema completo"""

    def test_full_collaborator_lifecycle(self):
        """Test ciclo di vita completo collaboratore"""
        # 1. Crea collaboratore
        collaborator_data = {
            "first_name": "Integration",
            "last_name": "Test",
            "email": "integration.test@example.com",
            "phone": "+39 111 222 3333"
        }

        create_response = client.post("/collaborators/", json=collaborator_data)
        assert create_response.status_code == 200
        collaborator_id = create_response.json()["id"]

        # 2. Recupera collaboratore
        get_response = client.get(f"/collaborators/{collaborator_id}")
        assert get_response.status_code == 200
        assert get_response.json()["email"] == "integration.test@example.com"

        # 3. Aggiorna collaboratore
        update_data = {"phone": "+39 999 888 7777"}
        update_response = client.put(f"/collaborators/{collaborator_id}", json=update_data)
        assert update_response.status_code == 200
        assert update_response.json()["phone"] == "+39 999 888 7777"

        # 4. Elimina collaboratore (soft delete)
        delete_response = client.delete(f"/collaborators/{collaborator_id}")
        assert delete_response.status_code == 200

    def test_concurrent_requests(self):
        """Test gestione richieste concorrenti"""
        import threading
        import random

        results = []

        def create_collaborator(index):
            collaborator_data = {
                "first_name": f"Concurrent{index}",
                "last_name": "Test",
                "email": f"concurrent{index}@example.com",
                "phone": f"+39 {random.randint(100000000, 999999999)}"
            }

            response = client.post("/collaborators/", json=collaborator_data)
            results.append(response.status_code)

        # Crea 10 thread che fanno richieste simultanee
        threads = []
        for i in range(10):
            thread = threading.Thread(target=create_collaborator, args=(i,))
            threads.append(thread)
            thread.start()

        # Aspetta completamento
        for thread in threads:
            thread.join()

        # Verifica che la maggior parte delle richieste sia andata a buon fine
        success_count = len([r for r in results if r == 200])
        assert success_count >= 8  # Almeno 8 su 10 dovrebbero riuscire

def run_performance_test():
    """Test di performance e stress"""
    print("\\n=== PERFORMANCE TEST ===")

    start_time = time.time()

    # Test creazione multipla collaboratori
    for i in range(50):
        collaborator_data = {
            "first_name": f"Perf{i}",
            "last_name": "Test",
            "email": f"perf{i}@example.com",
            "phone": f"+39 {i:09d}"
        }

        response = client.post("/collaborators/", json=collaborator_data)
        if response.status_code != 200:
            print(f"Failed to create collaborator {i}: {response.status_code}")

    end_time = time.time()
    total_time = end_time - start_time

    print(f"Created 50 collaborators in {total_time:.2f} seconds")
    print(f"Average time per request: {(total_time/50)*1000:.2f}ms")

    # Test recupero multiplo
    start_time = time.time()

    for i in range(50):
        response = client.get("/collaborators/")
        if response.status_code != 200:
            print(f"Failed to get collaborators: {response.status_code}")

    end_time = time.time()
    total_time = end_time - start_time

    print(f"Retrieved collaborators 50 times in {total_time:.2f} seconds")
    print(f"Average time per request: {(total_time/50)*1000:.2f}ms")

if __name__ == "__main__":
    print("\\n🧪 AVVIO TEST SUITE MIGLIORAMENTI GESTIONALE")
    print("=" * 60)

    # Esegui test con pytest
    print("\\n1. Test Error Handling...")
    pytest.main(["-v", "-x", "test_improvements.py::TestErrorHandling"])

    print("\\n2. Test Input Validation...")
    pytest.main(["-v", "-x", "test_improvements.py::TestInputValidation"])

    print("\\n3. Test Backup System...")
    pytest.main(["-v", "-x", "test_improvements.py::TestBackupSystem"])

    print("\\n4. Test Performance Monitoring...")
    pytest.main(["-v", "-x", "test_improvements.py::TestPerformanceMonitoring"])

    print("\\n5. Test API Endpoints...")
    pytest.main(["-v", "-x", "test_improvements.py::TestAPIEndpoints"])

    print("\\n6. Test System Integration...")
    pytest.main(["-v", "-x", "test_improvements.py::TestSystemIntegration"])

    # Test di performance
    run_performance_test()

    print("\\n✅ TUTTI I TEST COMPLETATI")
    print("=" * 60)