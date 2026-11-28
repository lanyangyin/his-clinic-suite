# 医嘱状态与 DC 规则

## cancelled（已取消/撤回）

- 医生开单后**尚未发送**到接收科室；
- 医生端不再显示；
- 接收科室工作台不显示；
- 未收费用同步取消。

## dc（已停止/DC）

- 医嘱**已经发送**到检验、影像、药房、治疗室等；
- 医生端保留记录，状态显示“已停止（DC）”；
- 接收科室工作台保留记录，状态显示 DC；
- 不允许采样、检查、发药、执行；
- 已收费用不直接删除，由收费处按退费流程处理。

## 覆盖范围

- 检验申请
- 检查申请
- 处方（药房）
- 治疗单
- 护理/执行类医嘱按各模块状态机处理

## 接口

- 检验：`POST /lab/requests/{id}/cancel`
- 检查：`POST /pacs/requests/{id}/cancel`
- 处方：`POST /encounters/{encounter_id}/prescriptions/{prescription_id}/stop`
- 治疗：`POST /treatments/{id}/cancel`
