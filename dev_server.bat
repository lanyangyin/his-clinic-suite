@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" goto no_venv

echo Starting HIS server (source mode)...
echo URL:    http://127.0.0.1:8001
echo Admin:  http://127.0.0.1:8001/admin
echo Close this window to stop the server.
".venv\Scripts\python.exe" scripts\run_server.py
set "RC=%ERRORLEVEL%"
pause
exit /b %RC%

:no_venv
echo [ERROR] .venv not found.
echo Run: py -3.12 -m venv .venv
echo Then install dependencies before starting the server.
pause
exit /b 1
