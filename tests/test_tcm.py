"""中药处方与煎药室：开方→审方→发药→浸泡→煎煮→包装→发放。"""


def _setup(client, auth):
    patient = client.post(
        "/patients/",
        json={"name": "中药患者", "id_number": "110101198501019999"},
        headers=auth["cashier"],
    ).json()
    dept = client.post(
        "/departments/", json={"name": "中医科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/",
        json={"name": "中医医生", "department_id": dept["id"]},
        headers=auth["admin"],
    ).json()
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    encounter = client.post(
        "/encounters/",
        json={"registration_id": reg["id"], "diagnosis": "风寒感冒"},
        headers=auth["doctor"],
    ).json()
    herb_a = client.post(
        "/tcm/herbs",
        json={
            "code": "TCM-GC",
            "name": "桂枝",
            "price_per_g": 0.1,
            "toxicity": "none",
        },
        headers=auth["admin"],
    ).json()
    herb_b = client.post(
        "/tcm/herbs",
        json={
            "code": "TCM-BS",
            "name": "白芍",
            "price_per_g": 0.2,
        },
        headers=auth["admin"],
    ).json()
    return patient, encounter, herb_a, herb_b


def _prescribe(client, auth, encounter, herb_a, herb_b, service="decoct"):
    return client.post(
        f"/tcm/encounters/{encounter['id']}/prescriptions",
        json={
            "formula_name": "桂枝汤",
            "usage": "internal",
            "packs": 3,
            "decoct_service": service,
            "decoction_method": "常规煎煮，先煎",
            "items": [
                {"herb_id": herb_a["id"], "dose_g": 9, "special": "none"},
                {"herb_id": herb_b["id"], "dose_g": 6, "special": "last"},
            ],
        },
        headers=auth["doctor"],
    )


def test_tcm_prescription_and_decoction_flow(client, auth):
    patient, encounter, herb_a, herb_b = _setup(client, auth)
    response = _prescribe(client, auth, encounter, herb_a, herb_b)
    assert response.status_code == 201, response.text
    prescription = response.json()
    assert prescription["prescription_no"].startswith("TCM")
    assert prescription["status"] == "pending"
    assert prescription["total_amount"] == 6.3  # (0.1*9+0.2*6)*3
    assert len(prescription["items"]) == 2
    assert prescription["items"][1]["special"] == "last"

    work = client.get(
        "/tcm/prescriptions", params={"status": "pending"}, headers=auth["pharmacist"]
    ).json()
    assert any(row["prescription_no"] == prescription["prescription_no"] for row in work)

    reviewed = client.post(
        f"/tcm/prescriptions/{prescription['id']}/review", headers=auth["pharmacist"]
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "reviewed"

    dispensed = client.post(
        f"/tcm/prescriptions/{prescription['id']}/dispense",
        headers=auth["pharmacist"],
    )
    assert dispensed.status_code == 200
    assert dispensed.json()["status"] == "decocting"

    orders = client.get(
        "/tcm/decoction-orders", headers=auth["decoction"]
    ).json()
    order = next(row for row in orders if row["prescription_id"] == prescription["id"])
    assert order["patient_name"] == "中药患者"

    soaked = client.post(
        f"/tcm/decoction-orders/{order['id']}/soak",
        json={"soak_minutes": 30},
        headers=auth["decoction"],
    )
    assert soaked.status_code == 200
    assert soaked.json()["status"] == "soaking"

    decocted = client.post(
        f"/tcm/decoction-orders/{order['id']}/decoct",
        json={"machine_no": "煎药机-1", "decoct_minutes": 40},
        headers=auth["decoction"],
    )
    assert decocted.status_code == 200
    assert decocted.json()["status"] == "decocting"

    packaged = client.post(
        f"/tcm/decoction-orders/{order['id']}/package",
        json={"bags": 6, "bag_volume_ml": 200, "expires_days": 7},
        headers=auth["decoction"],
    )
    assert packaged.status_code == 200, packaged.text
    body = packaged.json()
    assert body["status"] == "completed"
    assert body["bags"] == 6
    assert len(body["bags_list"]) == 6
    assert "中药患者" in body["bags_list"][0]["label"]

    issued = client.post(
        f"/tcm/decoction-orders/{order['id']}/issue",
        json={"pickup_method": "self", "receiver": "患者本人"},
        headers=auth["decoction"],
    )
    assert issued.status_code == 200
    assert issued.json()["status"] == "issued"

    detail = client.get(
        f"/tcm/prescriptions/{prescription['id']}", headers=auth["pharmacist"]
    ).json()
    assert detail["status"] == "completed"


def test_self_decoct_and_invalid_transitions(client, auth):
    patient, encounter, herb_a, herb_b = _setup(client, auth)
    prescription = _prescribe(client, auth, encounter, herb_a, herb_b, service="self").json()
    # 未审核不能发药
    blocked = client.post(
        f"/tcm/prescriptions/{prescription['id']}/dispense",
        headers=auth["pharmacist"],
    )
    assert blocked.status_code == 400
    client.post(f"/tcm/prescriptions/{prescription['id']}/review", headers=auth["pharmacist"])
    dispensed = client.post(
        f"/tcm/prescriptions/{prescription['id']}/dispense",
        headers=auth["pharmacist"],
    ).json()
    assert dispensed["status"] == "completed"
    orders = client.get("/tcm/decoction-orders", headers=auth["pharmacist"]).json()
    assert all(row["prescription_id"] != prescription["id"] for row in orders)


def test_tcm_permissions(client, auth):
    patient, encounter, herb_a, herb_b = _setup(client, auth)
    response = _prescribe(client, auth, encounter, herb_a, herb_b)
    prescription = response.json()
    # 医生不能审核中药处方
    denied = client.post(
        f"/tcm/prescriptions/{prescription['id']}/review", headers=auth["doctor"]
    )
    assert denied.status_code == 403
    # 药师不能开方
    assert client.post(
        f"/tcm/encounters/{encounter['id']}/prescriptions",
        json={"items": [{"herb_id": herb_a["id"], "dose_g": 1}]},
        headers=auth["pharmacist"],
    ).status_code == 403
