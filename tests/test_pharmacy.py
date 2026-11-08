from datetime import date, timedelta


def make_drug(client, auth, name="A药", base_price=10.0):
    return client.post(
        "/drugs/", json={"name": name, "base_price": base_price}, headers=auth["admin"]
    ).json()


def make_registration(client, auth):
    patient = client.post(
        "/patients/", json={"name": "张三", "id_number": "110101199001011234"},
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
    return client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()


def make_paid_encounter(client, auth):
    reg = make_registration(client, auth)
    encounter = client.post(
        "/encounters/", json={"registration_id": reg["id"]}, headers=auth["doctor"]
    ).json()
    drug = make_drug(client, auth, "A药", 10.0)
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 1},
        headers=auth["doctor"],
    )
    client.post(
        "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    )
    client.post(
        "/pharmacy/stock-in",
        json={
            "drug_id": drug["id"],
            "batch_no": "B001",
            "expiry": "2027-06-30",
            "quantity": 10,
        },
        headers=auth["pharmacist"],
    )
    return encounter


def stock_in(client, auth, drug_id, batch_no, expiry, location="", quantity=1):
    return client.post(
        "/pharmacy/stock-in",
        json={
            "drug_id": drug_id,
            "batch_no": batch_no,
            "expiry": expiry,
            "location": location,
            "quantity": quantity,
        },
        headers=auth["pharmacist"],
    )


def test_stock_in_new_batch(client, auth):
    drug = make_drug(client, auth)
    r = stock_in(client, auth, drug["id"], "B001", "2027-06-30", "A-01", 100)
    assert r.status_code == 201
    body = r.json()
    assert body["batch_no"] == "B001"
    assert body["quantity"] == 100
    assert body["expiry"] == "2027-06-30"


def test_stock_in_same_batch_merges(client, auth):
    drug = make_drug(client, auth)
    first = stock_in(client, auth, drug["id"], "B001", "2027-06-30", quantity=50).json()
    second = stock_in(client, auth, drug["id"], "B001", "2027-06-30", quantity=30)
    assert second.status_code == 201
    assert second.json()["id"] == first["id"]
    assert second.json()["quantity"] == 80


def test_stock_in_missing_drug(client, auth):
    r = stock_in(client, auth, 999, "B001", "2027-06-30", quantity=10)
    assert r.status_code == 400
    assert r.json()["detail"] == "药品不存在"


def test_stock_in_invalid_quantity(client, auth):
    drug = make_drug(client, auth)
    r = stock_in(client, auth, drug["id"], "B001", "2027-06-30", quantity=0)
    assert r.status_code == 422


def test_get_stock(client, auth):
    drug = make_drug(client, auth)
    stock = stock_in(client, auth, drug["id"], "B001", "2027-06-30", "A-01", 100).json()
    r = client.get(f"/pharmacy/stocks/{stock['id']}")
    assert r.status_code == 200
    assert r.json()["quantity"] == 100


def test_get_stock_missing(client):
    assert client.get("/pharmacy/stocks/999").status_code == 404


def test_dispense_after_payment(client, auth):
    encounter = make_paid_encounter(client, auth)
    r = client.post(
        "/pharmacy/dispense",
        json={"encounter_id": encounter["id"]},
        headers=auth["pharmacist"],
    )
    assert r.status_code == 201


def test_dispense_before_payment_rejected(client, auth):
    reg = make_registration(client, auth)
    encounter = client.post(
        "/encounters/", json={"registration_id": reg["id"]}, headers=auth["doctor"]
    ).json()
    r = client.post(
        "/pharmacy/dispense",
        json={"encounter_id": encounter["id"]},
        headers=auth["pharmacist"],
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "该就诊尚未收费"


def test_dispense_after_refund_rejected(client, auth):
    reg = make_registration(client, auth)
    encounter = client.post(
        "/encounters/", json={"registration_id": reg["id"]}, headers=auth["doctor"]
    ).json()
    drug = make_drug(client, auth)
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 1},
        headers=auth["doctor"],
    )
    pay = client.post(
        "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    ).json()
    client.post(f"/payments/{pay['id']}/refund", headers=auth["cashier"])
    # 退费后不能发药
    r = client.post(
        "/pharmacy/dispense",
        json={"encounter_id": encounter["id"]},
        headers=auth["pharmacist"],
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "该就诊尚未收费"


def test_duplicate_dispense_rejected(client, auth):
    encounter = make_paid_encounter(client, auth)
    client.post(
        "/pharmacy/dispense",
        json={"encounter_id": encounter["id"]},
        headers=auth["pharmacist"],
    )
    r = client.post(
        "/pharmacy/dispense",
        json={"encounter_id": encounter["id"]},
        headers=auth["pharmacist"],
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "该就诊已发药"


def test_dispense_missing_encounter(client, auth):
    r = client.post(
        "/pharmacy/dispense", json={"encounter_id": 999}, headers=auth["pharmacist"]
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "就诊记录不存在"


def test_dispense_requires_stock(client, auth):
    reg = make_registration(client, auth)
    encounter = client.post(
        "/encounters/", json={"registration_id": reg["id"]}, headers=auth["doctor"]
    ).json()
    drug = make_drug(client, auth)
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 5},
        headers=auth["doctor"],
    )
    client.post(
        "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    )
    # 不入库直接发药
    r = client.post(
        "/pharmacy/dispense",
        json={"encounter_id": encounter["id"]},
        headers=auth["pharmacist"],
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "库存不足：A药"


def test_dispense_deducts_stock(client, auth):
    reg = make_registration(client, auth)
    encounter = client.post(
        "/encounters/", json={"registration_id": reg["id"]}, headers=auth["doctor"]
    ).json()
    drug = make_drug(client, auth)
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 30},
        headers=auth["doctor"],
    )
    client.post(
        "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    )
    stock = stock_in(client, auth, drug["id"], "B001", "2027-06-30", quantity=100).json()
    r = client.post(
        "/pharmacy/dispense",
        json={"encounter_id": encounter["id"]},
        headers=auth["pharmacist"],
    )
    assert r.status_code == 201
    got = client.get(f"/pharmacy/stocks/{stock['id']}").json()
    assert got["quantity"] == 70  # 100 - 30


def test_dispense_uses_nearest_expiry_first(client, auth):
    reg = make_registration(client, auth)
    encounter = client.post(
        "/encounters/", json={"registration_id": reg["id"]}, headers=auth["doctor"]
    ).json()
    drug = make_drug(client, auth)
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 80},
        headers=auth["doctor"],
    )
    client.post(
        "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    )
    near = stock_in(client, auth, drug["id"], "B001", "2027-06-30", quantity=50).json()
    far = stock_in(client, auth, drug["id"], "B002", "2028-06-30", quantity=100).json()
    client.post(
        "/pharmacy/dispense",
        json={"encounter_id": encounter["id"]},
        headers=auth["pharmacist"],
    )
    assert client.get(f"/pharmacy/stocks/{near['id']}").json()["quantity"] == 0
    assert client.get(f"/pharmacy/stocks/{far['id']}").json()["quantity"] == 70
    # 近效期批次先用完，远期批次只扣剩余 30


def test_dispense_skips_expired_batch(client, auth):
    reg = make_registration(client, auth)
    encounter = client.post(
        "/encounters/", json={"registration_id": reg["id"]}, headers=auth["doctor"]
    ).json()
    drug = make_drug(client, auth)
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 10},
        headers=auth["doctor"],
    )
    client.post(
        "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    )
    expired = stock_in(
        client,
        auth,
        drug["id"],
        "B000",
        (date.today() - timedelta(days=1)).isoformat(),
        quantity=999,
    ).json()
    valid = stock_in(client, auth, drug["id"], "B001", "2027-06-30", quantity=10).json()
    r = client.post(
        "/pharmacy/dispense",
        json={"encounter_id": encounter["id"]},
        headers=auth["pharmacist"],
    )
    assert r.status_code == 201
    # 过期批次被锁定，数量不变；有效批次被扣完
    assert client.get(f"/pharmacy/stocks/{expired['id']}").json()["quantity"] == 999
    assert client.get(f"/pharmacy/stocks/{valid['id']}").json()["quantity"] == 0


def test_get_dispense(client, auth):
    encounter = make_paid_encounter(client, auth)
    disp = client.post(
        "/pharmacy/dispense",
        json={"encounter_id": encounter["id"]},
        headers=auth["pharmacist"],
    ).json()
    r = client.get(f"/pharmacy/dispense/{disp['id']}")
    assert r.status_code == 200
    assert r.json()["encounter_id"] == encounter["id"]


def test_get_dispense_missing(client):
    assert client.get("/pharmacy/dispense/999").status_code == 404
