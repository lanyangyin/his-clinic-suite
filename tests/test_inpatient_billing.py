def setup_admitted(client, auth, drug_price=12.5):
    """建患者/医生/病区/床位并入院，返回 (admission, doctor, drug)。"""
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
    ward = client.post("/wards/", json={"name": "内科病区"}, headers=auth["admin"]).json()
    bed = client.post(
        "/beds/", json={"ward_id": ward["id"], "code": "101"}, headers=auth["admin"]
    ).json()
    admission = client.post(
        "/admissions/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"], "bed_id": bed["id"]},
        headers=auth["cashier"],
    ).json()
    drug = client.post(
        "/drugs/", json={"name": "阿莫西林胶囊", "base_price": drug_price},
        headers=auth["admin"],
    ).json()
    return admission, doctor, drug


def make_order(client, auth, admission, doctor, drug, order_type="standing", quantity=2):
    return client.post(
        f"/admissions/{admission['id']}/orders",
        json={"doctor_id": doctor["id"], "drug_id": drug["id"], "order_type": order_type, "quantity": quantity},
        headers=auth["doctor"],
    ).json()


def test_execution_creates_charge(client, auth):
    admission, doctor, drug = setup_admitted(client, auth)
    order = make_order(client, auth, admission, doctor, drug)
    r = client.post(f"/orders/{order['id']}/execute", json={}, headers=auth["nurse"])
    assert r.status_code == 201

    charges = client.get(f"/admissions/{admission['id']}/charges").json()
    assert len(charges) == 1
    charge = charges[0]
    assert charge["quantity"] == 2
    assert charge["unit_price"] == 12.5
    assert charge["amount"] == 25.0  # 2 * 12.5
    assert charge["execution_id"] == r.json()["id"]


def test_standing_order_multiple_executions_accumulate_charges(client, auth):
    admission, doctor, drug = setup_admitted(client, auth)
    order = make_order(client, auth, admission, doctor, drug)
    for _ in range(3):
        client.post(f"/orders/{order['id']}/execute", json={}, headers=auth["nurse"])

    charges = client.get(f"/admissions/{admission['id']}/charges").json()
    assert len(charges) == 3
    assert all(c["amount"] == 25.0 for c in charges)


def test_stat_order_single_charge(client, auth):
    admission, doctor, drug = setup_admitted(client, auth)
    order = make_order(client, auth, admission, doctor, drug, order_type="stat", quantity=1)
    client.post(f"/orders/{order['id']}/execute", json={}, headers=auth["nurse"])
    charges = client.get(f"/admissions/{admission['id']}/charges").json()
    assert len(charges) == 1
    assert charges[0]["amount"] == 12.5


def test_bill_summary(client, auth):
    admission, doctor, drug = setup_admitted(client, auth)
    order = make_order(client, auth, admission, doctor, drug)
    client.post(f"/orders/{order['id']}/execute", json={}, headers=auth["nurse"])
    client.post(f"/orders/{order['id']}/execute", json={}, headers=auth["nurse"])

    bill = client.get(f"/admissions/{admission['id']}/bill").json()
    assert bill["charge_count"] == 2
    assert bill["total_amount"] == 50.0  # 2 次执行 * 2 数量 * 12.5


def test_execute_after_discharge_rejected(client, auth):
    admission, doctor, drug = setup_admitted(client, auth)
    order = make_order(client, auth, admission, doctor, drug)
    client.post(f"/admissions/{admission['id']}/discharge", headers=auth["doctor"])
    r = client.post(f"/orders/{order['id']}/execute", json={}, headers=auth["nurse"])
    assert r.status_code == 400
    assert r.json()["detail"] == "该患者已出院，不能执行医嘱"


def test_charges_and_bill_missing_admission(client, auth):
    assert client.get("/admissions/999/charges").status_code == 404
    assert client.get("/admissions/999/bill").status_code == 404


def test_bill_empty(client, auth):
    admission, doctor, drug = setup_admitted(client, auth)
    bill = client.get(f"/admissions/{admission['id']}/bill").json()
    assert bill["charge_count"] == 0
    assert bill["total_amount"] == 0.0
