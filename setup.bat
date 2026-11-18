@echo off
REM First time setup. Double-click to run.
cd /d "%~dp0"
if not exist .venv python -m venv .venv
call .venv\Scripts\activate
pip install -r requirements.txt
if not exist .env copy .env.example .env
python manage.py migrate
python manage.py seed_demo
python manage.py test
pause
