# NFC 就诊卡说明

## 设计

`patient_cards`：

- 一个患者同一时间只能有一张 `active` 卡
- 卡号全局唯一
- 挂失后状态 `lost`，不能再按卡查患者
- 换卡后旧卡 `replaced`，新卡 `active`

## 接口

发卡：

```http
POST /patients/{id}/cards
{"card_uid": "NFC-1001", "note": "首次发卡"}
```

按卡查患者：

```http
GET /patients/by-card/{card_uid}
```

只返回 `active` 卡，避免挂失卡继续使用。

挂失：

```http
POST /patients/{id}/cards/{card_id}/lost
```

换卡：

```http
POST /patients/{id}/cards/reissue
{"card_uid": "NFC-1002", "note": "挂失补卡"}
```

## 桌面端

收费员工作站：

- 患者建档页新增 NFC 卡号、绑定 NFC 卡、按卡查患者
- 挂号页新增 NFC 卡号、按卡带出患者

NFC 读卡器按键盘模式输入卡号即可，不需要额外 SDK。

## 边界

- 目前没有读卡器厂商 SDK/加密扇区读写，卡号按键盘输入/读卡器模拟键入。
- 没有卡押金、退卡、卡工本费。
- 没有卡号与医保卡/电子健康卡互通。
- 没有防止复制卡（UID 可克隆）的能力。
