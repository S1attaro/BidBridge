@echo off
REM Download the latest SAM.gov jobs and load them. Safe to run any time.
REM To run it every morning: open Task Scheduler, Create Basic Task, Daily,
REM and pick this file as the program to start.
cd /d "%~dp0"
call .venv\Scripts\activate
python manage.py refresh_jobs
