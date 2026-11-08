#!/usr/bin/env bash
# 安装为 systemd 服务（Ubuntu/Debian；需 sudo）
set -euo pipefail

if [ "${EUID:-$(id -u)}" -ne 0 ]; then
    echo "[错误] 请用 sudo 运行本脚本"
    exit 1
fi

DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE=/etc/systemd/system/his.service

if [ -x "$DIR/his-server" ]; then
    EXEC="$DIR/his-server"
else
    EXEC="$DIR/.venv/bin/python $DIR/scripts/run_server.py"
fi

cat > "$SERVICE" <<EOF
[Unit]
Description=HIS 门诊部系统
After=network.target

[Service]
Type=simple
WorkingDirectory=$DIR
ExecStart=$EXEC
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now his.service
echo "服务已安装并启动：his.service"
echo "查看状态: systemctl status his"
echo "查看日志: journalctl -u his -f"
