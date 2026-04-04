@echo off
echo ========================================
echo   AVVIO RAPIDO GESTIONALE
echo ========================================
echo.

REM Verifica se Docker Desktop e' in esecuzione
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRORE] Docker Desktop non e' in esecuzione!
    echo Avvio Docker Desktop...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    echo Attendo 30 secondi per l'avvio di Docker...
    timeout /t 30 /nobreak >nul
)

echo [OK] Docker e' attivo
echo.

REM Avvia tutti i servizi (usa cache)
echo Avvio servizi...
docker compose up -d

REM Attendi che i servizi siano pronti
echo.
echo Attesa avvio servizi (60 secondi)...
echo [INFO] Le migrazioni database sono automatiche all'avvio del backend
timeout /t 60 /nobreak >nul

REM Mostra lo stato
echo.
echo ========================================
echo   STATO SERVIZI
echo ========================================
docker compose ps

echo.
echo ========================================
echo   IL GESTIONALE E' PRONTO!
echo ========================================
echo.
echo Frontend: http://localhost:3001
echo Backend API: http://localhost:8001/docs
echo Database: localhost:5434
echo.
echo Per vedere i log: docker compose logs -f
echo Per fermare: docker compose down
echo.

REM Apri il browser
start http://localhost:3001

pause
