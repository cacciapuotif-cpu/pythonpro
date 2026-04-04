# 📜 SCRIPT DI VERIFICA E TEST AUTOMATIZZATI

## Descrizione

Questa directory contiene script automatizzati per **testare, verificare e validare** il sistema Gestionale Collaboratori dopo fix e modifiche.

---

## 🔧 Script Disponibili

### 1. `verify_fixes.bat` - Verifica Fix e Regressioni

**Scopo**: Esegue suite completa di test per verificare che tutti i fix siano ancora attivi e non ci siano regressioni.

**Cosa testa**:
- ✅ Health endpoints (backend + frontend)
- ✅ Connessione database
- ✅ CRUD Collaboratori (CREATE, READ)
- ✅ CRUD Progetti (CREATE, READ)
- ✅ Status container Docker
- ✅ Assenza errori critici nei log

**Come eseguirlo**:
```batch
cd scripts
verify_fixes.bat
```

**Output**:
- Report salvato in: `_fix_results/reports/verification_<timestamp>.txt`
- Console output con PASS/FAIL per ogni test

**Durata**: ~30 secondi

---

### 2. `simulate_restart.bat` - Test Persistenza Riavvio

**Scopo**: Simula un riavvio PC completo per testare persistenza dati e recovery automatico.

**Fasi del test**:
1. Salva stato corrente sistema
2. Crea dati di test
3. Ferma tutti i container (simula shutdown)
4. Pausa 10 secondi (simula PC spento)
5. Riavvia container (simula boot)
6. Attende inizializzazione (90s)
7. Verifica persistenza dati

**Come eseguirlo**:
```batch
cd scripts
simulate_restart.bat
```

**Output**:
- `_fix_results/logs/health_before_restart.json`
- `_fix_results/logs/health_after_restart.json`
- `_fix_results/logs/containers_before_restart.txt`
- `_fix_results/logs/containers_after_restart.txt`
- `_fix_results/logs/data_after_restart.json`

**Durata**: ~2 minuti (include attesa 90s startup)

---

### 3. `stress_test.py` - Load e Stress Testing

**Scopo**: Esegue test di carico con richieste concorrenti per verificare stabilità sotto stress.

**Configurazione**:
```python
NUM_THREADS = 10              # Thread concorrenti
REQUESTS_PER_THREAD = 50      # Richieste per thread
TIMEOUT = 5                   # Timeout richieste
```

**Operazioni testate**:
- GET `/health` (500 richieste)
- GET `/collaborators/` (500 richieste)
- GET `/projects/` (500 richieste)
- POST `/collaborators/` (50 richieste)

**Come eseguirlo**:
```batch
cd scripts
python stress_test.py
```

**Output**:
- Console: statistiche real-time e summary
- `_fix_results/reports/stress_test_report.json`

**Metriche riportate**:
- Richieste totali / riuscite / fallite
- Success rate %
- Throughput (req/s)
- Tempo medio risposta
- CPU e memory usage

**Durata**: ~18 secondi

---

### 4. `apply_all_fixes.bat` - Applicazione Patch

**Scopo**: Guida l'applicazione delle patch raccomandate per fix minori.

**Fix applicati**:
1. Frontend healthcheck timeout (10s → 30s)
2. Rimozione variabile unused ESLint

**Come eseguirlo**:
```batch
cd scripts
apply_all_fixes.bat
```

**Note**:
- Crea backup automatici prima delle modifiche
- Guida step-by-step per modifiche manuali necessarie
- Richiede conferma utente prima di procedere

**Durata**: Variabile (dipende da modifiche manuali)

---

## 📊 Interpretazione Risultati

### Success Criteria

| Test | Criterio Pass |
|------|---------------|
| verify_fixes.bat | Tutti i test ritornano ✓ |
| simulate_restart.bat | Dati persistiti + health OK post-restart |
| stress_test.py | Success rate >= 95% |

### Failure Handling

Se uno script fallisce:

1. **verify_fixes.bat**:
   - Controllare output per identificare test fallito
   - Eseguire `docker compose logs <service>` per debug
   - Verificare che container siano running: `docker compose ps`

2. **simulate_restart.bat**:
   - Verificare che container si siano riavviati: `docker ps`
   - Controllare integrità volume database
   - Aumentare tempo attesa se necessario

3. **stress_test.py**:
   - Success rate < 95% → verificare errori specifici nel report JSON
   - Timeout frequenti → aumentare `TIMEOUT` o ridurre load
   - Controllare resource system (CPU, RAM)

---

## 🔄 Workflow Raccomandato

### Dopo Modifiche al Codice

```batch
REM 1. Rebuild container
docker compose up -d --build

REM 2. Verifica base
cd scripts
verify_fixes.bat

REM 3. Test persistenza
simulate_restart.bat

REM 4. Stress test (opzionale ma raccomandato)
python stress_test.py
```

### Pre-Deploy Produzione

```batch
REM 1. Verifica completa
cd scripts
verify_fixes.bat

REM 2. Stress test
python stress_test.py

REM 3. Review report finale
type ..\_fix_results\FINAL_VERIFICATION_REPORT.md
```

---

## 🛠️ Personalizzazione Script

### Modificare Stress Test

Editare `stress_test.py`:

```python
# Aumentare carico
NUM_THREADS = 20              # Più thread concorrenti
REQUESTS_PER_THREAD = 100     # Più richieste

# Cambiare timeout
TIMEOUT = 10                  # Timeout più alto

# Cambiare URL base (per test remoto)
BASE_URL = "https://mio-server.com"
```

### Aggiungere Test Custom

In `verify_fixes.bat`, aggiungere sezione:

```batch
REM ==========================================
REM TEST CUSTOM: Descrizione
REM ==========================================
echo [TEST X] Testando feature custom...
curl -f http://localhost:8001/mio-endpoint > output.json
if %errorlevel% equ 0 (
    echo    ✓ Test custom: PASS
) else (
    echo    ✗ Test custom: FAIL
)
```

---

## 📦 Dipendenze

### verify_fixes.bat & simulate_restart.bat
- ✅ Windows (cmd.exe)
- ✅ curl (incluso Windows 10+)
- ✅ Docker Desktop running

### stress_test.py
- ✅ Python 3.7+
- ✅ Package: `requests`

Installare dipendenze Python:
```batch
pip install requests
```

---

## 🐛 Troubleshooting

### "curl: command not found"
Windows 10+ include curl. Se non disponibile:
- Installare curl: https://curl.se/windows/
- O usare PowerShell: `Invoke-WebRequest`

## Stato Attuale

Gli script operativi aggiornati fanno riferimento allo stack reale del progetto:

- backend locale: `http://localhost:8001`
- frontend locale: `http://localhost:3001`
- database Docker esposto: `5434`
- orchestrazione: `docker compose`
- servizio backup dedicato: `backup_scheduler`

### "python: command not found"
Installare Python:
- Download: https://python.org/downloads/
- Durante install, check "Add to PATH"

### "Docker not running"
Avviare Docker Desktop prima di eseguire script.

### "Permission denied"
Eseguire cmd.exe come Administrator.

---

## 📁 Output Files

Tutti gli output sono salvati in `_fix_results/`:

```
_fix_results/
├── logs/
│   ├── backend_current.log
│   ├── health_before_restart.json
│   ├── health_after_restart.json
│   ├── stress_test_output.txt
│   └── ...
│
└── reports/
    ├── verification_<timestamp>.txt
    ├── stress_test_report.json
    ├── FINAL_VERIFICATION_REPORT.md
    └── FINAL_VERIFICATION_REPORT.json
```

---

## 🚀 Continuous Integration

Per integrare in CI/CD pipeline:

```yaml
# .github/workflows/test.yml
name: Verify Fixes
on: [push, pull_request]
jobs:
  test:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v2
      - name: Start services
        run: docker compose up -d
      - name: Wait for startup
        run: timeout /t 90
      - name: Run verification
        run: cd scripts && verify_fixes.bat
      - name: Run stress test
        run: cd scripts && python stress_test.py
```

---

## 📞 Supporto

Per problemi con gli script:

1. Controllare log in `_fix_results/logs/`
2. Verificare prerequisiti (Docker, Python, curl)
3. Consultare sezione Troubleshooting sopra
4. Verificare che sistema base funzioni: `docker compose ps`

---

**Ultimo aggiornamento**: 2025-09-30
**Versione script**: 1.0
**Compatibilità**: Windows 10+, Docker Desktop
