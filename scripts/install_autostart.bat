@echo off
setlocal
cd /d "%~dp0"

net session >nul 2>&1
if errorlevel 1 goto no_admin

schtasks /create /tn "HIS-Server" /tr "\"%~dp0his-server.exe\"" /sc onstart /ru SYSTEM /rl HIGHEST /f
if errorlevel 1 goto create_failed
schtasks /run /tn "HIS-Server"
echo Created startup task HIS-Server and started it.
echo Manage: taskschd.msc
pause
exit /b 0

:no_admin
echo [ERROR] Run this script as Administrator.
pause
exit /b 1

:create_failed
echo [ERROR] Failed to create the startup task.
pause
exit /b 1
