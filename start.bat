@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" goto no_venv

echo [1/3] Checking database schema...
".venv\Scripts\python.exe" scripts\init_db.py
if errorlevel 1 goto db_failed

echo [2/3] Opening browser...
".venv\Scripts\python.exe" -c "import webbrowser; from app.settings import PORT; webbrowser.open(f'http://127.0.0.1:{PORT}/admin'); webbrowser.open(f'http://127.0.0.1:{PORT}/docs')"

echo [3/3] Starting HIS server. Close this window to stop.
".venv\Scripts\python.exe" scripts\run_server.py
set "RC=%ERRORLEVEL%"
pause
exit /b %RC%

:no_venv
echo [ERROR] .venv not found.
echo Run: py -3.12 -m venv .venv
pause
exit /b 1

:db_failed
echo [ERROR] Database initialization failed. See output above.
pause
exit /b 1
