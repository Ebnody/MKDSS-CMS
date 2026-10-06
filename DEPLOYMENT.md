# MKDSS Deployment Guide

## Windows
Install a supported Python version (Django 6.0 officially supports Python 3.12–3.14). Create the virtual environment and install `requirements.txt`.

1. `py -3.12 -m venv venv`
2. `venv\Scripts\activate`
3. `python -m pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and set a real `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, and optional LibreOffice path.
5. `python manage.py migrate`
6. `python manage.py createsuperuser`
7. `python manage.py collectstatic --noinput`
8. Start Waitress with `scripts\start_waitress.bat` after setting `MKDSS_PORT`.

## LAN access
Bind Waitress to `0.0.0.0:<port>` and allow that TCP port through Windows Firewall only for the intended LAN profile. Do not expose the application directly to the Internet.

## Initial role
After creating the first login, use the Django admin or the System Admin panel to assign the explicit `SYSTEM_ADMIN` profile role and department as appropriate. A Django superuser does not automatically receive application-role permissions.

## Backup
Use `scripts\backup.bat` or an equivalent controlled backup job. Back up the SQLite database, originals, previews and configuration. Test restoration regularly.

## LibreOffice
Install LibreOffice on the server if Office previews are required. Set `LIBREOFFICE_PATH` to the `soffice.exe` executable. Conversion is invoked with `shell=False`, a controlled temporary directory and a timeout; originals are preserved.

## Production
Set `DJANGO_DEBUG=False`. Use a long random secret key. Set `ALLOWED_HOSTS`. HTTPS can be added later at the Windows server/reverse-proxy layer.

## Initial System Admin

After migrations, create the first application System Admin with:

`python manage.py create_system_admin --username YOUR_USERNAME`

If the username already exists, the command promotes that account's application role to **System Admin**. If it does not exist, the command creates it and securely prompts for a password. The application role is stored in `UserProfile.role`; a Django superuser is not required for normal MKDSS administration.


## Windows quick start

1. Create/activate the virtual environment and install `requirements.txt`.
2. Copy `.env.example` to `.env` and set `DJANGO_SECRET_KEY`.
3. Run `CREATE_SYSTEM_ADMIN.bat` to create the first application System Admin account, or run `python manage.py create_system_admin`.
4. Run `START_MKDSS.bat`. It applies migrations, collects static assets, and starts the local server on port 8000.

Static assets are served through WhiteNoise so the application UI remains available with `DEBUG=False`. User-uploaded compliance files are not exposed as public static/media URLs.
