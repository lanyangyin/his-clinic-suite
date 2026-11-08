@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [错误] 未找到虚拟环境 .venv
    echo 请先在本目录执行：uv sync
    pause
    exit /b 1
)

echo [1/3] 检查/升级数据库结构...
".venv\Scripts\python.exe" scripts\init_db.py
if errorlevel 1 (
    echo [错误] 数据库初始化失败，请查看上方输出
    pause
    exit /b 1
)

echo [2/3] 打开浏览器...
".venv\Scripts\python.exe" -c "import webbrowser; from app.settings import PORT; webbrowser.open(f'http://127.0.0.1:{PORT}/admin'); webbrowser.open(f'http://127.0.0.1:{PORT}/docs')"

echo [3/3] 启动 HIS 服务（关闭此窗口即停止服务；局域网访问地址见窗口输出）
".venv\Scripts\python.exe" scripts\run_server.py

pause
