@echo off
REM =================================================================
REM SCRIPT ESECUZIONE TESTS BACKEND
REM =================================================================

echo ========================================
echo ESECUZIONE UNIT TESTS BACKEND
echo ========================================
echo.

REM Esegui test con coverage
python -m pytest test_main.py -v --cov=. --cov-report=term-missing --cov-report=html

echo.
echo ========================================
echo TEST COMPLETATI
echo ========================================
echo Report HTML coverage: htmlcov/index.html
echo.

pause
