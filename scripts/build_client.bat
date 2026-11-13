@echo off
setlocal
cd /d "%~dp0\.."

if not exist ".venv\Scripts\python.exe" goto no_venv

".venv\Scripts\python.exe" -c "import PySide6" 2>nul
if errorlevel 1 goto no_pyside

echo [1/4] Cleaning old build...
if exist "build\his-client" rmdir /s /q "build\his-client"
if exist "dist\his-client" rmdir /s /q "dist\his-client"
if exist "dist\his-client.zip" del /q "dist\his-client.zip"

echo [2/4] Running PyInstaller...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --windowed --name his-client --onedir --paths . his_client\__main__.py
if errorlevel 1 goto build_failed

echo [3/4] Copying client config...
copy /Y "his_client\config.ini" "dist\his-client\config.ini" >nul

echo [4/4] Creating zip...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path 'dist\his-client\*' -DestinationPath 'dist\his-client.zip' -Force"
if errorlevel 1 goto zip_failed

echo.
echo Done: dist\his-client.zip
pause
exit /b 0

:no_venv
echo [ERROR] .venv not found.
echo Run: py -3.12 -m venv .venv
pause
exit /b 1

:no_pyside
echo [ERROR] PySide6 is not installed.
echo Install client dependencies first.
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
