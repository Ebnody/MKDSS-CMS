@echo off
setlocal
call .venv\Scripts\activate
python manage.py backup_system
