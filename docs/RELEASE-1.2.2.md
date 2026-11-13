# HIS 1.2.2 发布包

发布日期：2026-11-14

## 客户端布局审计

按登录、医生、收费、药房、护士、检验、治疗室、病案、院长、人事逐屏检查，详细说明：

[客户端布局审计](客户端布局审计.md)

## 主要调整

- 危急值从单患者右栏移到工作台底部，横跨全宽
- 危急值与当前患者操作区之间可拖动，高度写入 `ui_state.ini`
- 工作台移除“项目/数量/金额/状态”费用明细表，只保留费用摘要
- 完整费用明细统一在「收费」页
- 接诊前彻底移除诊断输入；诊断只能在病历页填写
- 医生队列从 8 列压缩为 6 列，优先患者、医生、就诊、诊断、待缴
- 护士、检验、院长进入工作站自动加载队列
- 护士、检验、收费、治疗室主要表格拉伸铺满
- 人事新建员工表单改为两列，减少横向空白
- 危急值顶部常驻提示改为稳定文本，避免字体缺字显示方框

## 保留

- 登录记忆：IP/端口/账号，密码不记忆
- 人事工作站：员工/医生/科室/账号
- 接诊后病历写诊断
- GPL-3.0-only

## 验证

- pytest：668 passed
- 客户端全流程：18/18
- 1366×900 多角色离屏截图检查
- 浅色主题截图检查

## 资产

| 文件 | 大小 | SHA256 |
|---|---:|---|
| `his-client.zip` | 49,800,969 | `C175614131C57766161D44FD3815D7F30FB4B074B753A9FBD51D272FD40CC8AF` |
| `his-server.zip` | 24,902,267 | `99656D25ED2C44FED32A1446E9E48513E329917D9937251273C391E6D8E37D3E` |
| `his-server-termux-1.2.2.tar.gz` | 345,399 | `6DA9C319F23A4E4FE41CD15491746E35170F3058233D1C9A1C2344D75AF70199` |

## 下载

- 客户端：https://github.com/lanyangyin/his-clinic-suite/releases/download/v1.2.2/his-client.zip
- 服务端：https://github.com/lanyangyin/his-clinic-suite/releases/download/v1.2.2/his-server.zip
- Termux 最小包：https://github.com/lanyangyin/his-clinic-suite/releases/download/v1.2.2/his-server-termux-1.2.2.tar.gz
