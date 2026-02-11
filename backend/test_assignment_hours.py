#!/usr/bin/env python3
"""
TEST COMPLETO SISTEMA MANSIONI E ORE RIMANENTI
Questo script testa il flusso completo:
1. Crea un collaboratore
2. Crea un progetto
3. Crea un'assegnazione con 20 ore
4. Inserisce una presenza di 5 ore
5. Verifica che le ore completate siano 5 e le rimanenti 15
6. Inserisce un'altra presenza di 3 ore
7. Verifica che le ore completate siano 8 e le rimanenti 12
8. Modifica la prima presenza a 7 ore
9. Verifica che le ore completate siano 10 e le rimanenti 10
10. Elimina la seconda presenza
11. Verifica che le ore completate siano 7 e le rimanenti 13
"""

import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8000"

# Colori per output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_test(message):
    print(f"{Colors.BLUE}{Colors.BOLD}[TEST]{Colors.END} {message}")

def print_success(message):
    print(f"{Colors.GREEN}[OK]{Colors.END} {message}")

def print_error(message):
    print(f"{Colors.RED}[ERROR]{Colors.END} {message}")

def print_info(message):
    print(f"{Colors.YELLOW}[INFO]{Colors.END} {message}")

def test_assignment_hours_flow():
    """Testa il flusso completo delle mansioni e ore"""

    print(f"\n{Colors.BOLD}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}TEST SISTEMA MANSIONI E ORE RIMANENTI{Colors.END}")
    print(f"{Colors.BOLD}{'='*70}{Colors.END}\n")

    # IDs che useremo
    collaborator_id = None
    project_id = None
    assignment_id = None
    attendance1_id = None
    attendance2_id = None

    try:
        # =====================================================================
        # STEP 1: Crea collaboratore
        # =====================================================================
        print_test("STEP 1: Creazione collaboratore test")
        collab_data = {
            "first_name": "Mario",
            "last_name": "Rossi",
            "email": f"mario.rossi.test_{datetime.now().timestamp()}@test.com",
            "phone": "1234567890",
            "position": "Docente",
            "is_active": True
        }
        response = requests.post(f"{BASE_URL}/collaborators/", json=collab_data)
        if response.status_code != 200:
            print_error(f"Errore creazione collaboratore: {response.text}")
            return False

        collaborator_id = response.json()["id"]
        print_success(f"Collaboratore creato con ID: {collaborator_id}")

        # =====================================================================
        # STEP 2: Crea progetto
        # =====================================================================
        print_test("STEP 2: Creazione progetto test")
        project_data = {
            "name": f"Progetto Test {datetime.now().timestamp()}",
            "description": "Progetto per test mansioni",
            "is_active": True
        }
        response = requests.post(f"{BASE_URL}/projects/", json=project_data)
        if response.status_code != 200:
            print_error(f"Errore creazione progetto: {response.text}")
            return False

        project_id = response.json()["id"]
        print_success(f"Progetto creato con ID: {project_id}")

        # =====================================================================
        # STEP 3: Crea assegnazione con 20 ore
        # =====================================================================
        print_test("STEP 3: Creazione assegnazione (20 ore totali)")
        today = datetime.now()
        assignment_data = {
            "collaborator_id": collaborator_id,
            "project_id": project_id,
            "role": "docente",
            "assigned_hours": 20.0,
            "start_date": today.isoformat(),
            "end_date": (today + timedelta(days=30)).isoformat(),
            "hourly_rate": 25.0,
            "contract_type": "professionale"
        }
        response = requests.post(f"{BASE_URL}/assignments/", json=assignment_data)
        if response.status_code != 200:
            print_error(f"Errore creazione assegnazione: {response.text}")
            return False

        assignment_id = response.json()["id"]
        assignment = response.json()
        print_success(f"Assegnazione creata con ID: {assignment_id}")
        print_info(f"  Ore assegnate: {assignment['assigned_hours']}h")
        print_info(f"  Ore completate: {assignment['completed_hours']}h")
        print_info(f"  Ore rimanenti: {assignment['assigned_hours'] - assignment['completed_hours']}h")

        # Verifica ore iniziali
        if assignment['completed_hours'] != 0:
            print_error(f"ERRORE: Ore completate dovrebbero essere 0, ma sono {assignment['completed_hours']}")
            return False

        # =====================================================================
        # STEP 4: Inserisce prima presenza (5 ore)
        # =====================================================================
        print_test("STEP 4: Inserimento prima presenza (5 ore)")
        work_date = today
        attendance1_data = {
            "collaborator_id": collaborator_id,
            "project_id": project_id,
            "assignment_id": assignment_id,
            "date": work_date.replace(hour=0, minute=0, second=0).isoformat(),
            "start_time": work_date.replace(hour=9, minute=0, second=0).isoformat(),
            "end_time": work_date.replace(hour=14, minute=0, second=0).isoformat(),
            "hours": 5.0,
            "notes": "Prima presenza di test"
        }
        response = requests.post(f"{BASE_URL}/attendances/", json=attendance1_data)
        if response.status_code != 200:
            print_error(f"Errore creazione presenza 1: {response.text}")
            return False

        attendance1_id = response.json()["id"]
        print_success(f"Presenza 1 creata con ID: {attendance1_id}")

        # Verifica ore dopo prima presenza
        response = requests.get(f"{BASE_URL}/assignments/{assignment_id}")
        assignment = response.json()
        print_info(f"  Ore completate: {assignment['completed_hours']}h")
        print_info(f"  Ore rimanenti: {assignment['assigned_hours'] - assignment['completed_hours']}h")

        if assignment['completed_hours'] != 5.0:
            print_error(f"ERRORE: Ore completate dovrebbero essere 5, ma sono {assignment['completed_hours']}")
            return False
        print_success("Ore completate corrette: 5h")

        # =====================================================================
        # STEP 5: Inserisce seconda presenza (3 ore)
        # =====================================================================
        print_test("STEP 5: Inserimento seconda presenza (3 ore)")
        work_date2 = today + timedelta(days=1)
        attendance2_data = {
            "collaborator_id": collaborator_id,
            "project_id": project_id,
            "assignment_id": assignment_id,
            "date": work_date2.replace(hour=0, minute=0, second=0).isoformat(),
            "start_time": work_date2.replace(hour=9, minute=0, second=0).isoformat(),
            "end_time": work_date2.replace(hour=12, minute=0, second=0).isoformat(),
            "hours": 3.0,
            "notes": "Seconda presenza di test"
        }
        response = requests.post(f"{BASE_URL}/attendances/", json=attendance2_data)
        if response.status_code != 200:
            print_error(f"Errore creazione presenza 2: {response.text}")
            return False

        attendance2_id = response.json()["id"]
        print_success(f"Presenza 2 creata con ID: {attendance2_id}")

        # Verifica ore dopo seconda presenza
        response = requests.get(f"{BASE_URL}/assignments/{assignment_id}")
        assignment = response.json()
        print_info(f"  Ore completate: {assignment['completed_hours']}h")
        print_info(f"  Ore rimanenti: {assignment['assigned_hours'] - assignment['completed_hours']}h")

        if assignment['completed_hours'] != 8.0:
            print_error(f"ERRORE: Ore completate dovrebbero essere 8, ma sono {assignment['completed_hours']}")
            return False
        print_success("Ore completate corrette: 8h (5 + 3)")

        # =====================================================================
        # STEP 6: Modifica prima presenza da 5 a 7 ore
        # =====================================================================
        print_test("STEP 6: Modifica prima presenza (da 5h a 7h)")
        update_data = {
            "hours": 7.0,
            "end_time": work_date.replace(hour=16, minute=0, second=0).isoformat()
        }
        response = requests.put(f"{BASE_URL}/attendances/{attendance1_id}", json=update_data)
        if response.status_code != 200:
            print_error(f"Errore modifica presenza: {response.text}")
            return False

        print_success("Presenza 1 modificata")

        # Verifica ore dopo modifica
        response = requests.get(f"{BASE_URL}/assignments/{assignment_id}")
        assignment = response.json()
        print_info(f"  Ore completate: {assignment['completed_hours']}h")
        print_info(f"  Ore rimanenti: {assignment['assigned_hours'] - assignment['completed_hours']}h")

        if assignment['completed_hours'] != 10.0:
            print_error(f"ERRORE: Ore completate dovrebbero essere 10, ma sono {assignment['completed_hours']}")
            return False
        print_success("Ore completate corrette: 10h (7 + 3)")

        # =====================================================================
        # STEP 7: Elimina seconda presenza
        # =====================================================================
        print_test("STEP 7: Eliminazione seconda presenza")
        response = requests.delete(f"{BASE_URL}/attendances/{attendance2_id}")
        if response.status_code != 200:
            print_error(f"Errore eliminazione presenza: {response.text}")
            return False

        print_success("Presenza 2 eliminata")

        # Verifica ore dopo eliminazione
        response = requests.get(f"{BASE_URL}/assignments/{assignment_id}")
        assignment = response.json()
        print_info(f"  Ore completate: {assignment['completed_hours']}h")
        print_info(f"  Ore rimanenti: {assignment['assigned_hours'] - assignment['completed_hours']}h")

        if assignment['completed_hours'] != 7.0:
            print_error(f"ERRORE: Ore completate dovrebbero essere 7, ma sono {assignment['completed_hours']}")
            return False
        print_success("Ore completate corrette: 7h")

        # =====================================================================
        # STEP 8: Test presenza senza assignment_id (deve fallire dopo modifiche)
        # =====================================================================
        print_test("STEP 8: Test validazione - presenza senza mansione")
        invalid_data = {
            "collaborator_id": collaborator_id,
            "project_id": project_id,
            "date": work_date.replace(hour=0, minute=0, second=0).isoformat(),
            "start_time": work_date.replace(hour=9, minute=0, second=0).isoformat(),
            "end_time": work_date.replace(hour=14, minute=0, second=0).isoformat(),
            "hours": 5.0
        }
        response = requests.post(f"{BASE_URL}/attendances/", json=invalid_data)
        # Nota: il backend ancora permette assignment_id null,
        # ma il frontend ora lo richiede obbligatoriamente
        print_info("Backend ancora permette assignment_id null (opzionale)")
        print_info("Frontend ora richiede la mansione obbligatoriamente")

        # =====================================================================
        # RIEPILOGO FINALE
        # =====================================================================
        print(f"\n{Colors.BOLD}{'='*70}{Colors.END}")
        print(f"{Colors.BOLD}RIEPILOGO FINALE{Colors.END}")
        print(f"{Colors.BOLD}{'='*70}{Colors.END}")

        response = requests.get(f"{BASE_URL}/assignments/{assignment_id}")
        assignment = response.json()

        print(f"\n{Colors.BOLD}Assegnazione ID {assignment_id}:{Colors.END}")
        print(f"  Mansione: {assignment['role']}")
        print(f"  Ore Assegnate: {assignment['assigned_hours']}h")
        print(f"  Ore Completate: {assignment['completed_hours']}h")
        print(f"  Ore Rimanenti: {assignment['assigned_hours'] - assignment['completed_hours']}h")
        print(f"  Progresso: {assignment.get('progress_percentage', 0):.1f}%")

        print(f"\n{Colors.GREEN}{Colors.BOLD}[SUCCESS] TUTTI I TEST SUPERATI!{Colors.END}\n")
        return True

    except Exception as e:
        print_error(f"Errore durante i test: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Cleanup (opzionale)
        print(f"\n{Colors.YELLOW}Pulizia dati di test...{Colors.END}")
        if attendance1_id:
            try:
                requests.delete(f"{BASE_URL}/attendances/{attendance1_id}")
                print_info(f"Presenza 1 eliminata")
            except:
                pass
        if assignment_id:
            try:
                requests.delete(f"{BASE_URL}/assignments/{assignment_id}")
                print_info(f"Assegnazione eliminata")
            except:
                pass
        if collaborator_id:
            try:
                requests.delete(f"{BASE_URL}/collaborators/{collaborator_id}")
                print_info(f"Collaboratore eliminato")
            except:
                pass
        if project_id:
            try:
                requests.delete(f"{BASE_URL}/projects/{project_id}")
                print_info(f"Progetto eliminato")
            except:
                pass

if __name__ == "__main__":
    success = test_assignment_hours_flow()
    exit(0 if success else 1)
