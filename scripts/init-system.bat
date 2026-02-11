@echo off
REM Script di inizializzazione per Windows

echo 🚀 Inizializzazione Sistema Gestionale...

REM Controlla se Docker è in esecuzione
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker non è in esecuzione. Avvia Docker Desktop e riprova.
    pause
    exit /b 1
)

echo ✅ Docker è attivo

REM Ferma eventuali container in esecuzione
echo 🛑 Fermando container esistenti...
docker-compose down -v

REM Rimuove immagini vecchie per forzare rebuild
echo 🧹 Pulizia immagini vecchie...
docker-compose build --no-cache

REM Avvia tutti i servizi
echo 🏗️ Avviando servizi...
docker-compose up -d

REM Attende che i servizi siano healthy
echo ⏳ Attendendo che i servizi siano pronti...
timeout /t 10 /nobreak >nul

REM Controlla lo stato dei servizi
echo 🔍 Controllo stato servizi...
docker-compose ps

REM Controlla health check del backend
echo 🩺 Test connessione backend...
for /l %%i in (1,1,10) do (
    curl -f http://localhost:8001/health >nul 2>&1
    if %errorlevel% equ 0 (
        echo ✅ Backend connesso!
        goto frontend_check
    ) else (
        echo ⏳ Tentativo %%i/10 - Attendendo backend...
        timeout /t 3 /nobreak >nul
    )
)

:frontend_check
REM Controlla se il frontend è raggiungibile
echo 🌐 Test connessione frontend...
for /l %%i in (1,1,10) do (
    curl -f http://localhost:3001 >nul 2>&1
    if %errorlevel% equ 0 (
        echo ✅ Frontend connesso!
        goto success
    ) else (
        echo ⏳ Tentativo %%i/10 - Attendendo frontend...
        timeout /t 3 /nobreak >nul
    )
)

:success
echo.
echo 🎉 Sistema avviato con successo!
echo.
echo 📋 Accesso al gestionale:
echo    Frontend: http://localhost:3001
echo    API Docs: http://localhost:8001/docs
echo    Health:   http://localhost:8001/health
echo.
echo 🔧 Comandi utili:
echo    docker-compose logs backend   # Log backend
echo    docker-compose logs frontend  # Log frontend
echo    docker-compose ps            # Stato servizi
echo    docker-compose down          # Ferma tutto
echo.
echo Premere un tasto per aprire il browser...
pause >nul
start http://localhost:3001