#!/usr/bin/env bash
# 服务端启动（Linux/macOS）：初始化数据库并启动服务
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x ".venv/bin/python" ]; then
    echo "[错误] 未找到 .venv，请先执行: uv sync"
    exit 1
fi

echo "[1/2] 检查/升级数据库结构..."
".venv/bin/python" scripts/init_db.py

echo "[2/2] 启动 HIS 服务（Ctrl+C 停止）"
echo "管理台: http://127.0.0.1:${HIS_PORT:-8000}/admin"
exec ".venv/bin/python" scripts/run_server.py
