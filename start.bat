@echo off
REM ==================================
REM   AVVIO GESTIONALE - PRODUZIONE
REM ==================================

echo.
echo ========================================
echo   GESTIONALE - Avvio Sistema
echo ========================================
echo.

cd /d "%~dp0"

REM Verifica Docker
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Docker Desktop non attivo
    echo [*] Avvio Docker Desktop...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    echo [*] Attendo 30 secondi...
    timeout /t 30 /nobreak >nul
)

echo [OK] Docker attivo
echo.

REM Avvia servizi
echo [*] Avvio servizi...
docker compose up -d

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo   SISTEMA AVVIATO!
    echo ========================================
    echo.
    echo Frontend:  http://localhost:3001
    echo Backend:   http://localhost:8000
    echo Database:  localhost:5433
    echo Redis:     localhost:6379
    echo.
    echo [*] Attendi 60 secondi per l'avvio completo
    echo.

    REM Apri browser dopo 10 secondi
    timeout /t 10 /nobreak >nul
    start http://localhost:3001

) else (
    echo.
    echo [!] ERRORE durante l'avvio
    echo.
)

pause
