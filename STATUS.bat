@echo off
REM ==================================
REM   STATUS GESTIONALE
REM ==================================

echo.
echo ========================================
echo   GESTIONALE - Status Sistema
echo ========================================
echo.

cd /d "%~dp0"

docker compose ps

echo.
echo ========================================
echo   TEST ENDPOINTS
echo ========================================
echo.

echo [*] Test Frontend...
curl -s -o nul -w "Frontend (3001): HTTP %%{http_code}\n" http://localhost:3001/healthz --max-time 3

echo [*] Test Backend...
curl -s -o nul -w "Backend (8000):  HTTP %%{http_code}\n" http://localhost:8000/health --max-time 3

echo.
echo ========================================
echo   ACCESSI
echo ========================================
echo.
echo Frontend:  http://localhost:3001
echo Backend:   http://localhost:8000
echo API Docs:  http://localhost:8000/docs
echo Database:  localhost:5433
echo Redis:     localhost:6379
echo.

pause
