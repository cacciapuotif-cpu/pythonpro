@echo off
echo ========================================
echo RIAVVIO ONEDRIVE
echo ========================================
echo.

echo Chiusura OneDrive...
taskkill /F /IM OneDrive.exe >nul 2>&1

echo Attendere 3 secondi...
timeout /t 3 /nobreak >nul

echo Riavvio OneDrive...
start "" "%LocalAppData%\Microsoft\OneDrive\OneDrive.exe"

echo.
echo ========================================
echo OneDrive riavviato con successo!
echo ========================================
echo.
echo NOTA: Le cartelle seguenti NON dovrebbero essere sincronizzate:
echo   - frontend\node_modules (dipendenze Node.js)
echo   - backend\venv (ambiente virtuale Python)
echo   - backend\__pycache__ (file Python compilati)
echo.
echo Per escluderle dalla sincronizzazione:
echo 1. Clicca sull'icona OneDrive nella barra delle applicazioni
echo 2. Clicca su Impostazioni ^> Account ^> Scegli cartelle
echo 3. Deseleziona le cartelle sopra indicate
echo.
pause
