from app.modules.labels import zh
from his_client.labels import zh as client_zh


def test_server_labels():
    assert zh("role", "warehouse") == "库房管理员"
    assert zh("inbound_status", "stocked") == "已入库"
    assert zh("outbound_status", "partially_issued") == "部分出库"
    assert zh("outbound_type", "return") == "退库"
    assert zh("trace_status", "in_stock") == "在库"
    assert zh("upload_status", "success") == "成功"
    assert zh("channel", "mock") == "模拟"
    assert zh("ref_type", "dispense_return") == "退药"
    assert zh("http_method", "POST") == "提交"
    assert zh("http_status", "200") == "200 成功"
    assert zh("role", "unknown") == "unknown"
    assert zh("role", None) == "—"


def test_client_labels():
    assert client_zh("role", "pharmacist") == "药师"
    assert client_zh("registration_status", "registered") == "已挂号"
    assert client_zh("charge_status", "paid") == "已收费"
    assert client_zh("payment_status", "refunded") == "已退费"
    assert client_zh("ticket_status", "waiting") == "等候中"
    assert client_zh("treatment_status", "executed") == "已执行"
    assert client_zh("trace_status", "used") == "已使用"
    assert client_zh("outbound_status", "approved") == "已审核"


def test_admin_pages_show_chinese(client, auth):
    drug = client.post(
        "/drugs/", json={"name": "汉化测试药", "base_price": 10.0},
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
                    "batch_no": "ZH-B1",
                    "expiry": "2028-12-31",
                    "quantity": 2,
                }
            ],
        },
        headers=auth["warehouse"],
    ).json()
    client.post(f"/inbound/orders/{inbound['id']}/check", json={"items": []}, headers=auth["warehouse"])
    client.post(f"/inbound/orders/{inbound['id']}/stock", headers=auth["warehouse"])

    client.cookies.clear()
    client.post(
        "/admin/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    page = client.get("/admin/inbound")
    assert "<td>已入库</td>" in page.text
    assert "<td>药品</td>" in page.text

    users = client.get("/admin/users")
    assert "<td>管理员</td>" in users.text
    assert "库房管理员" in users.text

    audit = client.get("/admin/audit")
    assert "库房管理员" in audit.text
    assert "提交" in audit.text
