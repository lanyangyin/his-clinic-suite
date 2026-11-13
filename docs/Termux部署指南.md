# Android Termux 部署指南（优先 /sdcard）

适用：Android 10+、arm64 手机/平板。  
服务端版本：HIS 1.1.1。  
目标：源码、配置、数据库、备份**优先放 `/sdcard/HIS`**；Python 虚拟环境放内部，保证可执行。

> 说明：Android 的 `/sdcard` 是 FUSE/模拟存储，不是 ext4。  
> `/sdcard` 可以工作，但 SQLite 的可靠性低于内部存储。本文提供：
> - **A. sdcard 全量模式**：源码+数据库+备份都在 `/sdcard/HIS`
> - **B. 稳定模式**：源码/备份在 sdcard，数据库放内部
>
> 默认按 A 写，B 在数据库章节给出切换方法。

---

## 第 0 步：准备

- Android 10 以上
- arm64（`aarch64`）
- 4 GB 内存以上
- 8 GB 空闲存储
- Termux 从 **F-Droid** 或 GitHub Releases 安装，不要用应用商店旧版
- 手机和 Windows 客户端在同一个 Wi-Fi

示例：

```text
手机 IP：192.168.1.80
端口：8001
管理台：http://192.168.1.80:8001/admin
```

---

## 第 1 步：Termux 基础环境

```bash
pkg update
pkg upgrade -y
pkg install -y proot-distro git curl nano openssh net-tools
termux-setup-storage
```

`termux-setup-storage` 会请求存储权限，必须允许，否则 `/sdcard` 不可用。

检查：

```bash
ls /sdcard
```

能看到 `Download`、`Documents` 等目录。

---

## 第 2 步：安装 Ubuntu 并绑定 sdcard

```bash
proot-distro install ubuntu
proot-distro login ubuntu --bind /sdcard:/sdcard
```

进入 Ubuntu 后检查：

```bash
cat /etc/os-release
uname -m
ls /sdcard
```

应为 Ubuntu 24.04 左右、aarch64。

> 如果你的 proot-distro 版本不支持 `--bind`，先执行 `proot-distro login --help` 查看参数。  
> 没有绑定成功时，Ubuntu 内看不到 `/sdcard`，后续步骤会失败。

---

## 第 3 步：Ubuntu 依赖

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

时区：

```bash
ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime
echo "Asia/Shanghai" > /etc/timezone
date
```

---

## 第 4 步：获取服务端（推荐最小包，不必克隆整个仓库）

完整仓库包含客户端、测试、视频和截图，Termux 不需要。  
下载 **Termux 专用服务端源码包**，约 336 KB：

```bash
mkdir -p /sdcard/HIS
cd /sdcard/HIS

curl -L -o his-server-termux-1.1.1.tar.gz \
  https://github.com/lanyangyin/his-clinic-suite/releases/download/v1.1.1/his-server-termux-1.1.1.tar.gz

tar -xzf his-server-termux-1.1.1.tar.gz -C /sdcard/HIS --strip-components=1
ls
```

包内只有：

```text
app/
alembic/
scripts/
deploy/
config.ini
config.release.ini
requirements-server.txt
DEPLOY-TERMUX.md
```

不含：

- `his_client/`
- `tests/`
- 视频、截图
- `his.db`
- `.venv`

### 备选：克隆完整仓库

只有需要改客户端/服务端源码时才这样做：

```bash
mkdir -p /sdcard/HIS
cd /sdcard/HIS
git clone https://github.com/lanyangyin/his-clinic-suite.git .
```

私有仓库使用 SSH clone。源码在 `/sdcard`、`.git` 也在 `/sdcard`，Git 操作会慢一些，这是正常的。

---

## 第 5 步：虚拟环境放内部

不要把 `.venv` 放 `/sdcard`：FUSE 上可执行权限/符号链接不可靠，且性能差。

```bash
python3 -m venv /root/his-venv
/root/his-venv/bin/python -m pip install --upgrade pip
/root/his-venv/bin/pip install -r /sdcard/HIS/requirements-server.txt
```

检查：

```bash
/root/his-venv/bin/python -c "import fastapi, sqlalchemy, alembic; print('deps ok')"
```

---

## 第 6 步：配置

```bash
cd /sdcard/HIS
cp config.release.ini config.local.ini
/root/his-venv/bin/python -c "import secrets; print(secrets.token_urlsafe(48))"
```

编辑：

```bash
nano /sdcard/HIS/config.local.ini
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

数据库路径有两种模式，见下一步。

---

## 第 7 步：选择数据库位置

### A. sdcard 全量模式（优先 /sdcard）

```bash
mkdir -p /sdcard/HIS/data /sdcard/HIS/backups
```

启动时设置：

```bash
export HIS_DATABASE_URL=sqlite:////sdcard/HIS/data/his.db
export HIS_SQLITE_JOURNAL=DELETE
export HIS_SQLITE_SYNCHRONOUS=FULL
```

说明：

- 不使用 WAL，避免 FUSE 上 WAL 共享内存/锁问题
- `synchronous=FULL` 尽量降低断电损坏风险
- 仍然不是 ext4 级别的可靠性
- 只能单进程运行，不要同时开多个服务

### B. 稳定模式（推荐）

数据库放内部：

```bash
mkdir -p /root/his-data /sdcard/HIS/backups
export HIS_DATABASE_URL=sqlite:////root/his-data/his.db
# 保持默认 WAL，不设置 HIS_SQLITE_JOURNAL
```

源码和备份仍在 `/sdcard`，只有数据库在内部。

---

## 第 8 步：首次启动

### sdcard 全量模式

```bash
cd /sdcard/HIS
HIS_HOST=0.0.0.0 \
HIS_PORT=8001 \
HIS_PYTHON=/root/his-venv/bin/python \
HIS_DATABASE_URL=sqlite:////sdcard/HIS/data/his.db \
HIS_SQLITE_JOURNAL=DELETE \
HIS_SQLITE_SYNCHRONOUS=FULL \
bash ./scripts/run_server_linux.sh
```

### 稳定模式

```bash
cd /sdcard/HIS
HIS_HOST=0.0.0.0 \
HIS_PORT=8001 \
HIS_PYTHON=/root/his-venv/bin/python \
HIS_DATABASE_URL=sqlite:////root/his-data/his.db \
bash ./scripts/run_server_linux.sh
```

首次启动会自动：

1. 建库
2. Alembic 迁移
3. 创建 `admin/admin123`
4. 创建 `director/director123`
5. 启动 Uvicorn

看到：

```text
Uvicorn running on http://0.0.0.0:8001
```

---

## 第 9 步：验证

手机内部：

```bash
curl http://127.0.0.1:8001/health
```

应返回：

```json
{"status":"ok","version":"1.1.1"}
```

查看手机 IP（Termux 外层，不是 Ubuntu）：

```bash
ifconfig wlan0
```

从 Windows 浏览器访问：

```text
http://手机IP:8001/admin
```

登录：

```text
admin / admin123
```

立即修改密码，创建医生/收费员账号。

Windows 客户端 `config.ini`：

```ini
[server]
url = http://手机IP:8001
```

---

## 第 10 步：后台运行

Ubuntu 内：

```bash
apt install -y tmux
tmux new -s his
```

在 tmux 里执行第 8 步的启动命令。

按 `Ctrl+B`，再按 `D` 脱离。

回到：

```bash
tmux attach -t his
```

Termux 外层：

```bash
termux-wake-lock
```

并关闭 Termux 电池优化。

如果使用 nohup：

```bash
cd /sdcard/HIS
nohup env \
  HIS_HOST=0.0.0.0 \
  HIS_PORT=8001 \
  HIS_PYTHON=/root/his-venv/bin/python \
  HIS_DATABASE_URL=sqlite:////sdcard/HIS/data/his.db \
  HIS_SQLITE_JOURNAL=DELETE \
  HIS_SQLITE_SYNCHRONOUS=FULL \
  bash ./scripts/run_server_linux.sh \
  > /sdcard/HIS/server.log 2>&1 &
```

---

## 第 11 步：备份

### sdcard 数据库

```bash
cd /sdcard/HIS
sqlite3 data/his.db ".backup '/sdcard/HIS/backups/his_$(date +%Y%m%d_%H%M%S).db'"
```

### 内部数据库

```bash
sqlite3 /root/his-data/his.db \
  ".backup '/sdcard/HIS/backups/his_$(date +%Y%m%d_%H%M%S).db'"
```

然后把 `/sdcard/HIS/backups` 复制到电脑/网盘。

不要直接 `cp his.db`，尤其 WAL 模式。

---

## 第 12 步：升级

```bash
# 先备份
cd /sdcard/HIS
sqlite3 data/his.db ".backup '/sdcard/HIS/backups/before_upgrade.db'"

# 停 tmux 里的服务（Ctrl+C）
git pull
/root/his-venv/bin/pip install -r requirements-server.txt
```

再按第 8 步启动。

---

## 第 13 步：sdcard 模式注意事项

### 能放

- 源码 `/sdcard/HIS`
- 配置
- SQLite 数据库（A 模式，DELETE 日志）
- 备份

### 不要放

- `.venv`（内部 `/root/his-venv`）
- 多个服务进程同时写同一个数据库
- 在数据库运行时直接复制 `his.db`

### 风险

- `/sdcard` 是 FUSE，不是 ext4
- 断电/杀进程可能导致数据库损坏
- 比内部存储慢
- Android 11+ 分区存储权限可能变化
- 只适合小门诊/演示/备用

### 更稳的选择

- 源码和备份放 `/sdcard`
- 数据库放 `/root/his-data`
- 即第 7 步 B 模式

如果数据重要，强烈建议 B 模式，或者换 Linux 小主机。

---

## 第 14 步：验收清单

- [ ] `termux-setup-storage` 已授权
- [ ] `ls /sdcard` 正常
- [ ] `proot-distro login ubuntu --bind /sdcard:/sdcard` 正常
- [ ] 源码在 `/sdcard/HIS`
- [ ] `.venv` 在 `/root/his-venv`
- [ ] `config.local.ini` 改了 secret_key
- [ ] 数据库模式已选 A 或 B
- [ ] `/health` 返回 1.1.1
- [ ] 电脑能打开管理台
- [ ] admin 密码已改
- [ ] 客户端能连接
- [ ] `termux-wake-lock` 已开
- [ ] 备份已测试
- [ ] 没有把 `.venv` 放 `/sdcard`

---

## 常见问题

### Ubuntu 里看不到 /sdcard

登录时加：

```bash
proot-distro login ubuntu --bind /sdcard:/sdcard
```

并确认 Termux 已执行 `termux-setup-storage`。

### `bad interpreter`

脚本是 CRLF。当前仓库是 LF；旧副本执行：

```bash
sed -i 's/\r$//' scripts/run_server_linux.sh
```

### 数据库 locked / disk I/O error

- 确认使用 `HIS_SQLITE_JOURNAL=DELETE`
- 只运行一个服务进程
- 不要把数据库放 `/sdcard` 后还用 WAL
- 重要数据切到 B 模式

### 电脑打不开

- 同一 Wi-Fi
- 手机 IP 正确
- 服务监听 `0.0.0.0`
- 端口 8001
- 路由器未开 AP 隔离
- 手机浏览器先访问 `http://127.0.0.1:8001/health`

### `.venv` 放 sdcard 后无法执行

正常。放回 `/root/his-venv`。

---

## 最短流程

Termux：

```bash
pkg update
pkg install -y proot-distro git curl net-tools
termux-setup-storage
proot-distro install ubuntu
proot-distro login ubuntu --bind /sdcard:/sdcard
```

Ubuntu：

```bash
apt update
apt install -y python3 python3-venv python3-pip sqlite3 git curl tzdata tmux
mkdir -p /sdcard/HIS
cd /sdcard/HIS
git clone https://github.com/lanyangyin/his-clinic-suite.git .
python3 -m venv /root/his-venv
/root/his-venv/bin/pip install -r /sdcard/HIS/requirements-server.txt
cp config.release.ini config.local.ini
# 改 host=0.0.0.0 port=8001 secret_key
mkdir -p /sdcard/HIS/data /sdcard/HIS/backups
HIS_HOST=0.0.0.0 HIS_PORT=8001 \
HIS_PYTHON=/root/his-venv/bin/python \
HIS_DATABASE_URL=sqlite:////sdcard/HIS/data/his.db \
HIS_SQLITE_JOURNAL=DELETE HIS_SQLITE_SYNCHRONOUS=FULL \
bash ./scripts/run_server_linux.sh
```

验证：

```bash
curl http://127.0.0.1:8001/health
```
