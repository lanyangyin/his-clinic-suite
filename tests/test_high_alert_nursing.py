def setup(client, auth):
    patient = client.post(
        "/patients/",
        json={"name": "高危药品患者", "id_number": "110101199001015555"},
        headers=auth["cashier"],
    ).json()
    dept = client.post(
        "/departments/", json={"name": "高危药品科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/",
        json={"name": "高危药品医生", "department_id": dept["id"]},
        headers=auth["admin"],
    ).json()
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    enc = client.post(
        "/encounters/", json={"registration_id": reg["id"]}, headers=auth["doctor"]
    ).json()
    drug = client.post(
        "/drugs/",
        json={
            "name": "高危药品测试",
            "base_price": 50,
            "high_alert": True,
        },
        headers=auth["admin"],
    ).json()
    client.post(
        f"/encounters/{enc['id']}/prescriptions",
        json={
            "drug_id": drug["id"],
            "quantity": 1,
            "dosage": "1g",
            "route": "静滴",
            "days": 1,
        },
        headers=auth["doctor"],
    )
    orders = client.post(
        f"/nursing/encounters/{enc['id']}/sync", headers=auth["nurse"]
    ).json()
    order = next(row for row in orders if row["item_name"] == drug["name"])
    return order


def test_high_alert_requires_second_checker(client, auth):
    order = setup(client, auth)
    assert order["high_alert"] is True

    no_checker = client.post(
        f"/nursing/orders/{order['id']}/prepare",
        json={"solvent": "0.9%氯化钠", "dose": "1g", "batch_no": "B1"},
        headers=auth["nurse"],
    )
    assert no_checker.status_code == 400
    assert "核对人" in no_checker.json()["detail"]

    same = client.post(
        f"/nursing/orders/{order['id']}/prepare",
        json={
            "solvent": "0.9%氯化钠", "dose": "1g", "batch_no": "B1",
            "checked_by": "nurse",
        },
        headers=auth["nurse"],
    )
    assert same.status_code == 400
    assert "不能与配药人相同" in same.json()["detail"]

    ok = client.post(
        f"/nursing/orders/{order['id']}/prepare",
        json={
            "solvent": "0.9%氯化钠", "dose": "1g", "batch_no": "B1",
            "checked_by": "second-nurse",
        },
        headers=auth["nurse"],
    )
    assert ok.status_code == 201, ok.text
    assert ok.json()["checked_by"] == "second-nurse"


def test_non_high_alert_can_skip_checker(client, auth):
    # 普通药品沿用原行为：允许核对人留空
    patient = client.post(
        "/patients/",
        json={"name": "普通药品患者", "id_number": "110101199001014444"},
        headers=auth["cashier"],
    ).json()
    dept = client.post(
        "/departments/", json={"name": "普通药品科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/",
        json={"name": "普通药品医生", "department_id": dept["id"]},
        headers=auth["admin"],
    ).json()
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    enc = client.post(
        "/encounters/", json={"registration_id": reg["id"]}, headers=auth["doctor"]
    ).json()
    drug = client.post(
        "/drugs/", json={"name": "普通药品测试", "base_price": 5},
        headers=auth["admin"],
    ).json()
    client.post(
        f"/encounters/{enc['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 1, "route": "静滴"},
        headers=auth["doctor"],
    )
    order = next(
        row
        for row in client.post(
            f"/nursing/encounters/{enc['id']}/sync", headers=auth["nurse"]
        ).json()
        if row["item_name"] == drug["name"]
    )
    response = client.post(
        f"/nursing/orders/{order['id']}/prepare",
        json={"solvent": "0.9%氯化钠", "dose": "1支"},
        headers=auth["nurse"],
    )
    assert response.status_code == 201
