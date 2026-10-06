@echo off
setlocal
cd /d "%~dp0.."
if not exist venv py -3.12 -m venv venv
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if not exist .env (
    copy .env.example .env >nul
    for /f "delims=" %%S in ('python -c "import secrets; print(secrets.token_urlsafe(64))"') do powershell -NoProfile -Command "(Get-Content .env) -replace '^DJANGO_SECRET_KEY=.*$', 'DJANGO_SECRET_KEY=%%S' | Set-Content .env"
)
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check
if not exist data\documents\originals mkdir data\documents\originals
if not exist data\documents\previews mkdir data\documents\previews
if not exist data\backups mkdir data\backups
echo Setup complete. Create the first application System Admin with CREATE_SYSTEM_ADMIN.bat.
