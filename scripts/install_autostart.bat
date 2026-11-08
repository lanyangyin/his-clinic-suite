@echo off
chcp 65001 >nul
cd /d "%~dp0"

net session >nul 2>&1
if errorlevel 1 (
    echo [错误] 请右键“以管理员身份运行”本脚本
    pause
    exit /b 1
)

schtasks /create /tn "HIS-Server" /tr "\"%~dp0his-server.exe\"" /sc onstart /ru SYSTEM /rl HIGHEST /f
if errorlevel 1 (
    echo [错误] 创建开机启动任务失败
    pause
    exit /b 1
)
schtasks /run /tn "HIS-Server"
echo.
echo 已创建开机启动任务 HIS-Server 并立即启动
echo 管理：taskschd.msc
pause
