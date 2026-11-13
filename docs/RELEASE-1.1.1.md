# HIS 1.1.1 发布包

## 重点

- 复诊免挂号费，保留复诊记录
- 复诊自动关联上次挂号/就诊
- 病情变化、尚未接诊时可复诊转初诊
- **跨日未完成就诊保留 14 天**，看结果不用重新挂号
- 门诊工作台显示跨日日期和“跨日未完成”
- 医生站复诊流程提示
- 多诊断主诊断/其他诊断排序继续保留

## 文件

| 文件 | 大小 | SHA256 |
|---|---:|---|
| `dist/his-client.zip` | 49,783,521 | `64FB924A066BF71EC16892CF7B5181D358215F023B37369BEB489240F00F3256` |
| `dist/his-server.zip` | 24,898,878 | `2D9F60AF3B07578E1A4A7144CE89849AA13A9957ECD4614F768F80B551C29195` |

## 启动

客户端解压后改 `config.ini`：

```ini
[server]
url = http://服务器IP:8000
```

服务端解压后先改 `config.ini` 的 `secret_key`，再启动 `his-server.exe`。

## 验证

- pytest：666 passed
- 客户端全流程：18/18
- E2E：163 步
- 浅色/深色审计通过
- 服务端 exe：`/health` 返回 1.1.1
- 包内不含 `his.db`、日志、备份、开发密钥

## 操作

- 收费员复诊：`docs/screenshots/cashier_follow_up_flow.png`
- 医生站复诊：`docs/screenshots/doctor_follow_up_flow.png`
- 详细流程：`docs/复诊流程.md`

## GitHub Release

https://github.com/lanyangyin/his-clinic-suite/releases/tag/v1.1.1

- 客户端：https://github.com/lanyangyin/his-clinic-suite/releases/download/v1.1.1/his-client.zip
- 服务端：https://github.com/lanyangyin/his-clinic-suite/releases/download/v1.1.1/his-server.zip
