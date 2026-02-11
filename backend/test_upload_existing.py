"""
Test upload documenti usando un collaboratore esistente
"""

import requests
import io

BASE_URL = "http://localhost:8000"

def create_test_pdf():
    """Crea un PDF minimale per test"""
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

def test_upload():
    print("="  * 60)
    print("TEST UPLOAD DOCUMENTI")
    print("=" * 60)
    print()

    # 1. Ottieni primo collaboratore
    print("1. Recupero collaboratore esistente...")
    response = requests.get(f"{BASE_URL}/collaborators/")
    if response.status_code != 200:
        print(f"   ERRORE: {response.status_code}")
        return False

    collaborators = response.json()
    if not collaborators:
        print("   ERRORE: Nessun collaboratore trovato")
        return False

    collaborator = collaborators[0]
    collaborator_id = collaborator["id"]
    print(f"   OK - Uso collaboratore ID {collaborator_id}: {collaborator['first_name']} {collaborator['last_name']}")
    print()

    # 2. Upload documento identita
    print("2. Upload documento identita...")
    pdf_file = create_test_pdf()
    files = {"file": ("documento_test.pdf", pdf_file, "application/pdf")}

    response = requests.post(
        f"{BASE_URL}/collaborators/{collaborator_id}/upload-documento",
        files=files
    )

    if response.status_code != 200:
        print(f"   ERRORE: {response.status_code}")
        print(f"   {response.text}")
        return False

    result = response.json()
    print(f"   OK - Documento caricato: {result['filename']}")
    print()

    # 3. Upload curriculum
    print("3. Upload curriculum...")
    pdf_file = create_test_pdf()
    files = {"file": ("curriculum_test.pdf", pdf_file, "application/pdf")}

    response = requests.post(
        f"{BASE_URL}/collaborators/{collaborator_id}/upload-curriculum",
        files=files
    )

    if response.status_code != 200:
        print(f"   ERRORE: {response.status_code}")
        print(f"   {response.text}")
        return False

    result = response.json()
    print(f"   OK - Curriculum caricato: {result['filename']}")
    print()

    # 4. Verifica collaboratore aggiornato
    print("4. Verifica dati aggiornati...")
    response = requests.get(f"{BASE_URL}/collaborators/{collaborator_id}")
    collaborator = response.json()

    doc_filename = collaborator.get('documento_identita_filename')
    cv_filename = collaborator.get('curriculum_filename')

    print(f"   Documento identita: {doc_filename}")
    print(f"   Curriculum: {cv_filename}")

    if not doc_filename or not cv_filename:
        print("   ERRORE - Documenti non salvati nel database")
        return False

    print()

    # 5. Test download documento
    print("5. Test download documento...")
    response = requests.get(
        f"{BASE_URL}/collaborators/{collaborator_id}/download-documento"
    )

    if response.status_code != 200:
        print(f"   ERRORE: {response.status_code}")
        return False

    print(f"   OK - Download riuscito ({len(response.content)} bytes)")
    print()

    # 6. Test download curriculum
    print("6. Test download curriculum...")
    response = requests.get(
        f"{BASE_URL}/collaborators/{collaborator_id}/download-curriculum"
    )

    if response.status_code != 200:
        print(f"   ERRORE: {response.status_code}")
        return False

    print(f"   OK - Download riuscito ({len(response.content)} bytes)")
    print()

    # 7. Test eliminazione
    print("7. Test eliminazione documento...")
    response = requests.delete(
        f"{BASE_URL}/collaborators/{collaborator_id}/delete-documento"
    )

    if response.status_code != 200:
        print(f"   ERRORE: {response.status_code}")
        return False

    print(f"   OK - Documento eliminato")
    print()

    # 8. Verifica eliminazione
    print("8. Verifica eliminazione...")
    response = requests.get(f"{BASE_URL}/collaborators/{collaborator_id}")
    collaborator = response.json()

    if collaborator.get('documento_identita_filename'):
        print(f"   ERRORE - Documento ancora nel database")
        return False

    print(f"   OK - Documento rimosso dal database")
    print()

    print("=" * 60)
    print("TUTTI I TEST PASSATI!")
    print("=" * 60)

    return True

if __name__ == "__main__":
    try:
        success = test_upload()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\nERRORE: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
