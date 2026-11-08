def setup_admitted(client, auth, stock_quantity=100):
    """建患者/医生/病区/床位/药品/库存并入院，返回 (admission, doctor, drug, stock)。"""
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
        "/drugs/", json={"name": "头孢克肟胶囊", "base_price": 22.0},
        headers=auth["admin"],
    ).json()
    stock = client.post(
        "/pharmacy/stock-in",
        json={"drug_id": drug["id"], "batch_no": "B001", "expiry": "2027-06-30", "quantity": stock_quantity},
        headers=auth["pharmacist"],
    ).json()
    return admission, doctor, drug, stock


def make_order(client, auth, admission, doctor, drug, quantity=2):
    return client.post(
        f"/admissions/{admission['id']}/orders",
        json={"doctor_id": doctor["id"], "drug_id": drug["id"], "order_type": "standing", "quantity": quantity},
        headers=auth["doctor"],
    ).json()


def test_create_dispense_request(client, auth):
    admission, doctor, drug, stock = setup_admitted(client, auth)
    order = make_order(client, auth, admission, doctor, drug)
    r = client.post(f"/orders/{order['id']}/dispense-request", headers=auth["nurse"])
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "pending"
    assert body["quantity"] == 2
    assert body["drug_name"] == "头孢克肟胶囊"


def test_dispense_request_missing_order(client, auth):
    r = client.post("/orders/999/dispense-request", headers=auth["nurse"])
    assert r.status_code == 400
    assert r.json()["detail"] == "医嘱不存在"


def test_dispense_request_on_stopped_order_rejected(client, auth):
    admission, doctor, drug, stock = setup_admitted(client, auth)
    order = make_order(client, auth, admission, doctor, drug)
    client.post(f"/orders/{order['id']}/stop", headers=auth["doctor"])
    r = client.post(f"/orders/{order['id']}/dispense-request", headers=auth["nurse"])
    assert r.status_code == 400
    assert r.json()["detail"] == "该医嘱已停止或已完成，不能摆药"


def test_dispense_request_after_discharge_rejected(client, auth):
    admission, doctor, drug, stock = setup_admitted(client, auth)
    order = make_order(client, auth, admission, doctor, drug)
    client.post(f"/admissions/{admission['id']}/discharge", headers=auth["doctor"])
    r = client.post(f"/orders/{order['id']}/dispense-request", headers=auth["nurse"])
    assert r.status_code == 400
    assert r.json()["detail"] == "该患者已出院，不能摆药"


def test_dispense_deducts_stock(client, auth):
    admission, doctor, drug, stock = setup_admitted(client, auth, stock_quantity=100)
    order = make_order(client, auth, admission, doctor, drug)
    request = client.post(f"/orders/{order['id']}/dispense-request", headers=auth["nurse"]).json()

    r = client.post(f"/dispense-requests/{request['id']}/dispense", headers=auth["pharmacist"])
    assert r.status_code == 200
    assert r.json()["status"] == "dispensed"
    assert r.json()["dispensed_at"] is not None

    got = client.get(f"/pharmacy/stocks/{stock['id']}").json()
    assert got["quantity"] == 98  # 100 - 2


def test_dispense_twice_rejected(client, auth):
    admission, doctor, drug, stock = setup_admitted(client, auth)
    order = make_order(client, auth, admission, doctor, drug)
    request = client.post(f"/orders/{order['id']}/dispense-request", headers=auth["nurse"]).json()
    client.post(f"/dispense-requests/{request['id']}/dispense", headers=auth["pharmacist"])
    r = client.post(f"/dispense-requests/{request['id']}/dispense", headers=auth["pharmacist"])
    assert r.status_code == 400
    assert r.json()["detail"] == "该摆药单已处理"


def test_dispense_insufficient_stock(client, auth):
    admission, doctor, drug, stock = setup_admitted(client, auth, stock_quantity=1)
    order = make_order(client, auth, admission, doctor, drug)
    request = client.post(f"/orders/{order['id']}/dispense-request", headers=auth["nurse"]).json()
    r = client.post(f"/dispense-requests/{request['id']}/dispense", headers=auth["pharmacist"])
    assert r.status_code == 400
    assert r.json()["detail"] == "库存不足：头孢克肟胶囊"
    # 库存未被扣减（事务回滚）
    assert client.get(f"/pharmacy/stocks/{stock['id']}").json()["quantity"] == 1


def test_return_dispensed_restores_stock(client, auth):
    admission, doctor, drug, stock = setup_admitted(client, auth, stock_quantity=100)
    order = make_order(client, auth, admission, doctor, drug)
    request = client.post(f"/orders/{order['id']}/dispense-request", headers=auth["nurse"]).json()
    client.post(f"/dispense-requests/{request['id']}/dispense", headers=auth["pharmacist"])

    r = client.post(f"/dispense-requests/{request['id']}/return", headers=auth["pharmacist"])
    assert r.status_code == 200
    assert r.json()["status"] == "returned"
    assert r.json()["returned_at"] is not None
    # 库存回补
    assert client.get(f"/pharmacy/stocks/{stock['id']}").json()["quantity"] == 100


def test_return_pending_request_rejected(client, auth):
    admission, doctor, drug, stock = setup_admitted(client, auth)
    order = make_order(client, auth, admission, doctor, drug)
    request = client.post(f"/orders/{order['id']}/dispense-request", headers=auth["nurse"]).json()
    r = client.post(f"/dispense-requests/{request['id']}/return", headers=auth["pharmacist"])
    assert r.status_code == 400
    assert r.json()["detail"] == "仅已发药的摆药单可以退药"


def test_return_twice_rejected(client, auth):
    admission, doctor, drug, stock = setup_admitted(client, auth)
    order = make_order(client, auth, admission, doctor, drug)
    request = client.post(f"/orders/{order['id']}/dispense-request", headers=auth["nurse"]).json()
    client.post(f"/dispense-requests/{request['id']}/dispense", headers=auth["pharmacist"])
    client.post(f"/dispense-requests/{request['id']}/return", headers=auth["pharmacist"])
    r = client.post(f"/dispense-requests/{request['id']}/return", headers=auth["pharmacist"])
    assert r.status_code == 400
    assert r.json()["detail"] == "仅已发药的摆药单可以退药"


def test_list_dispense_requests(client, auth):
    admission, doctor, drug, stock = setup_admitted(client, auth)
    order = make_order(client, auth, admission, doctor, drug)
    client.post(f"/orders/{order['id']}/dispense-request", headers=auth["nurse"])
    client.post(f"/orders/{order['id']}/dispense-request", headers=auth["nurse"])
    r = client.get(f"/admissions/{admission['id']}/dispense-requests")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_get_dispense_request_missing(client):
    assert client.get("/dispense-requests/999").status_code == 404
    assert client.get("/admissions/999/dispense-requests").status_code == 404


def test_role_protection(client, auth):
    admission, doctor, drug, stock = setup_admitted(client, auth)
    order = make_order(client, auth, admission, doctor, drug)

    # 医生不能发起摆药
    r = client.post(f"/orders/{order['id']}/dispense-request", headers=auth["doctor"])
    assert r.status_code == 403

    # 护士不能发药
    request = client.post(f"/orders/{order['id']}/dispense-request", headers=auth["nurse"]).json()
    r = client.post(f"/dispense-requests/{request['id']}/dispense", headers=auth["nurse"])
    assert r.status_code == 403

    # 未登录不能申请摆药
    r = client.post(f"/orders/{order['id']}/dispense-request")
    assert r.status_code == 401
