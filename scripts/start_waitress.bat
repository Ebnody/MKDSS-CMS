@echo off
setlocal
cd /d "%~dp0.."
if not exist "venv\Scripts\python.exe" (
  echo Virtual environment not found.
  echo Create it with: py -3.12 -m venv venv
  pause
  exit /b 1
)
if "%MKDSS_PORT%"=="" set MKDSS_PORT=8000
venv\Scripts\python.exe -m waitress --host=0.0.0.0 --port=%MKDSS_PORT% config.wsgi:application
