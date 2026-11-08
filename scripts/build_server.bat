@echo off
chcp 65001 >nul
cd /d "%~dp0\.."

if not exist ".venv\Scripts\python.exe" (
    echo [错误] 未找到虚拟环境，请先执行 uv sync
    pause
    exit /b 1
)

echo [1/4] 清理旧构建...
if exist "build\his-server" rmdir /s /q "build\his-server"
if exist "dist\his-server" rmdir /s /q "dist\his-server"
if exist "dist\his-server.zip" del /q "dist\his-server.zip"

echo [2/4] PyInstaller 打包服务端（约 2~4 分钟）...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --name his-server --onedir --paths . ^
  --add-data "alembic;alembic" ^
  --add-data "alembic.ini;." ^
  --add-data "app\modules\admin\templates;app\modules\admin\templates" ^
  scripts\server_entry.py
if errorlevel 1 (
    echo [错误] 打包失败
    pause
    exit /b 1
)

echo [3/4] 写入配置文件与运维脚本...
copy /Y "config.ini" "dist\his-server\config.ini" >nul
copy /Y "backup.bat" "dist\his-server\backup.bat" >nul
copy /Y "scripts\install_service.bat" "dist\his-server\install_service.bat" >nul
copy /Y "scripts\uninstall_service.bat" "dist\his-server\uninstall_service.bat" >nul
copy /Y "scripts\install_autostart.bat" "dist\his-server\install_autostart.bat" >nul
copy /Y "scripts\uninstall_autostart.bat" "dist\his-server\uninstall_autostart.bat" >nul

echo [4/4] 生成绿色 zip 包...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path 'dist\his-server\*' -DestinationPath 'dist\his-server.zip' -Force"
if errorlevel 1 (
    echo [错误] 压缩失败
    pause
    exit /b 1
)

echo.
echo 完成：dist\his-server.zip
echo 部署：解压后编辑 config.ini（端口/密钥），双击 his-server.exe 即可（无需安装 Python）
pause
