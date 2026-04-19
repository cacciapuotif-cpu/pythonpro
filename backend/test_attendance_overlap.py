"""
Test per validazione sovrapposizioni orarie nelle presenze.

Verifica che un collaboratore non possa essere presente contemporaneamente:
1. Con due mansioni sullo stesso progetto
2. Con due progetti diversi

Un collaboratore può essere presente UNA SOLA VOLTA in un determinato orario.
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, Integer
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from database import Base
import models
import crud
import schemas

# Setup database di test in memoria
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


if "users" not in Base.metadata.tables:
    # Placeholder minimo per FK legacy presenti in metadata ma irrilevanti per questi test.
    from sqlalchemy import Table

    Table("users", Base.metadata, Column("id", Integer, primary_key=True))

def setup_test_db():
    """Crea database di test e dati iniziali"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    # Crea collaboratore di test
    collaborator = models.Collaborator(
        first_name="Mario",
        last_name="Rossi",
        email="mario.rossi@gmail.com",
        fiscal_code="RSSMRA80A01H501U",
        phone="1234567890",
        position="Sviluppatore"
    )
    db.add(collaborator)

    # Crea due progetti di test
    project1 = models.Project(
        name="Progetto A",
        description="Primo progetto di test",
        status="active"
    )
    project2 = models.Project(
        name="Progetto B",
        description="Secondo progetto di test",
        status="active"
    )
    db.add(project1)
    db.add(project2)

    db.commit()
    db.refresh(collaborator)
    db.refresh(project1)
    db.refresh(project2)

    return db, collaborator, project1, project2

def teardown_test_db(db):
    """Pulisce database di test"""
    db.close()
    Base.metadata.drop_all(bind=engine)

def test_sovrapposizione_stesso_progetto():
    """Test: Non può esserci sovrapposizione sullo stesso progetto"""
    db, collaborator, project1, project2 = setup_test_db()

    try:
        # Crea prima presenza: 09:00 - 13:00 su Progetto A
        attendance1_data = schemas.AttendanceCreate(
            collaborator_id=collaborator.id,
            project_id=project1.id,
            date=datetime(2024, 1, 15, 9, 0),
            start_time=datetime(2024, 1, 15, 9, 0),
            end_time=datetime(2024, 1, 15, 13, 0),
            hours=4.0
        )
        attendance1 = crud.create_attendance(db, attendance1_data)
        assert attendance1.id is not None
        print(f"[OK] Prima presenza creata: {attendance1.start_time} - {attendance1.end_time}")

        # Tentativo di creare seconda presenza sovrapposta: 10:00 - 14:00 su Progetto A
        # Dovrebbe fallire perché si sovrappone con la prima
        attendance2_data = schemas.AttendanceCreate(
            collaborator_id=collaborator.id,
            project_id=project1.id,  # Stesso progetto
            date=datetime(2024, 1, 15, 10, 0),
            start_time=datetime(2024, 1, 15, 10, 0),
            end_time=datetime(2024, 1, 15, 14, 0),
            hours=4.0
        )

        with pytest.raises(ValueError) as exc_info:
            crud.create_attendance(db, attendance2_data)

        assert "già presente" in str(exc_info.value).lower() or "già" in str(exc_info.value).lower()
        print(f"[OK] Sovrapposizione rilevata correttamente: {exc_info.value}")

    finally:
        teardown_test_db(db)

def test_sovrapposizione_progetti_diversi():
    """Test: Non può esserci sovrapposizione tra progetti diversi"""
    db, collaborator, project1, project2 = setup_test_db()

    try:
        # Crea prima presenza: 14:00 - 18:00 su Progetto A
        attendance1_data = schemas.AttendanceCreate(
            collaborator_id=collaborator.id,
            project_id=project1.id,
            date=datetime(2024, 1, 15, 14, 0),
            start_time=datetime(2024, 1, 15, 14, 0),
            end_time=datetime(2024, 1, 15, 18, 0),
            hours=4.0
        )
        attendance1 = crud.create_attendance(db, attendance1_data)
        assert attendance1.id is not None
        print(f"[OK] Prima presenza creata su Progetto A: {attendance1.start_time} - {attendance1.end_time}")

        # Tentativo di creare seconda presenza sovrapposta: 15:00 - 19:00 su Progetto B
        # Dovrebbe fallire perché il collaboratore è già impegnato
        attendance2_data = schemas.AttendanceCreate(
            collaborator_id=collaborator.id,
            project_id=project2.id,  # Progetto diverso!
            date=datetime(2024, 1, 15, 15, 0),
            start_time=datetime(2024, 1, 15, 15, 0),
            end_time=datetime(2024, 1, 15, 19, 0),
            hours=4.0
        )

        with pytest.raises(ValueError) as exc_info:
            crud.create_attendance(db, attendance2_data)

        assert "già impegnato" in str(exc_info.value).lower() or "già presente" in str(exc_info.value).lower()
        print(f"[OK] Sovrapposizione tra progetti diversi rilevata: {exc_info.value}")

    finally:
        teardown_test_db(db)

def test_presenze_non_sovrapposte_stesso_giorno():
    """Test: Presenze non sovrapposte nello stesso giorno sono permesse"""
    db, collaborator, project1, project2 = setup_test_db()

    try:
        # Crea prima presenza: 09:00 - 13:00
        attendance1_data = schemas.AttendanceCreate(
            collaborator_id=collaborator.id,
            project_id=project1.id,
            date=datetime(2024, 1, 15, 9, 0),
            start_time=datetime(2024, 1, 15, 9, 0),
            end_time=datetime(2024, 1, 15, 13, 0),
            hours=4.0
        )
        attendance1 = crud.create_attendance(db, attendance1_data)
        print(f"[OK] Prima presenza: {attendance1.start_time} - {attendance1.end_time}")

        # Crea seconda presenza NON sovrapposta: 14:00 - 18:00
        # Dovrebbe funzionare perché non c'è sovrapposizione
        attendance2_data = schemas.AttendanceCreate(
            collaborator_id=collaborator.id,
            project_id=project2.id,
            date=datetime(2024, 1, 15, 14, 0),
            start_time=datetime(2024, 1, 15, 14, 0),
            end_time=datetime(2024, 1, 15, 18, 0),
            hours=4.0
        )
        attendance2 = crud.create_attendance(db, attendance2_data)
        assert attendance2.id is not None
        print(f"[OK] Seconda presenza NON sovrapposta creata correttamente: {attendance2.start_time} - {attendance2.end_time}")

    finally:
        teardown_test_db(db)

def test_sovrapposizione_parziale():
    """Test: Sovrapposizione parziale viene rilevata"""
    db, collaborator, project1, project2 = setup_test_db()

    try:
        # Crea prima presenza: 10:00 - 14:00
        attendance1_data = schemas.AttendanceCreate(
            collaborator_id=collaborator.id,
            project_id=project1.id,
            date=datetime(2024, 1, 15, 10, 0),
            start_time=datetime(2024, 1, 15, 10, 0),
            end_time=datetime(2024, 1, 15, 14, 0),
            hours=4.0
        )
        attendance1 = crud.create_attendance(db, attendance1_data)
        print(f"[OK] Prima presenza: {attendance1.start_time} - {attendance1.end_time}")

        # Test varie sovrapposizioni parziali
        overlapping_times = [
            (datetime(2024, 1, 15, 9, 0), datetime(2024, 1, 15, 11, 0)),   # Inizio prima, finisce durante
            (datetime(2024, 1, 15, 12, 0), datetime(2024, 1, 15, 16, 0)),  # Inizia durante, finisce dopo
            (datetime(2024, 1, 15, 11, 0), datetime(2024, 1, 15, 13, 0)),  # Completamente contenuta
            (datetime(2024, 1, 15, 9, 0), datetime(2024, 1, 15, 15, 0)),   # Contiene completamente
        ]

        for start, end in overlapping_times:
            attendance_data = schemas.AttendanceCreate(
                collaborator_id=collaborator.id,
                project_id=project2.id,
                date=start,
                start_time=start,
                end_time=end,
                hours=(end - start).total_seconds() / 3600
            )

            with pytest.raises(ValueError) as exc_info:
                crud.create_attendance(db, attendance_data)

            print(f"[OK] Sovrapposizione parziale rilevata: {start.strftime('%H:%M')} - {end.strftime('%H:%M')}")

    finally:
        teardown_test_db(db)

def test_update_presenza_con_sovrapposizione():
    """Test: Update di presenza non può creare sovrapposizioni"""
    db, collaborator, project1, project2 = setup_test_db()

    try:
        # Crea due presenze non sovrapposte
        attendance1_data = schemas.AttendanceCreate(
            collaborator_id=collaborator.id,
            project_id=project1.id,
            date=datetime(2024, 1, 15, 9, 0),
            start_time=datetime(2024, 1, 15, 9, 0),
            end_time=datetime(2024, 1, 15, 13, 0),
            hours=4.0
        )
        attendance1 = crud.create_attendance(db, attendance1_data)

        attendance2_data = schemas.AttendanceCreate(
            collaborator_id=collaborator.id,
            project_id=project2.id,
            date=datetime(2024, 1, 15, 14, 0),
            start_time=datetime(2024, 1, 15, 14, 0),
            end_time=datetime(2024, 1, 15, 18, 0),
            hours=4.0
        )
        attendance2 = crud.create_attendance(db, attendance2_data)
        print(f"[OK] Due presenze non sovrapposte create")

        # Tentativo di modificare la seconda presenza per sovrapporla alla prima
        update_data = schemas.AttendanceUpdate(
            start_time=datetime(2024, 1, 15, 12, 0),  # Ora si sovrappone!
            end_time=datetime(2024, 1, 15, 16, 0)
        )

        with pytest.raises(ValueError) as exc_info:
            crud.update_attendance(db, attendance2.id, update_data)

        assert "già" in str(exc_info.value).lower()
        print(f"[OK] Update con sovrapposizione bloccato: {exc_info.value}")

    finally:
        teardown_test_db(db)

def run_all_tests():
    """Esegue tutti i test"""
    print("\n" + "="*70)
    print("TEST VALIDAZIONE SOVRAPPOSIZIONI ORARIE PRESENZE")
    print("="*70 + "\n")

    tests = [
        ("Test sovrapposizione stesso progetto", test_sovrapposizione_stesso_progetto),
        ("Test sovrapposizione progetti diversi", test_sovrapposizione_progetti_diversi),
        ("Test presenze non sovrapposte stesso giorno", test_presenze_non_sovrapposte_stesso_giorno),
        ("Test sovrapposizione parziale", test_sovrapposizione_parziale),
        ("Test update presenza con sovrapposizione", test_update_presenza_con_sovrapposizione),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        print("-" * 70)
        try:
            test_func()
            print(f"[PASS]\n")
            passed += 1
        except Exception as e:
            print(f"[FAIL]: {e}\n")
            failed += 1

    print("="*70)
    print(f"\nRISULTATI: {passed} passed, {failed} failed")
    print("="*70)

if __name__ == "__main__":
    run_all_tests()
