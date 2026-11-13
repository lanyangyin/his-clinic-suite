# HIS 1.2.0 发布包

发布日期：2026-11-14

## 新增

### 登录记忆

- 服务器 IP、端口、账号拆成三个可编辑下拉框
- 各保留最近 10 个，密码不保存
- 配置可调：

```ini
[client]
remember_login = true
remember_limit = 10
```

- 记忆文件：客户端目录 `login_history.json`
- 只含 IP/端口/账号，不含密码

### 人事工作站

- 新角色 `hr`
- 员工档案：新增、离职
- 医生管理：新增、停用/辞退
- 科室管理：新增、停用
- 账号管理：创建账号、角色选择、关联员工
- 员工入职时可勾选“同时创建登录账号”
- 人事不能创建 admin/director 账号

### 软删除

医生、科室采用 `active=0` 停用，不物理删除：

- 历史挂号、病历、处方不断链
- 有未完成就诊的医生不能停用
- 科室仍有在职医生时不能停用

## 修复/调整

- 版本升至 1.2.0
- pytest：668 passed
- 客户端全流程：18/18
- 登录页不再把服务器地址作为一个整串输入
- HR 角色的后端权限、客户端标签、工作站入口已接通

## 资产

| 文件 | 大小 | SHA256 |
|---|---:|---|
| `his-client.zip` | 49,797,573 | `112DA6948A2DC7A624A82830D79ADA1D088664ECCB8CE7839C1E7FC14ADBEBB0` |
| `his-server.zip` | 24,902,864 | `D9758DB9C8BC54BA7BB6DFC6CAFEF0B83181BC0A315777D4108FB98FE39A3964` |
| `his-server-termux-1.2.0.tar.gz` | 345,093 | `874F163F3C777563FEDF3C8BC957B1973D6F6B6A937755D05F9A2F04920E0877` |

## 下载

- 客户端：https://github.com/lanyangyin/his-clinic-suite/releases/download/v1.2.0/his-client.zip
- 服务端：https://github.com/lanyangyin/his-clinic-suite/releases/download/v1.2.0/his-server.zip
- Termux 最小包：https://github.com/lanyangyin/his-clinic-suite/releases/download/v1.2.0/his-server-termux-1.2.0.tar.gz

## 升级说明

1. 备份服务端 `his.db`
2. 替换服务端程序
3. 首次启动自动执行迁移 `0090`
4. 替换客户端
5. 保留客户端 `config.ini`

## License

GPL-3.0-only
