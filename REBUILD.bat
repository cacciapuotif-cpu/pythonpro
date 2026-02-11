@echo off
REM ==================================
REM   REBUILD GESTIONALE
REM ==================================

echo.
echo ========================================
echo   GESTIONALE - Rebuild Completo
echo ========================================
echo.

cd /d "%~dp0"

echo [*] Arresto e pulizia...
docker compose down -v

echo.
echo [*] Rebuild immagini (potrebbe richiedere 5-10 minuti)...
docker compose build --no-cache

echo.
echo [*] Avvio servizi...
docker compose up -d

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo   REBUILD COMPLETATO!
    echo ========================================
    echo.
    echo [*] Attendi 60 secondi per l'avvio completo
    echo [*] Apertura browser...
    timeout /t 10 /nobreak >nul
    start http://localhost:3001
) else (
    echo.
    echo [!] ERRORE durante il rebuild
)

echo.
pause
