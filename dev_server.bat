@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo [错误] 未找到 .venv，请先执行：py -3.12 -m venv .venv
    pause
    exit /b 1
)
echo 启动 HIS 服务端（源码模式）...
echo 地址：http://127.0.0.1:8001
echo 管理台：http://127.0.0.1:8001/admin
echo 关闭此窗口即停止服务。
".venv\Scripts\python.exe" scripts\run_server.py
pause
