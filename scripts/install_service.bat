@echo off
setlocal
cd /d "%~dp0"

net session >nul 2>&1
if errorlevel 1 goto no_admin

if not exist "tools\nssm.exe" goto no_nssm
if not exist "logs" mkdir "logs"

"tools\nssm.exe" install HISServer "%~dp0his-server.exe"
"tools\nssm.exe" set HISServer AppDirectory "%~dp0"
"tools\nssm.exe" set HISServer Start SERVICE_AUTO_START
"tools\nssm.exe" set HISServer AppStdout "%~dp0logs\server.log"
"tools\nssm.exe" set HISServer AppStderr "%~dp0logs\server.log"
"tools\nssm.exe" start HISServer
if errorlevel 1 goto install_failed

echo Installed and started service: HISServer
echo Manage: services.msc / logs\server.log
pause
exit /b 0

:no_admin
echo [ERROR] Run this script as Administrator.
pause
exit /b 1

:no_nssm
echo [ERROR] tools\nssm.exe not found.
echo Download NSSM from https://nssm.cc and place nssm.exe in tools\.
echo Alternatively use install_autostart.bat (Task Scheduler).
pause
exit /b 1

:install_failed
echo [ERROR] Failed to install or start the service.
pause
exit /b 1
