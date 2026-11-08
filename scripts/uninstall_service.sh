#!/usr/bin/env bash
# 卸载 systemd 服务（需 sudo）
set -euo pipefail

if [ "${EUID:-$(id -u)}" -ne 0 ]; then
    echo "[错误] 请用 sudo 运行本脚本"
    exit 1
fi

systemctl disable --now his.service 2>/dev/null || true
rm -f /etc/systemd/system/his.service
systemctl daemon-reload
echo "服务已移除：his.service"
