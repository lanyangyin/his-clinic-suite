def setup_admitted(client, auth):
    """建患者/医生/病区/床位并办理入院，返回 (admission)。"""
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
    return admission, doctor


def make_drug(client, auth, name="阿莫西林胶囊", base_price=12.5):
    return client.post(
        "/drugs/", json={"name": name, "base_price": base_price}, headers=auth["admin"]
    ).json()


def test_create_standing_order(client, auth):
    admission, doctor = setup_admitted(client, auth)
    drug = make_drug(client, auth)
    r = client.post(
        f"/admissions/{admission['id']}/orders",
        json={"doctor_id": doctor["id"], "drug_id": drug["id"], "order_type": "standing", "quantity": 2},
        headers=auth["doctor"],
    )
    assert r.status_code == 201
    body = r.json()
    assert body["order_type"] == "standing"
    assert body["status"] == "open"
    assert body["drug_name"] == "阿莫西林胶囊"


def test_order_invalid_type_rejected(client, auth):
    admission, doctor = setup_admitted(client, auth)
    drug = make_drug(client, auth)
    r = client.post(
        f"/admissions/{admission['id']}/orders",
        json={"doctor_id": doctor["id"], "drug_id": drug["id"], "order_type": "long", "quantity": 2},
        headers=auth["doctor"],
    )
    assert r.status_code == 422


def test_order_for_discharged_patient_rejected(client, auth):
    admission, doctor = setup_admitted(client, auth)
    drug = make_drug(client, auth)
    client.post(f"/admissions/{admission['id']}/discharge", headers=auth["doctor"])
    r = client.post(
        f"/admissions/{admission['id']}/orders",
        json={"doctor_id": doctor["id"], "drug_id": drug["id"], "order_type": "standing", "quantity": 1},
        headers=auth["doctor"],
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "该患者已出院，不能开医嘱"


def test_order_missing_drug(client, auth):
    admission, doctor = setup_admitted(client, auth)
    r = client.post(
        f"/admissions/{admission['id']}/orders",
        json={"doctor_id": doctor["id"], "drug_id": 999, "order_type": "stat", "quantity": 1},
        headers=auth["doctor"],
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "药品不存在"


def test_standing_order_executed_multiple_times(client, auth):
    admission, doctor = setup_admitted(client, auth)
    drug = make_drug(client, auth)
    order = client.post(
        f"/admissions/{admission['id']}/orders",
        json={"doctor_id": doctor["id"], "drug_id": drug["id"], "order_type": "standing", "quantity": 1},
        headers=auth["doctor"],
    ).json()

    first = client.post(
        f"/orders/{order['id']}/execute", json={"note": "早班"}, headers=auth["nurse"]
    )
    second = client.post(
        f"/orders/{order['id']}/execute", json={"note": "晚班"}, headers=auth["nurse"]
    )
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["order_id"] == order["id"]
    # 长期医嘱保持 open
    got = client.get(f"/orders/{order['id']}").json()
    assert got["status"] == "open"


def test_stat_order_finished_after_one_execution(client, auth):
    admission, doctor = setup_admitted(client, auth)
    drug = make_drug(client, auth)
    order = client.post(
        f"/admissions/{admission['id']}/orders",
        json={"doctor_id": doctor["id"], "drug_id": drug["id"], "order_type": "stat", "quantity": 1},
        headers=auth["doctor"],
    ).json()

    r = client.post(f"/orders/{order['id']}/execute", json={}, headers=auth["nurse"])
    assert r.status_code == 201
    got = client.get(f"/orders/{order['id']}").json()
    assert got["status"] == "finished"

    again = client.post(f"/orders/{order['id']}/execute", json={}, headers=auth["nurse"])
    assert again.status_code == 400
    assert again.json()["detail"] == "该医嘱已停止或已完成，不能执行"


def test_stop_standing_order(client, auth):
    admission, doctor = setup_admitted(client, auth)
    drug = make_drug(client, auth)
    order = client.post(
        f"/admissions/{admission['id']}/orders",
        json={"doctor_id": doctor["id"], "drug_id": drug["id"], "order_type": "standing", "quantity": 1},
        headers=auth["doctor"],
    ).json()

    r = client.post(f"/orders/{order['id']}/stop", headers=auth["doctor"])
    assert r.status_code == 200
    assert r.json()["status"] == "stopped"

    # 停止后不能执行
    execute = client.post(f"/orders/{order['id']}/execute", json={}, headers=auth["nurse"])
    assert execute.status_code == 400
    assert execute.json()["detail"] == "该医嘱已停止或已完成，不能执行"

    # 不能重复停止
    again = client.post(f"/orders/{order['id']}/stop", headers=auth["doctor"])
    assert again.status_code == 400
    assert again.json()["detail"] == "该医嘱已停止或已完成"


def test_list_admission_orders(client, auth):
    admission, doctor = setup_admitted(client, auth)
    drug = make_drug(client, auth)
    for order_type in ("standing", "stat"):
        client.post(
            f"/admissions/{admission['id']}/orders",
            json={"doctor_id": doctor["id"], "drug_id": drug["id"], "order_type": order_type, "quantity": 1},
            headers=auth["doctor"],
        )
    r = client.get(f"/admissions/{admission['id']}/orders")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_list_orders_missing_admission(client):
    assert client.get("/admissions/999/orders").status_code == 404


def test_get_order_missing(client):
    assert client.get("/orders/999").status_code == 404


def test_role_protection(client, auth):
    admission, doctor = setup_admitted(client, auth)
    drug = make_drug(client, auth)
    order_payload = {
        "doctor_id": doctor["id"],
        "drug_id": drug["id"],
        "order_type": "standing",
        "quantity": 1,
    }
    # 护士不能开医嘱
    r = client.post(
        f"/admissions/{admission['id']}/orders",
        json=order_payload,
        headers=auth["nurse"],
    )
    assert r.status_code == 403

    # 医生不能执行医嘱
    order = client.post(
        f"/admissions/{admission['id']}/orders",
        json=order_payload,
        headers=auth["doctor"],
    ).json()
    r = client.post(f"/orders/{order['id']}/execute", json={}, headers=auth["doctor"])
    assert r.status_code == 403

    # 未登录不能开医嘱
    r = client.post(f"/admissions/{admission['id']}/orders", json=order_payload)
    assert r.status_code == 401
