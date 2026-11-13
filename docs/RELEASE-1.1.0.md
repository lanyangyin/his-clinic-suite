# HIS 1.1.0 发布包

## 重点

- 初诊：正常挂号、收挂号费
- 复诊：免挂号费，保留复诊记录
- 复诊自动关联上次挂号/上次就诊
- 医生站复诊流程提示：先看历史 → 核对上次诊断/医嘱 → 记录本次复诊
- 病情变化且尚未接诊：可“复诊转初诊”，按初诊收挂号费
- 已接诊后不能改类型
- 治疗室“按上次治疗复诊”仍不新建挂号/就诊，只收治疗费

## 文件

| 文件 | 大小 | SHA256 |
|---|---:|---|
| `dist/his-client.zip` | 49,782,574 | `2EAB1F7C5B35AE4A6D7747DDF9D66DCB71B7A40EDE88B704856B42CC82F7B7AE` |
| `dist/his-server.zip` | 24,899,725 | `C3D64B40458638EF4E920F1367B735CDA3A8933DCC7CBA58A26E6398377B16CF` |

## 界面

- 收费员复诊：`docs/screenshots/cashier_follow_up_flow.png`
- 医生站复诊：`docs/screenshots/doctor_follow_up_flow.png`
- 多诊断病历：`docs/screenshots/doctor_multi_diagnosis.png`

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
- 服务端 exe：`/health` 返回 1.1.0，`/admin` 302
- 客户端 exe：启动存活
- 包内不含 `his.db`、日志、备份、开发密钥

## GitHub Release

已发布：

https://github.com/lanyangyin/his-clinic-system/releases/tag/v1.1.0

- 客户端：https://github.com/lanyangyin/his-clinic-system/releases/download/v1.1.0/his-client.zip
- 服务端：https://github.com/lanyangyin/his-clinic-system/releases/download/v1.1.0/his-server.zip
