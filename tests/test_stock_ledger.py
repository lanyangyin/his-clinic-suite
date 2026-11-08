def setup_stock(client, auth, drug_qty=10, material_qty=4):
    supplier = client.post(
        "/suppliers/", json={"code": "SUP-LED", "name": "流水测试供应商"},
        headers=auth["admin"],
    ).json()
    drug = client.post(
        "/drugs/", json={"name": "流水测试药", "base_price": 10.0},
        headers=auth["admin"],
    ).json()
    material = client.post(
        "/materials/items/",
        json={"code": "MAT-LED", "name": "流水测试耗材", "unit": "包", "price": 20.0},
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
                    "batch_no": "LED-B1",
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
    return supplier, drug, material


def make_outbound(client, auth, drug, quantity=6):
    order = client.post(
        "/warehouse/outbound-orders",
        json={
            "target_type": "pharmacy",
            "target_name": "药房",
            "items": [{"kind": "drug", "drug_id": drug["id"], "batch_no": "LED-B1", "quantity": quantity}],
        },
        headers=auth["pharmacist"],
    ).json()
    client.post(f"/warehouse/outbound-orders/{order['id']}/approve", headers=auth["warehouse"])
    client.post(f"/warehouse/outbound-orders/{order['id']}/issue", headers=auth["warehouse"])
    return order


def test_inbound_ledger_entries(client, auth):
    setup_stock(client, auth)
    rows = client.get("/stock/ledger?ref_type=inbound&warehouse=总库", headers=auth["admin"]).json()
    assert len(rows) == 2
    drug_row = next(r for r in rows if r["kind"] == "drug")
    material_row = next(r for r in rows if r["kind"] == "material")
    assert drug_row["direction"] == "in"
    assert drug_row["quantity"] == 10
    assert drug_row["balance_after"] == 10
    assert drug_row["operator"] == "warehouse"
    assert material_row["quantity"] == 4
    assert material_row["balance_after"] == 4


def test_outbound_ledger_entries(client, auth):
    supplier, drug, material = setup_stock(client, auth)
    make_outbound(client, auth, drug, 6)

    rows = client.get("/stock/ledger?ref_type=outbound", headers=auth["admin"]).json()
    assert len(rows) == 2
    out_row = next(r for r in rows if r["direction"] == "out")
    in_row = next(r for r in rows if r["direction"] == "in")
    assert out_row["warehouse"] == "总库"
    assert out_row["balance_after"] == 4
    assert in_row["warehouse"] == "药房"
    assert in_row["balance_after"] == 6


def test_dispense_and_return_ledger(client, auth):
    supplier, drug, material = setup_stock(client, auth)
    make_outbound(client, auth, drug, 6)

    patient = client.post(
        "/patients/", json={"name": "张三", "id_number": "110101199001011234"},
        headers=auth["cashier"],
    ).json()
    department = client.post(
        "/departments/", json={"name": "内科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/", json={"name": "王医生", "department_id": department["id"]},
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
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 2},
        headers=auth["doctor"],
    )
    client.post("/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"])
    dispense = client.post(
        "/pharmacy/dispense", json={"encounter_id": encounter["id"]}, headers=auth["pharmacist"]
    ).json()

    rows = client.get("/stock/ledger?ref_type=dispense", headers=auth["admin"]).json()
    assert len(rows) == 1
    assert rows[0]["warehouse"] == "药房"
    assert rows[0]["direction"] == "out"
    assert rows[0]["quantity"] == 2
    assert rows[0]["balance_after"] == 4
    assert rows[0]["operator"] == "pharmacist"

    client.post(f"/pharmacy/dispense/{dispense['id']}/return", headers=auth["pharmacist"])
    rows = client.get("/stock/ledger?ref_type=dispense_return", headers=auth["admin"]).json()
    assert len(rows) == 1
    assert rows[0]["direction"] == "in"
    assert rows[0]["balance_after"] == 6


def test_purchase_and_adjust_ledger(client, auth):
    supplier = client.post(
        "/suppliers/", json={"code": "SUP-LED2", "name": "采购供应商"}, headers=auth["admin"]
    ).json()
    drug = client.post(
        "/drugs/", json={"name": "采购测试药", "base_price": 5.0}, headers=auth["admin"]
    ).json()
    client.post(
        "/warehouse/purchase",
        json={"drug_id": drug["id"], "batch_no": "P-LED", "expiry": "2027-06-30", "quantity": 8, "supplier_id": supplier["id"]},
        headers=auth["admin"],
    )
    rows = client.get("/stock/ledger?ref_type=purchase", headers=auth["admin"]).json()
    assert len(rows) == 1
    assert rows[0]["balance_after"] == 8

    client.post(
        "/warehouse/check",
        json={"drug_id": drug["id"], "batch_no": "P-LED", "actual_quantity": 5},
        headers=auth["warehouse"],
    )
    rows = client.get("/stock/ledger?ref_type=adjust", headers=auth["admin"]).json()
    assert len(rows) == 1
    assert rows[0]["direction"] == "out"
    assert rows[0]["quantity"] == 3
    assert rows[0]["balance_after"] == 5


def test_ledger_filters_and_permissions(client, auth):
    setup_stock(client, auth)
    assert client.get("/stock/ledger").status_code == 401
    assert client.get("/stock/ledger", headers=auth["cashier"]).status_code == 403

    materials = client.get("/stock/ledger?kind=material", headers=auth["admin"]).json()
    assert len(materials) == 1
    assert materials[0]["kind"] == "material"

    inbound_only = client.get("/stock/ledger?direction=in", headers=auth["warehouse"]).json()
    assert all(row["direction"] == "in" for row in inbound_only)
