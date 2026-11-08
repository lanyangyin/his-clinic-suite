def make_encounter(client, auth):
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
        "/encounters/", json={"registration_id": reg["id"], "diagnosis": "感冒"},
        headers=auth["doctor"],
    ).json()
    return encounter


def make_item(client, auth, code="CBC", name="血常规", price=20.0):
    return client.post(
        "/lab/items/", json={"code": code, "name": name, "price": price},
        headers=auth["admin"],
    )


def test_create_lab_item(client, auth):
    r = make_item(client, auth)
    assert r.status_code == 201
    assert r.json()["code"] == "CBC"
    assert r.json()["name"] == "血常规"


def test_duplicate_item_code_rejected(client, auth):
    make_item(client, auth)
    r = make_item(client, auth)
    assert r.status_code == 400
    assert r.json()["detail"] == "检验项目编码已存在"


def test_create_lab_request(client, auth):
    encounter = make_encounter(client, auth)
    item = make_item(client, auth).json()
    r = client.post(
        f"/lab/encounters/{encounter['id']}/lab-requests",
        json={"item_id": item["id"]},
        headers=auth["doctor"],
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "pending"
    assert body["item_name"] == "血常规"
    assert body["requested_by"] == "doctor"


def test_request_missing_item(client, auth):
    encounter = make_encounter(client, auth)
    r = client.post(
        f"/lab/encounters/{encounter['id']}/lab-requests",
        json={"item_id": 999},
        headers=auth["doctor"],
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "检验项目不存在"


def test_request_on_closed_encounter_rejected(client, auth):
    encounter = make_encounter(client, auth)
    item = make_item(client, auth).json()
    drug = client.post(
        "/drugs/", json={"name": "A药", "base_price": 10.0}, headers=auth["admin"]
    ).json()
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 1},
        headers=auth["doctor"],
    )
    client.post(
        "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    )
    r = client.post(
        f"/lab/encounters/{encounter['id']}/lab-requests",
        json={"item_id": item["id"]},
        headers=auth["doctor"],
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "就诊已关闭，不能开检验申请"


def test_report_result(client, auth):
    encounter = make_encounter(client, auth)
    item = make_item(client, auth).json()
    request = client.post(
        f"/lab/encounters/{encounter['id']}/lab-requests",
        json={"item_id": item["id"]},
        headers=auth["doctor"],
    ).json()

    r = client.post(
        f"/lab/requests/{request['id']}/report",
        json={"result": "白细胞 6.2×10^9/L，正常范围"},
        headers=auth["lab"],
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "reported"
    assert "白细胞" in body["result"]
    assert body["reported_at"] is not None

    # 重复报告被拒
    again = client.post(
        f"/lab/requests/{request['id']}/report",
        json={"result": "x"},
        headers=auth["lab"],
    )
    assert again.status_code == 400
    assert again.json()["detail"] == "该检验申请已出结果"


def test_report_empty_result_rejected(client, auth):
    encounter = make_encounter(client, auth)
    item = make_item(client, auth).json()
    request = client.post(
        f"/lab/encounters/{encounter['id']}/lab-requests",
        json={"item_id": item["id"]},
        headers=auth["doctor"],
    ).json()
    r = client.post(
        f"/lab/requests/{request['id']}/report",
        json={"result": ""},
        headers=auth["lab"],
    )
    assert r.status_code == 422


def test_list_requests(client, auth):
    encounter = make_encounter(client, auth)
    item_a = make_item(client, auth, code="CBC", name="血常规").json()
    item_b = make_item(client, auth, code="LFT", name="肝功能").json()
    for item in (item_a, item_b):
        client.post(
            f"/lab/encounters/{encounter['id']}/lab-requests",
            json={"item_id": item["id"]},
            headers=auth["doctor"],
        )
    r = client.get(f"/lab/encounters/{encounter['id']}/lab-requests")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_get_request_missing(client):
    assert client.get("/lab/requests/999").status_code == 404


def test_get_item_missing(client):
    assert client.get("/lab/items/999").status_code == 404


def test_role_protection(client, auth):
    encounter = make_encounter(client, auth)
    item = make_item(client, auth).json()
    # 检验技师不能开申请
    r = client.post(
        f"/lab/encounters/{encounter['id']}/lab-requests",
        json={"item_id": item["id"]},
        headers=auth["lab"],
    )
    assert r.status_code == 403
    # 医生不能报告结果
    request = client.post(
        f"/lab/encounters/{encounter['id']}/lab-requests",
        json={"item_id": item["id"]},
        headers=auth["doctor"],
    ).json()
    r = client.post(
        f"/lab/requests/{request['id']}/report",
        json={"result": "x"},
        headers=auth["doctor"],
    )
    assert r.status_code == 403
    # 未登录不能开申请
    r = client.post(
        f"/lab/encounters/{encounter['id']}/lab-requests", json={"item_id": item["id"]}
    )
    assert r.status_code == 401
