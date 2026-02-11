# =================================================================
# FILE: test_main.py
# =================================================================
# SCOPO: Unit tests per API endpoints del gestionale
#
# Questo file contiene test automatizzati per verificare:
# - Funzionamento corretto degli endpoints API
# - Validazione dati in input
# - Gestione errori (4xx, 5xx)
# - Integrazione database
# - Business logic
#
# ESECUZIONE TESTS:
#   pytest test_main.py -v                    # Verbose output
#   pytest test_main.py --cov=.               # Con coverage
#   pytest test_main.py -k "test_collaborator" # Solo test specifici
# =================================================================

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, date

# Import app e dipendenze
from main import app
from database import Base, get_db
import models

# =================================================================
# SETUP DATABASE DI TEST
# =================================================================
# Usa database in-memory SQLite per test isolati e veloci
# Ogni test riceve un database pulito
# =================================================================

# URL database di test (in-memory, non tocca dati produzione)
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

# Crea engine per database test
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}  # SQLite multithread
)

# Session factory per test
TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


# =================================================================
# FIXTURES PYTEST
# =================================================================
# Fixtures sono funzioni che forniscono dati/setup per i test
# Eseguite automaticamente prima di ogni test che le richiede
# =================================================================

@pytest.fixture(scope="function")
def db_session():
    """
    Fixture che fornisce una sessione database pulita per ogni test.

    SCOPE: function = eseguita prima di OGNI test

    FLUSSO:
    1. Crea tutte le tabelle nel DB test
    2. Yield sessione al test
    3. Test esegue
    4. Rollback e chiusura sessione
    5. Drop tutte le tabelle (cleanup)

    IMPORTANTE: Ogni test ha DB isolato, nessuna interferenza tra test
    """
    # Setup: crea tabelle
    Base.metadata.create_all(bind=engine)

    # Crea sessione
    session = TestingSessionLocal()

    try:
        # Yield sessione al test
        yield session
    finally:
        # Teardown: cleanup dopo test
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """
    Fixture che fornisce TestClient FastAPI con DB mockato.

    TestClient permette di fare richieste HTTP simulate all'app
    senza avviare server reale.

    DEPENDENCY OVERRIDE:
    - app.dependency_overrides sostituisce get_db reale con DB test
    - Così tutti gli endpoint usano il database di test
    """
    # Override dependency: usa DB test invece di DB reale
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    # Crea client per fare richieste HTTP
    with TestClient(app) as test_client:
        yield test_client

    # Cleanup: rimuovi override
    app.dependency_overrides.clear()


# =================================================================
# FIXTURES DATI DI TEST
# =================================================================
# Fixtures che creano dati sample nel DB per i test
# =================================================================

@pytest.fixture
def sample_collaborator(db_session):
    """
    Crea un collaboratore di test nel database.

    RETURNS: dict con dati collaboratore creato
    """
    collaborator = models.Collaborator(
        first_name="Mario",
        last_name="Rossi",
        email="mario.rossi@test.com",
        phone="1234567890",
        position="Developer"
    )
    db_session.add(collaborator)
    db_session.commit()
    db_session.refresh(collaborator)

    return {
        "id": collaborator.id,
        "first_name": collaborator.first_name,
        "last_name": collaborator.last_name,
        "email": collaborator.email
    }


@pytest.fixture
def sample_project(db_session):
    """
    Crea un progetto di test nel database.

    RETURNS: dict con dati progetto creato
    """
    project = models.Project(
        name="Test Project",
        description="A test project for unit tests",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        status="active"
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    return {
        "id": project.id,
        "name": project.name,
        "status": project.status
    }


# =================================================================
# TEST SUITE: COLLABORATORI
# =================================================================

class TestCollaborators:
    """
    Test suite per endpoint /collaborators/

    Testa:
    - CREATE (POST)
    - READ (GET all, GET one)
    - UPDATE (PUT)
    - DELETE (DELETE)
    """

    def test_create_collaborator_success(self, client):
        """
        Test: Creazione collaboratore con dati validi

        GIVEN: Dati collaboratore validi
        WHEN: POST /collaborators/
        THEN: Status 201, collaboratore creato con ID
        """
        # Arrange: prepara dati
        payload = {
            "first_name": "Luigi",
            "last_name": "Verdi",
            "email": "luigi.verdi@test.com",
            "phone": "0987654321",
            "position": "Designer"
        }

        # Act: esegui richiesta
        response = client.post("/collaborators/", json=payload)

        # Assert: verifica risultato
        assert response.status_code == 201, f"Expected 201, got {response.status_code}"

        data = response.json()
        assert "id" in data, "Response should contain 'id' field"
        assert data["first_name"] == "Luigi"
        assert data["last_name"] == "Verdi"
        assert data["email"] == "luigi.verdi@test.com"


    def test_create_collaborator_duplicate_email(self, client, sample_collaborator):
        """
        Test: Creazione collaboratore con email duplicata

        GIVEN: Collaboratore esistente con email mario.rossi@test.com
        WHEN: POST /collaborators/ con stessa email
        THEN: Status 400, errore validazione
        """
        # Arrange: usa email già esistente (da fixture)
        payload = {
            "first_name": "Mario",
            "last_name": "Bianchi",
            "email": sample_collaborator["email"],  # Email duplicata!
            "phone": "1111111111",
            "position": "Manager"
        }

        # Act
        response = client.post("/collaborators/", json=payload)

        # Assert: dovrebbe fallire
        assert response.status_code == 400, "Duplicate email should return 400"
        assert "email" in response.json()["error"].lower() or "registrata" in response.json()["error"].lower()


    def test_get_collaborators_empty(self, client):
        """
        Test: GET lista collaboratori quando DB vuoto

        GIVEN: Database vuoto
        WHEN: GET /collaborators/
        THEN: Status 200, lista vuota []
        """
        response = client.get("/collaborators/")

        assert response.status_code == 200
        assert response.json() == [], "Empty database should return empty list"


    def test_get_collaborators_with_data(self, client, sample_collaborator):
        """
        Test: GET lista collaboratori con dati presenti

        GIVEN: 1 collaboratore nel database
        WHEN: GET /collaborators/
        THEN: Status 200, lista con 1 elemento
        """
        response = client.get("/collaborators/")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1, "Should return 1 collaborator"
        assert data[0]["email"] == sample_collaborator["email"]


    def test_get_collaborator_by_id_success(self, client, sample_collaborator):
        """
        Test: GET collaboratore specifico per ID

        GIVEN: Collaboratore con ID=1
        WHEN: GET /collaborators/1
        THEN: Status 200, dettagli collaboratore
        """
        collab_id = sample_collaborator["id"]
        response = client.get(f"/collaborators/{collab_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == collab_id
        assert data["first_name"] == sample_collaborator["first_name"]


    def test_get_collaborator_by_id_not_found(self, client):
        """
        Test: GET collaboratore con ID inesistente

        GIVEN: Database vuoto
        WHEN: GET /collaborators/9999
        THEN: Status 404
        """
        response = client.get("/collaborators/9999")

        assert response.status_code == 404
        assert "non trovato" in response.json()["detail"].lower()


    def test_update_collaborator_success(self, client, sample_collaborator):
        """
        Test: UPDATE collaboratore esistente

        GIVEN: Collaboratore esistente
        WHEN: PUT /collaborators/{id} con nuovi dati
        THEN: Status 200, dati aggiornati
        """
        collab_id = sample_collaborator["id"]
        update_payload = {
            "first_name": "Mario",
            "last_name": "Rossi Aggiornato",
            "position": "Senior Developer"
        }

        response = client.put(f"/collaborators/{collab_id}", json=update_payload)

        assert response.status_code == 200
        data = response.json()
        assert data["last_name"] == "Rossi Aggiornato"
        assert data["position"] == "Senior Developer"


    def test_delete_collaborator_success(self, client, sample_collaborator):
        """
        Test: DELETE collaboratore esistente

        GIVEN: Collaboratore esistente
        WHEN: DELETE /collaborators/{id}
        THEN: Status 200, collaboratore eliminato
        """
        collab_id = sample_collaborator["id"]

        # Delete
        response = client.delete(f"/collaborators/{collab_id}")
        assert response.status_code == 200

        # Verifica eliminazione: GET dovrebbe restituire 404
        get_response = client.get(f"/collaborators/{collab_id}")
        assert get_response.status_code == 404


# =================================================================
# TEST SUITE: PROGETTI
# =================================================================

class TestProjects:
    """
    Test suite per endpoint /projects/
    """

    def test_create_project_success(self, client):
        """
        Test: Creazione progetto con dati validi
        """
        payload = {
            "name": "Nuovo Progetto",
            "description": "Descrizione test",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "status": "active"
        }

        response = client.post("/projects/", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Nuovo Progetto"
        assert data["status"] == "active"


    def test_get_projects(self, client, sample_project):
        """
        Test: GET lista progetti
        """
        response = client.get("/projects/")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == sample_project["name"]


# =================================================================
# TEST SUITE: HEALTH E SISTEMA
# =================================================================

class TestSystem:
    """
    Test suite per endpoint di sistema e monitoring
    """

    def test_health_check(self, client):
        """
        Test: Health check endpoint

        GIVEN: Sistema attivo
        WHEN: GET /health
        THEN: Status 200, risposta con "healthy"
        """
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "database" in data


    def test_root_endpoint(self, client):
        """
        Test: Root endpoint /

        GIVEN: App avviata
        WHEN: GET /
        THEN: Status 200, messaggio di benvenuto
        """
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "online"


# =================================================================
# TEST SUITE: VALIDAZIONE INPUT
# =================================================================

class TestValidation:
    """
    Test suite per validazione dati in input (Pydantic)
    """

    def test_collaborator_invalid_email(self, client):
        """
        Test: Email non valida

        GIVEN: Payload con email malformata
        WHEN: POST /collaborators/
        THEN: Status 422 (Unprocessable Entity)
        """
        payload = {
            "first_name": "Test",
            "last_name": "User",
            "email": "not-an-email",  # Email invalida!
            "phone": "1234567890",
            "position": "Tester"
        }

        response = client.post("/collaborators/", json=payload)

        assert response.status_code == 422, "Invalid email should return 422"


    def test_collaborator_missing_required_field(self, client):
        """
        Test: Campo obbligatorio mancante

        GIVEN: Payload senza campo required (first_name)
        WHEN: POST /collaborators/
        THEN: Status 422
        """
        payload = {
            # "first_name": "Test",  # Mancante!
            "last_name": "User",
            "email": "test@test.com",
            "phone": "1234567890",
            "position": "Tester"
        }

        response = client.post("/collaborators/", json=payload)

        assert response.status_code == 422
        # Verifica che errore menzioni il campo mancante
        error_detail = str(response.json())
        assert "first_name" in error_detail.lower()


# =================================================================
# TEST SUITE: INTEGRAZIONE (CRUD COMPLETO)
# =================================================================

class TestIntegration:
    """
    Test di integrazione che verificano flussi completi
    """

    def test_full_crud_workflow(self, client):
        """
        Test integrazione: Workflow CRUD completo

        Simula caso d'uso reale:
        1. Crea collaboratore
        2. Leggi collaboratore
        3. Aggiorna collaboratore
        4. Elimina collaboratore
        5. Verifica eliminazione
        """
        # 1. CREATE
        create_payload = {
            "first_name": "Integration",
            "last_name": "Test",
            "email": "integration@test.com",
            "phone": "5555555555",
            "position": "QA"
        }
        create_response = client.post("/collaborators/", json=create_payload)
        assert create_response.status_code == 201
        collab_id = create_response.json()["id"]

        # 2. READ
        read_response = client.get(f"/collaborators/{collab_id}")
        assert read_response.status_code == 200
        assert read_response.json()["email"] == "integration@test.com"

        # 3. UPDATE
        update_payload = {"position": "Senior QA"}
        update_response = client.put(f"/collaborators/{collab_id}", json=update_payload)
        assert update_response.status_code == 200
        assert update_response.json()["position"] == "Senior QA"

        # 4. DELETE
        delete_response = client.delete(f"/collaborators/{collab_id}")
        assert delete_response.status_code == 200

        # 5. VERIFY DELETION
        verify_response = client.get(f"/collaborators/{collab_id}")
        assert verify_response.status_code == 404


# =================================================================
# TEST RUNNER CONFIGURATION
# =================================================================

if __name__ == "__main__":
    """
    Permette esecuzione diretta: python test_main.py

    Ma preferibile usare pytest da CLI per più opzioni
    """
    pytest.main([__file__, "-v", "--tb=short"])


# =================================================================
# NOTE PER ESECUZIONE
# =================================================================
"""
COMANDI UTILI:

# Esegui tutti i test
pytest test_main.py -v

# Esegui solo test che matchano pattern
pytest test_main.py -k "collaborator" -v

# Esegui con coverage report
pytest test_main.py --cov=. --cov-report=html

# Esegui in parallelo (richiede pytest-xdist)
pytest test_main.py -n auto

# Stop al primo fallimento
pytest test_main.py -x

# Mostra print statements
pytest test_main.py -s

# Report dettagliato errori
pytest test_main.py -vv --tb=long

OUTPUT ATTESO:
test_main.py::TestCollaborators::test_create_collaborator_success PASSED
test_main.py::TestCollaborators::test_create_collaborator_duplicate_email PASSED
test_main.py::TestCollaborators::test_get_collaborators_empty PASSED
...
==================== X passed in Y.YYs ====================
"""
