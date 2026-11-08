"""医保适配器：HIS 侧与医保平台交互的唯一通道。

生产接入路径：把 _send 里的直连 Mock 调用替换为 HTTPS+POST 客户端
（平台地址经环境变量注入），报文构造、国密签名/加密、响应校验逻辑全部不变。

两个对外能力：
  - check_prescription  事前提醒（医生开方前同步调用，返回 pass/warn/forbid）
  - settle_payment      结算（收费时调用，返回医保支付/自费金额）

服务不可用时抛 InsuranceUnavailable，调用方按"降级"处理（事前提醒放行、结算全额自费）。
"""
import json
import time
import uuid

from . import demo_keys
from .crypto import sm2_sign, sm2_verify, sm4_decrypt, sm4_encrypt
from . import mock_platform


class InsuranceUnavailable(Exception):
    """医保服务不可用（网络/超时/平台异常），调用方应降级处理。"""


class InsuranceForbiddenError(ValueError):
    """医保事前审核禁止开方。"""


def _build_request(req_type: str, data: dict) -> dict:
    """构造加密签名后的请求报文。"""
    plain = json.dumps(
        {
            "req_no": uuid.uuid4().hex[:16],
            "ts": time.strftime("%Y%m%d%H%M%S"),
            "type": req_type,
            "data": data,
        },
        ensure_ascii=False,
    ).encode()
    cipher = sm4_encrypt(plain)
    sign = sm2_sign(cipher.encode(), demo_keys.HIS_PRIVATE, demo_keys.HIS_PUBLIC)
    return {"cipher": cipher, "sign": sign}


def _send(payload: dict, handler):
    """发送报文（当前直连 Mock；生产替换为 HTTP POST）。"""
    return handler(payload)


def _unwrap_response(response: dict) -> dict:
    """验签并解密平台响应。"""
    ok = sm2_verify(
        response["sign"], response["cipher"].encode(), demo_keys.PLATFORM_PUBLIC
    )
    if not ok:
        raise InsuranceUnavailable("医保平台：响应签名校验失败")
    return json.loads(sm4_decrypt(response["cipher"]))


def check_prescription(
    *, diagnosis: str, drug_name: str, quantity: int, ratio: float
) -> dict:
    """事前提醒：返回 {"result": pass|warn|forbid, "message": ...}。"""
    try:
        payload = _build_request(
            "check",
            {
                "diagnosis": diagnosis,
                "drug_name": drug_name,
                "quantity": quantity,
                "ratio": ratio,
            },
        )
        response = _send(payload, mock_platform.handle_check)
        return _unwrap_response(response)
    except InsuranceUnavailable:
        raise
    except Exception as e:
        raise InsuranceUnavailable(f"医保服务不可用：{e}") from e


def settle_payment(*, lines: list[dict]) -> dict:
    """结算：lines = [{"drug_name", "total", "ratio"}, ...]。

    返回 {"insurance_amount", "self_pay_amount", "total"}。
    """
    try:
        payload = _build_request("settle", {"lines": lines})
        response = _send(payload, mock_platform.handle_settle)
        return _unwrap_response(response)
    except Exception as e:
        raise InsuranceUnavailable(f"医保服务不可用：{e}") from e
