import hashlib
import hmac
import json

import app.modules.payment_gateway.service as gateway


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload, ensure_ascii=False)

    def json(self):
        return self._payload


def make_encounter_with_charge(client, auth):
    patient = client.post(
        "/patients/", json={"name": "支付测试患者", "id_number": "110101199003011234"},
        headers=auth["cashier"],
    ).json()
    department = client.post(
        "/departments/", json={"name": "内科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/",
        json={"name": "王医生", "department_id": department["id"]},
        headers=auth["admin"],
    ).json()
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    encounter = client.post(
        "/encounters/", json={"registration_id": reg["id"]}, headers=auth["doctor"]
    ).json()
    drug = client.post(
        "/drugs/",
        json={"name": "支付测试药", "base_price": 10.0, "insurance_ratio": 0.8},
        headers=auth["admin"],
    ).json()
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 2},
        headers=auth["doctor"],
    )
    return encounter["id"]


def login_admin(client):
    client.cookies.clear()
    client.post(
        "/admin/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )


def configure_wechat(client):
    return client.post(
        "/admin/payment-channels",
        data={
            "channel": "wechat",
            "enabled": "on",
            "gateway_url": "https://pay.example.com/wechat",
            "merchant_id": "M123",
            "app_id": "app123",
            "api_secret": "secret123",
            "terminal_id": "T001",
            "cert_path": "",
            "remark": "测试",
        },
        follow_redirects=False,
    )


def test_wechat_mock_payment(client, auth):
    encounter_id = make_encounter_with_charge(client, auth)
    payment = client.post(
        "/payments/",
        json={"encounter_id": encounter_id, "channel": "wechat", "auth_code": "134567"},
        headers=auth["cashier"],
    )
    assert payment.status_code == 201, payment.text
    body = payment.json()
    assert body["channel"] == "wechat"
    assert body["channel_status"] == "mock"
    assert body["channel_trade_no"].startswith("MOCK")
    assert body["insurance_amount"] == 16.0
    assert body["self_pay_amount"] == 4.0


def test_insurance_card_mock_payment(client, auth):
    encounter_id = make_encounter_with_charge(client, auth)
    payment = client.post(
        "/payments/",
        json={
            "encounter_id": encounter_id,
            "channel": "insurance_card",
            "card_no": "YB123456",
        },
        headers=auth["cashier"],
    )
    assert payment.status_code == 201, payment.text
    body = payment.json()
    assert body["channel"] == "insurance_card"
    assert body["channel_trade_no"].startswith("MOCK")


def test_configured_gateway_payment(client, auth, monkeypatch):
    encounter_id = make_encounter_with_charge(client, auth)
    login_admin(client)
    assert configure_wechat(client).status_code == 302

    captured = {}

    def fake_post(url, data=None, headers=None, timeout=None):
        captured["url"] = url
        captured["data"] = data
        captured["headers"] = headers
        captured["timeout"] = timeout
        return FakeResponse({"code": "0", "trade_no": "WX123", "message": "支付成功"})

    monkeypatch.setattr(gateway.requests, "post", fake_post)
    payment = client.post(
        "/payments/",
        json={"encounter_id": encounter_id, "channel": "wechat", "auth_code": "134567"},
        headers=auth["cashier"],
    )
    assert payment.status_code == 201, payment.text
    body = payment.json()
    assert body["channel"] == "wechat"
    assert body["channel_status"] == "http"
    assert body["channel_trade_no"] == "WX123"

    assert captured["url"] == "https://pay.example.com/wechat"
    payload = json.loads(captured["data"].decode("utf-8"))
    assert payload["amount"] == 4.0
    assert payload["merchant_id"] == "M123"
    assert payload["auth_code"] == "134567"
    timestamp = captured["headers"]["X-Timestamp"]
    canonical = f"M123|{payload['out_trade_no']}|4.0|{timestamp}"
    expected = hmac.new(
        b"secret123", canonical.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    assert captured["headers"]["X-Sign"] == expected


def test_gateway_failure_aborts_payment(client, auth, monkeypatch):
    encounter_id = make_encounter_with_charge(client, auth)
    login_admin(client)
    configure_wechat(client)
    monkeypatch.setattr(
        gateway.requests,
        "post",
        lambda *args, **kwargs: FakeResponse({"code": "FAIL", "message": "余额不足"}),
    )
    payment = client.post(
        "/payments/",
        json={"encounter_id": encounter_id, "channel": "wechat", "auth_code": "134567"},
        headers=auth["cashier"],
    )
    assert payment.status_code == 400
    assert "支付失败" in payment.json()["detail"]
    charges = client.get(
        f"/charges/encounters/{encounter_id}", headers=auth["cashier"]
    ).json()
    assert all(charge["status"] == "pending" for charge in charges)


def test_gateway_connection_error(client, auth, monkeypatch):
    encounter_id = make_encounter_with_charge(client, auth)
    login_admin(client)
    configure_wechat(client)

    def boom(*args, **kwargs):
        raise gateway.requests.ConnectionError("refused")

    monkeypatch.setattr(gateway.requests, "post", boom)
    payment = client.post(
        "/payments/",
        json={"encounter_id": encounter_id, "channel": "wechat", "auth_code": "134567"},
        headers=auth["cashier"],
    )
    assert payment.status_code == 400
    assert "支付网关连接失败" in payment.json()["detail"]


def test_refund_mock_channel(client, auth):
    encounter_id = make_encounter_with_charge(client, auth)
    payment = client.post(
        "/payments/",
        json={"encounter_id": encounter_id, "channel": "wechat", "auth_code": "134567"},
        headers=auth["cashier"],
    ).json()
    refund = client.post(
        f"/payments/{payment['id']}/refund", headers=auth["cashier"]
    )
    assert refund.status_code == 200, refund.text
    assert refund.json()["status"] == "refunded"


def test_payment_channel_admin_page(client, auth):
    login_admin(client)
    page = client.get("/admin/payment-channels")
    assert page.status_code == 200
    assert "支付通道配置" in page.text
    assert "未配置（模拟）" in page.text

    assert configure_wechat(client).status_code == 302
    page = client.get("/admin/payment-channels")
    assert "已配置（真实通道）" in page.text
    assert "secret123" not in page.text
    assert "支付接口" not in page.text


def test_payment_channel_requires_admin(client, auth):
    client.cookies.clear()
    resp = client.post(
        "/admin/payment-channels",
        data={"channel": "wechat", "gateway_url": "https://evil.example.com"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "/admin/login" in resp.headers.get("location", "")
