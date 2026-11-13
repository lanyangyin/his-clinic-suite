#!/usr/bin/env bash
# 构建 Termux/Linux 服务端最小源码包（不含客户端/测试/文档大文件）。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(sed -n 's/^APP_VERSION = "\(.*\)"/\1/p' "$ROOT/app/version.py" | tr -d '\r')"
STAGE="$(mktemp -d)"
PKG="$STAGE/his-server"
OUT="$ROOT/dist/his-server-termux-${VERSION}.tar.gz"

cleanup() { rm -rf "$STAGE"; }
trap cleanup EXIT

mkdir -p "$PKG"
cp -a "$ROOT/app" "$PKG/app"
cp -a "$ROOT/alembic" "$PKG/alembic"
cp -a "$ROOT/scripts" "$PKG/scripts"
mkdir -p "$PKG/deploy"
cp -a "$ROOT/deploy/his-server.service" "$PKG/deploy/"
cp "$ROOT/alembic.ini" "$PKG/alembic.ini"
cp "$ROOT/requirements-server.txt" "$PKG/requirements-server.txt"
cp "$ROOT/pyproject.toml" "$PKG/pyproject.toml"
cp "$ROOT/config.release.ini" "$PKG/config.ini"
cp "$ROOT/config.release.ini" "$PKG/config.release.ini"
cp "$ROOT/backup.sh" "$PKG/backup.sh"
cp "$ROOT/docs/Termux部署指南.md" "$PKG/DEPLOY-TERMUX.md"

# 清掉 Python 缓存和本地运行数据
find "$PKG" -type d -name __pycache__ -prune -exec rm -rf {} +
find "$PKG" -type f -name '*.pyc' -delete
rm -rf "$PKG/app/modules/admin/templates/.cache" 2>/dev/null || true

chmod +x "$PKG/scripts/run_server_linux.sh" "$PKG/backup.sh"

mkdir -p "$ROOT/dist"
tar -czf "$OUT" -C "$STAGE" his-server
echo "built: $OUT"
ls -lh "$OUT"
