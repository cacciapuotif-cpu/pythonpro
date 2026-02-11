@echo off
REM ========================================
REM   MONITOR SISTEMA - Controllo Salute
REM ========================================
REM Questo script verifica che il sistema sia attivo
REM e lo riavvia se necessario

REM Non mostrare output (esecuzione silenziosa)
set SILENT=1

REM Verifica se Docker è in esecuzione
docker info >nul 2>&1
if %errorlevel% neq 0 (
    REM Docker non è attivo, esci
    exit /b 0
)

REM Verifica lo stato dei container
docker ps --filter "name=pythonpro" --filter "status=running" --format "{{.Names}}" | findstr /C:"pythonpro-backend" >nul 2>&1
set BACKEND_RUNNING=%errorlevel%

docker ps --filter "name=pythonpro" --filter "status=running" --format "{{.Names}}" | findstr /C:"pythonpro-frontend" >nul 2>&1
set FRONTEND_RUNNING=%errorlevel%

docker ps --filter "name=pythonpro" --filter "status=running" --format "{{.Names}}" | findstr /C:"pythonpro-db" >nul 2>&1
set DB_RUNNING=%errorlevel%

REM Se tutti i servizi sono attivi, esci
if %BACKEND_RUNNING% equ 0 if %FRONTEND_RUNNING% equ 0 if %DB_RUNNING% equ 0 (
    exit /b 0
)

REM Almeno un servizio non è attivo, riavvia
cd /d "%~dp0"
docker-compose up -d >nul 2>&1

REM Attendi 30 secondi
timeout /t 30 /nobreak >nul

REM Esegui migrazioni database
docker exec pythonpro-db-1 psql -U admin -d gestionale -c "ALTER TABLE collaborators ADD COLUMN IF NOT EXISTS documento_identita_filename VARCHAR(255), ADD COLUMN IF NOT EXISTS documento_identita_path VARCHAR(500), ADD COLUMN IF NOT EXISTS documento_identita_uploaded_at TIMESTAMP, ADD COLUMN IF NOT EXISTS curriculum_filename VARCHAR(255), ADD COLUMN IF NOT EXISTS curriculum_path VARCHAR(500), ADD COLUMN IF NOT EXISTS curriculum_uploaded_at TIMESTAMP;" >nul 2>&1

exit /b 0
