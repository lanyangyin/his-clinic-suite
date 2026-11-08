#!/usr/bin/env bash
# 数据库备份（Linux/macOS）
set -euo pipefail
cd "$(dirname "$0")"

mkdir -p backups
ts="$(date +%Y%m%d_%H%M%S)"
cp his.db "backups/his_${ts}.db"
echo "备份完成: backups/his_${ts}.db"
