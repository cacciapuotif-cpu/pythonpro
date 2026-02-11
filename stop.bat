@echo off
REM ==================================
REM   STOP GESTIONALE
REM ==================================

echo.
echo ========================================
echo   GESTIONALE - Stop Sistema
echo ========================================
echo.

cd /d "%~dp0"

echo [*] Arresto servizi...
docker compose down

if %errorlevel% equ 0 (
    echo.
    echo [OK] Sistema arrestato correttamente
) else (
    echo.
    echo [!] Errore durante l'arresto
)

echo.
pause
