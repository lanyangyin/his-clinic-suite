@echo off
setlocal
cd /d "%~dp0"

if not exist "his.db" goto no_db
if not exist "backups" mkdir "backups"

if exist ".venv\Scripts\python.exe" goto python_backup

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ts = Get-Date -Format 'yyyyMMdd_HHmmss'; Copy-Item -LiteralPath 'his.db' -Destination ('backups\his_' + $ts + '.db') -Force; Write-Host ('Backup: backups\his_' + $ts + '.db')"
goto done

:python_backup
".venv\Scripts\python.exe" -c "import sqlite3,datetime,pathlib; root=pathlib.Path('.'); dst=root/'backups'/('his_'+datetime.datetime.now().strftime('%%Y%%m%%d_%%H%%M%%S')+'.db'); src=sqlite3.connect('his.db'); out=sqlite3.connect(str(dst)); src.backup(out); out.close(); src.close(); print('Backup: '+str(dst))"
goto done

:no_db
echo [ERROR] his.db not found.
pause
exit /b 1

:done
echo Keep backups on another disk. Close this window when done.
pause
exit /b 0
