@echo off
REM ============================================================
REM SCRIPT DI RIAVVIO FRONTEND
REM ============================================================
REM Ferma e riavvia il frontend React per applicare modifiche
REM ============================================================

echo ====================================
echo   RIAVVIO FRONTEND REACT
echo ====================================
echo.

echo [1/4] Terminazione processi Node...
tasklist | findstr "node.exe" >nul
if %errorlevel% equ 0 (
    echo Trovati processi Node, termino...
    taskkill /F /IM node.exe >nul 2>&1
    timeout /t 2 /nobreak >nul
    echo OK - Processi terminati
) else (
    echo Nessun processo Node in esecuzione
)
echo.

echo [2/4] Pulizia cache frontend...
cd frontend
if exist "node_modules\.cache" (
    rmdir /s /q "node_modules\.cache" >nul 2>&1
    echo OK - Cache .cache pulita
)
if exist "build" (
    rmdir /s /q "build" >nul 2>&1
    echo OK - Directory build pulita
)
echo.

echo [3/4] Avvio frontend sulla porta 3001...
echo IMPORTANTE: Questa finestra rimarra' aperta con il server.
echo Per fermare, premi Ctrl+C in questa finestra.
echo.
echo Compilazione in corso...
echo (Potrebbe richiedere 30-60 secondi)
echo.

set PORT=3001
npm start

REM Il comando sopra blocca qui finché non viene interrotto
echo.
echo Frontend arrestato.
pause
