"""医保进销存真实接口适配：未配置走 Mock；配置后 HTTPS 上报并验回执。

实际部署时在管理台「医保接口」填写平台地址、机构编码、AppID/密钥、
签名方式（NONE/HMAC-SHA256/SM2）等；字段留空=Mock。
"""
import hashlib
import hmac
import json
import time
import uuid
from urllib.parse import urljoin

import requests

from app.modules.insurance.crypto import sm2_sign

from .interface_service import get_config, is_configured


class InterfaceError(Exception):
    """医保接口配置/调用异常。"""


def _mock(payload: dict) -> dict:
    if not payload.get("records"):
        return {"code": "1", "message": "无进销存明细", "receipt_no": ""}
    return {
        "code": "0",
        "message": "医保进销存接收成功（Mock）",
        "receipt_no": f"MOCK{uuid.uuid4().hex[:12].upper()}",
        "received_count": len(payload["records"]),
    }


def _sign(config, body: str, timestamp: str, nonce: str) -> str:
    if config.sign_type == "HMAC-SHA256":
        if not config.app_secret:
            raise InterfaceError("HMAC 签名需要 AppSecret")
        canonical = f"{config.org_code}{timestamp}{nonce}{body}"
        return hmac.new(
            config.app_secret.encode("utf-8"),
            canonical.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
    if config.sign_type == "SM2":
        if not config.private_key:
            raise InterfaceError("SM2 签名需要私钥")
        return sm2_sign(body.encode("utf-8"), config.private_key, config.public_key)
    return ""


def submit_inventory(db, payload: dict) -> dict:
    """提交医保进销存；返回 {code, message, receipt_no, channel, ...}。"""
    config = get_config(db)
    if not is_configured(config):
        result = _mock(payload)
        result["channel"] = "mock"
        return result

    url = urljoin(
        config.base_url.rstrip("/") + "/", config.upload_path.lstrip("/")
    )
    timestamp = str(int(time.time() * 1000))
    nonce = uuid.uuid4().hex[:16]
    body_obj = {
        "org_code": config.org_code,
        "app_id": config.app_id,
        "timestamp": timestamp,
        "nonce": nonce,
        "data": payload,
    }
    body = json.dumps(body_obj, ensure_ascii=False, separators=(",", ":"))
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "X-Org-Code": config.org_code,
        "X-App-Id": config.app_id,
        "X-Timestamp": timestamp,
        "X-Nonce": nonce,
    }
    try:
        signature = _sign(config, body, timestamp, nonce)
        if signature:
            headers["X-Sign"] = signature
        response = requests.post(
            url,
            data=body.encode("utf-8"),
            headers=headers,
            timeout=config.timeout or 30,
        )
    except InterfaceError as e:
        return {"code": "-1", "message": str(e), "receipt_no": "", "channel": "http"}
    except requests.RequestException as e:
        return {
            "code": "-1",
            "message": f"接口调用失败：{e}",
            "receipt_no": "",
            "channel": "http",
        }

    text = response.text or ""
    if response.status_code >= 400:
        return {
            "code": "-1",
            "message": f"HTTP {response.status_code}：{text[:200]}",
            "receipt_no": "",
            "channel": "http",
        }
    try:
        data = response.json()
    except ValueError:
        return {
            "code": "-1",
            "message": f"回执非 JSON：{text[:200]}",
            "receipt_no": "",
            "channel": "http",
        }

    code = str(data.get("code", data.get("result", "")))
    success = code in ("0", "200", "SUCCESS", "success") or data.get("success") is True
    return {
        "code": "0" if success else (code or "-1"),
        "message": data.get("message") or data.get("msg") or "",
        "receipt_no": data.get("receipt_no") or data.get("receiptNo") or "",
        "channel": "http",
        "raw": text[:1000],
    }
