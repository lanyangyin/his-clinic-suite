# 示范工程对照（本地下载版）

本文件只做设计对照，不运行第三方代码，不把第三方代码并入本项目。

## 1. 下载物与规模

| 项目 | 本地目录 | 压缩包 | 解压后 | 许可 |
|---|---|---:|---:|---|
| OpenHIS 信创版 | `reference/open-source/openhis-itai/repo/openhis-itai-develop/` | 8.86 MB | 3,957 文件 / 21.03 MB | GPL-3.0 |
| 上海哲策 医院信息系统_HIS | `reference/open-source/shanghai-his/repo/hospital-information-systemhis-master/` | 39.22 MB | 2,078 文件 / 101.59 MB | Apache-2.0 |
| 当前 HIS | 项目根目录 | — | 60 个业务包 / 57 个路由 | GPL-3.0-only（项目自身） |

两边都是完整业务系统，文件数量远大于当前项目；不能按文件数比较功能完整度。

## 2. 模块边界对照

### OpenHIS

后端目录：

```text
openhis-server-new/
  core-admin
  core-common
  core-flowable
  core-framework
  core-generator
  core-quartz
  core-system
  openhis-application
  openhis-common
  openhis-domain
  openhis-miniapp
openhis-ui-vue3/
```

特点：

- 平台化拆分明显：core-* 是基础平台，openhis-domain 是医疗领域模型；
- 有独立迁移记录目录；
- 有 Vue3 前端和小程序；
- 技术栈是 Java/Spring Boot + PostgreSQL/Redis，不是当前 FastAPI/PySide6。

### 上海哲策 HIS

```text
HIS-boot-module/
  his-module-his
  his-module-insurance
  his-module-physical-exam
  his-module-report
  his-module-tencent-meeting
  his-boot-module-airag
  his-module-demo
docs/
assets/
```

特点：

- 以 `his-module-his` 为核心业务模块，医保、体检、报表、远程会议分模块；
- 低代码平台 + Vue3；
- 操作手册非常详细，给出 19 大模块、100+ 页面和状态机；
- 有真实业务截图和 AI 生成的原型图，文档价值大于代码可直接复用价值。

### 当前 HIS

```text
app/modules/
  patient, registration, appointment, triage, encounter,
  lis, pacs, pharmacy, warehouse, billing, charges, cashier,
  tcm, treatment, treatment_room, nursing, surgery, inpatient,
  archive, insurance, insurance_catalog, gsp, hr, staff,
  admin, bi, reports, ...
```

特点：

- 一个模块一个包，边界总体清楚；
- 门诊主线完整；
- 住院、手术、麻醉、区域协同虽然有部分包/字段，但没有形成完整闭环；
- 没有把第三方平台的 core-*、租户、流程引擎强行搬进来。

## 3. 关键字段对照

### 3.1 处方头

当前：

```text
app/modules/encounter/models.py
class PrescriptionItem:
  encounter_id
  drug_id
  quantity
  unit_price
  dosage / frequency / route / days
```

**没有**：

- `prescription_id`
- `prescription_no`
- `type`
- `status`
- `reviewed_by/reviewed_at`

OpenHIS：

```text
openhis-domain/.../medication/domain/MedicationRequest.java
  prescriptionNo
  statusEnum
  encounterId
  medicationId
  quantity
  lotNumber
  practitionerId
  performLocation
```

审方记录：

```text
openhis-domain/.../jlau/domain/ReviewPrescriptionRecords.java
  prescriptionNo
  encounterId
  medRequestIds
  passFlag
  reasonText
  practitionerId
```

上海哲策：

```text
HIS-boot-module/his-module-his/.../entity/CmDrugadvice.java
  adviceCode（处方编号）
  adviceType
  prescriptionType（普通/急诊/儿科/精麻等）
  drugCode / drugName / spec
  usage / frequency / days
```

对照结论：

- 当前处方是“就诊下的一堆明细”，不是“处方头 + 明细”；
- 第三方系统都明确把处方号/处方类型/状态放在头记录；
- 当前应优先补 `prescriptions`，而不是继续在 `PrescriptionItem` 上加字段。

### 3.2 发药明细

当前：

```text
app/modules/pharmacy/models.py
class Dispense:
  encounter_id
  status
  verified_by / verified_at
  receiver_name / signature_path
```

**没有**：

- `dispense_items`
- `prescription_item_id`
- `quantity`
- `batch_no`
- `expiry`

OpenHIS：

```text
openhis-domain/.../medication/domain/MedicationDispense.java
  medReqId
  dispenseQuantity
  preparerId
  prepareTime
  dispenseTime
  dosageInstruction
  locationId
```

上海哲策：

```text
HIS-boot-module/his-module-his/.../entity/CmDruglist.java
  adviceCode / adviceId
  drugCode / drugName / spec
  send_status / send_qty / return_qty
  batch_no / expiry_date
```

对照结论：

- 当前 `Dispense` 是“一次就诊一条”，只能证明发过药，不能证明实际发了哪些明细、哪一批；
- 第三方系统都有“发药明细”表，这是处方闭环的关键；
- 应补 `dispense_items`，并与 `prescription_items` 关联。

### 3.3 审方

当前：

- 有药房发药/退药/取药码；
- 没有“待审方 → 通过/退回 → 调配 → 发药”的状态机；
- 医生开方后，收费/发药可以继续，药师没有独立审核环节。

OpenHIS：

- `ReviewPrescriptionRecords` 有 `passFlag`、`reasonText`、`practitionerId`；
- 审方记录与处方号、就诊关联。

上海哲策：

- README 明确“需要审方/皮试”分支；
- 发药前需“已交费处方核对”；
- 审方/皮试阳性有拦截。

对照结论：

- 当前最该补的不是更多药品字典，而是“处方状态 + 审方记录”。

### 3.4 病历留痕

当前：

- `MedicalRecord` 有 `signed_by`、`signed_at`；
- 签名后锁定，不能修改；
- 签名前的修改没有版本表。

上海哲策：

- README 明确“痕迹保留模式（谁改了什么一目了然）”“CA 数字证书签名”。

对照结论：

- 当前“签名后锁定”只是不可改，不是完整的修改留痕；
- 应增加 `medical_record_versions`，保存修改前后值和修改人/时间。

### 3.5 LIS/PACS

当前：

- `LabRequest` 有申请、采样、签收、检验、报告、审核、危急值；
- `ImagingRequest` 有申请、报告、`image_url`；
- 没有真实仪器/PACS 接口。

上海哲策：

- README 描述 LIS 标本状态机、危急值短信+系统双推、PACS 影像/远程会诊；
- 有独立的 `his-module-his` 内的 LIS/PACS 子模块。

对照结论：

- 当前门诊 LIS 状态比 PACS 完整；
- PACS 只有 URL 字段，不能宣称已接 PACS；
- 接口层应显式区分“已接入/未接入/Mock”。

### 3.6 字段级对照表

| 能力 | 当前 HIS | OpenHIS | 上海哲策 |
|---|---|---|---|
| 处方头 | 无；`PrescriptionItem` 直接挂 encounter | `MedicationRequest.prescriptionNo`、`statusEnum`、`encounterId`、`medicationId` | `CmDrugadvice.adviceCode`、`adviceType`、`prescriptionType`、`regCode` |
| 处方明细 | `PrescriptionItem` | `MedicationRequest` + `MedicationDispense` 关联 | `CmDruglist`，`adviceCode/adviceId` 关联 |
| 审方 | 无独立审方状态 | `ReviewPrescriptionRecords.passFlag/reasonText/practitionerId` | README/操作手册“审方/皮试”分支，发药前核对 |
| 发药头 | `Dispense(encounter_id,status,verified_by)` | `MedicationDispense` | 门诊发药记录 |
| 发药明细 | 无 | `medReqId`、`dispenseQuantity`、`preparerId`、`dispenseTime` | `CmDruglist.send_status/send_qty/return_qty` |
| 批号/效期 | 仅库存批次 | `lotNumber` 等 | `batch_no/expiry_date` |
| 处方状态 | 无 | `statusEnum/statusChangedTime` | `cm_drugadvice.status` 待发/已发/已退 |
| 病历留痕 | 签名锁定，无版本表 | — | README“痕迹保留/CA” |
| LIS | `LabRequest` 状态较完整 | 独立 LIS 模块 | LIS 状态机、危急值双推 |
| PACS | `ImagingRequest.image_url` | PACS 相关模块 | README PACS/远程会诊 |

结论：当前最缺的不是“再加一个处方页面”，而是把 **header / review / dispense detail / audit** 四个层次补齐。

## 4. 状态机对照

### 当前门诊

```text
registration:
  registered → visited（由接诊/收费推进）

encounter:
  open → paused → open
  open/paused → closed（收费）

prescription:
  无独立状态，只有 encounter 关闭与否

dispense:
  dispensed → returned
```

### 建议的目标状态

```text
prescription:
  draft → submitted → pending_review
  → approved / rejected
  → dispensing → dispensed
  → cancelled / returned

dispense:
  pending → prepared → dispensed → returned
```

### 第三方启示

- OpenHIS 用 `statusEnum/statusChangedTime` 记录请求状态；
- 上海哲策用 `cm_drugadvice.status`（待发药/已发药/已退药）和 `cm_druglist.send_status`（待发/已发/已退）分层；
- 当前应把“处方状态”和“发药状态”分开，不能只用一个 encounter 状态代表全部。

## 5. 能借鉴与不能借鉴

### 值得借鉴

1. 处方头 + 处方号 + 处方类型；
2. 审方记录（通过/退回/原因/审方人）；
3. 发药明细（数量/批号/效期/退药数量）；
4. 病历修改痕迹 + 电子签名；
5. LIS/PACS 接口状态和失败重试；
6. 统一字典/主数据，但不要一次做全院平台。

### 不直接借鉴

- Spring Boot/Vue3 技术栈替换当前 FastAPI/PySide6；
- 116 张平台表、租户、流程引擎、低代码平台；
- 住院/手术/麻醉/ICU 全量模块；
- 为了“像大医院”而增加当前没有运营能力的页面；
- 复制第三方代码或许可证不允许的资产。

## 6. 证据索引

| 主题 | 当前证据 | OpenHIS 证据 | 上海哲策证据 |
|---|---|---|---|
| 处方头 | `app/modules/encounter/models.py` `PrescriptionItem` | `.../medication/domain/MedicationRequest.java` | `.../entity/CmDrugadvice.java` |
| 审方 | 无独立模型 | `.../jlau/domain/ReviewPrescriptionRecords.java` | README/操作手册“审方”分支 |
| 发药 | `app/modules/pharmacy/models.py` `Dispense` | `.../medication/domain/MedicationDispense.java` | `.../entity/CmDruglist.java` |
| 病历 | `app/modules/encounter/models.py` `MedicalRecord` | — | README“痕迹保留/CA” |
| LIS | `app/modules/lis/models.py` | `openhis-domain` | `his-module-his` LIS |
| PACS | `app/modules/pacs/models.py` | `openhis-domain` | README PACS/远程会诊 |
| 迁移 | `alembic/versions/` | `迁移记录-DB变更记录/` | `docs/` + 操作手册表结构 |

## 7. 结论

两个示范工程的共同点不是“页面多”，而是：

```text
处方头、明细、审方、发药、执行都有独立记录和状态
```

当前 HIS 已完成处方头、审方状态、发药明细、病历版本、患者访问审计和审批待办聚合。

剩下的主要差距是：

```text
麻精药品处方权/专用处方
医保按处方头逐张上传
注射/输液执行单派生
可配置多级审批工作流
```

这就是从“能开方发药”走向“可审计、可追溯、可评级”的下一步。
