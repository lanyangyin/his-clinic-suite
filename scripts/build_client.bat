@echo off
chcp 65001 >nul
cd /d "%~dp0\.."

if not exist ".venv\Scripts\python.exe" (
    echo [错误] 未找到虚拟环境，请先执行 uv sync --extra client
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -c "import PySide6" 2>nul
if errorlevel 1 (
    echo [错误] 未安装客户端依赖 PySide6
    echo 请先执行：uv sync --extra client
    pause
    exit /b 1
)

echo [1/4] 清理旧构建...
if exist "build\his-client" rmdir /s /q "build\his-client"
if exist "dist\his-client" rmdir /s /q "dist\his-client"
if exist "dist\his-client.zip" del /q "dist\his-client.zip"

echo [2/4] PyInstaller 打包（首次约 1~3 分钟）...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --windowed --name his-client --onedir --paths . his_client\__main__.py
if errorlevel 1 (
    echo [错误] 打包失败
    pause
    exit /b 1
)

echo [3/4] 写入客户端配置...
copy /Y "his_client\config.ini" "dist\his-client\config.ini" >nul

echo [4/4] 生成绿色 zip 包...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path 'dist\his-client\*' -DestinationPath 'dist\his-client.zip' -Force"
if errorlevel 1 (
    echo [错误] 压缩失败
    pause
    exit /b 1
)

echo.
echo 完成：dist\his-client.zip
echo 分发：解压到各工作站，编辑 config.ini 的 [server] url 为服务器地址，双击 his-client.exe
pause
