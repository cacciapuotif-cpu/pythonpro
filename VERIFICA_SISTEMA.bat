@echo off
echo ========================================
echo   DIAGNOSTICA SISTEMA GESTIONALE
echo ========================================
echo.

REM Verifica Docker
echo [1/6] Verifica Docker Desktop...
docker info >nul 2>&1
if %errorlevel% equ 0 (
    echo   [OK] Docker Desktop attivo
) else (
    echo   [ERRORE] Docker Desktop non attivo!
    echo   Soluzione: Avvia Docker Desktop manualmente
    goto :end
)

echo.
echo [2/6] Verifica container...
docker ps --format "table {{.Names}}\t{{.Status}}" --filter "name=pythonpro"

echo.
echo [3/6] Test connessione Backend...
curl -s -o nul -w "HTTP Status: %%{http_code}\n" http://localhost:8000/health
if %errorlevel% equ 0 (
    echo   [OK] Backend risponde
) else (
    echo   [ERRORE] Backend non risponde
)

echo.
echo [4/6] Test connessione Frontend...
curl -s -o nul -w "HTTP Status: %%{http_code}\n" http://localhost:3001
if %errorlevel% equ 0 (
    echo   [OK] Frontend risponde
) else (
    echo   [ERRORE] Frontend non risponde
)

echo.
echo [5/6] Test connessione Database...
docker exec pythonpro-db-1 psql -U admin -d gestionale -c "SELECT 1;" >nul 2>&1
if %errorlevel% equ 0 (
    echo   [OK] Database connesso
) else (
    echo   [ERRORE] Database non raggiungibile
)

echo.
echo [6/6] Verifica schema database...
docker exec pythonpro-db-1 psql -U admin -d gestionale -c "\d collaborators" | findstr "documento_identita_filename" >nul 2>&1
if %errorlevel% equ 0 (
    echo   [OK] Schema database aggiornato
) else (
    echo   [ERRORE] Schema database non aggiornato
)

echo.
echo ========================================
echo   LOG ULTIMI ERRORI
echo ========================================
echo.
echo --- Backend (ultimi 20 righe) ---
docker logs pythonpro-backend-1 --tail 20 2>&1 | findstr /I "ERROR CRITICAL"
echo.
echo --- Frontend (ultimi 20 righe) ---
docker logs pythonpro-frontend-1 --tail 20 2>&1 | findstr /I "ERROR Failed"

:end
echo.
echo ========================================
echo   DIAGNOSTICA COMPLETATA
echo ========================================
echo.
echo Per vedere tutti i log: docker-compose logs -f
echo Per riavviare sistema: AVVIO_RAPIDO.bat
echo.
pause
