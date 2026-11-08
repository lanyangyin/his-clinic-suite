#!/usr/bin/env bash
# 打包 Linux 服务端（PyInstaller onedir，需在 Linux 上执行）
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -x ".venv/bin/python" ]; then
    echo "[错误] 未找到 .venv，请先执行: uv sync"
    exit 1
fi

echo "[1/4] 清理旧构建..."
rm -rf build/his-server dist/his-server dist/his-server-linux.zip

echo "[2/4] PyInstaller 打包（约 2~4 分钟）..."
".venv/bin/python" -m PyInstaller --noconfirm --clean --name his-server --onedir --paths . \
    --add-data "alembic:alembic" \
    --add-data "alembic.ini:." \
    --add-data "app/modules/admin/templates:app/modules/admin/templates" \
    scripts/server_entry.py

echo "[3/4] 写入配置与运维脚本..."
cp config.ini dist/his-server/config.ini
cp backup.sh dist/his-server/backup.sh
cp scripts/install_service.sh scripts/uninstall_service.sh dist/his-server/
chmod +x dist/his-server/his-server dist/his-server/backup.sh dist/his-server/install_service.sh dist/his-server/uninstall_service.sh

echo "[4/4] 生成压缩包..."
cd dist
if command -v zip >/dev/null 2>&1; then
    zip -r his-server-linux.zip his-server >/dev/null
else
    tar -czf his-server-linux.tar.gz his-server
fi
echo "完成：dist/his-server-linux.zip（或 .tar.gz）"
