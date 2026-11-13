@echo off
setlocal
cd /d "%~dp0\.."

if not exist ".venv\Scripts\python.exe" goto no_venv

echo [1/4] Cleaning old build...
if exist "build\his-server" rmdir /s /q "build\his-server"
if exist "dist\his-server" rmdir /s /q "dist\his-server"
if exist "dist\his-server.zip" del /q "dist\his-server.zip"

echo [2/4] Running PyInstaller...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --name his-server --onedir --paths . ^
  --add-data "alembic;alembic" ^
  --add-data "alembic.ini;." ^
  --add-data "app\modules\admin\templates;app\modules\admin\templates" ^
  scripts\server_entry.py
if errorlevel 1 goto build_failed

echo [3/4] Copying config and maintenance scripts...
copy /Y "config.release.ini" "dist\his-server\config.ini" >nul
copy /Y "backup.bat" "dist\his-server\backup.bat" >nul
copy /Y "scripts\install_service.bat" "dist\his-server\install_service.bat" >nul
copy /Y "scripts\uninstall_service.bat" "dist\his-server\uninstall_service.bat" >nul
copy /Y "scripts\install_autostart.bat" "dist\his-server\install_autostart.bat" >nul
copy /Y "scripts\uninstall_autostart.bat" "dist\his-server\uninstall_autostart.bat" >nul

echo [4/4] Creating zip...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path 'dist\his-server\*' -DestinationPath 'dist\his-server.zip' -Force"
if errorlevel 1 goto zip_failed

echo.
echo Done: dist\his-server.zip
pause
exit /b 0

:no_venv
echo [ERROR] .venv not found.
echo Run: py -3.12 -m venv .venv
pause
exit /b 1

:build_failed
echo [ERROR] PyInstaller build failed.
pause
exit /b 1

:zip_failed
echo [ERROR] Zip creation failed.
pause
exit /b 1
