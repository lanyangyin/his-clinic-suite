# HIS 1.2.4 发布包

发布日期：2026-11-14

## 主题实时跟随系统

- 监听 `QStyleHints.colorSchemeChanged`
- 监听 `ThemeChange` / `ApplicationPaletteChange`
- 1.5 秒低频轮询兜底
- 主题变化后重新应用全局 QSS、调色板、页签、患者卡、危急值标记
- 表单内容不丢、不重建窗口、不打断当前患者

详细说明：

[主题实时跟随系统](主题实时跟随.md)

## 出生日期 / 年龄 / 身份证

- 收费员建档、医生快速建档共用控件
- 身份证 → 出生日期 → 精确年龄
- 年龄 → 近似出生日期
- 18/15 位身份证
- 年龄不详独立选项
- 年龄精确到年月日

详细说明：

[出生日期/年龄/身份证联动](出生日期年龄联动.md)

## 验证

- pytest：674 passed
- 客户端全流程：18/18
- 系统浅色/深色切换由定时轮询和 Qt 信号共同覆盖

## 资产

| 文件 | 大小 | SHA256 |
|---|---:|---|
| `his-client.zip` | 49,811,991 | `9A0E54C666F2AB67DD120F058A6C23C7E9A9939C5B3A5C74C8E24EA800CDE95C` |
| `his-server.zip` | 24,904,417 | `3401B94D9F2819755E3E051A9714853EDC36F5F6F03E17916386CF8D607A585A` |
| `his-server-termux-1.2.4.tar.gz` | 345,410 | `4D057988FB795266BC9765D4C1C65E4615CBC965921C885316D048920A39D99A` |

## 下载

- 客户端：https://github.com/lanyangyin/his-clinic-suite/releases/download/v1.2.4/his-client.zip
- 服务端：https://github.com/lanyangyin/his-clinic-suite/releases/download/v1.2.4/his-server.zip
- Termux 最小包：https://github.com/lanyangyin/his-clinic-suite/releases/download/v1.2.4/his-server-termux-1.2.4.tar.gz
