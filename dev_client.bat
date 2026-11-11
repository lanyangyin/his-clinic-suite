@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo [错误] 未找到 .venv，请先执行：py -3.12 -m venv .venv
    pause
    exit /b 1
)
echo 启动 HIS 桌面客户端（源码模式）...
".venv\Scripts\python.exe" -m his_client %*
pause
