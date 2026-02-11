"""
SCRIPT SEED PER ENTI ATTUATORI

Popola il database con i 3 enti attuatori iniziali:
- piemmei scarl
- Next Group srl
- Wonder srl

Esecuzione:
    python seed_implementing_entities.py
"""

from sqlalchemy.orm import Session
from database import SessionLocal, engine
import models
import crud
import schemas
from datetime import datetime

def seed_implementing_entities():
    """Inserisce i 3 enti attuatori iniziali nel database"""

    db = SessionLocal()

    try:
        print("[SEED] Inizializzazione seed Enti Attuatori...")
        print("=" * 60)

        # Lista enti da creare
        entities_data = [
            {
                "ragione_sociale": "piemmei scarl",
                "forma_giuridica": "S.c.a.r.l.",
                "partita_iva": "00000000001",  # P.IVA fittizia per esempio
                "codice_fiscale": "00000000001",
                "codice_ateco": "85.59.20",  # Formazione professionale
                "rea_numero": "NA-000001",
                "registro_imprese": "Napoli",

                # Sede legale
                "indirizzo": "ViaExample 123",
                "cap": "80100",
                "citta": "Napoli",
                "provincia": "NA",
                "nazione": "IT",

                # Contatti
                "pec": "piemmei@pec.it",
                "email": "info@piemmei.it",
                "telefono": "+39 081 1234567",
                "sdi": "ABCDEFG",

                # Pagamenti
                "iban": "IT60X0542811101000000123456",
                "intestatario_conto": "piemmei scarl",

                # Referente
                "referente_nome": "Mario",
                "referente_cognome": "Rossi",
                "referente_email": "mario.rossi@piemmei.it",
                "referente_telefono": "+39 333 1234567",
                "referente_ruolo": "Responsabile Amministrativo",

                # Note
                "note": "Ente attuatore principale per progetti formativi ed educativi",
                "is_active": True
            },
            {
                "ragione_sociale": "Next Group srl",
                "forma_giuridica": "S.r.l.",
                "partita_iva": "00000000002",
                "codice_fiscale": "00000000002",
                "codice_ateco": "70.22.09",  # Consulenza gestionale
                "rea_numero": "MI-000002",
                "registro_imprese": "Milano",

                # Sede legale
                "indirizzo": "Corso Italia 456",
                "cap": "20100",
                "citta": "Milano",
                "provincia": "MI",
                "nazione": "IT",

                # Contatti
                "pec": "nextgroup@pec.it",
                "email": "info@nextgroup.it",
                "telefono": "+39 02 9876543",
                "sdi": "HIJKLMN",

                # Pagamenti
                "iban": "IT28W8000000292100645211151",
                "intestatario_conto": "Next Group S.r.l.",

                # Referente
                "referente_nome": "Laura",
                "referente_cognome": "Bianchi",
                "referente_email": "laura.bianchi@nextgroup.it",
                "referente_telefono": "+39 335 9876543",
                "referente_ruolo": "Project Manager",

                # Note
                "note": "Società di consulenza e gestione progetti innovativi",
                "is_active": True
            },
            {
                "ragione_sociale": "Wonder srl",
                "forma_giuridica": "S.r.l.",
                "partita_iva": "00000000003",
                "codice_fiscale": "00000000003",
                "codice_ateco": "62.02.00",  # Consulenza informatica
                "rea_numero": "RM-000003",
                "registro_imprese": "Roma",

                # Sede legale
                "indirizzo": "Viale Europa 789",
                "cap": "00100",
                "citta": "Roma",
                "provincia": "RM",
                "nazione": "IT",

                # Contatti
                "pec": "wonder@pec.it",
                "email": "info@wonder.it",
                "telefono": "+39 06 5551234",
                "sdi": "OPQRSTU",

                # Pagamenti
                "iban": "IT07Y0300203280284975661141",
                "intestatario_conto": "Wonder S.r.l.",

                # Referente
                "referente_nome": "Giuseppe",
                "referente_cognome": "Verdi",
                "referente_email": "giuseppe.verdi@wonder.it",
                "referente_telefono": "+39 347 5551234",
                "referente_ruolo": "Direttore Generale",

                # Note
                "note": "Azienda specializzata in soluzioni digitali e formazione tecnologica",
                "is_active": True
            }
        ]

        created_count = 0
        skipped_count = 0

        for entity_data in entities_data:
            # Verifica se l'ente esiste già (per P.IVA)
            existing = crud.get_implementing_entity_by_piva(db, entity_data["partita_iva"])

            if existing:
                print(f"[SKIP] {entity_data['ragione_sociale']} (P.IVA {entity_data['partita_iva']}) gia' esistente")
                skipped_count += 1
                continue

            # Crea lo schema Pydantic
            entity_schema = schemas.ImplementingEntityCreate(**entity_data)

            # Crea l'ente
            created_entity = crud.create_implementing_entity(db, entity_schema)

            print(f"[OK] CREATO: {created_entity.ragione_sociale}")
            print(f"   ID: {created_entity.id}")
            print(f"   P.IVA: {created_entity.partita_iva}")
            print(f"   Sede: {created_entity.citta} ({created_entity.provincia})")
            print(f"   PEC: {created_entity.pec}")
            print()

            created_count += 1

        print("=" * 60)
        print(f"[OK] Seed completato!")
        print(f"   Enti creati: {created_count}")
        print(f"   Enti saltati (gia' esistenti): {skipped_count}")
        print()

        # Mostra riepilogo finale
        all_entities = crud.get_implementing_entities(db, limit=100)
        print(f"[INFO] Totale enti attuatori nel database: {len(all_entities)}")
        print()

        for entity in all_entities:
            print(f"   - {entity.ragione_sociale} - {entity.citta} ({entity.partita_iva})")

        print()
        print("[SUCCESS] Database popolato con successo!")

    except Exception as e:
        print(f"[ERROR] ERRORE durante il seed: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    print()
    print("=" * 60)
    print("  SEED ENTI ATTUATORI")
    print("=" * 60)
    print()

    # Crea le tabelle se non esistono
    print("[INFO] Creazione tabelle database (se necessario)...")
    models.Base.metadata.create_all(bind=engine)
    print("[OK] Tabelle pronte")
    print()

    # Esegui seed
    seed_implementing_entities()
