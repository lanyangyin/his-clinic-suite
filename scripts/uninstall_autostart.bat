@echo off
chcp 65001 >nul
cd /d "%~dp0"

net session >nul 2>&1
if errorlevel 1 (
    echo [错误] 请右键“以管理员身份运行”本脚本
    pause
    exit /b 1
)

schtasks /end /tn "HIS-Server" >nul 2>&1
schtasks /delete /tn "HIS-Server" /f
echo 开机启动任务已删除：HIS-Server
pause
