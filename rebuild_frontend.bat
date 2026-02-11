@echo off
REM ========================================
REM REBUILD FRONTEND - Fix Riavvio
REM ========================================
echo.
echo ========================================
echo  REBUILD FRONTEND CONTAINER
echo ========================================
echo.

echo [1/5] Stopping frontend container...
docker-compose stop frontend
docker-compose rm -f frontend

echo.
echo [2/5] Removing old image...
docker rmi pythonpro-frontend:latest

echo.
echo [3/5] Rebuilding image (this may take 3-5 minutes)...
cd frontend
docker build --no-cache -t pythonpro-frontend:latest .
cd ..

echo.
echo [4/5] Starting frontend container...
docker-compose up -d frontend

echo.
echo [5/5] Waiting for frontend to be ready (40 seconds)...
timeout /t 40 /nobreak >nul

echo.
echo ========================================
echo  TESTING FRONTEND
echo ========================================
curl -I http://localhost:3001

echo.
echo ========================================
echo  REBUILD COMPLETE
echo ========================================
echo.
echo Frontend should be accessible at: http://localhost:3001
echo.
pause
