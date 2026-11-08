def setup_base(client, auth):
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
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    encounter = client.post(
        "/encounters/", json={"registration_id": reg["id"]}, headers=auth["doctor"]
    ).json()
    return patient, doctor, reg, encounter


def test_lab_items_list(client, auth):
    client.post(
        "/lab/items/", json={"code": "CBC", "name": "血常规", "price": 20.0},
        headers=auth["admin"],
    )
    rows = client.get("/lab/items/").json()
    assert len(rows) == 1
    assert rows[0]["name"] == "血常规"


def test_imaging_items_list(client, auth):
    client.post(
        "/pacs/items/",
        json={"code": "CXR", "name": "胸片", "body_part": "胸部", "price": 80.0},
        headers=auth["admin"],
    )
    rows = client.get("/pacs/items/").json()
    assert len(rows) == 1
    assert rows[0]["name"] == "胸片"


def test_pharmacy_stocks_list(client, auth):
    drug = client.post(
        "/drugs/", json={"name": "A药", "base_price": 10.0}, headers=auth["admin"]
    ).json()
    client.post(
        "/pharmacy/stock-in",
        json={"drug_id": drug["id"], "batch_no": "B1", "expiry": "2027-01-01", "quantity": 50},
        headers=auth["pharmacist"],
    )
    rows = client.get("/pharmacy/stocks").json()
    assert len(rows) == 1
    assert rows[0]["quantity"] == 50
    filtered = client.get(f"/pharmacy/stocks?drug_id={drug['id']}").json()
    assert len(filtered) == 1
    assert client.get("/pharmacy/stocks?drug_id=999").json() == []


def test_treatment_list_filter(client, auth):
    patient, doctor, reg, encounter = setup_base(client, auth)
    item = client.post(
        "/charges/items/",
        json={"code": "INFUSION", "name": "静脉输液", "category": "treatment", "price": 15.0},
        headers=auth["admin"],
    ).json()
    order = client.post(
        f"/treatments/encounters/{encounter['id']}",
        json={"item_id": item["id"]}, headers=auth["doctor"],
    ).json()

    pending = client.get("/treatments/?status=pending").json()
    assert len(pending) == 1
    assert pending[0]["id"] == order["id"]

    client.post(f"/treatments/{order['id']}/execute", headers=auth["nurse"])
    assert client.get("/treatments/?status=pending").json() == []
    done = client.get("/treatments/?status=done").json()
    assert len(done) == 1


def test_return_dispense_restores_stock_and_allows_refund(client, auth):
    patient, doctor, reg, encounter = setup_base(client, auth)
    drug = client.post(
        "/drugs/", json={"name": "退药测试药", "base_price": 10.0}, headers=auth["admin"]
    ).json()
    client.post(
        "/pharmacy/stock-in",
        json={"drug_id": drug["id"], "batch_no": "R1", "expiry": "2027-01-01", "quantity": 100},
        headers=auth["pharmacist"],
    )
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 4}, headers=auth["doctor"],
    )
    payment = client.post(
        "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    ).json()
    dispense = client.post(
        "/pharmacy/dispense", json={"encounter_id": encounter["id"]}, headers=auth["pharmacist"]
    ).json()
    stock = client.get(f"/pharmacy/stocks?drug_id={drug['id']}").json()[0]
    assert stock["quantity"] == 96

    # 已发药不能退费
    blocked = client.post(f"/payments/{payment['id']}/refund", headers=auth["cashier"])
    assert blocked.status_code == 400
    assert "已发药" in blocked.json()["detail"]

    returned = client.post(f"/pharmacy/dispense/{dispense['id']}/return", headers=auth["pharmacist"])
    assert returned.status_code == 200
    assert returned.json()["status"] == "returned"
    stock = client.get(f"/pharmacy/stocks?drug_id={drug['id']}").json()[0]
    assert stock["quantity"] == 100

    # 退药后可退费
    refunded = client.post(f"/payments/{payment['id']}/refund", headers=auth["cashier"])
    assert refunded.status_code == 200
    assert refunded.json()["status"] == "refunded"

    # 重复退药被拦截
    again = client.post(f"/pharmacy/dispense/{dispense['id']}/return", headers=auth["pharmacist"])
    assert again.status_code == 400
    assert again.json()["detail"] == "该发药记录已退回"
