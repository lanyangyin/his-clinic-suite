@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist "backups" mkdir "backups"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ts = Get-Date -Format 'yyyyMMdd_HHmmss'; Copy-Item -LiteralPath 'his.db' -Destination ('backups\his_' + $ts + '.db') -Force; Write-Host ('备份完成：backups\his_' + $ts + '.db')"

echo 提示：建议每天下班前双击本脚本备份一次；把 backups 目录复制到U盘/U云盘更稳妥。
pause
