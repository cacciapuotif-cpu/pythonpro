"""
Script di test per la funzionalità di upload documenti

Testa:
1. Creazione collaboratore
2. Upload documento identità (PDF)
3. Upload curriculum (PDF)
4. Download documenti
5. Eliminazione documenti
6. Verifica database
"""

import requests
import io
from datetime import datetime

BASE_URL = "http://localhost:8000"

def create_test_pdf():
    """Crea un file PDF fittizio per i test"""
    # Crea un PDF minimale valido
    pdf_content = b"""%PDF-1.4
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
    return io.BytesIO(pdf_content)

def test_upload_workflow():
    """Test completo del workflow upload"""

    print("=" * 60)
    print("TEST UPLOAD DOCUMENTI COLLABORATORE")
    print("=" * 60)
    print()

    # 1. Crea collaboratore di test
    print("1. Creazione collaboratore di test...")
    collaborator_data = {
        "first_name": "Mario",
        "last_name": "Rossi",
        "email": f"mario.rossi.test.{datetime.now().timestamp()}@example.com",
        "phone": "333-123-4567",
        "position": "Developer"
    }

    response = requests.post(f"{BASE_URL}/collaborators/", json=collaborator_data)
    if response.status_code != 200:
        print(f"   ERRORE creazione collaboratore: {response.status_code}")
        print(f"   {response.text}")
        return False

    collaborator = response.json()
    collaborator_id = collaborator["id"]
    print(f"   OK - Collaboratore creato con ID: {collaborator_id}")
    print()

    # 2. Upload documento identità
    print("2. Upload documento identita...")
    pdf_file = create_test_pdf()
    files = {"file": ("documento_identita.pdf", pdf_file, "application/pdf")}

    response = requests.post(
        f"{BASE_URL}/collaborators/{collaborator_id}/upload-documento",
        files=files
    )

    if response.status_code != 200:
        print(f"   ERRORE upload documento: {response.status_code}")
        print(f"   {response.text}")
        return False

    result = response.json()
    print(f"   OK - Documento caricato: {result['filename']}")
    print(f"   Path: {result['path']}")
    print()

    # 3. Upload curriculum
    print("3. Upload curriculum...")
    pdf_file = create_test_pdf()
    files = {"file": ("curriculum_vitae.pdf", pdf_file, "application/pdf")}

    response = requests.post(
        f"{BASE_URL}/collaborators/{collaborator_id}/upload-curriculum",
        files=files
    )

    if response.status_code != 200:
        print(f"   ERRORE upload curriculum: {response.status_code}")
        print(f"   {response.text}")
        return False

    result = response.json()
    print(f"   OK - Curriculum caricato: {result['filename']}")
    print(f"   Path: {result['path']}")
    print()

    # 4. Verifica dati collaboratore aggiornati
    print("4. Verifica dati collaboratore...")
    response = requests.get(f"{BASE_URL}/collaborators/{collaborator_id}")

    if response.status_code != 200:
        print(f"   ERRORE recupero collaboratore: {response.status_code}")
        return False

    collaborator = response.json()
    print(f"   Documento identita: {collaborator.get('documento_identita_filename', 'NON TROVATO')}")
    print(f"   Curriculum: {collaborator.get('curriculum_filename', 'NON TROVATO')}")
    print()

    # 5. Test download documento
    print("5. Test download documento identita...")
    response = requests.get(
        f"{BASE_URL}/collaborators/{collaborator_id}/download-documento"
    )

    if response.status_code != 200:
        print(f"   ERRORE download: {response.status_code}")
        return False

    print(f"   OK - Download riuscito ({len(response.content)} bytes)")
    print()

    # 6. Test download curriculum
    print("6. Test download curriculum...")
    response = requests.get(
        f"{BASE_URL}/collaborators/{collaborator_id}/download-curriculum"
    )

    if response.status_code != 200:
        print(f"   ERRORE download: {response.status_code}")
        return False

    print(f"   OK - Download riuscito ({len(response.content)} bytes)")
    print()

    # 7. Test eliminazione documento
    print("7. Test eliminazione documento identita...")
    response = requests.delete(
        f"{BASE_URL}/collaborators/{collaborator_id}/delete-documento"
    )

    if response.status_code != 200:
        print(f"   ERRORE eliminazione: {response.status_code}")
        return False

    print(f"   OK - Documento eliminato")
    print()

    # 8. Verifica eliminazione
    print("8. Verifica eliminazione...")
    response = requests.get(f"{BASE_URL}/collaborators/{collaborator_id}")
    collaborator = response.json()

    if collaborator.get('documento_identita_filename'):
        print(f"   ERRORE - Documento ancora presente nel database")
        return False

    print(f"   OK - Documento rimosso dal database")
    print()

    # 9. Cleanup - elimina collaboratore di test
    print("9. Cleanup...")
    response = requests.delete(f"{BASE_URL}/collaborators/{collaborator_id}")

    if response.status_code != 200:
        print(f"   WARNING - Impossibile eliminare collaboratore di test")
    else:
        print(f"   OK - Collaboratore di test eliminato")

    print()
    print("=" * 60)
    print("TUTTI I TEST PASSATI CON SUCCESSO!")
    print("=" * 60)

    return True

if __name__ == "__main__":
    try:
        success = test_upload_workflow()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\nERRORE DURANTE I TEST: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
