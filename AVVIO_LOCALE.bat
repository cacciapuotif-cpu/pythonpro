@echo off
:: ============================================================
:: AVVIO LOCALE - Gestionale Collaboratori (senza Docker)
:: ============================================================
:: Questo script avvia backend e frontend in locale
:: con Python venv e npm
:: ============================================================

echo.
echo ========================================
echo   AVVIO GESTIONALE COLLABORATORI
echo   (Modalita Locale - NO Docker)
echo ========================================
echo.

:: Vai nella directory dello script
cd /d "%~dp0"

echo [1/2] Avvio Backend FastAPI (porta 8000)...
echo.

:: Avvia il backend in una nuova finestra
start "Backend - Gestionale" cmd /k "cd /d %~dp0backend && venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

:: Aspetta 8 secondi per far partire il backend
echo Attendo 8 secondi per l'avvio del backend...
timeout /t 8 /nobreak

echo.
echo [2/2] Avvio Frontend React (porta 3001)...
echo.

:: Avvia il frontend in una nuova finestra
start "Frontend - Gestionale" cmd /k "cd /d %~dp0frontend && npm start"

:: Aspetta 20 secondi per la compilazione React
echo Attendo 20 secondi per la compilazione React...
timeout /t 20 /nobreak

echo.
echo ========================================
echo   GESTIONALE AVVIATO CON SUCCESSO!
echo ========================================
echo.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:3001
echo API Docs: http://localhost:8000/docs
echo.
echo Verifica che entrambe le finestre siano aperte:
echo - "Backend - Gestionale"  (Python/FastAPI)
echo - "Frontend - Gestionale" (React/npm)
echo.
echo ATTENZIONE: Non chiudere quelle finestre!
echo Per fermare, chiudi le finestre Backend e Frontend.
echo.

:: Apri il browser dopo 3 secondi
timeout /t 3 /nobreak
start http://localhost:3001

echo.
echo Browser aperto su http://localhost:3001
echo.
pause
