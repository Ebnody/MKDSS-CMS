@echo off
setlocal
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
  echo Virtual environment not found.
  echo Create it with: py -3.12 -m venv venv
  pause
  exit /b 1
)
if not exist ".env" (
  copy /Y ".env.example" ".env" >nul
  echo Created .env from .env.example. Edit it and set DJANGO_SECRET_KEY before continuing.
  pause
  exit /b 1
)
call "venv\Scripts\activate.bat"
python manage.py migrate
if errorlevel 1 goto :fail
python manage.py collectstatic --noinput
if errorlevel 1 goto :fail
if "%MKDSS_PORT%"=="" set MKDSS_PORT=8000
python -m waitress --host=0.0.0.0 --port=%MKDSS_PORT% config.wsgi:application
goto :eof
:fail
echo.
echo MKDSS startup failed. Review the error above.
pause
exit /b 1
