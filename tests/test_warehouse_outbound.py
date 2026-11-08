def setup_stock(client, auth, drug_qty=10, material_qty=5):
    supplier = client.post(
        "/suppliers/", json={"code": "SUP-OUT", "name": "出库测试供应商"},
        headers=auth["admin"],
    ).json()
    drug = client.post(
        "/drugs/", json={"name": "出库测试药", "base_price": 10.0},
        headers=auth["admin"],
    ).json()
    material = client.post(
        "/materials/items/",
        json={"code": "MAT-OUT", "name": "出库测试耗材", "unit": "包", "price": 20.0},
        headers=auth["admin"],
    ).json()
    inbound = client.post(
        "/inbound/orders",
        json={
            "order_type": "other",
            "supplier_id": supplier["id"],
            "items": [
                {
                    "kind": "drug",
                    "drug_id": drug["id"],
                    "batch_no": "OUT-B1",
                    "expiry": "2027-12-31",
                    "quantity": drug_qty,
                },
                {"kind": "material", "material_id": material["id"], "quantity": material_qty},
            ],
        },
        headers=auth["warehouse"],
    ).json()
    client.post(f"/inbound/orders/{inbound['id']}/check", json={"items": []}, headers=auth["warehouse"])
    client.post(f"/inbound/orders/{inbound['id']}/stock", headers=auth["warehouse"])
    return drug, material


def make_outbound(client, auth, drug, quantity=6):
    return client.post(
        "/warehouse/outbound-orders",
        json={
            "outbound_type": "requisition",
            "target_type": "pharmacy",
            "target_name": "药房",
            "note": "药房领用",
            "items": [
                {
                    "kind": "drug",
                    "drug_id": drug["id"],
                    "batch_no": "OUT-B1",
                    "expiry": "2027-12-31",
                    "quantity": quantity,
                }
            ],
        },
        headers=auth["pharmacist"],
    )


def test_outbound_drug_flow(client, auth):
    drug, material = setup_stock(client, auth)
    warehouse_before = client.get(f"/warehouse/stocks?drug_id={drug['id']}").json()[0]["quantity"]
    assert warehouse_before == 10

    r = make_outbound(client, auth, drug, 6)
    assert r.status_code == 201
    order = r.json()
    assert order["status"] == "submitted"
    assert order["outbound_no"].startswith("OUT")
    assert order["applicant"] == "pharmacist"

    approved = client.post(
        f"/warehouse/outbound-orders/{order['id']}/approve", headers=auth["warehouse"]
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["approver"] == "warehouse"

    issued = client.post(
        f"/warehouse/outbound-orders/{order['id']}/issue", headers=auth["warehouse"]
    )
    assert issued.status_code == 200
    assert issued.json()["status"] == "issued"

    warehouse = client.get(f"/warehouse/stocks?drug_id={drug['id']}").json()[0]
    assert warehouse["quantity"] == 4
    pharmacy = client.get(f"/pharmacy/stocks?drug_id={drug['id']}").json()
    assert pharmacy[0]["quantity"] == 6

    again = client.post(
        f"/warehouse/outbound-orders/{order['id']}/issue", headers=auth["warehouse"]
    )
    assert again.status_code == 400
    cancel = client.post(
        f"/warehouse/outbound-orders/{order['id']}/cancel", headers=auth["warehouse"]
    )
    assert cancel.status_code == 400


def test_outbound_material_to_pharmacy(client, auth):
    drug, material = setup_stock(client, auth)
    order = client.post(
        "/warehouse/outbound-orders",
        json={
            "outbound_type": "requisition",
            "target_type": "department",
            "target_name": "药房",
            "items": [{"kind": "material", "material_id": material["id"], "quantity": 2}],
        },
        headers=auth["pharmacist"],
    ).json()
    client.post(f"/warehouse/outbound-orders/{order['id']}/approve", headers=auth["warehouse"])
    client.post(f"/warehouse/outbound-orders/{order['id']}/issue", headers=auth["warehouse"])

    total = client.get(f"/materials/stocks?item_id={material['id']}").json()
    by_warehouse = {row["warehouse"]: row["quantity"] for row in total}
    assert by_warehouse["总库"] == 3
    assert by_warehouse["药房"] == 2


def test_outbound_insufficient_stock(client, auth):
    drug, material = setup_stock(client, auth, drug_qty=3)
    order = make_outbound(client, auth, drug, quantity=10).json()
    client.post(f"/warehouse/outbound-orders/{order['id']}/approve", headers=auth["warehouse"])
    r = client.post(f"/warehouse/outbound-orders/{order['id']}/issue", headers=auth["warehouse"])
    assert r.status_code == 400
    assert "库存不足" in r.json()["detail"]
    # 抽查总库数量未变
    assert client.get(f"/warehouse/stocks?drug_id={drug['id']}").json()[0]["quantity"] == 3


def test_outbound_cancel_and_permissions(client, auth):
    drug, material = setup_stock(client, auth)
    denied = client.post(
        "/warehouse/outbound-orders",
        json={"items": [{"kind": "drug", "drug_id": drug["id"], "batch_no": "OUT-B1", "quantity": 1}]},
        headers=auth["cashier"],
    )
    assert denied.status_code == 403

    order = make_outbound(client, auth, drug, 2).json()
    cancelled = client.post(
        f"/warehouse/outbound-orders/{order['id']}/cancel", headers=auth["warehouse"]
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    approve = client.post(
        f"/warehouse/outbound-orders/{order['id']}/approve", headers=auth["warehouse"]
    )
    assert approve.status_code == 400


def test_outbound_requires_batch(client, auth):
    drug, material = setup_stock(client, auth)
    r = client.post(
        "/warehouse/outbound-orders",
        json={"items": [{"kind": "drug", "drug_id": drug["id"], "quantity": 1}]},
        headers=auth["pharmacist"],
    )
    assert r.status_code == 400
    assert "批号" in r.json()["detail"]


def test_outbound_roles_split(client, auth):
    """药房申请、库房审核/出库：角色不能越权。"""
    drug, material = setup_stock(client, auth)

    # 药房不能审核/出库
    order = make_outbound(client, auth, drug, 2).json()
    denied_approve = client.post(
        f"/warehouse/outbound-orders/{order['id']}/approve", headers=auth["pharmacist"]
    )
    assert denied_approve.status_code == 403
    denied_issue = client.post(
        f"/warehouse/outbound-orders/{order['id']}/issue", headers=auth["pharmacist"]
    )
    assert denied_issue.status_code == 403

    # 库房不能自己发起领用
    denied_create = client.post(
        "/warehouse/outbound-orders",
        json={"items": [{"kind": "drug", "drug_id": drug["id"], "batch_no": "OUT-B1", "quantity": 1}]},
        headers=auth["warehouse"],
    )
    assert denied_create.status_code == 403

    # 库房可审核
    approved = client.post(
        f"/warehouse/outbound-orders/{order['id']}/approve", headers=auth["warehouse"]
    )
    assert approved.status_code == 200


