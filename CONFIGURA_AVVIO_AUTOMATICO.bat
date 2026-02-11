@echo off
REM ================================================
REM CONFIGURA AVVIO AUTOMATICO GESTIONALE
REM ================================================

echo Configurazione avvio automatico...
echo.

REM Rimuovi task esistente se presente
schtasks /Delete /TN "GestionaleAvvio" /F >nul 2>&1

REM Crea nuovo task
schtasks /Create /TN "GestionaleAvvio" /TR "%~dp0start.bat" /SC ONLOGON /RL HIGHEST /F

if errorlevel 0 (
    echo.
    echo OK - Avvio automatico configurato.
    echo.
    echo Il gestionale si avvierà automaticamente al login.
    echo.
    echo Per disabilitare: schtasks /Delete /TN "GestionaleAvvio" /F
) else (
    echo.
    echo ERRORE - Esegui come Amministratore.
)

echo.
pause
