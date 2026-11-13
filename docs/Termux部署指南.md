# Android Termux 独立部署指南（Ubuntu + proot/chroot）

适用：Android 10+，arm64 手机/平板。  
服务端版本：HIS 1.1.1。  
目标：手机跑服务端，局域网 Windows 客户端可以连接。

> Termux 只跑服务端，不要安装 PySide6 客户端。  
> **真正的 chroot 需要 root；没有 root 用 proot-distro，本文默认用 proot-distro。**

---

## 第 0 步：准备

### 手机

- Android 10 以上
- arm64（`aarch64`）
- 4 GB 内存以上，建议 6 GB
- 至少 8 GB 空闲存储
- 固定局域网 Wi-Fi，手机 IP 例如 `192.168.1.80`

### 软件

Termux 请从 **F-Droid** 或 Termux GitHub Releases 安装，不要用应用商店的老版本。

### 需要知道

```text
手机 IP：192.168.1.80
端口：8001
管理台：http://192.168.1.80:8001/admin
客户端连接地址：http://192.168.1.80:8001
```

### 重要限制

- 手机不是 7×24 服务器
- 多台收费/医生终端同时高频写入不建议
- 源码/备份可以放 `/sdcard`；**SQLite 数据库不建议放 `/sdcard`**（原因见下文）
- Termux 被系统杀死后服务会停
- 公网访问必须加 VPN/HTTPS，不要直接暴露 8001

---

## 第 1 步：安装 Termux 和基础工具

打开 Termux：

```bash
pkg update
pkg upgrade -y
pkg install -y proot-distro git curl nano openssh net-tools
```

检查架构：

```bash
uname -m
```

应为 `aarch64`。

---

## 第 2 步：安装 Ubuntu

```bash
proot-distro install ubuntu
proot-distro login ubuntu
```

进入 Ubuntu 后提示符类似：

```text
root@localhost:~#
```

检查：

```bash
cat /etc/os-release
uname -m
```

应为 Ubuntu 24.04 左右、aarch64。

---

## 第 3 步：安装 Ubuntu 依赖

```bash
apt update
apt upgrade -y
apt install -y \
  python3 python3-venv python3-pip \
  sqlite3 git curl ca-certificates tzdata nano tmux
```

检查：

```bash
python3 --version
sqlite3 --version
```

Python 应为 3.12.x。

设置时区：

```bash
ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime
echo "Asia/Shanghai" > /etc/timezone
date
```

---

## 第 4 步：获取项目

推荐放 `/root/his`。源码可以放 `/sdcard`，但 `.venv` 和 SQLite 数据库不要放 `/sdcard`。

```bash
cd /root
git clone https://github.com/lanyangyin/his-clinic-suite.git his
cd /root/his
ls
```

私有仓库用 SSH 时，先在 Termux/Ubuntu 配好 GitHub SSH key。

如果不用 Git，也可以在 Termux 里通过共享存储把源码复制到 rootfs；源码目录可以放 `/sdcard`，但 `.venv`、`his.db`、`his.db-wal` 不要放。

---

## 第 5 步：创建虚拟环境

```bash
cd /root/his
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -r requirements-server.txt
```

检查：

```bash
.venv/bin/python -c "import fastapi, sqlalchemy, alembic; print('deps ok')"
```

不要安装 `pyside6`，服务端不需要。

---

## 第 6 步：生成配置和密钥

```bash
cd /root/his
cp config.release.ini config.local.ini
.venv/bin/python -c "import secrets; print(secrets.token_urlsafe(48))"
```

编辑：

```bash
nano config.local.ini
```

修改：

```ini
[server]
host = 0.0.0.0
port = 8001
secret_key = 粘贴随机字符串

[database]
url =

[clinic]
name = 你的诊所名称
address =
phone =
```

说明：

- `0.0.0.0` 允许同一 Wi-Fi 的电脑访问
- 端口用 8001，不要用 80/443
- 数据库默认 `/root/his/his.db`
- **数据库不要放到 `/sdcard`**

```bash
chmod 600 config.local.ini
```

---

## 第 7 步：首次启动

前台启动：

```bash
cd /root/his
HIS_HOST=0.0.0.0 HIS_PORT=8001 ./scripts/run_server_linux.sh
```

首次启动会自动：

1. 建库
2. 迁移到最新版本
3. 创建 `admin/admin123`
4. 创建 `director/director123`
5. 启动 Uvicorn

看到：

```text
Uvicorn running on http://0.0.0.0:8001
```

---

## 第 8 步：验证

### 手机内部

另开一个 Termux 会话（不要关掉服务）：

```bash
curl http://127.0.0.1:8001/health
```

应返回：

```json
{"status":"ok","version":"1.1.1"}
```

### 查看手机 IP

在 Termux（不是 Ubuntu）执行：

```bash
ifconfig wlan0
```

或：

```bash
ip addr show wlan0
```

找到 `inet 192.168.x.x`。

### 从电脑访问

Windows 浏览器：

```text
http://192.168.1.80:8001/admin
```

登录：

```text
admin / admin123
```

登录后立即改密码，创建医生、收费员等账号。

### 客户端连接

Windows 客户端 `config.ini`：

```ini
[server]
url = http://192.168.1.80:8001
```

手机和电脑必须在同一个 Wi-Fi，且路由器没有开启 AP 隔离。

---

## 第 9 步：后台运行

### 方式 A：tmux（推荐，简单）

Ubuntu 内：

```bash
tmux new -s his
cd /root/his
HIS_HOST=0.0.0.0 HIS_PORT=8001 ./scripts/run_server_linux.sh
```

按 `Ctrl+B`，再按 `D` 脱离。

回到会话：

```bash
tmux attach -t his
```

### 方式 B：nohup

```bash
cd /root/his
nohup env HIS_HOST=0.0.0.0 HIS_PORT=8001 \
  ./scripts/run_server_linux.sh \
  > /root/his/server.log 2>&1 &
```

查看：

```bash
ps aux | grep run_server
tail -f /root/his/server.log
```

### 保持 Termux 存活

在 Termux 侧执行：

```bash
termux-wake-lock
```

并：

- 关闭 Termux 的电池优化
- 允许后台运行
- 不要从最近任务里划掉 Termux

Android 12+ 可能杀 phantom process，必要时用 ADB 调整（不保证所有机型）：

```bash
adb shell settings put global settings_enable_monitor_phantom_procs false
```

---

## 第 10 步：备份

在 Ubuntu 内：

```bash
mkdir -p /root/his/backups
cd /root/his
sqlite3 his.db ".backup '/root/his/backups/his_$(date +%Y%m%d_%H%M%S).db'"
```

查看：

```bash
ls -lh /root/his/backups
```

从 Termux 复制到共享存储：

```bash
termux-setup-storage
```

先确认 proot rootfs 路径：

```bash
ls /data/data/com.termux/files/usr/var/lib/proot-distro/installed-rootfs/ubuntu/root/his/backups
```

然后：

```bash
cp /data/data/com.termux/files/usr/var/lib/proot-distro/installed-rootfs/ubuntu/root/his/backups/*.db \
   /sdcard/Download/
```

不要在数据库运行时只 `cp his.db`，WAL 模式下可能不一致；用 `sqlite3 .backup`。

---

## 关于 /sdcard 的准确说法

### 可以放

- 项目源码
- 文档
- 导出的备份文件
- 安装包/压缩包

### 不建议放

- `his.db`
- `his.db-wal`
- `his.db-shm`
- `.venv`
- 大量频繁读写的文件

原因：

- Android `/sdcard` 是 FUSE/模拟存储，不是普通 ext4
- SQLite WAL 需要可靠的共享内存和文件锁，FUSE 上可能失败
- 可能出现 `database is locked`、`disk I/O error`、异常断电后损坏
- Android 11+ 的分区存储/权限会让 Termux 访问 `/sdcard` 更复杂
- `.venv` 里有符号链接和可执行权限，放 `/sdcard` 容易出问题

如果只是想把源码放 `/sdcard` 节省内部空间，可以；但数据库和虚拟环境放 rootfs：

```text
/root/his         源码 + .venv + his.db + his.db-wal
/sdcard/Download  只放备份/安装包
```

“能启动”不等于“可靠”。门诊数据不要拿 SQLite 在 `/sdcard` 上冒险。

## 第 11 步：升级

```bash
# 先备份
cd /root/his
sqlite3 his.db ".backup '/root/his/backups/before_upgrade.db'"

# 停服务（tmux 里 Ctrl+C）
cd /root/his
git pull
.venv/bin/pip install -r requirements-server.txt

# 重新启动
HIS_HOST=0.0.0.0 HIS_PORT=8001 ./scripts/run_server_linux.sh
```

数据库迁移启动时自动执行。

---

## 第 12 步：可选 root chroot

只有手机已 root 才考虑。没有 root 直接用 proot-distro，不要强行 chroot。

```bash
mount -t proc proc /path/to/ubuntu/proc
mount -t sysfs sys /path/to/ubuntu/sys
mount --bind /dev /path/to/ubuntu/dev
mount --bind /dev/pts /path/to/ubuntu/dev/pts
chroot /path/to/ubuntu /bin/bash
```

chroot 里同样需要 Python、虚拟环境、项目、配置；Android 没有 systemd，仍要用 tmux/nohup 保活。

风险：

- root 操作可能损坏系统
- 内核/挂载差异
- 手机厂商限制
- 不建议作为生产服务器

---

## 第 13 步：验收清单

- [ ] Termux 从 F-Droid/GitHub 安装
- [ ] Ubuntu 24.04 aarch64
- [ ] Python 3.12
- [ ] `requirements-server.txt` 安装成功
- [ ] `config.local.ini` 改了 secret_key
- [ ] `/health` 返回 1.1.1
- [ ] 电脑能打开 `http://手机IP:8001/admin`
- [ ] admin 默认密码已改
- [ ] 创建医生/收费员账号
- [ ] Windows 客户端能连接
- [ ] termux-wake-lock 已开
- [ ] 电池优化已关闭
- [ ] 备份已测试
- [ ] SQLite 数据库不在 `/sdcard`

---

## 常见问题

### `bad interpreter`

脚本是 CRLF 换行。当前仓库已统一 LF；如果从旧副本复制，执行：

```bash
sed -i 's/\r$//' scripts/run_server_linux.sh
```

### 电脑打不开

- 手机和电脑同一 Wi-Fi
- 路由器没开 AP 隔离
- 服务监听 `0.0.0.0`，不是 `127.0.0.1`
- 端口 8001
- 手机防火墙/安全软件
- 先用手机浏览器访问 `http://127.0.0.1:8001/health`

### `/health` 404

旧版本没有该接口；确认版本 ≥ 1.0，或访问 `/admin`。

### 数据库 locked

- SQLite 数据库不要放 `/sdcard`
- 只运行一个服务进程
- 用 `.backup`，不要直接复制 WAL 数据库
- 关闭其他打开数据库的工具

### proot 很慢

正常。proot 是用户态模拟，性能低于原生 Linux。  
如果长期使用，建议换迷你 PC/树莓派/云服务器。

### 手机重启后服务没了

Termux/Termux:Boot 可以配置自启，但 Android 厂商限制很多，不保证。  
重要场景建议用 Linux 小主机。

---

## 最短命令汇总

Termux：

```bash
pkg update
pkg install -y proot-distro git curl
proot-distro install ubuntu
proot-distro login ubuntu
```

Ubuntu：

```bash
apt update
apt install -y python3 python3-venv python3-pip sqlite3 git curl tzdata tmux
cd /root
git clone https://github.com/lanyangyin/his-clinic-suite.git his
cd /root/his
python3 -m venv .venv
.venv/bin/pip install -r requirements-server.txt
cp config.release.ini config.local.ini
# 编辑 config.local.ini：host=0.0.0.0 port=8001 secret_key
HIS_HOST=0.0.0.0 HIS_PORT=8001 ./scripts/run_server_linux.sh
```

另一个 Termux 会话：

```bash
curl http://127.0.0.1:8001/health
```
