def setup_master(client, auth):
    supplier = client.post(
        "/suppliers/",
        json={"code": "SUP1", "name": "演示医药公司", "contact": "张三", "phone": "13800000000"},
        headers=auth["admin"],
    ).json()
    drug = client.post(
        "/drugs/",
        json={"name": "入库测试药", "spec": "0.25g*24粒", "unit": "盒", "base_price": 12.5},
        headers=auth["admin"],
    ).json()
    device = client.post(
        "/materials/items/",
        json={
            "code": "DEV001",
            "name": "电子血压计",
            "spec": "HEM-7120",
            "unit": "台",
            "price": 300,
            "category": "device",
            "manufacturer": "欧姆龙",
            "registration_no": "沪械注准20202070001",
        },
        headers=auth["admin"],
    ).json()
    office = client.post(
        "/materials/items/",
        json={"code": "OFF001", "name": "打印纸", "spec": "A4", "unit": "箱", "price": 120, "category": "office"},
        headers=auth["admin"],
    ).json()
    return supplier, drug, device, office


def make_order(client, auth, supplier, drug, device, rejected_note="包装破损"):
    return client.post(
        "/inbound/orders",
        json={
            "order_type": "other",
            "supplier_id": supplier["id"],
            "source": "purchase",
            "delivery_no": "随货同行-001",
            "invoice_no": "FP-001",
            "items": [
                {
                    "kind": "drug",
                    "drug_id": drug["id"],
                    "batch_no": "B20261101",
                    "expiry": "2027-12-31",
                    "quantity": 10,
                    "unit_price": 12.5,
                    "storage_condition": "常温",
                    "location": "A-01",
                },
                {
                    "kind": "material",
                    "material_id": device["id"],
                    "quantity": 5,
                    "unit_price": 300,
                    "warehouse": "总库",
                },
            ],
        },
        headers=auth["pharmacist"],
    )


def test_inbound_flow_stock_posted(client, auth):
    supplier, drug, device, office = setup_master(client, auth)
    r = make_order(client, auth, supplier, drug, device)
    assert r.status_code == 201
    order = r.json()
    assert order["status"] == "received"
    assert order["order_no"].startswith("IN")
    assert len(order["items"]) == 2
    drug_item = next(i for i in order["items"] if i["kind"] == "drug")
    assert drug_item["batch_no"] == "B20261101"
    assert drug_item["amount"] == 125.0

    # 验收：药品不合格 2 盒
    checked = client.post(
        f"/inbound/orders/{order['id']}/check",
        json={"items": [{"item_id": drug_item["id"], "rejected_qty": 2, "reject_reason": "包装破损"}]},
        headers=auth["pharmacist"],
    )
    assert checked.status_code == 200
    assert checked.json()["status"] == "checked"
    assert checked.json()["checked_by"] == "pharmacist"

    stocked = client.post(f"/inbound/orders/{order['id']}/stock", headers=auth["pharmacist"])
    assert stocked.status_code == 200
    assert stocked.json()["status"] == "stocked"

    stocks = client.get(f"/pharmacy/stocks?drug_id={drug['id']}").json()
    assert stocks[0]["quantity"] == 8
    material_stocks = client.get(f"/materials/stocks?item_id={device['id']}").json()
    assert material_stocks[0]["quantity"] == 5


def test_inbound_drug_requires_batch_and_expiry(client, auth):
    supplier, drug, device, office = setup_master(client, auth)
    bad = client.post(
        "/inbound/orders",
        json={
            "order_type": "drug",
            "items": [{"kind": "drug", "drug_id": drug["id"], "quantity": 1, "unit_price": 10}],
        },
        headers=auth["pharmacist"],
    )
    assert bad.status_code == 400
    assert "批号" in bad.json()["detail"]

    bad_expiry = client.post(
        "/inbound/orders",
        json={
            "order_type": "drug",
            "items": [{"kind": "drug", "drug_id": drug["id"], "batch_no": "B1", "quantity": 1}],
        },
        headers=auth["pharmacist"],
    )
    assert bad_expiry.status_code == 400
    assert "有效期" in bad_expiry.json()["detail"]


def test_inbound_device_requires_registration_no(client, auth):
    supplier, drug, device, office = setup_master(client, auth)
    device_without_license = client.post(
        "/materials/items/",
        json={"code": "DEV002", "name": "简易雾化器", "price": 200, "category": "device"},
        headers=auth["admin"],
    ).json()
    r = client.post(
        "/inbound/orders",
        json={
            "order_type": "device",
            "items": [{"kind": "material", "material_id": device_without_license["id"], "quantity": 1}],
        },
        headers=auth["pharmacist"],
    )
    assert r.status_code == 400
    assert "注册证" in r.json()["detail"]


def test_inbound_state_machine_and_permissions(client, auth):
    supplier, drug, device, office = setup_master(client, auth)
    order = make_order(client, auth, supplier, drug, device).json()

    # 未验收不能入库
    early = client.post(f"/inbound/orders/{order['id']}/stock", headers=auth["pharmacist"])
    assert early.status_code == 400
    assert "验收" in early.json()["detail"]

    # 收费员不能创建入库单
    denied = client.post(
        "/inbound/orders",
        json={"order_type": "office", "items": [{"kind": "material", "material_id": office["id"], "quantity": 1}]},
        headers=auth["cashier"],
    )
    assert denied.status_code == 403

    # 取消（未入库）
    cancelled = client.post(f"/inbound/orders/{order['id']}/cancel", headers=auth["pharmacist"])
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    again = client.post(f"/inbound/orders/{order['id']}/cancel", headers=auth["pharmacist"])
    assert again.status_code == 400


def test_inbound_list_and_details(client, auth):
    supplier, drug, device, office = setup_master(client, auth)
    order = make_order(client, auth, supplier, drug, device).json()
    rows = client.get("/inbound/orders?status=received", headers=auth["admin"]).json()
    assert len(rows) == 1
    assert rows[0]["id"] == order["id"]
    assert client.get(f"/inbound/orders/{order['id']}").json()["delivery_no"] == "随货同行-001"
    assert client.get("/inbound/orders/999").status_code == 404
