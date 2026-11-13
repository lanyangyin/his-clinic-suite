#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON="${HIS_PYTHON:-.venv/bin/python}"
if [ ! -x "$PYTHON" ]; then
  echo "缺少 Python 虚拟环境：$PYTHON" >&2
  echo "可设置 HIS_PYTHON=/path/to/venv/bin/python" >&2
  exit 1
fi

export HIS_HOST="${HIS_HOST:-0.0.0.0}"
export HIS_PORT="${HIS_PORT:-8001}"
export TZ="${TZ:-Asia/Shanghai}"

exec "$PYTHON" scripts/run_server.py
