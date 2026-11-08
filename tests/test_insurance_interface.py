import hashlib
import hmac
import json
from datetime import date

import app.modules.insurance_inventory.adapter as adapter


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload, ensure_ascii=False)

    def json(self):
        return self._payload


def login_admin(client):
    client.cookies.clear()
    resp = client.post(
        "/admin/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    assert resp.status_code == 302


def save_config(client, **overrides):
    data = {
        "enabled": "on",
        "base_url": "https://mi.example.com",
        "upload_path": "/inventory/upload",
        "org_code": "H123456",
        "org_name": "演示医院",
        "app_id": "app001",
        "app_secret": "secret123",
        "sign_type": "HMAC-SHA256",
        "timeout": "15",
        "remark": "测试配置",
    }
    data.update(overrides)
    return client.post("/admin/insurance-interface", data=data, follow_redirects=False)


def make_movement(client, auth):
    today = date.today().isoformat()
    drug = client.post(
        "/drugs/",
        json={
            "name": "接口测试药",
            "spec": "0.1g*10片",
            "dosage_form": "片剂",
            "insurance_code": "ITF001",
            "base_price": 10.0,
        },
        headers=auth["admin"],
    ).json()
    inbound = client.post(
        "/inbound/orders",
        json={
            "order_type": "drug",
            "items": [
                {
                    "kind": "drug",
                    "drug_id": drug["id"],
                    "batch_no": "ITF-B1",
                    "expiry": "2028-12-31",
                    "quantity": 2,
                }
            ],
        },
        headers=auth["warehouse"],
    ).json()
    client.post(f"/inbound/orders/{inbound['id']}/check", json={"items": []}, headers=auth["warehouse"])
    client.post(f"/inbound/orders/{inbound['id']}/stock", headers=auth["warehouse"])
    return today


def test_interface_page_blank_by_default(client, auth):
    login_admin(client)
    page = client.get("/admin/insurance-interface")
    assert page.status_code == 200
    assert "医保接口配置" in page.text
    assert "未配置（进销存上传走 Mock" in page.text
    assert 'name="base_url" value=""' in page.text


def test_save_config_masks_secrets(client, auth):
    login_admin(client)
    saved = save_config(client)
    assert saved.status_code == 302

    page = client.get("/admin/insurance-interface")
    assert "已配置（进销存上传走真实 HTTPS 接口）" in page.text
    assert "H123456" in page.text
    assert "secret123" not in page.text
    assert 'value=""' in page.text  # 密钥输入框不回显明文


def test_upload_uses_configured_http_interface(client, auth, monkeypatch):
    today = make_movement(client, auth)
    login_admin(client)
    assert save_config(client).status_code == 302

    captured = {}

    def fake_post(url, data=None, headers=None, timeout=None):
        captured["url"] = url
        captured["data"] = data
        captured["headers"] = headers
        captured["timeout"] = timeout
        return FakeResponse(
            {"code": "0", "message": "接收成功", "receipt_no": "R123456"}
        )

    monkeypatch.setattr(adapter.requests, "post", fake_post)

    upload = client.post(
        "/insurance/inventory/upload",
        json={"start_date": today, "end_date": today},
        headers=auth["admin"],
    ).json()
    assert upload["status"] == "success"
    assert upload["channel"] == "http"

    detail = client.get(
        f"/insurance/inventory/uploads/{upload['id']}", headers=auth["admin"]
    ).json()
    response = json.loads(detail["response"])
    assert response["receipt_no"] == "R123456"
    assert response["channel"] == "http"

    assert captured["url"] == "https://mi.example.com/inventory/upload"
    assert captured["headers"]["X-Org-Code"] == "H123456"
    assert captured["headers"]["X-App-Id"] == "app001"
    assert captured["timeout"] == 15
    body_text = captured["data"].decode("utf-8")
    body = json.loads(body_text)
    assert body["org_code"] == "H123456"
    assert body["data"]["records"]

    timestamp = captured["headers"]["X-Timestamp"]
    nonce = captured["headers"]["X-Nonce"]
    canonical = f"H123456{timestamp}{nonce}{body_text}"
    expected = hmac.new(
        b"secret123", canonical.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    assert captured["headers"]["X-Sign"] == expected


def test_upload_marks_failed_on_platform_rejection(client, auth, monkeypatch):
    today = make_movement(client, auth)
    login_admin(client)
    save_config(client)

    monkeypatch.setattr(
        adapter.requests,
        "post",
        lambda *args, **kwargs: FakeResponse({"code": "1", "message": "平台拒绝"}),
    )
    upload = client.post(
        "/insurance/inventory/upload",
        json={"start_date": today, "end_date": today},
        headers=auth["admin"],
    ).json()
    assert upload["status"] == "failed"
    assert upload["channel"] == "http"
    detail = client.get(
        f"/insurance/inventory/uploads/{upload['id']}", headers=auth["admin"]
    ).json()
    assert "平台拒绝" in detail["response"]


def test_upload_marks_failed_on_connection_error(client, auth, monkeypatch):
    today = make_movement(client, auth)
    login_admin(client)
    save_config(client)

    def boom(*args, **kwargs):
        raise adapter.requests.ConnectionError("connection refused")

    monkeypatch.setattr(adapter.requests, "post", boom)
    upload = client.post(
        "/insurance/inventory/upload",
        json={"start_date": today, "end_date": today},
        headers=auth["admin"],
    ).json()
    assert upload["status"] == "failed"
    detail = client.get(
        f"/insurance/inventory/uploads/{upload['id']}", headers=auth["admin"]
    ).json()
    assert "接口调用失败" in detail["response"]


def test_blank_config_falls_back_to_mock(client, auth):
    today = make_movement(client, auth)
    upload = client.post(
        "/insurance/inventory/upload",
        json={"start_date": today, "end_date": today},
        headers=auth["admin"],
    ).json()
    assert upload["status"] == "success"
    assert upload["channel"] == "mock"
    detail = client.get(
        f"/insurance/inventory/uploads/{upload['id']}", headers=auth["admin"]
    ).json()
    assert "Mock" in detail["response"]


def test_interface_config_requires_admin_session(client, auth):
    client.cookies.clear()
    resp = client.post(
        "/admin/insurance-interface",
        data={"base_url": "https://evil.example.com"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "/admin/login" in resp.headers.get("location", "")
