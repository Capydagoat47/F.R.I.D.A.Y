@echo off
setlocal
cd /d "%~dp0"
set "FRIDAY_AUTO_OPEN=0"
start "FRIDAY Server" cmd /k ""%~dp0friday_env\Scripts\python.exe" "%~dp0server.py""
timeout /t 4 /nobreak >nul
start "" "http://127.0.0.1:5000"
