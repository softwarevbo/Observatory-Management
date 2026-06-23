@echo off
cd /d "%~dp0"
echo ====================================================
echo Starting IIA Management-own System Backup...
echo ====================================================
.venv_win\Scripts\python.exe backup_restore.py backup
echo ====================================================
echo Backup process completed.
echo ====================================================
pause
