@echo off
REM =================================================================
REM SCRIPT DI SIMULAZIONE RIAVVIO PC E TEST DI PERSISTENZA
REM =================================================================
REM Questo script simula un riavvio PC fermando e riavviando
REM tutti i container Docker, verificando persistenza dati.
REM =================================================================

echo ========================================
echo SIMULAZIONE RIAVVIO PC - TEST PERSISTENZA
echo ========================================
echo.

REM Step 1: Salva stato corrente
echo [1/6] Salvando stato attuale del sistema...
curl -s http://localhost:8000/health > ..\_fix_results\logs\health_before_restart.json
docker-compose ps > ..\_fix_results\logs\containers_before_restart.txt
echo    ✓ Stato salvato

REM Step 2: Crea dati di test
echo [2/6] Creando dati di test per verifica persistenza...
curl -s -X POST http://localhost:8000/collaborators/ ^
  -H "Content-Type: application/json" ^
  -d "{\"first_name\":\"Test\",\"last_name\":\"Restart\",\"email\":\"test.restart@test.com\",\"phone\":\"1234567890\",\"position\":\"Test\"}" ^
  > ..\_fix_results\logs\test_data_created.json
echo    ✓ Dati di test creati

REM Step 3: Stop completo (simula shutdown PC)
echo [3/6] Fermando tutti i container (simula shutdown PC)...
docker-compose stop
echo    ✓ Tutti i container fermati

REM Pausa per simulare PC spento
echo [4/6] Pausa 10 secondi (simula PC spento)...
timeout /t 10 /nobreak > nul
echo    ✓ Pausa completata

REM Step 4: Riavvio (simula boot PC)
echo [5/6] Riavviando container (simula boot PC)...
docker-compose start
echo    ✓ Container riavviati

REM Attendi che i servizi siano pronti
echo [6/6] Attendendo inizializzazione servizi (90s)...
timeout /t 90 /nobreak > nul

REM Verifica salute sistema
echo.
echo ========================================
echo VERIFICA STATO POST-RIAVVIO
echo ========================================
curl -s http://localhost:8000/health > ..\_fix_results\logs\health_after_restart.json
docker-compose ps > ..\_fix_results\logs\containers_after_restart.txt

echo.
echo Testando persistenza dati...
curl -s http://localhost:8000/collaborators/ > ..\_fix_results\logs\data_after_restart.json

echo.
echo ========================================
echo TEST RIAVVIO COMPLETATO
echo ========================================
echo Log salvati in: _fix_results\logs\
echo - health_before_restart.json
echo - health_after_restart.json
echo - containers_before_restart.txt
echo - containers_after_restart.txt
echo - data_after_restart.json
echo ========================================
