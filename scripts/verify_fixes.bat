@echo off
REM =================================================================
REM SCRIPT DI VERIFICA COMPLETA FIX E REGRESSIONI
REM =================================================================
REM Esegue test automatizzati per verificare tutti i fix implementati
REM e testare eventuali regressioni.
REM =================================================================

setlocal enabledelayedexpansion
set TIMESTAMP=%date:~-4%-%date:~3,2%-%date:~0,2%_%time:~0,2%-%time:~3,2%-%time:~6,2%
set TIMESTAMP=%TIMESTAMP: =0%
set REPORT_FILE=..\_fix_results\reports\verification_%TIMESTAMP%.txt
set BACKEND_URL=http://localhost:8001

if not exist ..\_fix_results mkdir ..\_fix_results
if not exist ..\_fix_results\logs mkdir ..\_fix_results\logs
if not exist ..\_fix_results\reports mkdir ..\_fix_results\reports

echo ================================================================ > %REPORT_FILE%
echo REPORT DI VERIFICA FIX - %TIMESTAMP% >> %REPORT_FILE%
echo ================================================================ >> %REPORT_FILE%
echo. >> %REPORT_FILE%

echo ========================================
echo VERIFICA COMPLETA FIX - REGRESSIONE TEST
echo ========================================
echo Report: %REPORT_FILE%
echo.

REM ==========================================
REM TEST 1: Verifica Health Endpoints
REM ==========================================
echo [TEST 1] Verificando health endpoints...
curl -f %BACKEND_URL%/health > nul 2>&1
if %errorlevel% equ 0 (
    echo    ✓ Backend health: PASS >> %REPORT_FILE%
    echo    ✓ Backend health: PASS
) else (
    echo    ✗ Backend health: FAIL >> %REPORT_FILE%
    echo    ✗ Backend health: FAIL
)

curl -f http://localhost:3001/ > nul 2>&1
if %errorlevel% equ 0 (
    echo    ✓ Frontend health: PASS >> %REPORT_FILE%
    echo    ✓ Frontend health: PASS
) else (
    echo    ✗ Frontend health: FAIL >> %REPORT_FILE%
    echo    ✗ Frontend health: FAIL
)

REM ==========================================
REM TEST 2: Verifica Database Connection
REM ==========================================
echo [TEST 2] Verificando connessione database...
docker compose exec -T db pg_isready -U admin -d gestionale > nul 2>&1
if %errorlevel% equ 0 (
    echo    ✓ Database connection: PASS >> %REPORT_FILE%
    echo    ✓ Database connection: PASS
) else (
    echo    ✗ Database connection: FAIL >> %REPORT_FILE%
    echo    ✗ Database connection: FAIL
)

REM ==========================================
REM TEST 3: Test CRUD Collaboratori
REM ==========================================
echo [TEST 3] Testando CRUD Collaboratori...

REM CREATE
curl -s -X POST %BACKEND_URL%/collaborators/ ^
  -H "Content-Type: application/json" ^
  -d "{\"first_name\":\"Verify\",\"last_name\":\"Test\",\"email\":\"verify.test@test.com\",\"phone\":\"9876543210\",\"position\":\"Tester\"}" ^
  > ..\_fix_results\logs\test_create_collaborator.json

findstr "id" ..\_fix_results\logs\test_create_collaborator.json > nul 2>&1
if %errorlevel% equ 0 (
    echo    ✓ CREATE Collaboratore: PASS >> %REPORT_FILE%
    echo    ✓ CREATE Collaboratore: PASS
) else (
    echo    ✗ CREATE Collaboratore: FAIL >> %REPORT_FILE%
    echo    ✗ CREATE Collaboratore: FAIL
)

REM READ
curl -s %BACKEND_URL%/collaborators/ > ..\_fix_results\logs\test_read_collaborators.json
findstr "first_name" ..\_fix_results\logs\test_read_collaborators.json > nul 2>&1
if %errorlevel% equ 0 (
    echo    ✓ READ Collaboratori: PASS >> %REPORT_FILE%
    echo    ✓ READ Collaboratori: PASS
) else (
    echo    ✗ READ Collaboratori: FAIL >> %REPORT_FILE%
    echo    ✗ READ Collaboratori: FAIL
)

REM ==========================================
REM TEST 4: Test CRUD Progetti
REM ==========================================
echo [TEST 4] Testando CRUD Progetti...

curl -s -X POST %BACKEND_URL%/projects/ ^
  -H "Content-Type: application/json" ^
  -d "{\"name\":\"Test Project\",\"description\":\"Test verification project\",\"start_date\":\"2025-01-01\",\"end_date\":\"2025-12-31\",\"status\":\"active\"}" ^
  > ..\_fix_results\logs\test_create_project.json

findstr "id" ..\_fix_results\logs\test_create_project.json > nul 2>&1
if %errorlevel% equ 0 (
    echo    ✓ CREATE Progetto: PASS >> %REPORT_FILE%
    echo    ✓ CREATE Progetto: PASS
) else (
    echo    ✗ CREATE Progetto: FAIL >> %REPORT_FILE%
    echo    ✗ CREATE Progetto: FAIL
)

REM ==========================================
REM TEST 5: Verifica Container Status
REM ==========================================
echo [TEST 5] Verificando status container...
docker compose ps > ..\_fix_results\logs\container_status.txt

findstr "running" ..\_fix_results\logs\container_status.txt | findstr "backend" > nul 2>&1
if %errorlevel% equ 0 (
    echo    ✓ Backend container: RUNNING >> %REPORT_FILE%
    echo    ✓ Backend container: RUNNING
) else (
    echo    ✗ Backend container: NOT RUNNING >> %REPORT_FILE%
    echo    ✗ Backend container: NOT RUNNING
)

findstr "running" ..\_fix_results\logs\container_status.txt | findstr "frontend" > nul 2>&1
if %errorlevel% equ 0 (
    echo    ✓ Frontend container: RUNNING >> %REPORT_FILE%
    echo    ✓ Frontend container: RUNNING
) else (
    echo    ✗ Frontend container: NOT RUNNING >> %REPORT_FILE%
    echo    ✗ Frontend container: NOT RUNNING
)

findstr "running" ..\_fix_results\logs\container_status.txt | findstr "db" > nul 2>&1
if %errorlevel% equ 0 (
    echo    ✓ Database container: RUNNING >> %REPORT_FILE%
    echo    ✓ Database container: RUNNING
) else (
    echo    ✗ Database container: NOT RUNNING >> %REPORT_FILE%
    echo    ✗ Database container: NOT RUNNING
)

findstr "running" ..\_fix_results\logs\container_status.txt | findstr "backup_scheduler" > nul 2>&1
if %errorlevel% equ 0 (
    echo    ✓ Backup scheduler: RUNNING >> %REPORT_FILE%
    echo    ✓ Backup scheduler: RUNNING
) else (
    echo    ✗ Backup scheduler: NOT RUNNING >> %REPORT_FILE%
    echo    ✗ Backup scheduler: NOT RUNNING
)

REM ==========================================
REM TEST 6: Verifica Logs Errori
REM ==========================================
echo [TEST 6] Verificando assenza errori critici nei logs...
docker compose logs --tail=100 backend > ..\_fix_results\logs\backend_test_logs.txt

findstr /I "ERROR CRITICAL" ..\_fix_results\logs\backend_test_logs.txt > nul 2>&1
if %errorlevel% neq 0 (
    echo    ✓ Nessun errore critico: PASS >> %REPORT_FILE%
    echo    ✓ Nessun errore critico: PASS
) else (
    echo    ✗ Trovati errori critici: FAIL >> %REPORT_FILE%
    echo    ✗ Trovati errori critici: FAIL
)

REM ==========================================
REM SUMMARY
REM ==========================================
echo. >> %REPORT_FILE%
echo ================================================================ >> %REPORT_FILE%
echo RIEPILOGO VERIFICA >> %REPORT_FILE%
echo ================================================================ >> %REPORT_FILE%
echo Timestamp: %TIMESTAMP% >> %REPORT_FILE%
echo Report salvato in: %REPORT_FILE% >> %REPORT_FILE%
echo ================================================================ >> %REPORT_FILE%

echo.
echo ========================================
echo VERIFICA COMPLETATA
echo ========================================
echo Report salvato in: %REPORT_FILE%
echo.
