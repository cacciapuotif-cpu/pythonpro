"""
Seed dati di esempio per Blocco 1 — Anagrafica espansa.
Eseguire una sola volta: python3 seed_blocco1.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from database import SessionLocal
import models

db = SessionLocal()

try:
    # ── Agenzie ──────────────────────────────────
    agenzie_data = [
        {"nome": "Alfa Consulting Group", "telefono": "081 123 4567",
         "email": "info@alfaconsulting.it", "attivo": True},
        {"nome": "Sud Formazione Srl", "telefono": "081 987 6543",
         "email": "info@sudformazione.it", "attivo": True},
        {"nome": "Campania Lavoro Network", "telefono": "082 555 0011",
         "email": "rete@campanialavoro.it", "attivo": True},
    ]
    agenzie = []
    for data in agenzie_data:
        existing = db.query(models.Agenzia).filter(models.Agenzia.nome == data["nome"]).first()
        if not existing:
            obj = models.Agenzia(**data)
            db.add(obj)
            db.flush()
            agenzie.append(obj)
            print(f"  [+] Agenzia: {obj.nome}")
        else:
            agenzie.append(existing)
            print(f"  [=] Agenzia già presente: {existing.nome}")
    db.commit()

    # ── Consulenti ───────────────────────────────
    consulenti_data = [
        {"nome": "Marco", "cognome": "Esposito", "email": "m.esposito@alfaconsulting.it",
         "telefono": "333 111 2222", "partita_iva": "12345678903",
         "zona_competenza": "Napoli, Caserta", "provvigione_percentuale": 8.0,
         "agenzia_idx": 0, "attivo": True},
        {"nome": "Laura", "cognome": "De Luca", "email": "l.deluca@sudformazione.it",
         "telefono": "347 222 3333", "partita_iva": "98765432101",
         "zona_competenza": "Salerno, Avellino", "provvigione_percentuale": 7.5,
         "agenzia_idx": 1, "attivo": True},
        {"nome": "Antonio", "cognome": "Ferrara", "email": "a.ferrara@example.it",
         "telefono": "328 444 5555", "partita_iva": "11223344556",
         "zona_competenza": "Benevento, Campobasso", "provvigione_percentuale": 9.0,
         "agenzia_idx": 2, "attivo": True},
        {"nome": "Giulia", "cognome": "Romano", "email": "g.romano@freelance.it",
         "telefono": "320 666 7777", "partita_iva": "55667788990",
         "zona_competenza": "Napoli centro", "provvigione_percentuale": 6.0,
         "agenzia_idx": None, "attivo": True},
        {"nome": "Pasquale", "cognome": "Martino", "email": "p.martino@campanialavoro.it",
         "telefono": "349 888 9999", "partita_iva": "22334455668",
         "zona_competenza": "Tutta la Campania", "provvigione_percentuale": 10.0,
         "agenzia_idx": 2, "attivo": True},
    ]
    consulenti = []
    for data in consulenti_data:
        agenzia_idx = data.pop("agenzia_idx")
        agenzia_id = agenzie[agenzia_idx].id if agenzia_idx is not None else None
        existing = db.query(models.Consulente).filter(
            models.Consulente.email == data["email"]
        ).first()
        if not existing:
            obj = models.Consulente(**data, agenzia_id=agenzia_id)
            db.add(obj)
            db.flush()
            consulenti.append(obj)
            print(f"  [+] Consulente: {obj.cognome} {obj.nome}")
        else:
            consulenti.append(existing)
            print(f"  [=] Consulente già presente: {existing.cognome} {existing.nome}")
    db.commit()

    # ── Aziende Clienti ──────────────────────────
    aziende_data = [
        {"ragione_sociale": "Nexus Innovations Srl", "partita_iva": "12398765432",
         "settore_ateco": "62.01", "indirizzo": "Via Toledo 120", "citta": "Napoli",
         "cap": "80132", "provincia": "NA", "email": "info@nexusinnovations.it",
         "pec": "nexusinnovations@pec.it", "telefono": "081 234 5678",
         "referente_nome": "Dott. Carlo Blu", "referente_email": "c.blu@nexusinnovations.it",
         "consulente_idx": 0, "attivo": True},
        {"ragione_sociale": "Forma & Lavoro Cooperativa", "partita_iva": "98712345678",
         "settore_ateco": "85.59", "indirizzo": "Corso Umberto I 44", "citta": "Salerno",
         "cap": "84121", "provincia": "SA", "email": "segreteria@formalavoro.it",
         "pec": "formalavoro@pec.it", "telefono": "089 123 4567",
         "referente_nome": "Ing. Maria Rossi", "referente_email": "m.rossi@formalavoro.it",
         "consulente_idx": 1, "attivo": True},
        {"ragione_sociale": "Horizon Training SpA", "partita_iva": "11456789012",
         "settore_ateco": "85.59", "indirizzo": "Viale Europa 5", "citta": "Caserta",
         "cap": "81100", "provincia": "CE", "email": "hr@horizontraining.it",
         "pec": "horizon@pec.it", "telefono": "082 345 6789",
         "referente_nome": "Avv. Luigi Verde", "referente_email": "l.verde@horizontraining.it",
         "consulente_idx": 0, "attivo": True},
        {"ragione_sociale": "Meridionale Formazione Srl", "partita_iva": "55489012367",
         "settore_ateco": "85.32", "indirizzo": "Via Amendola 18", "citta": "Benevento",
         "cap": "82100", "provincia": "BN", "email": "info@meridionaleformazione.it",
         "pec": "meridionale@pec.it", "telefono": "082 456 7890",
         "referente_nome": "Dott.ssa Anna Neri", "referente_email": "a.neri@meridionaleformazione.it",
         "consulente_idx": 2, "attivo": True},
        {"ragione_sociale": "Campus Pro Srls", "partita_iva": "22489012378",
         "settore_ateco": "85.59", "indirizzo": "Via Roma 77", "citta": "Avellino",
         "cap": "83100", "provincia": "AV", "email": "info@campuspro.it",
         "pec": "campuspro@pec.it", "telefono": "082 567 8901",
         "referente_nome": "Sig. Franco Giallo", "referente_email": "f.giallo@campuspro.it",
         "consulente_idx": 3, "attivo": True},
        {"ragione_sociale": "Sviluppo Competenze Srl", "partita_iva": "33412345679",
         "settore_ateco": "85.59", "indirizzo": "Via Garibaldi 33", "citta": "Napoli",
         "cap": "80142", "provincia": "NA", "email": "info@sviluppocompetenze.it",
         "pec": "sviluppocompetenze@pec.it", "telefono": "081 678 9012",
         "referente_nome": "Dott. Paolo Bianchi", "referente_email": "p.bianchi@sviluppocompetenze.it",
         "consulente_idx": 4, "attivo": True},
        {"ragione_sociale": "FuturoLavoro Associazione", "partita_iva": "44512389012",
         "settore_ateco": "94.99", "indirizzo": "Via Dante 9", "citta": "Napoli",
         "cap": "80135", "provincia": "NA", "email": "info@futurolavoro.org",
         "pec": "futurolavoro@pec.it", "telefono": "081 789 0123",
         "referente_nome": "Sig.ra Elena Viola", "referente_email": "e.viola@futurolavoro.org",
         "consulente_idx": None, "attivo": True},
        {"ragione_sociale": "Enti & Risorse Srl", "partita_iva": "66534512390",
         "settore_ateco": "78.10", "indirizzo": "Corso Meridionale 22", "citta": "Napoli",
         "cap": "80143", "provincia": "NA", "email": "contatti@entirisorse.it",
         "pec": "entirisorse@legalmail.it", "telefono": "081 890 1234",
         "referente_nome": "Dott. Ugo Marrone", "referente_email": "u.marrone@entirisorse.it",
         "consulente_idx": 1, "attivo": False},  # disattiva di esempio
        {"ragione_sociale": "Agora Formazione Cooperativa", "partita_iva": "77612398765",
         "settore_ateco": "85.59", "indirizzo": "Vico Equense 14", "citta": "Napoli",
         "cap": "80069", "provincia": "NA", "email": "info@agoraformazione.it",
         "pec": "agora@pec.it", "telefono": "081 901 2345",
         "referente_nome": "Dott.ssa Rita Serra", "referente_email": "r.serra@agoraformazione.it",
         "consulente_idx": 4, "attivo": True},
        {"ragione_sociale": "ProSkills Academy Srl", "partita_iva": "88723456780",
         "settore_ateco": "85.59", "indirizzo": "Via Caracciolo 41", "citta": "Napoli",
         "cap": "80122", "provincia": "NA", "email": "hello@proskillsacademy.it",
         "pec": "proskills@pec.it", "telefono": "081 012 3456",
         "referente_nome": "CEO Andrea Costa", "referente_email": "a.costa@proskillsacademy.it",
         "consulente_idx": 0, "attivo": True},
    ]
    for data in aziende_data:
        consulente_idx = data.pop("consulente_idx")
        consulente_id = consulenti[consulente_idx].id if consulente_idx is not None else None
        existing = db.query(models.AziendaCliente).filter(
            models.AziendaCliente.ragione_sociale == data["ragione_sociale"]
        ).first()
        if not existing:
            obj = models.AziendaCliente(**data, consulente_id=consulente_id)
            db.add(obj)
            db.flush()
            print(f"  [+] Azienda: {obj.ragione_sociale}")
        else:
            print(f"  [=] Azienda già presente: {existing.ragione_sociale}")
    db.commit()
    print("\n✅ Seed Blocco 1 completato.")

except Exception as e:
    db.rollback()
    print(f"\n❌ Errore durante il seed: {e}")
    raise
finally:
    db.close()
