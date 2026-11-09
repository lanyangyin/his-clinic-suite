"""客户端界面中文标签（接口内部值保持不变）。"""

LABELS: dict[str, dict[str, str]] = {
    "role": {
        "admin": "管理员",
        "doctor": "医生",
        "nurse": "护士",
        "cashier": "收费员",
        "pharmacist": "药师",
        "warehouse": "库房管理员",
        "lab": "检验技师",
        "radiology": "影像技师",
    },
    "kind": {"drug": "药品", "material": "物资"},
    "inbound_status": {
        "received": "已收货",
        "checked": "已验收",
        "stocked": "已入库",
        "cancelled": "已取消",
    },
    "outbound_status": {
        "submitted": "已申请",
        "approved": "已审核",
        "partially_issued": "部分出库",
        "issued": "已出库",
        "cancelled": "已取消",
    },
    "outbound_type": {
        "requisition": "领用出库",
        "transfer": "调拨",
        "scrap": "报损",
        "return": "退库",
    },
    "trace_status": {
        "in_stock": "在库",
        "used": "已使用",
        "returned": "已退回",
        "void": "作废",
    },
    "registration_status": {
        "registered": "已挂号",
        "waiting": "候诊中",
        "visited": "已就诊",
        "cancelled": "已取消",
    },
    "encounter_status": {"open": "就诊中", "closed": "已结束"},
    "payment_status": {
        "paid": "已收费",
        "partially_refunded": "部分退费",
        "refunded": "已退费",
    },
    "dispense_status": {"dispensed": "已发药", "returned": "已退药"},
    "charge_status": {
        "pending": "待收费",
        "paid": "已收费",
        "partially_refunded": "部分退费",
        "refunded": "已退费",
    },
    "ticket_status": {
        "waiting": "等候中",
        "called": "已叫号",
        "skipped": "已过号",
        "completed": "已完成",
        "done": "已完成",
    },
    "treatment_status": {
        "pending": "待执行",
        "executed": "已执行",
        "cancelled": "已取消",
    },
    "charge_type": {
        "registration": "挂号费",
        "consultation": "诊查费",
        "drug": "药品费",
        "lab": "检验费",
        "imaging": "检查费",
        "treatment": "治疗费",
        "material": "材料费",
        "other": "其他",
    },
    "payment_channel": {
        "cash": "现金",
        "wechat": "微信支付",
        "alipay": "支付宝",
        "pos": "POS 刷卡",
        "insurance_card": "医保卡",
    },
}


def zh(group: str, value) -> str:
    if value is None or value == "":
        return "—"
    mapping = LABELS.get(group, {})
    return mapping.get(str(value), str(value))
