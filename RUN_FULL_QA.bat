@echo off
setlocal
cd /d "%~dp0"
echo ================================================
echo MKDSS COMPLIANCE SYSTEM - FULL QA
echo ================================================
echo.
if not exist "venv\Scripts\python.exe" (
  echo ERROR: venv\Scripts\python.exe was not found.
  echo Run this script from the deployed project with its venv present.
  exit /b 1
)

echo [1/3] Django system check...
venv\Scripts\python.exe manage.py check
if errorlevel 1 goto :fail

echo.
echo [2/3] Migration check...
venv\Scripts\python.exe manage.py migrate
if errorlevel 1 goto :fail

echo.
echo [3/3] Full test suite...
venv\Scripts\python.exe manage.py test
if errorlevel 1 goto :fail

echo.
echo ================================================
echo QA RESULT: PASS
 echo ================================================
exit /b 0

:fail
echo.
echo ================================================
echo QA RESULT: FAIL
echo ================================================
exit /b 1
