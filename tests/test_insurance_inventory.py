from datetime import date, timedelta


def setup_movement(client, auth):
    today = date.today().isoformat()
    client.post(
        "/insurance/catalog/import",
        files={
            "file": (
                "inv.csv",
                (
                    "国家医保药品代码,药品名称,剂型,规格,生产厂家,单位,医保类别\n"
                    "INV001,进销存测试药,片剂,0.1g*10片,演示药业,盒,甲\n"
                ).encode("utf-8"),
                "text/csv",
            )
        },
        headers=auth["admin"],
    )
    drug = client.post(
        "/drugs/",
        json={
            "name": "进销存测试药",
            "spec": "0.1g*10片",
            "dosage_form": "片剂",
            "insurance_code": "INV001",
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
                    "batch_no": "INV-B1",
                    "expiry": "2028-12-31",
                    "quantity": 5,
                }
            ],
        },
        headers=auth["warehouse"],
    ).json()
    client.post(f"/inbound/orders/{inbound['id']}/check", json={"items": []}, headers=auth["warehouse"])
    client.post(f"/inbound/orders/{inbound['id']}/stock", headers=auth["warehouse"])

    order = client.post(
        "/warehouse/outbound-orders",
        json={"items": [{"kind": "drug", "drug_id": drug["id"], "batch_no": "INV-B1", "quantity": 2}]},
        headers=auth["pharmacist"],
    ).json()
    client.post(f"/warehouse/outbound-orders/{order['id']}/approve", headers=auth["warehouse"])
    client.post(f"/warehouse/outbound-orders/{order['id']}/issue", headers=auth["warehouse"])
    return drug, today


def test_inventory_preview_and_upload(client, auth):
    drug, today = setup_movement(client, auth)
    preview = client.post(
        "/insurance/inventory/preview",
        json={"start_date": today, "end_date": today},
        headers=auth["admin"],
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["record_count"] >= 3  # 入库 1 + 出库 2
    assert body["total_amount"] > 0
    assert body["unmatched_count"] == 0
    first = body["records"][0]
    assert first["insurance_code"] == "INV001"
    assert first["drug_name"] == "进销存测试药"
    assert first["business_type"] in ("入库", "出库")
    assert first["direction"] in ("in", "out")

    upload = client.post(
        "/insurance/inventory/upload",
        json={"start_date": today, "end_date": today},
        headers=auth["admin"],
    )
    assert upload.status_code == 200, upload.text
    record = upload.json()
    assert record["status"] == "success"
    assert record["record_count"] >= 3
    assert record["upload_no"].startswith("INV")

    history = client.get("/insurance/inventory/uploads", headers=auth["admin"]).json()
    assert history[0]["id"] == record["id"]

    detail = client.get(
        f"/insurance/inventory/uploads/{record['id']}", headers=auth["admin"]
    ).json()
    assert "INV001" in detail["payload"]
    assert "receipt_no" in detail["response"]


def test_inventory_empty_period_and_permissions(client, auth):
    empty = client.post(
        "/insurance/inventory/preview",
        json={"start_date": "2000-01-01", "end_date": "2000-01-02"},
        headers=auth["admin"],
    ).json()
    assert empty["record_count"] == 0

    failed = client.post(
        "/insurance/inventory/upload",
        json={"start_date": "2000-01-01", "end_date": "2000-01-02"},
        headers=auth["admin"],
    )
    assert failed.status_code == 400

    assert client.post(
        "/insurance/inventory/preview",
        json={"start_date": "2000-01-01", "end_date": "2000-01-02"},
        headers=auth["cashier"],
    ).status_code == 403
    assert client.post(
        "/insurance/inventory/upload",
        json={"start_date": "2000-01-01", "end_date": "2000-01-02"},
        headers=auth["warehouse"],
    ).status_code == 403


def test_inventory_unmatched_count(client, auth):
    today = date.today().isoformat()
    drug = client.post(
        "/drugs/", json={"name": "无码药", "base_price": 5.0}, headers=auth["admin"]
    ).json()
    inbound = client.post(
        "/inbound/orders",
        json={
            "order_type": "drug",
            "items": [
                {
                    "kind": "drug",
                    "drug_id": drug["id"],
                    "batch_no": "NOCODE-B1",
                    "expiry": "2028-12-31",
                    "quantity": 2,
                }
            ],
        },
        headers=auth["warehouse"],
    ).json()
    client.post(f"/inbound/orders/{inbound['id']}/check", json={"items": []}, headers=auth["warehouse"])
    client.post(f"/inbound/orders/{inbound['id']}/stock", headers=auth["warehouse"])

    preview = client.post(
        "/insurance/inventory/preview",
        json={"start_date": today, "end_date": today},
        headers=auth["admin"],
    ).json()
    assert preview["unmatched_count"] == 1

def test_inventory_admin_page(client, auth):
    drug, today = setup_movement(client, auth)
    client.cookies.clear()
    resp = client.post(
        "/admin/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    assert resp.status_code == 302

    page = client.get(f"/admin/insurance-inventory?start_date={today}&end_date={today}")
    assert page.status_code == 200
    assert "医保进销存上传" in page.text
    assert "INV001" in page.text

    uploaded = client.post(
        "/admin/insurance-inventory/upload",
        data={"start_date": today, "end_date": today},
        follow_redirects=False,
    )
    assert uploaded.status_code == 302

    page = client.get(f"/admin/insurance-inventory?start_date={today}&end_date={today}")
    assert "success" in page.text

    history = client.get("/insurance/inventory/uploads", headers=auth["admin"]).json()
    detail = client.get(f"/admin/insurance-inventory/{history[0]['id']}")
    assert detail.status_code == 200
    assert "医保回执" in detail.text
    assert "INV001" in detail.text
