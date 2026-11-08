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


def make_drug(client, auth, name="阿莫西林胶囊", base_price=12.5):
    return client.post(
        "/drugs/", json={"name": name, "base_price": base_price}, headers=auth["admin"]
    ).json()


def test_create_encounter_marks_registration_visited(client, auth):
    reg = make_registration(client, auth)
    r = client.post(
        "/encounters/",
        json={"registration_id": reg["id"], "diagnosis": "感冒"},
        headers=auth["doctor"],
    )
    assert r.status_code == 201
    assert r.json()["status"] == "open"
    assert r.json()["diagnosis"] == "感冒"
    # 状态流转：挂号从 registered -> visited
    got = client.get(f"/registrations/{reg['id']}")
    assert got.json()["status"] == "visited"


def test_duplicate_encounter_returns_existing(client, auth):
    reg = make_registration(client, auth)
    payload = {"registration_id": reg["id"], "diagnosis": "感冒"}
    first = client.post("/encounters/", json=payload, headers=auth["doctor"])
    second = client.post("/encounters/", json=payload, headers=auth["doctor"])
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]


def test_encounter_missing_registration(client, auth):
    r = client.post(
        "/encounters/",
        json={"registration_id": 999, "diagnosis": "x"},
        headers=auth["doctor"],
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "挂号记录不存在"


def test_add_prescription_item(client, auth):
    reg = make_registration(client, auth)
    encounter = client.post(
        "/encounters/", json={"registration_id": reg["id"]}, headers=auth["doctor"]
    ).json()
    drug = make_drug(client, auth)
    r = client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 2},
        headers=auth["doctor"],
    )
    assert r.status_code == 201
    body = r.json()
    assert body["drug_id"] == drug["id"]
    assert body["drug_name"] == "阿莫西林胶囊"
    assert body["quantity"] == 2
    assert body["unit_price"] == 12.5  # 单价由药品基准价自动带出


def test_add_prescription_item_missing_encounter(client, auth):
    r = client.post(
        "/encounters/999/prescriptions",
        json={"drug_id": 1, "quantity": 1},
        headers=auth["doctor"],
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "就诊记录不存在"


def test_add_prescription_item_missing_drug(client, auth):
    reg = make_registration(client, auth)
    encounter = client.post(
        "/encounters/", json={"registration_id": reg["id"]}, headers=auth["doctor"]
    ).json()
    r = client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": 999, "quantity": 1},
        headers=auth["doctor"],
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "药品不存在"


def test_prescription_quantity_validation(client, auth):
    reg = make_registration(client, auth)
    encounter = client.post(
        "/encounters/", json={"registration_id": reg["id"]}, headers=auth["doctor"]
    ).json()
    r = client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": 1, "quantity": 0},
        headers=auth["doctor"],
    )
    assert r.status_code == 422


def test_list_prescriptions(client, auth):
    reg = make_registration(client, auth)
    encounter = client.post(
        "/encounters/", json={"registration_id": reg["id"]}, headers=auth["doctor"]
    ).json()
    drug_a = make_drug(client, auth, name="A药", base_price=1.0)
    drug_b = make_drug(client, auth, name="B药", base_price=2.0)
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug_a["id"], "quantity": 1},
        headers=auth["doctor"],
    )
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug_b["id"], "quantity": 2},
        headers=auth["doctor"],
    )
    r = client.get(f"/encounters/{encounter['id']}/prescriptions")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 2
    assert {i["drug_name"] for i in items} == {"A药", "B药"}


def test_list_prescriptions_missing_encounter(client):
    assert client.get("/encounters/999/prescriptions").status_code == 404


def test_get_encounter_missing(client):
    assert client.get("/encounters/999").status_code == 404
