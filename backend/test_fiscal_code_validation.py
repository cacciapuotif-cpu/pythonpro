"""
TEST DI INTEGRAZIONE PER VALIDAZIONE CODICE FISCALE

Questi test verificano che:
1. Non sia possibile creare due collaboratori con lo stesso codice fiscale
2. Non sia possibile aggiornare un collaboratore con un CF già esistente
3. Il database blocchi inserimenti duplicati (constraint DB)
4. Le API restituiscano errori 409 con messaggi chiari in italiano

Questo previene data corruption e garantisce l'integrità dei dati.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from main import app
import models

# ====================
# SETUP DATABASE DI TEST
# ====================

# Database in memoria per i test (veloce, isolato, pulito ogni volta)
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Crea tutte le tabelle nel database di test
Base.metadata.create_all(bind=engine)


def override_get_db():
    """Override della dependency del database per usare il DB di test"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


# Sostituisci il database reale con quello di test
app.dependency_overrides[get_db] = override_get_db

# Client di test FastAPI
client = TestClient(app)


# ====================
# FIXTURES
# ====================

@pytest.fixture(autouse=True)
def clean_db():
    """Fixture che pulisce il database prima e dopo ogni test"""
    # Pulisci PRIMA del test
    db = TestingSessionLocal()
    try:
        db.query(models.Assignment).delete()
        db.query(models.Attendance).delete()
        db.query(models.Collaborator).delete()
        db.query(models.Project).delete()
        db.commit()
    finally:
        db.close()

    yield  # Esegui il test

    # Pulisci DOPO il test
    db = TestingSessionLocal()
    try:
        db.query(models.Assignment).delete()
        db.query(models.Attendance).delete()
        db.query(models.Collaborator).delete()
        db.query(models.Project).delete()
        db.commit()
    finally:
        db.close()


@pytest.fixture
def sample_collaborator_data():
    """Dati di esempio per un collaboratore valido"""
    return {
        "first_name": "Mario",
        "last_name": "Rossi",
        "email": "mario.rossi@example.com",
        "fiscal_code": "RSSMRA80A01H501Z",
        "phone": "333-123-4567",
        "position": "Sviluppatore",
        "birthplace": "Roma",
        "birth_date": "1980-01-01T00:00:00Z",
        "gender": "maschio",
        "city": "Roma",
        "address": "Via Roma 1",
        "education": "laurea"
    }


# ====================
# TEST CREAZIONE COLLABORATORI CON CF DUPLICATO
# ====================

def test_create_collaborator_success(sample_collaborator_data):
    """
    TEST 1: Verifica che la creazione di un collaboratore valido funzioni
    """
    response = client.post("/collaborators/", json=sample_collaborator_data)

    assert response.status_code == 200, f"Errore: {response.json()}"
    data = response.json()

    assert data["first_name"] == sample_collaborator_data["first_name"]
    assert data["last_name"] == sample_collaborator_data["last_name"]
    assert data["email"] == sample_collaborator_data["email"]
    assert data["fiscal_code"] == sample_collaborator_data["fiscal_code"]
    assert "id" in data
    print("✅ TEST 1 PASSED: Collaboratore creato correttamente")


def test_create_collaborator_duplicate_fiscal_code(sample_collaborator_data):
    """
    TEST 2: Verifica che non sia possibile creare due collaboratori con lo stesso CF

    Comportamento atteso:
    - Primo inserimento: SUCCESS (200)
    - Secondo inserimento (stesso CF): ERRORE 409 con messaggio chiaro
    """
    # PRIMO INSERIMENTO - deve funzionare
    response1 = client.post("/collaborators/", json=sample_collaborator_data)
    assert response1.status_code == 200, "Primo inserimento fallito"

    # SECONDO INSERIMENTO - stesso CF, email diversa - deve fallire
    duplicate_data = sample_collaborator_data.copy()
    duplicate_data["email"] = "altro.email@example.com"  # Email diversa
    duplicate_data["first_name"] = "Luigi"  # Nome diverso
    # Ma stesso CF!

    response2 = client.post("/collaborators/", json=duplicate_data)

    # Verifica errore 409 (Conflict)
    assert response2.status_code == 409, f"Atteso 409, ricevuto {response2.status_code}. Response: {response2.json()}"

    # Verifica messaggio d'errore in italiano
    response_json = response2.json()
    error_detail = response_json.get("detail", response_json.get("error", ""))
    assert error_detail, f"Nessun messaggio di errore trovato. Response completa: {response_json}"
    assert "codice fiscale" in error_detail.lower(), f"Messaggio errore non chiaro: '{error_detail}'"
    assert sample_collaborator_data["fiscal_code"].upper() in error_detail, "CF non menzionato nell'errore"

    print("✅ TEST 2 PASSED: Duplicato CF correttamente bloccato con errore 409")


def test_create_collaborator_duplicate_fiscal_code_case_insensitive(sample_collaborator_data):
    """
    TEST 3: Verifica che il controllo CF sia case-insensitive

    Comportamento atteso:
    - "RSSMRA80A01H501Z" e "rssmra80a01h501z" sono considerati duplicati
    """
    # PRIMO INSERIMENTO - CF uppercase
    response1 = client.post("/collaborators/", json=sample_collaborator_data)
    assert response1.status_code == 200

    # SECONDO INSERIMENTO - CF lowercase (ma stesso CF)
    duplicate_data = sample_collaborator_data.copy()
    duplicate_data["email"] = "altro@example.com"
    duplicate_data["fiscal_code"] = sample_collaborator_data["fiscal_code"].lower()

    response2 = client.post("/collaborators/", json=duplicate_data)

    # Deve fallire anche con lowercase
    assert response2.status_code == 409, "Case-insensitive check fallito"

    print("✅ TEST 3 PASSED: Case-insensitive CF check funziona")


# ====================
# TEST AGGIORNAMENTO COLLABORATORE CON CF DUPLICATO
# ====================

def test_update_collaborator_duplicate_fiscal_code():
    """
    TEST 4: Verifica che non sia possibile aggiornare un collaboratore
    con un CF già usato da un altro collaboratore
    """
    # Crea due collaboratori
    collab1_data = {
        "first_name": "Mario",
        "last_name": "Rossi",
        "email": "mario@example.com",
        "fiscal_code": "RSSMRA80A01H501Z",
    }
    collab2_data = {
        "first_name": "Luigi",
        "last_name": "Verdi",
        "email": "luigi@example.com",
        "fiscal_code": "VRDLGU85B02F205X",
    }

    resp1 = client.post("/collaborators/", json=collab1_data)
    resp2 = client.post("/collaborators/", json=collab2_data)

    assert resp1.status_code == 200
    assert resp2.status_code == 200

    collab1_id = resp1.json()["id"]
    collab2_id = resp2.json()["id"]

    # Prova ad aggiornare collab2 con il CF di collab1
    update_data = {"fiscal_code": collab1_data["fiscal_code"]}
    response = client.put(f"/collaborators/{collab2_id}", json=update_data)

    # Deve fallire con 409
    assert response.status_code == 409, f"Atteso 409, ricevuto {response.status_code}"

    # Verifica messaggio d'errore
    error_detail = response.json().get("detail", "")
    assert "codice fiscale" in error_detail.lower()

    print("✅ TEST 4 PASSED: Update con CF duplicato correttamente bloccato")


# ====================
# TEST VALIDAZIONE CAMPO CF OBBLIGATORIO
# ====================

def test_create_collaborator_missing_fiscal_code():
    """
    TEST 5: Verifica che il CF sia obbligatorio
    """
    data = {
        "first_name": "Test",
        "last_name": "User",
        "email": "test@example.com",
        # fiscal_code mancante!
    }

    response = client.post("/collaborators/", json=data)

    # Deve fallire con errore di validazione (422)
    assert response.status_code == 422, f"Atteso 422, ricevuto {response.status_code}"

    print("✅ TEST 5 PASSED: CF obbligatorio correttamente validato")


def test_create_collaborator_invalid_fiscal_code_length():
    """
    TEST 6: Verifica validazione lunghezza CF (deve essere 16 caratteri)
    """
    data = {
        "first_name": "Test",
        "last_name": "User",
        "email": "test@example.com",
        "fiscal_code": "TROPPOBREVE",  # Meno di 16 caratteri
    }

    response = client.post("/collaborators/", json=data)

    # Può fallire con 422 (validazione Pydantic) o 400 (validazione SQLAlchemy)
    assert response.status_code in [400, 422], f"Atteso 400/422, ricevuto {response.status_code}"

    print("✅ TEST 6 PASSED: Lunghezza CF validata")


# ====================
# ESEGUI TUTTI I TEST
# ====================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🧪 ESECUZIONE TEST VALIDAZIONE CODICE FISCALE")
    print("=" * 60 + "\n")

    # Esegui con pytest
    pytest.main([__file__, "-v", "-s"])
