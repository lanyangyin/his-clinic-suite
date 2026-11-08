"""支付通道：现金/微信/支付宝/POS/医保卡。

配置默认留空：未配置时模拟成功，便于先跑通流程；
实际部署在管理台「支付配置」填商户号/网关/密钥/终端号即可走真实接口。
"""
import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime

import requests
from sqlalchemy.orm import Session

from .models import PaymentChannelConfig

CHANNELS: dict[str, str] = {
    "cash": "现金",
    "wechat": "微信支付",
    "alipay": "支付宝",
    "pos": "POS 刷卡",
    "insurance_card": "医保卡",
}

CHANNEL_ORDER = ["cash", "wechat", "alipay", "pos", "insurance_card"]


def get_config(db: Session, channel: str) -> PaymentChannelConfig | None:
    return (
        db.query(PaymentChannelConfig)
        .filter(PaymentChannelConfig.channel == channel)
        .first()
    )


def channel_rows(db: Session) -> list[dict]:
    """管理台展示用：固定五个通道，未建配置时显示空白默认值。"""
    rows = []
    for channel in CHANNEL_ORDER:
        config = get_config(db, channel)
        rows.append(
            {
                "channel": channel,
                "name": config.display_name if config and config.display_name else CHANNELS[channel],
                "enabled": bool(config and config.enabled),
                "gateway_url": config.gateway_url if config else "",
                "merchant_id": config.merchant_id if config else "",
                "app_id": config.app_id if config else "",
                "terminal_id": config.terminal_id if config else "",
                "cert_path": config.cert_path if config else "",
                "remark": config.remark if config else "",
                "secret_mask": mask_secret(config.api_secret) if config else "",
                "configured": bool(config and config.enabled and config.gateway_url),
            }
        )
    return rows


def save_config(
    db: Session,
    channel: str,
    *,
    enabled: bool,
    gateway_url: str,
    merchant_id: str,
    app_id: str,
    api_secret: str,
    terminal_id: str,
    cert_path: str,
    remark: str,
    updated_by: str,
) -> PaymentChannelConfig:
    if channel not in CHANNELS:
        raise ValueError("未知支付通道")
    config = get_config(db, channel)
    if not config:
        config = PaymentChannelConfig(channel=channel)
        db.add(config)
    config.enabled = enabled
    config.gateway_url = gateway_url.strip()
    config.merchant_id = merchant_id.strip()
    config.app_id = app_id.strip()
    config.terminal_id = terminal_id.strip()
    config.cert_path = cert_path.strip()
    config.remark = remark.strip()
    if api_secret:
        config.api_secret = api_secret
    config.updated_by = updated_by
    config.updated_at = datetime.now()
    db.commit()
    db.refresh(config)
    return config


def mask_secret(value: str, keep: int = 3) -> str:
    if not value:
        return ""
    return "*" * max(len(value) - keep, 0) + value[-3:]


def _live(config: PaymentChannelConfig | None) -> bool:
    return bool(config and config.enabled and config.gateway_url.strip())


def _mock_trade_no(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:16].upper()}"


def _sign(secret: str, canonical: str) -> str:
    return hmac.new(
        secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def charge(
    db: Session,
    channel: str,
    amount: float,
    *,
    auth_code: str = "",
    card_no: str = "",
    subject: str = "",
) -> dict:
    """发起支付；返回 {status, trade_no, message, channel, raw?}。"""
    if channel not in CHANNELS:
        return {"status": "failed", "trade_no": "", "message": "未知支付通道", "channel": channel}
    if channel == "cash":
        return {
            "status": "success",
            "trade_no": "",
            "message": "现金收费成功",
            "channel": "cash",
        }
    if amount <= 0:
        return {
            "status": "success",
            "trade_no": "",
            "message": "无需自费，医保已覆盖",
            "channel": channel,
        }

    config = get_config(db, channel)
    if not _live(config):
        return {
            "status": "success",
            "trade_no": _mock_trade_no("MOCK"),
            "message": f"{CHANNELS[channel]}模拟支付成功（未配置真实通道）",
            "channel": channel,
            "channel_status": "mock",
        }

    if channel in ("wechat", "alipay") and not auth_code:
        return {
            "status": "failed",
            "trade_no": "",
            "message": "请扫描/输入付款码",
            "channel": channel,
        }
    if channel == "insurance_card" and not card_no:
        return {
            "status": "failed",
            "trade_no": "",
            "message": "请刷医保卡/输入卡号",
            "channel": channel,
        }

    out_trade_no = f"PAY{datetime.now():%Y%m%d%H%M%S}{uuid.uuid4().hex[:6].upper()}"
    timestamp = str(int(time.time()))
    payload = {
        "channel": channel,
        "merchant_id": config.merchant_id,
        "app_id": config.app_id,
        "terminal_id": config.terminal_id,
        "out_trade_no": out_trade_no,
        "amount": round(amount, 2),
        "auth_code": auth_code,
        "card_no": card_no,
        "subject": subject or "门诊收费",
        "timestamp": timestamp,
    }
    canonical = f"{config.merchant_id}|{out_trade_no}|{payload['amount']}|{timestamp}"
    headers = {
        "Content-Type": "application/json",
        "X-Merchant-Id": config.merchant_id,
        "X-App-Id": config.app_id,
        "X-Timestamp": timestamp,
        "X-Sign": _sign(config.api_secret, canonical),
    }
    try:
        response = requests.post(
            config.gateway_url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            timeout=20,
        )
    except requests.RequestException as e:
        return {
            "status": "failed",
            "trade_no": "",
            "message": f"支付网关连接失败：{e}",
            "channel": channel,
        }

    text = response.text or ""
    if response.status_code >= 400:
        return {
            "status": "failed",
            "trade_no": "",
            "message": f"支付网关 HTTP {response.status_code}：{text[:200]}",
            "channel": channel,
        }
    try:
        body = response.json()
    except ValueError:
        return {
            "status": "failed",
            "trade_no": "",
            "message": f"支付网关回执非 JSON：{text[:200]}",
            "channel": channel,
        }
    code = str(body.get("code", body.get("result", "")))
    success = code in ("0", "200", "SUCCESS", "success") or body.get("success") is True
    return {
        "status": "success" if success else "failed",
        "trade_no": body.get("trade_no") or body.get("tradeNo") or out_trade_no,
        "message": body.get("message") or body.get("msg") or ("支付成功" if success else "支付失败"),
        "channel": channel,
        "channel_status": "http",
        "raw": text[:1000],
    }


def refund(
    db: Session, channel: str, trade_no: str, amount: float
) -> dict:
    """支付退款；未配置/现金走模拟，配置后调用网关。"""
    if channel == "cash" or amount <= 0:
        return {"status": "success", "message": "现金/无需退款"}
    config = get_config(db, channel)
    if not _live(config):
        return {"status": "success", "message": f"{CHANNELS[channel]}模拟退款成功"}
    payload = {
        "type": "refund",
        "channel": channel,
        "merchant_id": config.merchant_id,
        "trade_no": trade_no,
        "amount": round(amount, 2),
        "timestamp": str(int(time.time())),
    }
    try:
        response = requests.post(
            config.gateway_url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            timeout=20,
        )
        body = response.json()
    except (requests.RequestException, ValueError) as e:
        return {"status": "failed", "message": f"退款失败：{e}"}
    code = str(body.get("code", body.get("result", "")))
    success = code in ("0", "200", "SUCCESS", "success") or body.get("success") is True
    return {
        "status": "success" if success else "failed",
        "message": body.get("message") or body.get("msg") or "",
    }
