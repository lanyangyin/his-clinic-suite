# HIS 1.2.1 发布包

发布日期：2026-11-14

## 门诊工作台 UX 修复

- 接诊不再要求先填诊断；诊断可后补
- 内层“门诊工作台”更名为“候诊队列”，避免与外层工作站重名
- 接诊列表显示患者姓名、性别/年龄、医生、分诊、状态，不再只有 ID
- 切换二级页签时侧栏固定宽度，内容不再右移
- 删除工作台右栏重复患者卡，统一使用左侧患者摘要
- 快速建档增加年龄字段，不再默认 1 岁
- 现场挂号优先当前登录医生；更换医生弹窗确认
- 输液/治疗状态增加“治疗中/待治疗”显示
- 危急值面板移到右下角
- 新增常驻危急值红色标记，不依赖弹窗

详细说明：

[门诊工作台 UX 调整](门诊工作台UX调整.md)

## 保留

- 登录记忆：IP/端口/账号，密码不记忆
- 人事工作站：员工/医生/科室/账号
- GPL-3.0-only

## 验证

- pytest：668 passed
- 客户端全流程：18/18
- 版本：1.2.1

## 资产

| 文件 | 大小 | SHA256 |
|---|---:|---|
| `his-client.zip` | 49,801,354 | `9DACB5519AA7C8F778353A95540B7D4B74E78771D06800DCD6E4C104D18C6AB4` |
| `his-server.zip` | 24,904,852 | `F90AB1C7F26E17091E83DCC9A03455300B8EC6DCB3118CB6AD3879BD5AC43C68` |
| `his-server-termux-1.2.1.tar.gz` | 345,412 | `11CAFD9CD821159A3CF12E7F3D38C5AC771CDDE89CF3CDA100395531B56E1489` |

## 下载

- 客户端：https://github.com/lanyangyin/his-clinic-suite/releases/download/v1.2.1/his-client.zip
- 服务端：https://github.com/lanyangyin/his-clinic-suite/releases/download/v1.2.1/his-server.zip
- Termux 最小包：https://github.com/lanyangyin/his-clinic-suite/releases/download/v1.2.1/his-server-termux-1.2.1.tar.gz
