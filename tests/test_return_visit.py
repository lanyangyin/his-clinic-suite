"""已收费患者回诊：同一挂号下新建就诊，不重新挂号。"""


def _setup(client, auth):
    patient = client.post(
        "/patients/",
        json={"name": "回诊患者", "id_number": "110101199203039999"},
        headers=auth["cashier"],
    ).json()
    dept = client.post(
        "/departments/", json={"name": "回诊内科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/",
        json={"name": "回诊医生", "department_id": dept["id"]},
        headers=auth["admin"],
    ).json()
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    encounter = client.post(
        "/encounters/",
        json={"registration_id": reg["id"], "diagnosis": "回诊原诊断"},
        headers=auth["doctor"],
    ).json()
    drug = client.post(
        "/drugs/",
        json={"name": "回诊药", "base_price": 10.0},
        headers=auth["admin"],
    ).json()
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 1},
        headers=auth["doctor"],
    )
    payment = client.post(
        "/payments/",
        json={"encounter_id": encounter["id"], "channel": "cash"},
        headers=auth["cashier"],
    )
    assert payment.status_code == 201, payment.text
    return patient, reg, encounter, doctor


def test_return_visit_uses_same_registration(client, auth):
    patient, reg, original, _ = _setup(client, auth)
    response = client.post(
        f"/encounters/{original['id']}/return",
        json={},
        headers=auth["doctor"],
    )
    assert response.status_code == 201, response.text
    returned = response.json()
    assert returned["id"] != original["id"]
    assert returned["registration_id"] == reg["id"]
    assert returned["original_encounter_id"] == original["id"]
    assert returned["status"] == "open"
    assert returned["visit_type"] == "follow_up"

    # 同一次挂号没有新增挂号记录
    regs = client.get(
        "/registrations/", params={"patient_id": patient["id"]}, headers=auth["cashier"]
    )
    assert regs.status_code == 200, regs.text
    assert len(regs.json()) == 1

    # 工作台显示最新回诊就诊
    rows = client.get("/encounters/worklist", headers=auth["doctor"]).json()
    row = next(item for item in rows if item["registration_id"] == reg["id"])
    assert row["encounter_id"] == returned["id"]
    assert row["encounter_status"] == "open"

    # 回诊可以继续开方
    drug = client.post(
        "/drugs/",
        json={"name": "回诊新药", "base_price": 5.0},
        headers=auth["admin"],
    ).json()
    prescribed = client.post(
        f"/encounters/{returned['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 1},
        headers=auth["doctor"],
    )
    assert prescribed.status_code == 201, prescribed.text


def test_return_visit_requires_closed_encounter(client, auth):
    _, _, original, _ = _setup(client, auth)
    returned = client.post(
        f"/encounters/{original['id']}/return", json={}, headers=auth["doctor"]
    )
    assert returned.status_code == 201
    again = client.post(
        f"/encounters/{original['id']}/return", json={}, headers=auth["doctor"]
    )
    # 已有进行中的回诊，返回同一条，不重复创建
    assert again.status_code == 201
    assert again.json()["id"] == returned.json()["id"]

    # 原就诊已收费；未收费的进行中就诊不能再次回诊
    open_return = client.post(
        f"/encounters/{returned.json()['id']}/return",
        json={},
        headers=auth["doctor"],
    )
    assert open_return.status_code == 400

