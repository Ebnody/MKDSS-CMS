@echo off
setlocal
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
  echo Creating Python virtual environment...
  python -m venv venv
  if errorlevel 1 goto :fail
)
call "venv\Scripts\activate.bat"
echo Installing application dependencies...
python -m pip install --upgrade pip
if errorlevel 1 goto :fail
python -m pip install -r requirements.txt
if errorlevel 1 goto :fail
if not exist ".env" (
  copy /Y ".env.example" ".env" >nul
  echo.
  echo .env was created from .env.example.
  echo Edit .env and set DJANGO_SECRET_KEY, then run SETUP_MKDSS.bat again.
  pause
  exit /b 0
)
echo Applying database migrations...
python manage.py migrate
if errorlevel 1 goto :fail
echo Collecting static UI assets...
python manage.py collectstatic --noinput
if errorlevel 1 goto :fail
echo.
echo MKDSS setup completed successfully.
echo Next: run CREATE_SYSTEM_ADMIN.bat, then START_MKDSS.bat
pause
exit /b 0
:fail
echo.
echo MKDSS setup failed. Review the error above.
pause
exit /b 1
