# Linux 与 Android Termux 部署

## 结论

- **Linux：可以，推荐。**
- **Android Termux + Ubuntu：可以，但只建议小门诊/演示/备用。**
- **真正的 `chroot` 需要 Android 已 root；未 root 用 `proot-distro`，不是 chroot，速度慢一些。**
- 服务端不需要 PySide6，桌面客户端不要装进 Termux。

## 已在 Linux 实测

环境：

- WSL Ubuntu 24.04
- Python 3.12.3
- SQLite
- arm64/x86_64 均可

结果：

```text
数据库结构: created
Uvicorn running on http://127.0.0.1:8002
GET /health -> 200 {"status":"ok","version":"0.92.1"}
GET /admin -> 302
```

注意：项目放在 WSL 的 `/mnt/d` 下时，`/mnt/d` 的 9p 文件系统可能让 Alembic 建库卡住；把项目放到 Linux 本机目录（如 `/opt/his`、`/tmp/his-test`）正常。生产不要放 Windows 挂载盘。

## Linux 部署

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv sqlite3

sudo mkdir -p /opt/his
sudo chown "$USER":"$USER" /opt/his
# 把项目复制到 /opt/his

cd /opt/his
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-server.txt

cp config.ini config.local.ini
# 修改 config.local.ini 的 [server] host/port、[clinic] 名称

HIS_HOST=0.0.0.0 HIS_PORT=8001 ./scripts/run_server_linux.sh
```

首次启动会自动：

1. 建表/升级到 Alembic head
2. 创建 `admin/admin123`
3. 创建 `director/director123`

生产环境务必尽快改默认密码。

### systemd

```bash
sudo cp deploy/his-server.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now his-server
sudo systemctl status his-server
curl http://127.0.0.1:8001/health
```

### 反向代理/HTTPS

不要把 8001 直接暴露公网。建议：

- 内网：直接访问 `http://服务器IP:8001`
- 远程：Tailscale/WireGuard
- 公网：Caddy/Nginx + HTTPS

Basic Auth 走明文 HTTP 不安全。

## Android Termux

### 方案 A：proot-distro（推荐，免 root）

```bash
pkg update
pkg install -y proot-distro
proot-distro install ubuntu
proot-distro login ubuntu

apt update
apt install -y python3.12 python3.12-venv sqlite3 tzdata
```

把项目复制到 Ubuntu 的 `~/his`，不要放 `/sdcard`：

```bash
cd ~/his
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-server.txt
HIS_HOST=0.0.0.0 HIS_PORT=8001 ./scripts/run_server_linux.sh
```

Termux 侧：

```bash
termux-wake-lock
```

关闭 Android 电池优化，允许 Termux 后台运行。

### 方案 B：chroot（需要 root）

有 root 的 Android 可以挂载 Ubuntu rootfs 后：

```bash
mount -t proc proc /path/to/ubuntu/proc
mount -t sysfs sys /path/to/ubuntu/sys
mount --bind /dev /path/to/ubuntu/dev
mount --bind /dev/pts /path/to/ubuntu/dev/pts
chroot /path/to/ubuntu /bin/bash
```

没有 root 就不要用 `chroot`，用 proot-distro。

### Android 限制

- 端口不要用 80/443；非 root 不能绑定 1024 以下，使用 8001。
- 数据库必须放 rootfs 的 ext4 内，不要放 `/sdcard`：
  - `/sdcard` 是 FUSE，SQLite WAL/文件锁不可靠
- Android 12+ 的 phantom process killer 可能杀掉后台 Python：
  - 关闭电池优化
  - 必要时用 adb 关闭 phantom 限制
- 手机休眠/热 throttling 会影响稳定性
- 不建议多台收费/医生终端同时高频写入；SQLite 单写者
- 定期备份 `his.db`，先 `PRAGMA wal_checkpoint(TRUNCATE)` 或 `sqlite3 .backup`

## 配置

`config.local.ini` 示例：

```ini
[server]
host = 0.0.0.0
port = 8001

[clinic]
name = 邹治国中西医结合诊所
address = ...
phone = ...
```

环境变量优先：

```bash
HIS_HOST=0.0.0.0
HIS_PORT=8001
HIS_DATABASE_URL=sqlite:////opt/his/his.db
HIS_SECRET_KEY=换成长随机串
TZ=Asia/Shanghai
```

## 健康检查

```bash
curl http://127.0.0.1:8001/health
# {"status":"ok","version":"0.92.1"}
```

## 什么时候不该用 Android

- 多医生/多收费窗口并发
- 需要 7x24 稳定运行
- 需要公网访问
- 数据量大、备份要求高

这些场景用 Linux 小主机、迷你 PC、树莓派或云服务器；Android 只做演示/应急备用。
