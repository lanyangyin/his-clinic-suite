def make_drug(client, auth, name="阿莫西林胶囊", price=12.5):
    return client.post(
        "/drugs/", json={"name": name, "base_price": price}, headers=auth["admin"]
    ).json()


def make_supplier(client, auth, code="SUP01", name="国药控股"):
    return client.post(
        "/suppliers/",
        json={"code": code, "name": name, "contact": "张经理", "phone": "13800000000"},
        headers=auth["admin"],
    )


def test_create_supplier(client, auth):
    r = make_supplier(client, auth)
    assert r.status_code == 201
    body = r.json()
    assert body["code"] == "SUP01"
    assert body["name"] == "国药控股"
    assert body["contact"] == "张经理"


def test_duplicate_supplier_code_rejected(client, auth):
    make_supplier(client, auth)
    r = make_supplier(client, auth)
    assert r.status_code == 400
    assert r.json()["detail"] == "供应商编码已存在"


def test_list_and_get_supplier(client, auth):
    supplier = make_supplier(client, auth).json()
    all_suppliers = client.get("/suppliers/").json()
    assert len(all_suppliers) == 1
    assert all_suppliers[0]["id"] == supplier["id"]
    one = client.get(f"/suppliers/{supplier['id']}")
    assert one.status_code == 200
    assert one.json()["name"] == "国药控股"


def test_get_supplier_missing(client):
    assert client.get("/suppliers/999").status_code == 404


def test_purchase_with_supplier_creates_record(client, auth):
    drug = make_drug(client, auth)
    supplier = make_supplier(client, auth).json()
    r = client.post(
        "/warehouse/purchase",
        json={
            "drug_id": drug["id"],
            "batch_no": "S-B001",
            "expiry": "2027-06-30",
            "quantity": 100,
            "supplier_id": supplier["id"],
        },
        headers=auth["admin"],
    )
    assert r.status_code == 201

    purchases = client.get(f"/warehouse/purchases?drug_id={drug['id']}").json()
    assert len(purchases) == 1
    record = purchases[0]
    assert record["supplier_id"] == supplier["id"]
    assert record["supplier_name"] == "国药控股"
    assert record["quantity"] == 100
    assert record["purchased_by"] == "admin"
    assert record["drug_name"] == "阿莫西林胶囊"


def test_purchase_without_supplier(client, auth):
    drug = make_drug(client, auth)
    r = client.post(
        "/warehouse/purchase",
        json={"drug_id": drug["id"], "batch_no": "B002", "expiry": "2027-06-30", "quantity": 50},
        headers=auth["admin"],
    )
    assert r.status_code == 201
    purchases = client.get("/warehouse/purchases").json()
    assert purchases[0]["supplier_id"] is None
    assert purchases[0]["supplier_name"] == ""


def test_purchase_with_missing_supplier(client, auth):
    drug = make_drug(client, auth)
    r = client.post(
        "/warehouse/purchase",
        json={
            "drug_id": drug["id"],
            "batch_no": "B003",
            "expiry": "2027-06-30",
            "quantity": 10,
            "supplier_id": 999,
        },
        headers=auth["admin"],
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "供应商不存在"


def test_purchase_filter_by_supplier(client, auth):
    drug = make_drug(client, auth)
    supplier_a = make_supplier(client, auth, code="SUP01", name="供应商A").json()
    supplier_b = make_supplier(client, auth, code="SUP02", name="供应商B").json()
    for supplier, batch in ((supplier_a, "A1"), (supplier_b, "B1")):
        client.post(
            "/warehouse/purchase",
            json={
                "drug_id": drug["id"],
                "batch_no": batch,
                "expiry": "2027-06-30",
                "quantity": 10,
                "supplier_id": supplier["id"],
            },
            headers=auth["admin"],
        )
    only_a = client.get(f"/warehouse/purchases?supplier_id={supplier_a['id']}").json()
    assert len(only_a) == 1
    assert only_a[0]["supplier_name"] == "供应商A"


def test_role_protection(client, auth):
    r = make_supplier(client, auth)
    assert r.status_code == 201
    # 医生不能维护供应商
    r = client.post(
        "/suppliers/",
        json={"code": "SUP99", "name": "X"},
        headers=auth["doctor"],
    )
    assert r.status_code == 403
    # 未登录
    r = client.post("/suppliers/", json={"code": "SUP98", "name": "X"})
    assert r.status_code == 401


def test_supplier_license_and_suspension_blocks_inbound(client, auth):
    supplier = client.post(
        "/suppliers/",
        json={
            "code": "SUP-LIC",
            "name": "证照供应商",
            "license_no": "沪药监械经营许20260001",
            "license_expiry": "2028-12-31",
            "first_business_approved": True,
        },
        headers=auth["admin"],
    ).json()
    assert supplier["license_no"].startswith("沪药监")
    assert supplier["first_business_approved"] is True
    updated = client.put(
        f"/suppliers/{supplier['id']}",
        json={"status": "blacklist", "blacklist_reason": "证照过期"},
        headers=auth["admin"],
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["status"] == "blacklist"
    drug = make_drug(client, auth, "黑名单供应商药")
    inbound = client.post(
        "/inbound/orders",
        json={
            "order_type": "drug",
            "supplier_id": supplier["id"],
            "items": [
                {
                    "kind": "drug",
                    "drug_id": drug["id"],
                    "batch_no": "BLK-1",
                    "expiry": "2027-12-31",
                    "quantity": 1,
                }
            ],
        },
        headers=auth["warehouse"],
    )
    assert inbound.status_code == 400
    assert "黑名单" in inbound.json()["detail"]


def test_supplier_license_expiry_alert(client, auth):
    expired = client.post(
        "/suppliers/",
        json={
            "code": "SUP-EXP",
            "name": "证照过期供应商",
            "license_no": "EXP-001",
            "license_expiry": "2020-01-01",
        },
        headers=auth["admin"],
    ).json()
    future = client.post(
        "/suppliers/",
        json={
            "code": "SUP-FUT",
            "name": "证照正常供应商",
            "license_no": "FUT-001",
            "license_expiry": "2099-12-31",
        },
        headers=auth["admin"],
    ).json()
    rows = client.get("/suppliers/expiring", headers=auth["admin"]).json()
    ids = {row["id"] for row in rows}
    assert expired["id"] in ids
    assert future["id"] not in ids
    page = client.get("/admin/master/suppliers")
    assert page.status_code == 200
    drug = make_drug(client, auth, "过期供应商药")
    inbound = client.post(
        "/inbound/orders",
        json={
            "order_type": "drug",
            "supplier_id": expired["id"],
            "items": [
                {
                    "kind": "drug",
                    "drug_id": drug["id"],
                    "batch_no": "EXP-1",
                    "expiry": "2027-12-31",
                    "quantity": 1,
                }
            ],
        },
        headers=auth["warehouse"],
    )
    assert inbound.status_code == 400
    assert "证照已过期" in inbound.json()["detail"]
