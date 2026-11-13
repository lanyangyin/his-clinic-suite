@echo off
setlocal
cd /d "%~dp0"

net session >nul 2>&1
if errorlevel 1 goto no_admin

schtasks /end /tn "HIS-Server" >nul 2>&1
schtasks /delete /tn "HIS-Server" /f
if errorlevel 1 goto delete_failed
echo Removed startup task: HIS-Server
pause
exit /b 0

:no_admin
echo [ERROR] Run this script as Administrator.
pause
exit /b 1

:delete_failed
echo [ERROR] Failed to delete the startup task.
pause
exit /b 1
