# HIS 1.0.0 发布包

## 重点

- 门诊诊断改为多诊断：主诊断 + 其他诊断
- 第一行主诊断，后面按重要性排序
- 诊断独立表 `encounter_diagnoses`
- 病历页可添加/删除/上移/下移/保存全部诊断
- 门诊工作台保留主诊断快捷输入 + “多诊断”
- 病历打印按顺序输出全部诊断
- 旧单诊断数据自动回填为主诊断
- 初诊/复诊类型和上次就诊关联继续保留

## 文件

| 文件 | 大小 | SHA256 |
|---|---:|---|
| `dist/his-client.zip` | 49,781,373 | `9A4BB1D4FDA162DD90B8D844255F07AF9A3C12AE925F9577F2834EF8AEA41C0D` |
| `dist/his-server.zip` | 24,897,341 | `A856A0DBDCE74A5CF23126A531C8595C6D9169222A00AF4CE6356362E24CD1FE` |

## 启动

客户端解压后改 `config.ini`：

```ini
[server]
url = http://服务器IP:8000
```

服务端解压后先改 `config.ini` 的 `secret_key`，再启动 `his-server.exe`。

服务端包内不含 `his.db`、日志、备份、开发密钥。

## 验证

- pytest：664 passed
- 客户端全流程：18/18
- E2E：163 步
- 浅色/深色审计通过
- 服务端 exe：`/health` 返回 1.0.0，`/admin` 302
- 客户端 exe：启动存活

## GitHub Release

已发布：

https://github.com/lanyangyin/his-clinic/releases/tag/v1.0.0

- 客户端：https://github.com/lanyangyin/his-clinic/releases/download/v1.0.0/his-client.zip
- 服务端：https://github.com/lanyangyin/his-clinic/releases/download/v1.0.0/his-server.zip
