#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -x ".venv/bin/python" ]; then
  echo "缺少 .venv，请先创建：python3.12 -m venv .venv && .venv/bin/pip install -r requirements-server.txt" >&2
  exit 1
fi

export HIS_HOST="${HIS_HOST:-0.0.0.0}"
export HIS_PORT="${HIS_PORT:-8001}"
export TZ="${TZ:-Asia/Shanghai}"

exec .venv/bin/python scripts/run_server.py
