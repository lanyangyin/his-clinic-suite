@echo off
chcp 65001 >nul
cd /d "%~dp0"

net session >nul 2>&1
if errorlevel 1 (
    echo [错误] 请右键“以管理员身份运行”本脚本
    pause
    exit /b 1
)

if not exist "tools\nssm.exe" (
    echo [提示] 未找到 tools\nssm.exe
    echo 方式一：从 https://nssm.cc 下载 nssm.exe 放到本目录 tools\ 下，再运行本脚本
    echo 方式二：改用 install_autostart.bat（任务计划开机启动，无需 NSSM）
    pause
    exit /b 1
)

if not exist "logs" mkdir "logs"

"tools\nssm.exe" install HISServer "%~dp0his-server.exe"
"tools\nssm.exe" set HISServer AppDirectory "%~dp0"
"tools\nssm.exe" set HISServer Start SERVICE_AUTO_START
"tools\nssm.exe" set HISServer AppStdout "%~dp0logs\server.log"
"tools\nssm.exe" set HISServer AppStderr "%~dp0logs\server.log"
"tools\nssm.exe" start HISServer

echo.
echo 服务已安装并启动：HISServer（开机自动启动）
echo 管理：services.msc / logs\server.log
pause
