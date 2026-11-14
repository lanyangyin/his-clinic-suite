# HIS 1.2.3 发布包

发布日期：2026-11-14

## 出生日期 / 年龄 / 身份证联动

- 收费员建档和医生快速建档共用同一个控件
- 身份证填完自动提取出生日期
- 支持 18 位身份证和 15 位老身份证
- 18 位校验位错误时仍提取出生日期，但明确提示核对
- 出生日期 → 精确年龄（年/月/日）
- 年龄（年/月/日） → 近似出生日期
- 出生日期用日历选择框
- 年龄用年/月/日三个滚动输入框
- “年龄不详”独立勾选，默认不伪造年龄
- 收费员患者列表显示精确年龄
- 年龄不详允许建档，`birth_date = null`

详细说明：

[出生日期/年龄/身份证联动](出生日期年龄联动.md)

## admin 身份评估

不把 admin 做成一个叫“管理员”的医生记录：

- 会污染医生排班/挂号列表
- 病历会归属成“管理员医生”
- 管理账号和临床医生职责不同

保留：

```text
admin = 超级管理员 = 所有工作站入口
admin ≠ 自动成为临床医生
```

如果管理员本人出诊，建立真实医生档案，用医生账号登录，或后续做 `users.doctor_id` 关联。

## 其他

- 医生/收费端年龄控件统一
- 年龄显示精确到年月日
- 患者列表不再只显示整数岁
- 测试 674 passed

## 资产

| 文件 | 大小 | SHA256 |
|---|---:|---|
| `his-client.zip` | 49,807,752 | `A704F0A9CE995B9A1B649A229672974912A92CC53367BD6D5AD6D61B47C4B45C` |
| `his-server.zip` | 24,903,677 | `58DF1D6A1728B7AA9C02537DFED736E6597DE98B547B1A3AD9394FE124EFB060` |
| `his-server-termux-1.2.3.tar.gz` | 345,406 | `ABF13885DCC2EECA9FAB14E0C68A57E676DF12359F44FADABDACEB9073DECD06` |

## 下载

- 客户端：https://github.com/lanyangyin/his-clinic-suite/releases/download/v1.2.3/his-client.zip
- 服务端：https://github.com/lanyangyin/his-clinic-suite/releases/download/v1.2.3/his-server.zip
- Termux 最小包：https://github.com/lanyangyin/his-clinic-suite/releases/download/v1.2.3/his-server-termux-1.2.3.tar.gz
