@echo off
REM ================================================================
REM Script per escludere node_modules da OneDrive
REM ================================================================
REM
REM I file "null" trovati sono nelle librerie npm (node_modules).
REM Questi file sono legittimi ma causano problemi a OneDrive.
REM
REM La soluzione e' escludere node_modules dalla sincronizzazione.
REM ================================================================

echo.
echo ================================================================
echo ESCLUSIONE NODE_MODULES DA ONEDRIVE
echo ================================================================
echo.
echo I seguenti file problematici sono stati trovati in node_modules:
echo   - frontend\node_modules\...\null.js
echo   - frontend\node_modules\...\null\ (directory)
echo.
echo Questi sono file LEGITTIMI delle librerie JavaScript ma
echo causano problemi di sincronizzazione con OneDrive.
echo.
echo SOLUZIONE: Escludere node_modules da OneDrive
echo.
echo ================================================================
echo.

REM Ottieni il percorso corrente
set "PROJECT_DIR=%~dp0"
set "NODE_MODULES_DIR=%PROJECT_DIR%frontend\node_modules"

echo Directory da escludere: %NODE_MODULES_DIR%
echo.

REM Verifica che la directory esista
if not exist "%NODE_MODULES_DIR%" (
    echo [ERRORE] Directory node_modules non trovata!
    echo.
    pause
    exit /b 1
)

echo Per escludere node_modules da OneDrive, hai 2 opzioni:
echo.
echo OPZIONE 1 - Attributo FILE (Consigliato):
echo ============================================
echo 1. Apri Esplora File
echo 2. Vai in: %NODE_MODULES_DIR%
echo 3. Tasto destro sulla cartella "node_modules"
echo 4. Proprieta ^> Avanzate
echo 5. Deseleziona "File pronto per l'archiviazione"
echo 6. Applica a questa cartella, sottocartelle e file
echo.
echo.
echo OPZIONE 2 - Impostazioni OneDrive (Alternativa):
echo ================================================
echo 1. Tasto destro sull'icona OneDrive nella system tray
echo 2. Impostazioni ^> Account ^> Scegli cartelle
echo 3. Deseleziona "frontend\node_modules"
echo 4. OK
echo.
echo.
echo NOTA: Dopo l'esclusione, node_modules NON verra' piu' sincronizzato.
echo       Questo e' NORMALE e DESIDERATO per progetti di sviluppo.
echo.
echo ================================================================
echo.

REM Prova a impostare l'attributo automaticamente
echo Tentativo di impostare attributo automaticamente...
echo.

attrib +U "%NODE_MODULES_DIR%" /S /D 2>nul

if errorlevel 1 (
    echo [AVVISO] Non e' stato possibile impostare l'attributo automaticamente.
    echo           Usa OPZIONE 1 manualmente.
) else (
    echo [OK] Attributo impostato! OneDrive dovrebbe escludere node_modules.
    echo.
    echo Verifica:
    echo 1. Tasto destro su node_modules ^> Proprieta
    echo 2. Controlla che "File pronto per l'archiviazione" sia deselezionato
)

echo.
echo ================================================================
echo.
echo ALTERNATIVA: Se continui ad avere problemi:
echo.
echo 1. Sposta il progetto FUORI da OneDrive:
echo    - Crea C:\Projects\pythonpro
echo    - Sposta il progetto li
echo    - node_modules non sara' piu' in OneDrive
echo.
echo 2. Usa Git per il backup (non OneDrive):
echo    - git add .
echo    - git commit -m "backup"
echo    - git push
echo.
echo ================================================================
echo.

pause
