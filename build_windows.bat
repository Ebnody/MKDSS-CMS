@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 (
  echo Python Launcher was not found. Install Python 3.12 or newer first.
  pause
  exit /b 1
)
py -3.12 -m venv .build-venv
if errorlevel 1 goto failed
.build-venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 goto failed
.build-venv\Scripts\python.exe -m pip install -r requirements-desktop.txt
if errorlevel 1 goto failed
if not exist "assets\mkdss_icon.ico" (
  echo Required application icon not found: assets\mkdss_icon.ico
  goto failed
)
.build-venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name MKDSS_CMS_Desktop --icon "assets\mkdss_icon.ico" --add-data "assets\mkdss_icon.ico;assets" --collect-all webview desktop_client\mkdss_cms_desktop.py
if errorlevel 1 goto failed
echo.
echo Build complete: dist\MKDSS_CMS_Desktop.exe
echo Copy this EXE to each client PC. Configure the server on first launch.
echo Microsoft Edge WebView2 Runtime is required on each client PC.
pause
exit /b 0
:failed
echo Build failed. Review the error messages above.
pause
exit /b 1
