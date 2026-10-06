@echo off
setlocal
call venv\Scripts\activate
python apply_ui_notifications.py
if errorlevel 1 (
  echo.
  echo Patch failed. Review the message above.
  pause
  exit /b 1
)
echo.
echo Patch applied successfully.
echo Run: python manage.py migrate
pause
