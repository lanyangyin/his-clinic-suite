# Linux 独立部署指南（从第 0 步到可用）

适用：Ubuntu 24.04 LTS，x86_64 或 arm64。Debian 12 默认 Python 3.11，需自行安装 Python 3.12 后再按本文部署。  
服务端版本：HIS 1.1.1。  
目标：一台 Linux 主机跑服务端，局域网内 Windows 客户端可以登录使用。

> 不要使用 Windows 的 `his-server.exe`；Linux 用源码 + Python 虚拟环境部署。

---

## 第 0 步：准备

### 硬件

- 2 核 CPU 以上
- 2 GB 内存以上（建议 4 GB）
- 5 GB 可用磁盘
- 固定局域网 IP，例如 `192.168.1.50`

### 系统

推荐 Ubuntu 24.04 LTS，自带 Python 3.12。  
Ubuntu 22.04 默认 Python 3.10，不建议直接照搬；要么升级到 24.04，要么自行安装 Python 3.12。

### 需要知道的信息

```text
服务器局域网 IP：192.168.1.50
服务端口：8001
管理台：http://192.168.1.50:8001/admin
客户端地址：http://192.168.1.50:8001
```

---

## 第 1 步：安装系统依赖

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y \
  python3.12 python3.12-venv python3-pip \
  sqlite3 git curl ca-certificates tzdata
```

检查：

```bash
python3.12 --version
sqlite3 --version
```

应看到 Python 3.12.x。

设置时区：

```bash
sudo timedatectl set-timezone Asia/Shanghai
date
```

---

## 第 2 步：创建运行用户和目录

不要用 root 跑服务。

```bash
sudo useradd --system --create-home --shell /bin/bash his
sudo mkdir -p /opt/his
sudo chown -R his:his /opt/his
```

后面所有命令用 `his` 用户执行：

```bash
sudo -iu his
cd /opt/his
```

---

## 第 3 步：把项目放到 /opt/his

### 方式 A：Git 克隆

```bash
cd /opt/his
git clone https://github.com/lanyangyin/his-clinic-suite.git .
```

如果仓库是私有的，使用 SSH：

```bash
git clone git@github.com:lanyangyin/his-clinic-suite.git .
```

### 方式 B：从开发机复制

在开发机执行：

```bash
scp -r D:\Documents\PycharmProjects\HIS his@192.168.1.50:/opt/his
```

复制后确认：

```bash
ls /opt/his
```

应看到：

```text
app/ alembic/ scripts/ docs/ pyproject.toml requirements-server.txt config.ini
```

---

## 第 4 步：创建 Python 虚拟环境

```bash
cd /opt/his
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -r requirements-server.txt
```

检查：

```bash
.venv/bin/python -c "import fastapi, sqlalchemy, alembic; print('deps ok')"
```

---

## 第 5 步：生成配置和密钥

不要直接使用仓库里的开发密钥。

```bash
cd /opt/his
cp config.release.ini config.local.ini
```

生成随机密钥：

```bash
.venv/bin/python -c "import secrets; print(secrets.token_urlsafe(48))"
```

编辑：

```bash
nano config.local.ini
```

至少修改：

```ini
[server]
host = 0.0.0.0
port = 8001
secret_key = 粘贴刚生成的随机字符串

[database]
url =

[clinic]
name = 你的诊所名称
address = 你的地址
phone = 你的电话
```

说明：

- `host=0.0.0.0` 允许局域网客户端访问
- 只本机访问可改 `127.0.0.1`
- `database.url` 留空 = `/opt/his/his.db`
- 不要把数据库放 Windows 共享盘/NFS

检查权限：

```bash
chmod 600 config.local.ini
```

---

## 第 6 步：首次启动

```bash
cd /opt/his
HIS_HOST=0.0.0.0 HIS_PORT=8001 ./scripts/run_server_linux.sh
```

首次启动会自动：

1. 创建 SQLite 数据库
2. 执行 Alembic 迁移到最新版本
3. 创建管理员 `admin/admin123`
4. 创建院长 `director/director123`
5. 启动 Uvicorn

看到：

```text
数据库结构: created
Uvicorn running on http://0.0.0.0:8001
```

> 第一次启动后马上修改默认密码。

---

## 第 7 步：验证服务

另开一个终端：

```bash
curl http://127.0.0.1:8001/health
```

应返回：

```json
{"status":"ok","version":"1.1.1"}
```

管理台：

```text
http://服务器IP:8001/admin
```

用：

```text
admin / admin123
```

登录后：

1. 修改 admin 密码
2. 创建医生账号
3. 创建收费员、药房、护士等账号
4. 维护科室、医生、收费项目、药品目录

---

## 第 8 步：客户端连接

Windows 客户端解压后编辑 `config.ini`：

```ini
[server]
url = http://192.168.1.50:8001
```

双击 `his-client.exe`。  
如果客户端版本低于服务端最低版本，会提示升级。

---

## 第 9 步：配置 systemd 开机启动

复制服务文件：

```bash
sudo cp /opt/his/deploy/his-server.service /etc/systemd/system/his-server.service
```

检查文件：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now his-server
sudo systemctl status his-server
```

日志：

```bash
journalctl -u his-server -f
```

健康检查：

```bash
curl http://127.0.0.1:8001/health
```

服务文件默认：

```text
User=his
WorkingDirectory=/opt/his
HIS_PORT=8001
ExecStart=/opt/his/.venv/bin/python /opt/his/scripts/run_server.py
```

如果实际路径不同，先修改 `deploy/his-server.service`。

---

## 第 10 步：防火墙

只允许局域网访问 8001：

```bash
sudo ufw allow from 192.168.0.0/16 to any port 8001 proto tcp
sudo ufw enable
sudo ufw status
```

不要把 8001 直接暴露到公网。

远程访问建议：

- Tailscale / WireGuard
- 或 Caddy/Nginx + HTTPS + 访问控制

Basic Auth 走 HTTP 明文不安全。

---

## 第 11 步：备份

SQLite 有 WAL，不能只 `cp his.db`。

安全备份：

```bash
sudo mkdir -p /var/backups/his
sudo chown his:his /var/backups/his

sudo -u his sqlite3 /opt/his/his.db \
  ".backup '/var/backups/his/his_$(date +%Y%m%d_%H%M%S).db'"
```

每天定时：

```bash
sudo crontab -u his -e
```

加入：

```cron
30 22 * * * sqlite3 /opt/his/his.db ".backup '/var/backups/his/his_$(date +\%Y\%m\%d).db'"
```

至少每周把备份复制到另一台机器或移动硬盘。

---

## 第 12 步：升级

```bash
sudo systemctl stop his-server
sudo -u his sqlite3 /opt/his/his.db ".backup '/var/backups/his/before_upgrade.db'"

sudo -iu his
cd /opt/his
git pull
.venv/bin/pip install -r requirements-server.txt
exit

sudo systemctl start his-server
sudo systemctl status his-server
curl http://127.0.0.1:8001/health
```

数据库迁移会在启动时自动执行。

---

## 第 13 步：验收清单

- [ ] `/health` 返回 200
- [ ] `/admin` 可以登录
- [ ] admin 默认密码已改
- [ ] 已创建医生、收费员等账号
- [ ] Windows 客户端可以连接
- [ ] 可以完成一次挂号 → 接诊 → 开方 → 收费
- [ ] systemd 开机自启正常
- [ ] 备份任务已配置
- [ ] 服务器 IP 固定
- [ ] 8001 没有暴露公网

---

## 常见问题

### `/health` 返回 404

旧版本没有健康检查接口。确认版本 ≥ 1.0，或直接访问 `/admin`。

### 启动报 `no such table: users`

这是旧版启动顺序问题。当前 `run_server.py` 会先执行 `ensure_schema()`。确认代码是 1.0+，并删除不完整的新库后重试。

### 端口被占用

```bash
sudo ss -ltnp | grep 8001
```

改 `config.local.ini` 的端口，同时改客户端 URL。

### 数据库 locked

- 不要把数据库放 `/mnt/d`、NFS、SMB
- 确认只有一个服务进程
- 备份用 `.backup`，不要直接复制 WAL 中的库

### 中文乱码

```bash
sudo locale-gen zh_CN.UTF-8
sudo timedatectl set-timezone Asia/Shanghai
```

### 客户端连不上

- 服务器 `curl http://127.0.0.1:8001/health` 正常吗
- 从客户端机器 `ping 服务器IP`
- 防火墙是否放行 8001
- 客户端 `config.ini` 是否是服务器 IP，不是 127.0.0.1

---

## 最短命令汇总

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv sqlite3 git curl
sudo useradd --system --create-home --shell /bin/bash his
sudo mkdir -p /opt/his && sudo chown his:his /opt/his
sudo -iu his
cd /opt/his
git clone https://github.com/lanyangyin/his-clinic-suite.git .
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-server.txt
cp config.release.ini config.local.ini
# 编辑 config.local.ini：host/port/secret_key/clinic
HIS_HOST=0.0.0.0 HIS_PORT=8001 ./scripts/run_server_linux.sh
```

另一个终端：

```bash
curl http://127.0.0.1:8001/health
```
