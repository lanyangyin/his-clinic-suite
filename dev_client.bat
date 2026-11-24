@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" goto no_venv

echo Starting HIS desktop client (source mode)...
echo Keep this window open while the client is running.
".venv\Scripts\python.exe" -m his_client %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" pause
exit /b %RC%

:no_venv
echo [ERROR] .venv not found.
echo Run: py -3.12 -m venv .venv
pause
exit /b 1
