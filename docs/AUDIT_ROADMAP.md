# AUDIT ROADMAP — PythonPro ERP

> Generato: 2026-04-06  
> Piano di intervento prioritizzato post-audit

---

## RIEPILOGO QUANTITATIVO

| Categoria | Totale |
|---|---|
| Moduli analizzati | 21 |
| Classi SQLAlchemy | 25 |
| Funzioni CRUD totali | 220 |
| Funzioni CRUD non esposte | ~23 |
| Endpoint REST totali | ~130 |
| Componenti React analizzati | 35+ |
| File migrazioni Alembic | 34 |
| Bug critici | 5 |
| Problemi importanti | 5 |
| Miglioramenti proposti | 7 |

---

## 🔴 FASE 1 — CRITICI (Sprint 1, ~1-2 settimane)

> Bloccano il corretto funzionamento in produzione o creano rischi di sicurezza/dati.

### C1 — Credenziali hardcoded [effort: S, 1-2h]
**Problema**: password `admin123` hardcoded in `main.py`  
**Fix**: leggere da env var `ADMIN_DEFAULT_PASSWORD`  
**Dipendenze**: nessuna  
**Ordine**: **primo** — sicurezza immediata

### C2 — Verifica catena migrazioni Alembic [effort: M, 2-4h]
**Problema**: 5 file hash-named potrebbero essere orfani  
**Fix**: `alembic heads` → se > 1, collegare i rami orfani  
**Dipendenze**: accesso al DB in staging  
**Ordine**: **secondo** — fondamenta per tutto il resto

### C3 — Formalizzare ensure_runtime_schema_updates() [effort: L, 1-2 giorni]
**Problema**: 250 righe di `ALTER TABLE` bypassano Alembic  
**Fix**: convertire ogni ALTER in migrazione Alembic, rimuovere la funzione  
**Dipendenze**: C2 completata  
**Ordine**: **terzo**

### C4 — Fix FK errata template_piano_finanziario_id [effort: M, 4-6h]
**Problema**: FK punta a `contract_templates` invece di `template_piani_finanziari`  
**Fix**: correggere modello + creare migrazione Alembic  
**Dipendenze**: C3 completata (per non creare conflitti con runtime ALTER)  
**Ordine**: **quarto**

### C5 — Testare deploy fresh su DB vuoto [effort: M, 4-6h]
**Problema**: dopo C2+C3+C4, verificare che `alembic upgrade head` funzioni su DB vuoto  
**Fix**: script di CI/CD che esegue deploy su DB vuoto e verifica  
**Dipendenze**: C2, C3, C4  
**Ordine**: **quinto** (validazione della fase 1)

---

## 🟡 FASE 2 — IMPORTANTI (Sprint 2-3, ~2-3 settimane)

> Degradano la funzionalità o creano rischi di incoerenza dati.

### I1 — Unificare campi avviso/ente_erogatore su Project [effort: L, 2-3 giorni]
**Problema**: 3 sistemi paralleli (testo + avviso_id + avviso_pf_id) non sincronizzati  
**Azioni**:
1. Deprecare `ente_erogatore` e `avviso` (String) — renderli nullable
2. Rimuovere il loro `UniqueConstraint` da `PianoFinanziario`
3. Mantenere solo `avviso_pf_id` come riferimento strutturato
4. Script di migrazione dati: popolare `avviso_pf_id` dai dati legacy dove possibile
5. Aggiornare frontend per rimuovere i dropdown ridondanti  
**Dipendenze**: C4

### I2 — Aggiornamento automatico progress_percentage [effort: M, 1 giorno]
**Problema**: percentuali avanzamento obsolete nel dashboard  
**Fix**: hook post-commit su `create_attendance`/`delete_attendance`  
**Dipendenze**: nessuna

### I3 — Paginazione report timesheet [effort: S, 2-4h]
**Problema**: `limit=10000` hardcoded  
**Fix**: paginazione o streaming  
**Dipendenze**: nessuna

### I4 — DELETE soft per Ordine [effort: S, 1-2h]
**Problema**: nessun endpoint DELETE per ordini  
**Fix**: aggiungere `DELETE /{id}` con soft-delete  
**Dipendenze**: nessuna

### I5 — Cache in-process → Redis [effort: M, 1 giorno]
**Problema**: cache inutile con multi-worker  
**Fix opzione A**: rimuovere `QueryCache` (soluzione rapida)  
**Fix opzione B**: migrare a Redis (già presente nel progetto)  
**Dipendenze**: nessuna

---

## 🟢 FASE 3 — MIGLIORAMENTI (Sprint 4+, quando opportuno)

> Non bloccanti, migliorano qualità e manutenibilità.

### M1 — CORS configurabile via env var [effort: S, 1h]
**Fix**: `CORS_ALLOWED_ORIGINS` come env var

### M2 — Pulizia funzioni CRUD non esposte [effort: M, 2-4h]
**Azioni**: per ognuna delle ~23 funzioni, decidere: esporre via endpoint o rimuovere

### M3 — Unificare campi duplicati AgentRun/AgentSuggestion [effort: S, 2-4h]
**Fix**: deprecare `agent_name`/`confidence` legacy, usare solo `agent_type`/`confidence_score`

### M4 — Unificare reviewed_by in AgentReviewAction [effort: S, 1-2h]
**Fix**: usare solo `reviewed_by_user_id` (FK), rimuovere `reviewed_by` (String)

### M5 — Constraint UNIQUE su Attendance a livello DB [effort: M, 1 giorno]
**Fix**: aggiungere `UniqueConstraint('collaborator_id', 'project_id', 'data', 'ora_inizio')`

### M6 — Collegamento Ordine → Progetto via UI [effort: M, 1 giorno]
**Fix**: aggiungere `project_id` agli ordini e gestirlo nel frontend

### M7 — Flag is_agency/is_consultant con FK reale [effort: M, 2-4h]
**Fix**: se `is_agency=True`, validare che esista un record in `agenzie`

---

## CHECKLIST PRE-PRODUZIONE

### Sicurezza
- [ ] `ADMIN_DEFAULT_PASSWORD` configurato via env var (C1)
- [ ] `CORS_ALLOWED_ORIGINS` configurato per il dominio di produzione (M1)
- [ ] Variabili d'ambiente sensibili in `.env` non committate in git
- [ ] `DEBUG=False` in produzione

### Schema DB
- [ ] `alembic heads` mostra un solo head (C2)
- [ ] `alembic upgrade head` funziona su DB vuoto senza errori (C5)
- [ ] `ensure_runtime_schema_updates()` rimossa (C3)
- [ ] FK `template_piano_finanziario_id` corretta (C4)

### Funzionalità core
- [ ] Flusso Collaboratore → Assegnazione → Presenza registra correttamente le ore
- [ ] Progress del progetto si aggiorna dopo ogni presenza (I2)
- [ ] Piano Finanziario si crea correttamente dal progetto
- [ ] Generazione PDF contratti funziona
- [ ] Export timesheet non va in timeout (I3)

### Modulo commerciale
- [ ] Flusso Preventivo → Ordine funziona
- [ ] Ordini errati possono essere annullati (I4)

### Performance
- [ ] Report con dataset reali (>1000 presenze) risponde in <5s
- [ ] Nessun endpoint con `limit` hardcoded elevato

### Agenti AI
- [ ] AgentRun si crea e completa senza errori
- [ ] Suggerimenti vengono mostrati nel dashboard
- [ ] Review action (accetta/rifiuta) funziona

---

## ORDINE DI ESECUZIONE CONSIGLIATO

```
C1 (30min) → C2 (4h) → C3 (2gg) → C4 (6h) → C5 (6h)
                                                    ↓
I3 (4h) → I4 (2h) → I2 (1gg) → I5 (1gg) → I1 (3gg)
                                                    ↓
M1 → M3 → M4 → M2 → M5 → M6 → M7
```

**Durata totale stimata**:
- Fase 1 (Critici): ~4-5 giorni lavorativi
- Fase 2 (Importanti): ~8-10 giorni lavorativi
- Fase 3 (Miglioramenti): ~5-7 giorni lavorativi
- **Totale**: ~4-5 settimane per il sistema completamente consolidato

---

## NOTE FINALI

Il sistema è **funzionante per le operazioni CRUD core**. I problemi critici riguardano principalmente:
1. **Integrità schema DB** (migrazioni orfane, FK errata, runtime ALTER)
2. **Sicurezza** (credenziali hardcoded)

La **architettura modulare** è ben strutturata e scalabile. Il modulo commerciale (preventivi/ordini) e quello dei piani finanziari sono i più complessi e richiedono attenzione speciale durante il refactoring.

L'assenza di test automatici (`tests/`) è il gap più grande per garantire stabilità durante il refactoring — considerare di aggiungere almeno test di integrazione per i flussi critici prima di iniziare la Fase 2.
