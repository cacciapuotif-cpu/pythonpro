"""
Script di test per le nuove funzionalità:
1. Campo assignment_id nelle presenze
2. Calcolo differenza ore assegnate vs presenze
"""

import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000"

def print_section(title):
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

def test_create_collaborator():
    print_section("TEST 1: Creazione Collaboratore")

    data = {
        "first_name": "Mario",
        "last_name": "Rossi",
        "email": f"mario.rossi.test{datetime.now().timestamp()}@test.com",
        "phone": "1234567890",
        "position": "Sviluppatore",
        "fiscal_code": f"RSSMRA80A01H501{int(datetime.now().timestamp()) % 10}"
    }

    response = requests.post(f"{BASE_URL}/collaborators/", json=data)
    if response.status_code == 200:
        collab = response.json()
        print(f"OK - Collaboratore creato: {collab['first_name']} {collab['last_name']} (ID: {collab['id']})")
        return collab
    else:
        print(f"ERRORE - Status: {response.status_code}, Dettagli: {response.text}")
        return None

def test_create_project():
    print_section("TEST 2: Creazione Progetto")

    data = {
        "name": f"Progetto Test {datetime.now().timestamp()}",
        "description": "Progetto per testare le nuove funzionalita",
        "start_date": datetime.now().isoformat(),
        "end_date": (datetime.now() + timedelta(days=90)).isoformat(),
        "status": "active",
        "cup": "TEST12345",
        "ente_erogatore": "Test Entity"
    }

    response = requests.post(f"{BASE_URL}/projects/", json=data)
    if response.status_code == 200:
        project = response.json()
        print(f"OK - Progetto creato: {project['name']} (ID: {project['id']})")
        return project
    else:
        print(f"ERRORE - Status: {response.status_code}, Dettagli: {response.text}")
        return None

def test_create_assignment(collaborator_id, project_id):
    print_section("TEST 3: Creazione Assignment (Mansione)")

    data = {
        "collaborator_id": collaborator_id,
        "project_id": project_id,
        "role": "docente",
        "assigned_hours": 50.0,
        "start_date": datetime.now().isoformat(),
        "end_date": (datetime.now() + timedelta(days=60)).isoformat(),
        "hourly_rate": 35.0,
        "contract_type": "professionale"
    }

    response = requests.post(f"{BASE_URL}/assignments/", json=data)
    if response.status_code == 200:
        assignment = response.json()
        print(f"OK - Assignment creato:")
        print(f"   - Mansione: {assignment['role']}")
        print(f"   - Ore assegnate: {assignment['assigned_hours']}h")
        print(f"   - Ore completate: {assignment.get('completed_hours', 0)}h")
        print(f"   - Ore rimanenti: {assignment['assigned_hours'] - assignment.get('completed_hours', 0)}h")
        print(f"   - Progresso: {assignment.get('progress_percentage', 0)}%")
        return assignment
    else:
        print(f"ERRORE - Status: {response.status_code}, Dettagli: {response.text}")
        return None

def test_create_attendance_with_assignment(collaborator_id, project_id, assignment_id):
    print_section("TEST 4: Creazione Presenza con Assignment")

    today = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)

    data = {
        "collaborator_id": collaborator_id,
        "project_id": project_id,
        "assignment_id": assignment_id,
        "date": today.isoformat(),
        "start_time": today.isoformat(),
        "end_time": (today + timedelta(hours=5)).isoformat(),
        "hours": 5.0,
        "notes": "Test presenza con mansione collegata"
    }

    response = requests.post(f"{BASE_URL}/attendances/", json=data)
    if response.status_code == 200:
        attendance = response.json()
        print(f"OK - Presenza creata:")
        print(f"   - Collaboratore ID: {attendance['collaborator_id']}")
        print(f"   - Progetto ID: {attendance['project_id']}")
        print(f"   - Assignment ID: {attendance.get('assignment_id', 'NON PRESENTE!')}")
        print(f"   - Ore: {attendance['hours']}h")
        return attendance
    else:
        print(f"ERRORE - Status: {response.status_code}, Dettagli: {response.text}")
        return None

def test_get_updated_assignment(assignment_id):
    print_section("TEST 5: Verifica Aggiornamento Ore Assignment")

    response = requests.get(f"{BASE_URL}/assignments/{assignment_id}")
    if response.status_code == 200:
        assignment = response.json()
        print(f"OK - Assignment aggiornato:")
        print(f"   - Ore assegnate: {assignment['assigned_hours']}h")
        print(f"   - Ore completate: {assignment.get('completed_hours', 0)}h")
        print(f"   - Ore rimanenti: {assignment['assigned_hours'] - assignment.get('completed_hours', 0)}h")
        print(f"   - Progresso: {assignment.get('progress_percentage', 0):.1f}%")

        # Verifica che le ore completate siano state aggiornate
        if assignment.get('completed_hours', 0) > 0:
            print("\n   SUCCESSO! Le ore completate sono state aggiornate correttamente!")
        else:
            print("\n   ATTENZIONE! Le ore completate non sono state aggiornate.")

        return assignment
    else:
        print(f"ERRORE - Status: {response.status_code}, Dettagli: {response.text}")
        return None

def test_create_more_attendances(collaborator_id, project_id, assignment_id):
    print_section("TEST 6: Creazione Presenze Multiple")

    for i in range(3):
        day = datetime.now() - timedelta(days=i+1)
        day = day.replace(hour=9, minute=0, second=0, microsecond=0)

        data = {
            "collaborator_id": collaborator_id,
            "project_id": project_id,
            "assignment_id": assignment_id,
            "date": day.isoformat(),
            "start_time": day.isoformat(),
            "end_time": (day + timedelta(hours=4)).isoformat(),
            "hours": 4.0,
            "notes": f"Presenza giorno {i+1}"
        }

        response = requests.post(f"{BASE_URL}/attendances/", json=data)
        if response.status_code == 200:
            print(f"OK - Presenza {i+1} creata: 4h")
        else:
            print(f"ERRORE - Presenza {i+1} fallita: {response.status_code}")

def run_all_tests():
    print("\n" + "#"*60)
    print("#  TEST COMPLETO NUOVE FUNZIONALITA")
    print("#"*60)

    # Test 1: Crea collaboratore
    collab = test_create_collaborator()
    if not collab:
        print("\nTest fallito: impossibile creare collaboratore")
        return

    # Test 2: Crea progetto
    project = test_create_project()
    if not project:
        print("\nTest fallito: impossibile creare progetto")
        return

    # Test 3: Crea assignment
    assignment = test_create_assignment(collab['id'], project['id'])
    if not assignment:
        print("\nTest fallito: impossibile creare assignment")
        return

    # Test 4: Crea presenza con assignment
    attendance = test_create_attendance_with_assignment(collab['id'], project['id'], assignment['id'])
    if not attendance:
        print("\nTest fallito: impossibile creare presenza")
        return

    # Verifica che assignment_id sia presente
    if attendance.get('assignment_id'):
        print("\n>>> SUCCESSO! assignment_id presente nella presenza <<<")
    else:
        print("\n>>> ERRORE! assignment_id NON presente nella presenza <<<")

    # Test 5: Verifica aggiornamento ore
    assignment_updated = test_get_updated_assignment(assignment['id'])

    # Test 6: Crea altre presenze
    test_create_more_attendances(collab['id'], project['id'], assignment['id'])

    # Test 7: Verifica finale
    print_section("TEST 7: Verifica Finale")
    final_assignment = test_get_updated_assignment(assignment['id'])

    if final_assignment:
        expected_hours = 5 + (4 * 3)  # 5h prima presenza + 4h x 3 presenze
        actual_hours = final_assignment.get('completed_hours', 0)

        print(f"\nOre totali attese: {expected_hours}h")
        print(f"Ore totali registrate: {actual_hours}h")

        if actual_hours == expected_hours:
            print("\n>>> TEST COMPLETATO CON SUCCESSO! <<<")
        else:
            print(f"\n>>> ATTENZIONE! Discrepanza ore: attese {expected_hours}h, registrate {actual_hours}h <<<")

    print("\n" + "#"*60)
    print("#  FINE TEST")
    print("#"*60 + "\n")

if __name__ == "__main__":
    try:
        run_all_tests()
    except Exception as e:
        print(f"\n\nERRORE GENERALE: {e}")
        import traceback
        traceback.print_exc()
