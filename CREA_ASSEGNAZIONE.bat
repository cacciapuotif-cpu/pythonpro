@echo off
echo ========================================
echo   CREA ASSEGNAZIONE - Workaround SQL
echo ========================================
echo.

set /p COLLABORATOR_ID="ID Collaboratore: "
set /p PROJECT_ID="ID Progetto: "
set /p ROLE="Ruolo (es. docente, tutor, progettista): "
set /p HOURS="Ore assegnate: "
set /p START_DATE="Data inizio (YYYY-MM-DD): "
set /p END_DATE="Data fine (YYYY-MM-DD): "
set /p RATE="Tariffa oraria (es. 50.0): "

echo.
echo Creazione assegnazione...
docker exec -i pythonpro-db-1 psql -U admin -d gestionale -c "INSERT INTO assignments (collaborator_id, project_id, role, assigned_hours, start_date, end_date, hourly_rate, created_at, is_active) VALUES (%COLLABORATOR_ID%, %PROJECT_ID%, '%ROLE%', %HOURS%, '%START_DATE% 00:00:00', '%END_DATE% 23:59:59', %RATE%, NOW(), true) RETURNING id, role, assigned_hours;"

if %errorlevel% equ 0 (
    echo.
    echo [OK] Assegnazione creata con successo!
) else (
    echo.
    echo [ERRORE] Impossibile creare l'assegnazione
)

echo.
pause
