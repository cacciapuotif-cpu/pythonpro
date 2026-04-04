# 📋 Guida: Gestione Enti Attuatori e Timesheet

## ✅ Componenti Già Implementati

Le maschere per la **gestione degli Enti Attuatori** e il **Timesheet** sono **già complete e funzionanti** nel sistema!

---

## 🏢 Gestione Enti Attuatori

### Accesso
Dalla barra di navigazione principale, clicca su:
**🏢 Enti Attuatori**

### Componenti Coinvolti
```
frontend/src/components/
├── ImplementingEntitiesList.js      # Lista e gestione enti
├── ImplementingEntityModal.js       # Modal per creare/modificare
├── ImplementingEntitiesList.css     # Stili lista
└── ImplementingEntityModal.css      # Stili modal
```

### Funzionalità Disponibili

#### 1️⃣ Visualizzazione Lista Enti
- **Vista card** con tutte le informazioni principali
- **Indicatore stato** (Attivo/Inattivo)
- **Informazioni mostrate:**
  - Ragione sociale e forma giuridica
  - Sede completa (indirizzo, città, provincia)
  - Partita IVA
  - PEC
  - Referente

#### 2️⃣ Ricerca e Filtri
- **Ricerca testuale** per:
  - Nome/ragione sociale
  - Partita IVA
  - Città
  - Provincia
- **Filtri rapidi:**
  - Tutti gli enti
  - Solo enti attivi
  - Solo enti inattivi

#### 3️⃣ Creazione Nuovo Ente
**Bottone:** ➕ Nuovo Ente Attuatore

**Campi del Form:**

**Dati Legali:**
- Ragione Sociale * (obbligatorio)
- Forma Giuridica (S.r.l., S.c.a.r.l., S.p.A., ecc.)
- Partita IVA * (11 cifre, validazione automatica)
- Codice Fiscale (11 o 16 caratteri)
- Codice ATECO
- Numero REA
- Registro Imprese

**Sede Legale:**
- Indirizzo completo
- CAP (5 cifre)
- Città
- Provincia (sigla 2 lettere)
- Nazione (codice ISO, default: IT)

**Contatti:**
- PEC (validazione email)
- Email ordinaria
- Telefono
- Codice SDI (7 caratteri, per fatturazione elettronica)

**Dati Pagamento:**
- IBAN (27 caratteri per IBAN italiano)
- Intestatario conto

**Referente:**
- Nome
- Cognome
- Email
- Telefono
- Ruolo (es: "Responsabile Amministrativo")

**Branding:**
- Logo (upload file)

**Altro:**
- Note libere
- Stato (Attivo/Inattivo)

#### 4️⃣ Modifica Ente Esistente
Clicca su **✏️ Modifica** su qualsiasi card ente.
Tutti i campi sono pre-popolati con i dati esistenti.

#### 5️⃣ Disattivazione Ente
Clicca su **🗑️ Disattiva**.
- **Soft delete**: l'ente non viene eliminato, solo disattivato
- Richiede conferma prima dell'azione
- Gli enti disattivati rimangono nel database per storicizzazione

### Validazioni Automatiche
- **Partita IVA**: 11 cifre numeriche, rimozione automatica prefisso "IT"
- **Codice Fiscale**: 11 cifre o 16 alfanumerici
- **PEC/Email**: formato email valido
- **IBAN**: 27 caratteri, prefisso IT obbligatorio
- **CAP**: 5 cifre numeriche
- **Provincia**: 2 lettere maiuscole

### API Endpoints Utilizzati
```javascript
GET    /implementing-entities/          # Lista enti
POST   /implementing-entities/          # Crea ente
GET    /implementing-entities/{id}      # Dettaglio ente
PUT    /implementing-entities/{id}      # Aggiorna ente
DELETE /implementing-entities/{id}      # Disattiva ente
```

---

## ⏱️ Timesheet Report

### Accesso
Dalla barra di navigazione principale, clicca su:
**⏱️ Timesheet**

### Componenti Coinvolti
```
frontend/src/components/
├── TimesheetReport.js               # Report completo
└── TimesheetReport.css              # Stili
```

### Funzionalità Disponibili

#### 1️⃣ Filtri Report
- **👤 Collaboratore**: Dropdown con tutti i collaboratori
- **📁 Progetto**: Dropdown con tutti i progetti
- **📅 Da Data**: Filtro data inizio
- **📅 A Data**: Filtro data fine
- **🔄 Resetta Filtri**: Rimuove tutti i filtri

#### 2️⃣ Statistiche Riepilogative (Cards)
- **⏱️ Ore Totali**: Somma di tutte le ore filtrate
- **📋 Presenze**: Numero totale presenze
- **👥 Collaboratori**: Numero collaboratori coinvolti
- **📁 Progetti**: Numero progetti coinvolti

#### 3️⃣ Tabella Dettaglio Presenze
Visualizza tutte le presenze con:
- **Data**: Formato italiano (gg/mm/aaaa)
- **Collaboratore**: Nome completo
- **Progetto**: Nome progetto
- **Ora Inizio**: Formato 24h (hh:mm)
- **Ora Fine**: Formato 24h (hh:mm)
- **Ore**: Badge con ore totali (es: 8.0h)
- **Note**: Note della presenza
- **Totale**: Riga di riepilogo con somma ore

#### 4️⃣ Riepilogo per Collaboratore
Sezione con card per ogni collaboratore che mostra:
- Nome completo collaboratore
- **Ore Totali**: Somma ore del collaboratore
- **Presenze**: Numero presenze registrate

#### 5️⃣ Riepilogo per Progetto
Sezione con card per ogni progetto che mostra:
- Nome progetto
- **Ore Totali**: Somma ore sul progetto
- **Presenze**: Numero presenze registrate

### Calcoli Automatici
- **Filtro real-time**: I calcoli si aggiornano immediatamente quando cambi i filtri
- **Aggregazioni**:
  - Somma ore per collaboratore
  - Somma ore per progetto
  - Conteggio presenze per collaboratore
  - Conteggio presenze per progetto

### Formattazione
- **Date**: Formato italiano (gg/mm/aaaa)
- **Orari**: Formato 24h (hh:mm)
- **Ore**: 1 decimale (es: 8.5h)

### Stati Interfaccia
- **Loading**: Spinner durante caricamento dati
- **Empty State**: Messaggio quando nessuna presenza trovata
- **Error State**: Alert rosso in caso di errori

---

## 🔗 Integrazione con Altri Componenti

### Workflow Completo
```
1. Crea Enti Attuatori (🏢 Enti Attuatori)
   ↓
2. Crea Progetti (📁 Progetti)
   ↓
3. Crea Collaboratori (👥 Collaboratori)
   ↓
4. Associa Progetto-Mansione-Ente (🔗 Associazioni Progetto-Ente)
   ↓
5. Registra Presenze (📅 Calendario)
   ↓
6. Visualizza Timesheet (⏱️ Timesheet)
   ↓
7. Analizza Statistiche (📊 Dashboard)
```

---

## 📸 Screenshots Concettuali

### Gestione Enti Attuatori
```
┌─────────────────────────────────────────────────────┐
│ 🏢 Gestione Enti Attuatori                         │
│ Gestisci gli enti che attuano i progetti formativi │
│                                  [➕ Nuovo Ente]    │
├─────────────────────────────────────────────────────┤
│                                                     │
│ [🔍 Cerca per nome, P.IVA, città...]              │
│                                                     │
│ [Tutti (5)] [Attivi (4)] [Inattivi (1)]           │
│                                                     │
├─────────────────────────────────────────────────────┤
│                                                     │
│ ┌─────────────────┐  ┌─────────────────┐          │
│ │ piemmei scarl   │  │ Next Group srl  │          │
│ │ S.c.a.r.l.      │  │ S.r.l.          │          │
│ │                 │  │                 │          │
│ │ 📍 Via Roma 1   │  │ 📍 Via Verdi 5  │          │
│ │ 💼 12345678901  │  │ 💼 98765432109  │          │
│ │                 │  │                 │          │
│ │ [✏️ Modifica]   │  │ [✏️ Modifica]   │          │
│ │ [🗑️ Disattiva]  │  │ [🗑️ Disattiva]  │          │
│ └─────────────────┘  └─────────────────┘          │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### Timesheet Report
```
┌─────────────────────────────────────────────────────┐
│ ⏱️ Timesheet Report                                 │
│ Report completo delle ore lavorate                  │
├─────────────────────────────────────────────────────┤
│                                                     │
│ [👤 Tutti] [📁 Tutti] [📅 Da] [📅 A] [🔄 Reset]   │
│                                                     │
├─────────────────────────────────────────────────────┤
│                                                     │
│ ┌────┐ ┌────┐ ┌────┐ ┌────┐                       │
│ │⏱️  │ │📋  │ │👥  │ │📁  │                       │
│ │160h│ │25  │ │5   │ │3   │                       │
│ └────┘ └────┘ └────┘ └────┘                       │
│                                                     │
├─────────────────────────────────────────────────────┤
│ 📋 Dettaglio Presenze                              │
├─────────────────────────────────────────────────────┤
│ Data     │Collaboratore│Progetto│Inizio│Fine│Ore  │
│──────────┼─────────────┼────────┼──────┼────┼─────│
│15/01/25  │Mario Rossi  │Prog A  │09:00 │17:00│8.0h│
│16/01/25  │Luigi Verdi  │Prog A  │09:00 │13:00│4.0h│
│          │             │        │      │TOTALE│12h │
└─────────────────────────────────────────────────────┘
```

---

## 🚀 Come Avviare

### 1. Avvia il Sistema
```bash
# Con Docker
make docker-up

# Senza Docker (sviluppo)
make dev
```

### 2. Accedi all'Applicazione
```
Frontend: http://localhost:3001
```

### 3. Naviga alle Sezioni
- **Enti Attuatori**: Click su "🏢 Enti Attuatori" nella navbar
- **Timesheet**: Click su "⏱️ Timesheet" nella navbar

---

## 🎯 Test Rapido

### Test Enti Attuatori
```
1. Click "🏢 Enti Attuatori"
2. Click "➕ Nuovo Ente Attuatore"
3. Compila form:
   - Ragione Sociale: "Test S.r.l."
   - P.IVA: "12345678901"
   - Città: "Roma"
4. Click "Salva"
5. Verifica card appaia nella lista
```

### Test Timesheet
```
1. Vai su "📅 Calendario" e registra alcune presenze
2. Click "⏱️ Timesheet"
3. Verifica tabella con presenze
4. Prova filtri per collaboratore/progetto
5. Verifica statistiche si aggiornino
```

---

## 🐛 Risoluzione Problemi

### Enti Attuatori Non Si Caricano
```bash
# Verifica backend
curl http://localhost:8001/implementing-entities/

# Check logs
make docker-logs
```

### Timesheet Vuoto
- Assicurati di aver registrato presenze dal calendario
- Verifica filtri date non escludano tutte le presenze
- Click "🔄 Resetta Filtri"

### Errori Validazione Form
- **P.IVA**: Deve essere 11 cifre numeriche
- **IBAN**: Deve iniziare con "IT" e avere 27 caratteri
- **Email/PEC**: Formato email valido richiesto

---

## 📚 Riferimenti

### File Sorgente
- **Frontend:**
  - `frontend/src/components/ImplementingEntitiesList.js`
  - `frontend/src/components/ImplementingEntityModal.js`
  - `frontend/src/components/TimesheetReport.js`
  - `frontend/src/services/api.js`

- **Backend:**
  - `backend/app/api/implementing_entities.py` (probabilmente)
  - `backend/app/models.py` → `ImplementingEntity`
  - `backend/app/schemas/` → Schemi validazione

### API Docs
Consulta la documentazione interattiva:
```
http://localhost:8001/docs
```

Sezioni rilevanti:
- **Implementing Entities** - CRUD completo enti
- **Attendances** - Presenze per timesheet

---

## ✅ Checklist Funzionalità

### Enti Attuatori
- [x] Lista enti con card
- [x] Ricerca testuale
- [x] Filtri attivi/inattivi
- [x] Creazione nuovo ente
- [x] Modifica ente esistente
- [x] Disattivazione soft delete
- [x] Validazione campi
- [x] Messaggi feedback utente
- [x] Gestione errori

### Timesheet
- [x] Tabella presenze
- [x] Filtro per collaboratore
- [x] Filtro per progetto
- [x] Filtro per date
- [x] Statistiche aggregate
- [x] Riepilogo per collaboratore
- [x] Riepilogo per progetto
- [x] Formattazione date/ore italiane
- [x] Calcoli real-time
- [x] Empty state

---

**🎉 Tutti i Componenti Sono Pronti e Funzionanti!**

Non serve creare nulla: basta avviare l'applicazione e usare le funzionalità esistenti.
