def make_drug(client, auth, name="阿莫西林胶囊", price=12.5):
    return client.post(
        "/drugs/", json={"name": name, "base_price": price}, headers=auth["admin"]
    ).json()


def purchase(client, auth, drug_id, batch_no="W001", expiry="2027-06-30", quantity=100):
    return client.post(
        "/warehouse/purchase",
        json={"drug_id": drug_id, "batch_no": batch_no, "expiry": expiry, "quantity": quantity},
        headers=auth["admin"],
    )


def test_purchase_stock(client, auth):
    drug = make_drug(client, auth)
    r = purchase(client, auth, drug["id"])
    assert r.status_code == 201
    body = r.json()
    assert body["quantity"] == 100
    assert body["drug_name"] == "阿莫西林胶囊"
    assert body["expiry"] == "2027-06-30"


def test_purchase_same_batch_merges(client, auth):
    drug = make_drug(client, auth)
    first = purchase(client, auth, drug["id"], quantity=50).json()
    second = purchase(client, auth, drug["id"], quantity=30)
    assert second.status_code == 201
    assert second.json()["id"] == first["id"]
    assert second.json()["quantity"] == 80


def test_purchase_missing_drug(client, auth):
    r = purchase(client, auth, 999)
    assert r.status_code == 400
    assert r.json()["detail"] == "药品不存在"


def test_transfer_to_pharmacy(client, auth):
    drug = make_drug(client, auth)
    purchase(client, auth, drug["id"], quantity=100)
    r = client.post(
        "/warehouse/transfer",
        json={"drug_id": drug["id"], "batch_no": "W001", "quantity": 40},
        headers=auth["pharmacist"],
    )
    assert r.status_code == 200
    body = r.json()
    assert body["warehouse_quantity"] == 60
    assert body["pharmacy_quantity"] == 40
    assert body["transferred_quantity"] == 40
    # 药房库存可查
    got = client.get(f"/pharmacy/stocks/{body['pharmacy_stock_id']}").json()
    assert got["quantity"] == 40
    assert got["batch_no"] == "W001"


def test_transfer_merges_into_existing_pharmacy_batch(client, auth):
    drug = make_drug(client, auth)
    purchase(client, auth, drug["id"], quantity=100)
    # 药房先有同批次库存（门诊入库）
    client.post(
        "/pharmacy/stock-in",
        json={"drug_id": drug["id"], "batch_no": "W001", "expiry": "2027-06-30", "quantity": 10},
        headers=auth["pharmacist"],
    )
    r = client.post(
        "/warehouse/transfer",
        json={"drug_id": drug["id"], "batch_no": "W001", "quantity": 40},
        headers=auth["pharmacist"],
    ).json()
    assert r["pharmacy_quantity"] == 50  # 10 + 40


def test_transfer_insufficient_warehouse_stock(client, auth):
    drug = make_drug(client, auth)
    purchase(client, auth, drug["id"], quantity=10)
    r = client.post(
        "/warehouse/transfer",
        json={"drug_id": drug["id"], "batch_no": "W001", "quantity": 100},
        headers=auth["pharmacist"],
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "药库库存不足"
    # 药库数量未变
    stocks = client.get("/warehouse/stocks").json()
    assert stocks[0]["quantity"] == 10


def test_transfer_missing_batch(client, auth):
    drug = make_drug(client, auth)
    r = client.post(
        "/warehouse/transfer",
        json={"drug_id": drug["id"], "batch_no": "NOPE", "quantity": 1},
        headers=auth["pharmacist"],
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "药库无该批次库存"


def test_check_adjusts_stock_with_diff(client, auth):
    drug = make_drug(client, auth)
    purchase(client, auth, drug["id"], quantity=100)
    r = client.post(
        "/warehouse/check",
        json={"drug_id": drug["id"], "batch_no": "W001", "actual_quantity": 97},
        headers=auth["pharmacist"],
    )
    assert r.status_code == 200
    body = r.json()
    assert body["expected_quantity"] == 100
    assert body["actual_quantity"] == 97
    assert body["diff"] == -3
    assert body["checked_by"] == "pharmacist"
    # 库存已按实际调整
    stocks = client.get("/warehouse/stocks").json()
    assert stocks[0]["quantity"] == 97


def test_check_missing_batch(client, auth):
    drug = make_drug(client, auth)
    r = client.post(
        "/warehouse/check",
        json={"drug_id": drug["id"], "batch_no": "NOPE", "actual_quantity": 1},
        headers=auth["pharmacist"],
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "药库无该批次库存"


def test_check_history(client, auth):
    drug = make_drug(client, auth)
    purchase(client, auth, drug["id"], quantity=100)
    for actual in (98, 99):
        client.post(
            "/warehouse/check",
            json={"drug_id": drug["id"], "batch_no": "W001", "actual_quantity": actual},
            headers=auth["pharmacist"],
        )
    r = client.get(f"/warehouse/checks?drug_id={drug['id']}")
    assert r.status_code == 200
    checks = r.json()
    assert len(checks) == 2
    # 倒序：最新在前
    assert checks[0]["actual_quantity"] == 99


def test_list_stocks_filter(client, auth):
    drug_a = make_drug(client, auth, name="A药", price=1.0)
    drug_b = make_drug(client, auth, name="B药", price=2.0)
    purchase(client, auth, drug_a["id"], batch_no="A1")
    purchase(client, auth, drug_b["id"], batch_no="B1")
    all_stocks = client.get("/warehouse/stocks").json()
    assert len(all_stocks) == 2
    only_a = client.get(f"/warehouse/stocks?drug_id={drug_a['id']}").json()
    assert len(only_a) == 1
    assert only_a[0]["drug_name"] == "A药"


def test_role_protection(client, auth):
    drug = make_drug(client, auth)
    # 医生不能采购（直接用 doctor 凭据，绕过辅助函数）
    r = client.post(
        "/warehouse/purchase",
        json={"drug_id": drug["id"], "batch_no": "X1", "expiry": "2027-06-30", "quantity": 1},
        headers=auth["doctor"],
    )
    assert r.status_code == 403
    # 收费员不能调拨
    purchase(client, auth, drug["id"])
    r = client.post(
        "/warehouse/transfer",
        json={"drug_id": drug["id"], "batch_no": "W001", "quantity": 1},
        headers=auth["cashier"],
    )
    assert r.status_code == 403
    # 未登录不能盘点
    r = client.post(
        "/warehouse/check",
        json={"drug_id": drug["id"], "batch_no": "W001", "actual_quantity": 1},
    )
    assert r.status_code == 401
