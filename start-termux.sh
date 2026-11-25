#!/usr/bin/env bash
# HIS Termux 启动脚本（Termux 外层或 proot Ubuntu 内均可）
#
# 用法（在 /sdcard/HIS 下）：
#   bash ./start-termux.sh             前台启动
#   bash ./start-termux.sh --background 后台启动
#   bash ./start-termux.sh status      查看状态
#   bash ./start-termux.sh stop        停止后台进程
#   bash ./start-termux.sh logs        跟踪日志
#
# 环境变量：
#   HIS_PYTHON           Python 解释器，默认 /root/his-venv/bin/python
#   HIS_HOST             监听地址，默认 0.0.0.0
#   HIS_PORT             端口，默认 8001
#   HIS_DATABASE_URL     数据库 URL；不设置则用 config.ini / config.local.ini
#   HIS_TERMUX_NO_REEXEC 设为 1 时，即使在外层 Termux 也不自动进入 proot
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
PID_FILE="$ROOT/run/termux.pid"
LOG_FILE="$ROOT/server.log"

usage() {
    sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'
}

# 在 Termux 外层时，自动进入已安装的 Ubuntu，再执行本脚本。
if [ "${HIS_TERMUX_NO_REEXEC:-0}" != "1" ] \
    && command -v proot-distro >/dev/null 2>&1 \
    && { [ "$(uname -o 2>/dev/null || true)" = "Android" ] || [ ! -f /etc/os-release ]; }; then
    if command -v termux-wake-lock >/dev/null 2>&1; then
        termux-wake-lock || true
    fi
    echo "[HIS] Entering proot Ubuntu..."
    exec proot-distro login ubuntu --bind /sdcard:/sdcard -- \
        bash -lc "cd \"$ROOT\" && exec bash ./start-termux.sh $*"
fi

# 外层 Termux 的唤醒锁只在外层有效；Ubuntu 内通常没有该命令。
if command -v termux-wake-lock >/dev/null 2>&1; then
    termux-wake-lock || true
fi

# 帮助不需要 Python 环境
case "${1:-}" in
    -h|--help|help)
        usage
        exit 0
        ;;
esac

PYTHON="${HIS_PYTHON:-/root/his-venv/bin/python}"
if [ ! -x "$PYTHON" ]; then
    for candidate in "$ROOT/.venv/bin/python" "$(command -v python3 2>/dev/null || true)"; do
        if [ -n "$candidate" ] && [ -x "$candidate" ]; then
            PYTHON="$candidate"
            break
        fi
    done
fi
if [ ! -x "$PYTHON" ]; then
    echo "[HIS] Python not found."
    echo "      Create the venv first:"
    echo "      python3 -m venv /root/his-venv"
    echo "      /root/his-venv/bin/pip install -r $ROOT/requirements-server.txt"
    echo "      Or set HIS_PYTHON=/path/to/python"
    exit 1
fi

if ! "$PYTHON" -c "import fastapi, sqlalchemy, alembic" >/dev/null 2>&1; then
    echo "[HIS] Python dependencies are missing for: $PYTHON"
    echo "      $PYTHON -m pip install -r $ROOT/requirements-server.txt"
    exit 1
fi

export HIS_HOST="${HIS_HOST:-0.0.0.0}"
export HIS_PORT="${HIS_PORT:-8001}"
export TZ="${TZ:-Asia/Shanghai}"

# sdcard 模式下使用更保守的 SQLite 日志/同步策略；内部存储不强制。
if [ -z "${HIS_DATABASE_URL:-}" ] && [ -d "$ROOT/data" ]; then
    export HIS_DATABASE_URL="sqlite:///$ROOT/data/his.db"
fi
if [[ "${HIS_DATABASE_URL:-}" == *"/sdcard/"* ]]; then
    export HIS_SQLITE_JOURNAL="${HIS_SQLITE_JOURNAL:-DELETE}"
    export HIS_SQLITE_SYNCHRONOUS="${HIS_SQLITE_SYNCHRONOUS:-FULL}"
fi

start_foreground() {
    echo "[HIS] root:   $ROOT"
    echo "[HIS] python: $PYTHON"
    echo "[HIS] listen: http://$HIS_HOST:$HIS_PORT"
    [ -n "${HIS_DATABASE_URL:-}" ] && echo "[HIS] db:     $HIS_DATABASE_URL"
    exec "$PYTHON" scripts/run_server.py
}

start_background() {
    mkdir -p "$ROOT/run"
    if [ -f "$PID_FILE" ]; then
        old_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
        if [ -n "$old_pid" ] && kill -0 "$old_pid" 2>/dev/null; then
            echo "[HIS] already running: PID $old_pid"
            exit 0
        fi
        rm -f "$PID_FILE"
    fi
    echo "[HIS] starting in background..."
    nohup "$PYTHON" scripts/run_server.py >>"$LOG_FILE" 2>&1 &
    echo $! >"$PID_FILE"
    sleep 2
    if kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "[HIS] started: PID $(cat "$PID_FILE")"
        echo "[HIS] log:     $LOG_FILE"
        echo "[HIS] stop:    bash ./start-termux.sh stop"
    else
        echo "[HIS] failed to start; see $LOG_FILE"
        rm -f "$PID_FILE"
        exit 1
    fi
}

stop_background() {
    if [ ! -f "$PID_FILE" ]; then
        echo "[HIS] not running (pid file missing)"
        return 0
    fi
    pid="$(cat "$PID_FILE")"
    if [ -z "$pid" ] || ! kill -0 "$pid" 2>/dev/null; then
        rm -f "$PID_FILE"
        echo "[HIS] not running"
        return 0
    fi
    kill "$pid" 2>/dev/null || true
    for _ in $(seq 1 20); do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.2
    done
    if kill -0 "$pid" 2>/dev/null; then
        echo "[HIS] process did not exit: PID $pid"
        return 1
    fi
    rm -f "$PID_FILE"
    echo "[HIS] stopped"
}

case "${1:-}" in
    ""|--foreground|-f)
        start_foreground
        ;;
    -d|--background)
        start_background
        ;;
    stop)
        stop_background
        ;;
    status)
        if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
            echo "[HIS] running: PID $(cat "$PID_FILE")"
        else
            echo "[HIS] not running"
        fi
        ;;
    logs)
        touch "$LOG_FILE"
        tail -f "$LOG_FILE"
        ;;
    -h|--help|help)
        usage
        ;;
    *)
        echo "[HIS] unknown argument: $1"
        usage
        exit 2
        ;;
esac
