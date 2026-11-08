@echo off
chcp 65001 >nul
cd /d "%~dp0"

net session >nul 2>&1
if errorlevel 1 (
    echo [错误] 请右键“以管理员身份运行”本脚本
    pause
    exit /b 1
)

if exist "tools\nssm.exe" (
    "tools\nssm.exe" stop HISServer
    "tools\nssm.exe" remove HISServer confirm
    echo 服务已停止并移除：HISServer
) else (
    echo [提示] 未找到 tools\nssm.exe，若用任务计划启动请运行 uninstall_autostart.bat
)
pause
