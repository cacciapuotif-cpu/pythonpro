# App Mobile Gestionale PythonPro

## 📱 Integrazione Mobile Expo con Backend PythonPro

Questa app mobile iOS/Android integrata con il gestionale PythonPro esistente mostra i dati reali nelle 4 tab:
- **Collaboratori**
- **Enti Attuatori**
- **Progetti**
- **Calendario** (Presenze)

---

## 🎯 Configurazione Completata

### Backend
- **URL**: `http://192.168.1.40:8001`
- **Health Check**: `http://192.168.1.40:8001/health`
- **OpenAPI Docs**: `http://192.168.1.40:8001/docs`

### Mobile
- **Metro Port**: `8090` (NON 3000/3001 che sono occupati)
- **Framework**: Expo Router con React Navigation
- **State Management**: React Query (@tanstack/react-query)
- **Validazione**: Zod
- **HTTP Client**: Axios

---

## 📡 Endpoint API Utilizzati

### 1. Collaboratori
**Endpoint**: `GET /api/v1/collaborators/`

**Dati mostrati**:
```typescript
{
  id: number;
  nome: string;
  cognome: string;
  email?: string;
  telefono?: string;
  ruolo?: string;
}
```

**Schermata**: `mobile/app/(tabs)/index.tsx`

---

### 2. Enti Attuatori
**Endpoint**: `GET /api/v1/entities/`

**Dati mostrati**:
```typescript
{
  id: number;
  ragione_sociale: string;
  partita_iva: string;
  citta?: string;
  email?: string;
  telefono?: string;
  is_active: boolean;
}
```

**Schermata**: `mobile/app/(tabs)/enti.tsx`

---

### 3. Progetti
**Endpoint**: `GET /api/v1/projects/`

**Dati mostrati**:
```typescript
{
  id: number;
  titolo: string;
  stato?: string; // active, completed, paused, cancelled
  ore_previste?: number;
  ore_effettive?: number;
  budget?: number;
  codice_progetto?: string;
}
```

**Schermata**: `mobile/app/(tabs)/progetti.tsx`

---

### 4. Calendario (Presenze)
**Endpoint**: `GET /api/v1/attendances/`

**Dati mostrati**:
```typescript
{
  id: number;
  collaborator_id: number;
  project_id: number;
  data: string; // ISO date
  ora_inizio?: string;
  ora_fine?: string;
  ore_lavorate?: number;
  luogo?: string;
  tipo_attivita?: string;
}
```

**Schermata**: `mobile/app/(tabs)/calendario.tsx`

---

## 🚀 Avvio dell'App

### Opzione 1: LAN (Consigliato)
```bash
cd mobile
npm run mobile:dev:lan
# Metro su porta 8090
# Backend su http://192.168.1.40:8001
```

### Opzione 2: Tunnel (se iPhone fuori rete locale)
```bash
cd mobile
npm run mobile:dev:tunnel
# Usa tunnel Expo per accesso remoto
```

### Opzione 3: Standard
```bash
cd mobile
npx expo start
```

---

## 📱 Test su iPhone

1. **Installa Expo Go** dall'App Store
2. **Avvia il server** con uno dei comandi sopra
3. **Scansiona il QR code** mostrato in console
4. **L'app si carica** e mostra le 4 tab in basso

### Navigazione
- 👥 **Collaboratori**: Lista di tutti i collaboratori con ruolo ed email
- 🏢 **Enti**: Lista enti attuatori con P.IVA e città
- 💼 **Progetti**: Lista progetti con stato, ore e budget
- 📅 **Calendario**: Eventi ordinati per data con orari e luogo

### Funzionalità
- **Pull-to-refresh** su ogni schermata
- **Fallback offline** con dati di esempio se il backend non risponde
- **Loading spinner** durante il caricamento
- **Banner di avviso** se offline

---

## 🎨 Design System

Il design mantiene i **colori esistenti** dell'app:

```typescript
// Colori primari
primary: '#007AFF' (iOS blue)
success: '#34C759'
warning: '#FF9500'
error: '#FF3B30'

// Grayscale
gray900: '#1C1C1E'
gray600: '#48484A'
gray400: '#8E8E93'
gray200: '#C7C7CC'

// Background
bgPrimary: '#FFFFFF'
bgSecondary: '#F2F2F7'
```

**Font**: SF Pro (iOS standard)
**Spacing**: 4, 8, 16, 24, 32, 48px
**Border radius**: 8, 12, 16px
**Shadows**: iOS-style elevations

---

## 📂 Struttura File Modificati/Creati

```
mobile/
├── .env                          # ✅ CREATO
│   └── EXPO_PUBLIC_API_BASE_URL=http://192.168.1.40:8001
│
├── src/
│   ├── lib/
│   │   ├── constants.ts          # ✅ AGGIORNATO (endpoint + BASE_URL)
│   │   └── api.ts                # ✅ ESTESO (4 nuovi metodi)
│   │
│   ├── types/
│   │   └── api.ts                # ✅ ESTESO (4 nuovi schemi Zod)
│   │
│   └── styles/
│       └── tokens.ts             # ✅ ESISTENTE (colori mantenuti)
│
└── app/
    └── (tabs)/
        ├── _layout.tsx           # ✅ AGGIORNATO (4 tab)
        ├── index.tsx             # ✅ RISCRITTO (Collaboratori)
        ├── enti.tsx              # ✅ CREATO
        ├── progetti.tsx          # ✅ CREATO
        └── calendario.tsx        # ✅ CREATO
```

---

## 🔧 Troubleshooting

### Porta Metro occupata
```bash
# Usa la porta 8090 configurata
npx expo start --lan --port 8090
```

### Backend non raggiungibile
- ✅ Verifica che il backend sia su `0.0.0.0:8001`
- ✅ Verifica che CORS sia abilitato per origin "*"
- ✅ Verifica il firewall su Windows
- ✅ Usa `ipconfig` per controllare l'IP della LAN

### iPhone non vede il QR code
```bash
# Usa tunnel mode
npx expo start --tunnel
```

### Errore CORS
Il backend deve avere:
```python
# FastAPI
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In produzione: lista specifica
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 🧪 Test Completati

✅ Backend raggiungibile su `http://192.168.1.40:8001/health`
✅ OpenAPI schema recuperato correttamente
✅ 4 tab implementate con dati reali
✅ Design system iOS rispettato
✅ Colori originali mantenuti
✅ Pull-to-refresh funzionante
✅ Fallback offline implementato
✅ Metro su porta 8090 (no conflitti)
✅ TypeScript + Zod validation

---

## 📸 Screenshot

L'app mostra:

1. **Tab Collaboratori**
   - Card bianche con shadow
   - Nome + Cognome (titolo)
   - Ruolo (blu primario)
   - Email e telefono (grigio)

2. **Tab Enti**
   - Ragione sociale (titolo)
   - P.IVA (blu primario)
   - Città, email, telefono
   - Badge "Non attivo" se disattivato

3. **Tab Progetti**
   - Titolo progetto
   - Badge colorato per stato (verde=attivo, grigio=completato, etc.)
   - Codice progetto
   - Statistiche: ore previste/effettive, budget

4. **Tab Calendario**
   - Data formattata (es: "ven 2 nov 2025")
   - Orario (09:00 - 13:00)
   - Badge tipo attività (blu chiaro)
   - Luogo e ore lavorate
   - Note opzionali

---

## 🚀 Prossimi Step (Opzionali)

- [ ] Aggiungere autenticazione (Bearer token)
- [ ] Implementare dettaglio su tap (router.push)
- [ ] Aggiungere ricerca/filtri
- [ ] Implementare paginazione
- [ ] Aggiungere immagini/avatar
- [ ] Sincronizzazione offline (React Query + AsyncStorage)
- [ ] Notifiche push

---

## 📞 Support

Per problemi di configurazione:
1. Verifica che il backend sia in esecuzione su porta 8001
2. Verifica l'IP della LAN con `ipconfig`
3. Controlla i log di Metro nella console
4. Usa `--tunnel` se il telefono è fuori rete

**URL Utili**:
- Backend Health: http://192.168.1.40:8001/health
- Backend Docs: http://192.168.1.40:8001/docs
- Metro Bundler: http://localhost:8090

---

**✅ Integrazione completata! L'app è pronta per il test su iPhone con Expo Go.**
