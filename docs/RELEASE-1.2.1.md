# HIS 1.2.1 发布包

发布日期：2026-11-14

## 门诊工作台 UX 修复

- 接诊前不再提供诊断输入框；接诊只建就诊，诊断统一在病历页填写
- 内层“门诊工作台”更名为“候诊队列”，避免与外层工作站重名
- 接诊列表显示患者姓名、性别/年龄、医生、分诊、状态，不再只有 ID
- 切换二级页签时侧栏固定宽度，内容不再右移
- 删除工作台右栏重复患者卡，统一使用左侧患者摘要
- 快速建档增加年龄字段，不再默认 1 岁
- 现场挂号优先当前登录医生；更换医生弹窗确认
- 输液/治疗状态增加“治疗中/待治疗”显示
- 危急值面板移到下方，与当前患者操作区之间可自由拖动高度
- 危急值高度写入 `ui_state.ini`，下次启动恢复
- 工作台移除“项目/数量/金额/状态”费用表，只保留费用摘要；明细在收费页
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
| `his-client.zip` | 49,798,057 | `48C719F09C826F7E2129FA59168ED2A1BAC45D82D15DAB3213F6360BB9621636` |
| `his-server.zip` | 24,903,280 | `3E47D40909803E5863CF8183217B22B313C85654EBE1761681577E6788DAA157` |
| `his-server-termux-1.2.1.tar.gz` | 345,400 | `95E110BD5209032925BF9D365F863A3C80F6DA4F08F947EC2FE9B3F5E04AEA68` |

## 下载

- 客户端：https://github.com/lanyangyin/his-clinic-suite/releases/download/v1.2.1/his-client.zip
- 服务端：https://github.com/lanyangyin/his-clinic-suite/releases/download/v1.2.1/his-server.zip
- Termux 最小包：https://github.com/lanyangyin/his-clinic-suite/releases/download/v1.2.1/his-server-termux-1.2.1.tar.gz
