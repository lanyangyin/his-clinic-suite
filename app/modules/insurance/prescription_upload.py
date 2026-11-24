"""处方级医保上传适配器。

未配置 URL 时只做本地状态/审计；配置后按一张处方一次 HTTP 调用。
真实接入需要医保平台提供的签名、报文和回执格式，本适配器保留最小扩展点。
"""
import json
from urllib.request import Request, urlopen

from app import settings


def upload_prescription(header, items: list, db=None) -> dict:
    from app.modules.integrations.service import get_value

    url = get_value(db, "insurance_upload_url") if db is not None else getattr(settings, "INSURANCE_PRESCRIPTION_UPLOAD_URL", "")
    token = get_value(db, "insurance_upload_token") if db is not None else getattr(settings, "INSURANCE_PRESCRIPTION_UPLOAD_TOKEN", "")
    payload = {
        "prescription_no": header.prescription_no,
        "type": header.type,
        "patient_id": None,
        "items": [
            {
                "drug_id": item.drug_id,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "insurance_category": item.insurance_category,
            }
            for item in items
        ],
    }
    if not url:
        return {"mode": "local", "ok": True, "message": "未配置医保上传地址，记录本地上传状态"}
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}" if token else "",
        },
    )
    with urlopen(req, timeout=10) as response:
        body = response.read().decode("utf-8")
        result = json.loads(body) if body else {}
    if not result.get("ok", True):
        raise ValueError(result.get("message") or "医保上传失败")
    return {"mode": "http", "ok": True, "response": result}
