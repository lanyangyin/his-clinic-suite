@echo off
setlocal
cd /d "%~dp0"

net session >nul 2>&1
if errorlevel 1 goto no_admin

if not exist "tools\nssm.exe" goto no_nssm

"tools\nssm.exe" stop HISServer
"tools\nssm.exe" remove HISServer confirm
echo Stopped and removed service: HISServer
pause
exit /b 0

:no_admin
echo [ERROR] Run this script as Administrator.
pause
exit /b 1

:no_nssm
echo [ERROR] tools\nssm.exe not found.
echo If the server was started by Task Scheduler, run uninstall_autostart.bat.
pause
exit /b 1
