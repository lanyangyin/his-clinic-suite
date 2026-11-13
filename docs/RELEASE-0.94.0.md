# HIS 0.94.0 发布包

## 文件

| 文件 | 大小 | SHA256 |
|---|---:|---|
| `dist/his-client.zip` | 49,774,099 | `E8D7B00EEE418AE65DDE79041BB76B3D026D9D9629184D0AC0EE1362993E5909` |
| `dist/his-server.zip` | 24,892,912 | `AEC15F683BA0D6A97E51FC424941BE3BCACE271E79B3895704FF0BB6BCF14D5F` |

## 客户端

解压 `his-client.zip`，编辑 `config.ini`：

```ini
[server]
url = http://服务器IP:8000
```

双击 `his-client.exe`。

## 服务端

解压 `his-server.zip`，**先修改 `config.ini` 的 `secret_key`**：

```ini
[server]
host = 0.0.0.0
port = 8000
secret_key = 换成随机长字符串
```

双击 `his-server.exe`，首次启动自动建库并创建：

- `admin/admin123`
- `director/director123`

生产环境立即修改默认密码。

## 包内不含

- `his.db`
- `config.local.ini`
- 开发用真实 `secret_key`
- 备份、日志、签名、照片

服务端包内 `config.ini` 是发布模板，`secret_key` 必须由部署者替换。

## 已验证

- 客户端 exe 启动存活
- 服务端 exe 在 8010 启动，`/health` 返回 `0.94.0`，`/admin` 302
- pytest 660 passed
- E2E 163 步
- 浅色/深色审计通过

## GitHub Release

需要 GitHub CLI 登录或 Token：

```bash
gh release create v0.94.0 \
  dist/his-client.zip \
  dist/his-server.zip \
  --title "HIS 0.94.0" \
  --notes-file docs/RELEASE-0.94.0.md
```

当前环境没有 `gh`，也没有 `GITHUB_TOKEN`，所以二进制资产未上传；源码已推送到 GitHub。
