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


def make_charge_item(client, auth, code="REG", name="挂号费", category="registration", price=10.0, ratio=0.7):
    return client.post(
        "/charges/items/",
        json={"code": code, "name": name, "category": category, "price": price, "insurance_ratio": ratio},
        headers=auth["admin"],
    )


def test_charge_item_crud(client, auth):
    r = make_charge_item(client, auth)
    assert r.status_code == 201
    assert r.json()["code"] == "REG"

    dup = make_charge_item(client, auth)
    assert dup.status_code == 400
    assert dup.json()["detail"] == "收费项目编码已存在"

    by_code = client.get("/charges/items/by-code/REG")
    assert by_code.status_code == 200
    assert by_code.json()["name"] == "挂号费"
    assert client.get("/charges/items/by-code/NOPE").status_code == 404

    items = client.get("/charges/items/?category=registration").json()
    assert len(items) == 1


def test_encounter_auto_charges_registration_and_consultation(client, auth):
    make_charge_item(client, auth, code="REG", name="挂号费", category="registration", price=10.0)
    make_charge_item(client, auth, code="CONSULT", name="诊疗费", category="consultation", price=20.0)
    reg = make_registration(client, auth)
    encounter = client.post(
        "/encounters/", json={"registration_id": reg["id"], "diagnosis": "感冒"},
        headers=auth["doctor"],
    ).json()

    charges = client.get(f"/charges/encounters/{encounter['id']}").json()
    names = {c["item_name"]: c["amount"] for c in charges}
    assert names["挂号费"] == 10.0
    assert names["诊疗费"] == 20.0
    assert all(c["status"] == "pending" for c in charges)


def test_prescription_generates_drug_charge(client, auth):
    reg = make_registration(client, auth)
    encounter = client.post(
        "/encounters/", json={"registration_id": reg["id"]}, headers=auth["doctor"]
    ).json()
    drug = client.post(
        "/drugs/", json={"name": "A药", "base_price": 12.5, "insurance_ratio": 0.8},
        headers=auth["admin"],
    ).json()
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 2},
        headers=auth["doctor"],
    )
    charges = client.get(f"/charges/encounters/{encounter['id']}").json()
    drug_charges = [c for c in charges if c["charge_type"] == "drug"]
    assert len(drug_charges) == 1
    assert drug_charges[0]["item_name"] == "A药"
    assert drug_charges[0]["quantity"] == 2
    assert drug_charges[0]["unit_price"] == 12.5
    assert drug_charges[0]["amount"] == 25.0
    assert drug_charges[0]["insurance_ratio"] == 0.8


def test_lab_and_imaging_generate_charges(client, auth):
    reg = make_registration(client, auth)
    encounter = client.post(
        "/encounters/", json={"registration_id": reg["id"]}, headers=auth["doctor"]
    ).json()
    lab_item = client.post(
        "/lab/items/", json={"code": "CBC", "name": "血常规", "price": 20.0},
        headers=auth["admin"],
    ).json()
    client.post(
        f"/lab/encounters/{encounter['id']}/lab-requests",
        json={"item_id": lab_item["id"]},
        headers=auth["doctor"],
    )
    img_item = client.post(
        "/pacs/items/", json={"code": "CXR", "name": "胸部正位片", "body_part": "胸部", "price": 80.0},
        headers=auth["admin"],
    ).json()
    client.post(
        f"/pacs/encounters/{encounter['id']}/imaging-requests",
        json={"item_id": img_item["id"]},
        headers=auth["doctor"],
    )

    charges = client.get(f"/charges/encounters/{encounter['id']}").json()
    types = {c["charge_type"]: c["amount"] for c in charges}
    assert types["lab"] == 20.0
    assert types["imaging"] == 80.0


def test_payment_aggregates_all_charges(client, auth):
    make_charge_item(client, auth, code="REG", price=10.0)
    make_charge_item(client, auth, code="CONSULT", price=20.0)
    reg = make_registration(client, auth)
    encounter = client.post(
        "/encounters/", json={"registration_id": reg["id"]}, headers=auth["doctor"]
    ).json()
    drug = client.post(
        "/drugs/", json={"name": "A药", "base_price": 12.5, "insurance_ratio": 0.8},
        headers=auth["admin"],
    ).json()
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 2},
        headers=auth["doctor"],
    )

    payment = client.post(
        "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    ).json()
    # 10 + 20 + 25 = 55
    assert payment["amount"] == 55.0
    assert payment["status"] == "paid"

    charges = client.get(f"/charges/encounters/{encounter['id']}").json()
    assert all(c["status"] == "paid" for c in charges)

    summary = client.get(f"/charges/encounters/{encounter['id']}/summary").json()
    assert summary["total_paid"] == 55.0
    assert summary["total_pending"] == 0.0


def test_refund_marks_charges_refunded(client, auth):
    reg = make_registration(client, auth)
    encounter = client.post(
        "/encounters/", json={"registration_id": reg["id"]}, headers=auth["doctor"]
    ).json()
    drug = client.post(
        "/drugs/", json={"name": "A药", "base_price": 10.0}, headers=auth["admin"]
    ).json()
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 1},
        headers=auth["doctor"],
    )
    payment = client.post(
        "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    ).json()
    client.post(f"/payments/{payment['id']}/refund", headers=auth["cashier"])

    charges = client.get(f"/charges/encounters/{encounter['id']}").json()
    assert all(c["status"] == "refunded" for c in charges)
    summary = client.get(f"/charges/encounters/{encounter['id']}/summary").json()
    assert summary["total_refunded"] == 10.0


def test_charge_summary_missing_encounter(client):
    assert client.get("/charges/encounters/999").status_code == 404
    assert client.get("/charges/encounters/999/summary").status_code == 404


def test_charge_item_missing(client):
    assert client.get("/charges/items/999").status_code == 404
