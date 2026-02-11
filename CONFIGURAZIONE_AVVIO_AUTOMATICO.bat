@echo off
echo ========================================
echo   CONFIGURAZIONE AVVIO AUTOMATICO
echo ========================================
echo.

REM Verifica se lo script è eseguito come amministratore
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRORE] Questo script richiede privilegi di amministratore!
    echo Fai clic destro e seleziona "Esegui come amministratore"
    pause
    exit /b 1
)

echo [OK] Privilegi amministratore verificati
echo.

REM Ottieni il percorso della directory corrente
set "SCRIPT_DIR=%~dp0"
set "STARTUP_SCRIPT=%SCRIPT_DIR%AVVIO_RAPIDO.bat"
set "MONITOR_SCRIPT=%SCRIPT_DIR%MONITOR_SISTEMA.bat"

echo Directory progetto: %SCRIPT_DIR%
echo.

REM Crea Task Scheduler per avvio automatico
echo Configurazione Task Scheduler per avvio automatico...
echo.

REM Task 1: Avvio sistema all'accensione del PC
schtasks /create /tn "Gestionale_Avvio_Automatico" /tr "\"%STARTUP_SCRIPT%\"" /sc onlogon /rl highest /f
if %errorlevel% equ 0 (
    echo [OK] Task avvio automatico creato
) else (
    echo [ERRORE] Impossibile creare task avvio automatico
)

REM Task 2: Monitoring ogni 5 minuti
schtasks /create /tn "Gestionale_Monitor" /tr "\"%MONITOR_SCRIPT%\"" /sc minute /mo 5 /rl highest /f
if %errorlevel% equ 0 (
    echo [OK] Task monitoring creato
) else (
    echo [ERRORE] Impossibile creare task monitoring
)

REM Configura Docker Desktop per avvio automatico
echo.
echo Configurazione Docker Desktop per avvio automatico...
reg add "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run" /v "Docker Desktop" /t REG_SZ /d "C:\Program Files\Docker\Docker\Docker Desktop.exe" /f
if %errorlevel% equ 0 (
    echo [OK] Docker Desktop configurato per avvio automatico
) else (
    echo [ERRORE] Impossibile configurare Docker Desktop
)

echo.
echo ========================================
echo   CONFIGURAZIONE COMPLETATA!
echo ========================================
echo.
echo Task Scheduler configurato:
echo - Avvio automatico al login
echo - Monitoring ogni 5 minuti
echo - Docker Desktop avvio automatico
echo.
echo Per visualizzare i task:
echo   1. Apri "Task Scheduler" (Utilità di pianificazione)
echo   2. Cerca "Gestionale_Avvio_Automatico" e "Gestionale_Monitor"
echo.
echo Per disabilitare l'avvio automatico:
echo   schtasks /delete /tn "Gestionale_Avvio_Automatico" /f
echo   schtasks /delete /tn "Gestionale_Monitor" /f
echo.

pause
