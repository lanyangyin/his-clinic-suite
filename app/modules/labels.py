"""界面显示用的中文标签（接口/数据库内部值保持不变）。"""

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
    "inbound_status": {
        "received": "已收货",
        "checked": "已验收",
        "stocked": "已入库",
        "cancelled": "已取消",
    },
    "inbound_type": {
        "drug": "药品",
        "device": "器械",
        "other": "综合",
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
    "kind": {"drug": "药品", "material": "物资"},
    "match_status": {
        "matched": "已匹配",
        "ambiguous": "歧义",
        "unmatched": "未匹配",
    },
    "upload_status": {
        "submitted": "已提交",
        "success": "成功",
        "failed": "失败",
    },
    "channel": {"mock": "模拟", "http": "真实接口"},
    "trace_status": {
        "in_stock": "在库",
        "used": "已使用",
        "returned": "已退回",
        "void": "作废",
    },
    "ref_type": {
        "purchase": "采购入库",
        "inbound": "入库单",
        "stock_in": "入库",
        "outbound": "出库单",
        "dispense": "发药",
        "dispense_return": "退药",
        "return": "退库",
        "scrap": "报损",
        "adjust": "盘点调整",
        "usage": "使用",
        "material_stock_in": "物资入库",
    },
    "direction": {"in": "入库", "out": "出库"},
    "material_category": {
        "consumable": "耗材",
        "device": "医疗器械",
        "office": "办公用品",
        "other": "其他",
    },
    "sign_type": {
        "NONE": "不签名",
        "HMAC-SHA256": "HMAC-SHA256（密钥）",
        "SM2": "SM2（国密）",
    },
    "target_type": {"pharmacy": "药房", "department": "科室"},
    "registration_status": {
        "registered": "已挂号",
        "visited": "已就诊",
        "cancelled": "已取消",
    },
    "encounter_status": {"open": "就诊中", "closed": "已结束"},
    "payment_status": {"paid": "已收费", "refunded": "已退费"},
    "dispense_status": {"dispensed": "已发药", "returned": "已退药"},
    "charge_status": {
        "pending": "待收费",
        "paid": "已收费",
        "refunded": "已退费",
    },
    "ticket_status": {
        "waiting": "等候中",
        "called": "已叫号",
        "skipped": "已过号",
        "completed": "已完成",
    },
    "treatment_status": {
        "pending": "待执行",
        "executed": "已执行",
        "cancelled": "已取消",
    },
    "http_status": {
        "200": "200 成功",
        "201": "201 创建成功",
        "204": "204 无内容",
        "302": "302 跳转",
        "400": "400 请求有误",
        "401": "401 未登录",
        "403": "403 无权限",
        "404": "404 不存在",
        "409": "409 冲突",
        "422": "422 参数校验失败",
        "500": "500 服务器错误",
    },
    "http_method": {
        "GET": "查询",
        "POST": "提交",
        "PUT": "修改",
        "PATCH": "修改",
        "DELETE": "删除",
    },
}


def zh(group: str, value) -> str:
    """把内部英文值翻译为中文；未收录时原样返回，空值显示为 —。"""
    if value is None or value == "":
        return "—"
    mapping = LABELS.get(group, {})
    return mapping.get(str(value), str(value))
