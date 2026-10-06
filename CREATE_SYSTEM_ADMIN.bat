@echo off
setlocal
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
  echo Virtual environment not found.
  pause
  exit /b 1
)
call "venv\Scripts\activate.bat"
python manage.py create_system_admin
pause
