@echo off
REM Script batch per Windows - Gestionale Pythonpro

if "%1"=="" goto help
if "%1"=="help" goto help
if "%1"=="api" goto api
if "%1"=="frontend" goto frontend
if "%1"=="test" goto test
if "%1"=="audit" goto audit
if "%1"=="openapi-diff" goto openapi-diff
if "%1"=="clean" goto clean
if "%1"=="install" goto install

:help
echo ===================================================================
echo Gestionale Pythonpro - Comandi Disponibili
echo ===================================================================
echo.
echo Backend:
echo   commands api          - Avvia backend FastAPI (uvicorn)
echo   commands test         - Esegui test backend (pytest)
echo.
echo Frontend:
echo   commands frontend     - Avvia frontend React
echo.
echo Utility:
echo   commands audit        - Esegui audit repository (duplicati/orfani)
echo   commands openapi-diff - Confronta schema OpenAPI con skeleton
echo   commands clean        - Pulisci file temporanei
echo   commands install      - Installa dipendenze (backend + frontend)
echo.
echo ===================================================================
goto end

:api
echo Avvio backend FastAPI...
cd backend
call venv\Scripts\activate.bat
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
goto end

:frontend
echo Avvio frontend React...
cd frontend
npm start
goto end

:test
echo Esecuzione test backend...
cd backend
call venv\Scripts\activate.bat
pytest tests/ -v --tb=short
goto end

:audit
echo Esecuzione audit repository...
backend\venv\Scripts\python.exe scripts\audit_repo.py
goto end

:openapi-diff
echo Confronto schema OpenAPI...
backend\venv\Scripts\python.exe scripts\diff_openapi.py
goto end

:clean
echo Pulizia file temporanei...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
del /s /q *.pyc 2>nul
del /s /q *.pyo 2>nul
echo Pulizia completata
goto end

:install
echo Installazione dipendenze backend...
cd backend
call venv\Scripts\activate.bat
pip install -r requirements.txt
cd ..
echo Installazione dipendenze frontend...
cd frontend
npm install
cd ..
echo Installazione completata
goto end

:end
