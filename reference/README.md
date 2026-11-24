# HIS 标准与示范工程资料包

本目录是本地对照研究资料，**不参与产品打包，不随客户端/服务端发布**。

## 目录

浏览器入口：[index.html](index.html)

```text
reference/
├─ official/
│  ├─ NHC-2018-4/           全国医院信息化建设标准与规范
│  ├─ EMR-2018-1079/        电子病历应用水平分级评价标准
│  └─ SmartService-2019-236/医院智慧服务分级评估标准
├─ open-source/
│  ├─ openhis-itai/         OpenHIS 信创版（GPL-3.0）
│  └─ shanghai-his/         上海哲策 HIS（Apache-2.0）
├─ web/                     官方页面/README 的 HTML 与文本
├─ comparison.md            两个示范工程的详细对照
├─ manifest.json            文件大小/SHA256/来源
└─ manifest.md              可读版清单
```

## 官方文件

| 文件 | 内容 |
|---|---|
| `official/NHC-2018-4/standard.pdf` | 22 类 262 项官方 PDF |
| `official/NHC-2018-4/items.csv` | 262 项编号/类别/标题 |
| `official/EMR-2018-1079/combined-cn-standards.pdf` | 包含 EMR 标准、智慧服务标准等合集 |
| `official/EMR-2018-1079/standard.pdf` | 从合集抽取的 EMR 章节 |
| `official/EMR-2018-1079/standard.txt` | 仅 EMR 分级标准部分 |
| `official/EMR-2018-1079/emr-projects.csv` | 39 个评价项目 |
| `official/SmartService-2019-236/standard.pdf` | 从合集抽取的智慧服务章节 |
| `official/SmartService-2019-236/standard.txt` | 智慧服务标准全文提取 |
| `official/SmartService-2019-236/smart-projects.csv` | 17 个评估项目 |

每个官方目录都有 `source.md`，记录来源、字节数和 SHA256。

## 开源项目

### OpenHIS 信创版

- 压缩包：`open-source/openhis-itai/openhis-itai-develop.zip`
- 解压目录：`open-source/openhis-itai/repo/openhis-itai-develop/`
- 规模：3,957 文件，约 21.03 MB
- 许可：GPL-3.0
- 技术栈：Java / Spring Boot / PostgreSQL / Redis + Vue3

### 上海哲策 医院信息系统_HIS

- 压缩包：`open-source/shanghai-his/hospital-information-systemhis-master.zip`
- 解压目录：`open-source/shanghai-his/repo/hospital-information-systemhis-master/`
- 规模：2,078 文件，约 101.59 MB
- 许可：Apache-2.0
- 技术栈：Spring Boot 2.7 / MyBatis-Plus / Vue3 / MySQL / Redis

## 使用边界

- 官方标准版权归原发布机构，仅本地研究，不随产品分发。
- 第三方代码只读参考；GPL-3.0 代码不能直接复制进本项目而不处理许可义务。
- 不运行第三方系统，不引入其数据库/依赖。
- 网页内容抓取于 2026-11-22，动态页面可能只保存到前端壳。

## 校验

```powershell
Get-Content reference/manifest.md
```

或：

```powershell
python -c "import json; d=json.load(open('reference/manifest.json')); print(len(d['files']), d['repositories'])"
```

## 对照结论

先读：

- [示范工程对照](comparison.md)
- [标准逐条对照](../docs/标准逐条对照.md)

当前最值得补的仍是：

```text
处方头 → 审方 → 调配 → 发药 → 执行
病历修改留痕
患者访问审计
```
