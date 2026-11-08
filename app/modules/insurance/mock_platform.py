"""模拟医保平台（代表医保局侧）。

处理链路与真实平台一致：验签（HIS 公钥）→ 解密（SM4）→ 规则检查 → 签名（平台私钥）→ 加密。

规则（模拟医保目录与智能监管）：
  - 事前提醒：报销比例 <= 0 视为目录外 → 禁止；单次开方数量 > 5 → 提醒；否则通过
  - 结算：按每条明细的报销比例计算医保支付金额
"""
import json

from . import demo_keys
from .crypto import sm2_sign, sm2_verify, sm4_decrypt, sm4_encrypt


def _unwrap(payload: dict) -> dict:
    """验签并解密请求，返回明文；任一失败抛异常。"""
    ok = sm2_verify(payload["sign"], payload["cipher"].encode(), demo_keys.HIS_PUBLIC)
    if not ok:
        raise ValueError("医保平台：请求签名校验失败")
    return json.loads(sm4_decrypt(payload["cipher"]))


def _wrap(data: dict) -> dict:
    """签名并加密响应。"""
    plain = json.dumps(data, ensure_ascii=False).encode()
    cipher = sm4_encrypt(plain)
    sign = sm2_sign(cipher.encode(), demo_keys.PLATFORM_PRIVATE, demo_keys.PLATFORM_PUBLIC)
    return {"cipher": cipher, "sign": sign}


def handle_check(payload: dict) -> dict:
    """事前提醒：返回 pass / warn / forbid。"""
    req = _unwrap(payload)
    data = req["data"]
    ratio = float(data.get("ratio", 0))
    quantity = int(data.get("quantity", 0))
    drug_name = data.get("drug_name", "")

    if ratio <= 0:
        result, message = "forbid", f"该药品不在医保目录：{drug_name}"
    elif quantity > 5:
        result, message = "warn", f"超量提醒：{drug_name} 单次开方 {quantity} 超出常用量"
    else:
        result, message = "pass", "审核通过"
    return _wrap({"result": result, "message": message, "req_no": req.get("req_no")})


def handle_settle(payload: dict) -> dict:
    """结算：按明细逐条计算医保支付金额。"""
    req = _unwrap(payload)
    lines = req["data"].get("lines", [])
    grand_total = 0.0
    insurance_amount = 0.0
    for line in lines:
        total = float(line.get("total", 0))
        ratio = float(line.get("ratio", 0))
        grand_total += total
        insurance_amount += round(total * ratio, 2)
    return _wrap(
        {
            "result": "ok",
            "total": round(grand_total, 2),
            "insurance_amount": round(insurance_amount, 2),
            "self_pay_amount": round(grand_total - insurance_amount, 2),
            "req_no": req.get("req_no"),
        }
    )
