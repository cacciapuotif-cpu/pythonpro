# PythonPro Mobile App

App mobile iOS-first per il gestionale PythonPro, costruita con **Expo** + **React Native** + **Expo Router**.

## 🚀 Quick Start

### 1. Installazione Dipendenze

```bash
cd mobile
npm install
```

### 2. Configurazione Ambiente

Crea il file `.env.local` partendo da `.env.example`:

```bash
cp .env.example .env.local
```

**IMPORTANTE**: Modifica `.env.local` con l'IP del tuo PC:

```env
# Trova il tuo IP LAN con ipconfig (Windows)
# Esempio: 192.168.1.12
EXPO_PUBLIC_API_BASE_URL=http://192.168.1.12:8000
EXPO_PUBLIC_USE_MOCK=false
```

#### Come trovare il tuo IP LAN (Windows):

```bash
ipconfig
# Cerca "IPv4 Address" nella sezione della tua rete attiva
# Esempio: IPv4 Address. . . . . . . . . . . : 192.168.1.12
```

### 3. Avvio Development Server

#### Opzione A: LAN (Consigliato)

```bash
npm run mobile:dev:lan
```

- Metro Bundler partirà sulla porta **8090** (o fallback 8091, 8092...)
- Scansiona il QR code con l'app **Expo Go** sul tuo iPhone
- Assicurati che iPhone e PC siano sulla **stessa rete WiFi**

#### Opzione B: Tunnel (se LAN non funziona)

```bash
npm run mobile:dev:tunnel
```

- Utile se la rete ha restrizioni (VPN, firewall, rete guest)
- Più lento ma funziona sempre

### 4. Test su iOS

1. Scarica **Expo Go** dall'App Store
2. Apri Expo Go
3. Scansiona il QR code visualizzato nel terminale
4. L'app si caricherà automaticamente

---

## 📱 MVP Features

### Autenticazione
- ✅ Login con email/password
- ✅ Validazione form con Zod
- ✅ Token Bearer in AsyncStorage
- ✅ Auto-refresh token su 401
- ✅ Logout sicuro

### Gestione Items
- ✅ Lista items con pull-to-refresh
- ✅ Dettaglio item editabile
- ✅ Optimistic updates con rollback
- ✅ Cache intelligente con React Query
- ✅ Empty states e loading states

### UX/UI
- ✅ Design iOS-first (Human Interface Guidelines)
- ✅ Touch target ≥44pt
- ✅ Haptic feedback
- ✅ Screen reader support
- ✅ Toast notifications accessibili
- ✅ Safe Area support

---

## 🏗️ Architettura

```
mobile/
├── app/                          # Expo Router routes
│   ├── _layout.tsx              # Root layout (Auth + Query Provider)
│   ├── (public)/                # Public routes
│   │   └── login.tsx           # Login screen
│   └── (app)/                   # Authenticated routes
│       ├── _layout.tsx         # App layout with header
│       └── items/
│           ├── index.tsx       # Items list
│           └── [id].tsx        # Item detail (editable)
├── src/
│   ├── components/              # Reusable UI components
│   │   ├── Button.tsx
│   │   ├── Input.tsx
│   │   ├── Toast.tsx
│   │   ├── EmptyState.tsx
│   │   └── LoadingSpinner.tsx
│   ├── lib/                     # Core logic
│   │   ├── api.ts              # Typed API client (axios + zod)
│   │   ├── auth.tsx            # Auth context & hooks
│   │   ├── constants.ts        # App constants
│   │   └── mockData.ts         # Mock data for offline dev
│   ├── hooks/                   # Custom hooks
│   │   └── useItems.ts         # React Query hooks for items
│   ├── styles/                  # Design system
│   │   └── tokens.ts           # Design tokens (colors, spacing, etc)
│   └── types/                   # TypeScript types
│       └── api.ts              # Zod schemas & types
├── metro.config.js             # Metro bundler config (port auto-detection)
└── package.json
```

---

## 🔌 API Client

### Features

- **Typed requests/responses** con Zod validation
- **Bearer token** automatico da AsyncStorage
- **Auto-retry su 401** con refresh token
- **Error mapping** a messaggi umani (italiano)
- **Mock mode** per sviluppo offline

### Esempio utilizzo:

```typescript
import { api } from '@/lib/api';

// Login
const { tokens, user } = await api.login({
  email: 'user@example.com',
  password: 'password123',
});

// Get items
const items = await api.getItems();

// Update item
const updated = await api.updateItem(1, {
  nome: 'Nuovo nome',
  descrizione: 'Nuova descrizione',
});
```

---

## 🧪 Testing

### Setup (TODO)

```bash
npm install --save-dev jest @testing-library/react-native @testing-library/jest-native
```

### Run Tests

```bash
npm test
```

### Coverage Target

- API client: success, error, 401→refresh
- Components: Button, Input (a11y)
- Screens: Login (validation), ItemsList (states)

---

## 🐛 Troubleshooting

### Metro non si avvia sulla porta 8090

✅ **Soluzione**: Il config auto-rileva porte disponibili (8091, 8092...). Controlla il log.

### iPhone non riesce a connettersi (LAN)

Possibili cause:

1. **IP errato in `.env.local`**
   - Verifica con `ipconfig`
   - Deve essere l'IPv4 della rete WiFi attiva

2. **iPhone e PC su reti diverse**
   - Assicurati che siano sulla stessa rete WiFi
   - Evita reti guest separate

3. **Firewall Windows blocca Metro**
   - Windows Defender potrebbe chiedere permesso
   - Consenti accesso alla rete privata

4. **VPN attiva**
   - Disabilita VPN temporaneamente
   - Oppure usa `npm run mobile:dev:tunnel`

### "Network Error" / "Connection Failed"

Verifica:

1. **Backend in esecuzione?**
   ```bash
   # Dalla root del progetto
   cd backend
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

2. **Porta corretta?**
   - Default backend: `8000` o `8001`
   - Verifica in `.env.local`

3. **Backend accessibile da rete?**
   - Se usi Docker, assicurati che il backend sia pubblicato con `--host 0.0.0.0`
   - Testa da browser mobile: `http://IP_PC:8000/docs`

### iOS App Transport Security (ATS)

⚠️ **Development**: Expo Go permette HTTP in dev mode (nessuna config necessaria)

🚀 **Production**: Per build standalone serve HTTPS
- Deploy backend con certificato SSL
- Oppure configura ATS exception in `app.json` (non consigliato)

---

## 🎨 Design Tokens

Design system basato su **iOS Human Interface Guidelines**:

```typescript
// Colors
colors.primary = '#007AFF'  // iOS Blue
colors.success = '#34C759'  // iOS Green
colors.error = '#FF3B30'    // iOS Red

// Spacing (8-pt grid)
spacing.sm = 8
spacing.md = 16
spacing.lg = 24

// Touch Targets
touchTargets.min = 44  // iOS HIG minimum

// Typography
typography.sizes.base = 16
typography.weights.semibold = '600'
```

---

## 📦 Dipendenze Chiave

- **expo**: ~54.0 - Framework
- **expo-router**: ~6.0 - File-based routing
- **@tanstack/react-query**: ^5.90 - Server state management
- **axios**: ^1.13 - HTTP client
- **zod**: ^3.25 - Schema validation
- **react-hook-form**: ^7.66 - Form management
- **@react-native-async-storage/async-storage**: ^2.2 - Persistent storage
- **expo-haptics**: ^15.0 - Haptic feedback

---

## 🔐 Security Best Practices

### Tokens
- ✅ Salvati in **AsyncStorage** (secure su iOS)
- ✅ Auto-clear su logout/401 hard fail
- ✅ Refresh token utilizzato per rinnovo automatico

### Validazione
- ✅ Input sanitization con **Zod**
- ✅ Server response validation
- ✅ XSS protection (no dangerouslySetInnerHTML)

### Network
- ⚠️ **Development**: HTTP ok (Expo Go)
- ✅ **Production**: Solo HTTPS

---

## 📊 Performance

- **Optimistic updates** con rollback su errore
- **Cache intelligente** (staleTime: 5min, gcTime: 10min)
- **Debounced inputs** (300ms)
- **Pull-to-refresh** per refresh manuale
- **Lazy loading** ready (FlatList virtualizzato)

---

## 🚧 Roadmap

- [ ] Unit tests con Jest + RTL
- [ ] E2E tests con Detox
- [ ] Offline-first con AsyncStorage sync
- [ ] Push notifications
- [ ] Biometric authentication (FaceID/TouchID)
- [ ] Dark mode support
- [ ] Multi-language (i18n)
- [ ] Android optimization

---

## 📝 Notes

### Porte utilizzate

- **Metro Bundler**: 8090 (o auto-detect)
- **Backend API**: 8000 o 8001
- **Porte bloccate**: 3000, 3001, 8000, 8001, 5434, 6381, 3200, 4317-4318, 8888, 9000-9001, 9090

### Demo Mode

Abilita mock data per demo offline:

```env
EXPO_PUBLIC_USE_MOCK=true
```

- Nessuna chiamata HTTP
- Dati fittizi coerenti
- Utile per presentazioni senza backend

---

## 🤝 Contributing

1. Crea feature branch
2. Implementa con test
3. Verifica a11y
4. PR con descrizione chiara

---

## 📄 License

Proprietario - PythonPro Team
