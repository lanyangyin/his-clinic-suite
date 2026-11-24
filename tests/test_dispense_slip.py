def _make_paid_encounter(client, auth):
    from datetime import date, timedelta

    patient = client.post(
        "/patients/",
        json={"name": "取药凭证患者", "id_number": "110101199001011234"},
        headers=auth["cashier"],
    ).json()
    department = client.post(
        "/departments/", json={"name": "取药凭证科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/",
        json={"name": "取药凭证医生", "department_id": department["id"]},
        headers=auth["admin"],
    ).json()
    registration = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    encounter = client.post(
        "/encounters/",
        json={"registration_id": registration["id"]},
        headers=auth["doctor"],
    ).json()
    drug = client.post(
        "/drugs/",
        json={
            "name": "取药凭证药",
            "spec": "10mg",
            "unit": "盒",
            "dosage_form": "片剂",
            "base_price": 12.0,
        },
        headers=auth["admin"],
    ).json()
    client.post(
        "/pharmacy/stock-in",
        json={
            "drug_id": drug["id"],
            "batch_no": "SLIP001",
            "expiry": (date.today() + timedelta(days=365)).isoformat(),
            "quantity": 10,
        },
        headers=auth["pharmacist"],
    )
    item = client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={
            "drug_id": drug["id"],
            "quantity": 2,
            "dosage": "1片",
            "frequency": "bid",
            "route": "口服",
            "days": 3,
        },
        headers=auth["doctor"],
    )
    assert item.status_code == 201, item.text
    payment = client.post(
        "/payments/", json={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    )
    assert payment.status_code == 201, payment.text
    called = client.post(
        f"/pharmacy/calls/{encounter['id']}",
        json={"window_no": "3号窗", "note": "请取药"},
        headers=auth["pharmacist"],
    )
    assert called.status_code == 200, called.text
    dispensed = client.post(
        "/pharmacy/dispense",
        json={"encounter_id": encounter["id"], "receiver_name": "取药凭证患者"},
        headers=auth["pharmacist"],
    )
    assert dispensed.status_code == 201, dispensed.text
    return encounter, drug


def test_dispense_slip_aggregates_patient_items_and_queue(client, auth):
    encounter, drug = _make_paid_encounter(client, auth)
    r = client.get(
        f"/pharmacy/dispense-slips/{encounter['id']}", headers=auth["pharmacist"]
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["encounter_id"] == encounter["id"]
    assert data["patient"]["name"].endswith("***")
    assert data["patient"]["patient_no"]
    assert data["department"] == "取药凭证科"
    assert data["doctor_name"] == "取药凭证医生"
    assert data["window_no"] == "3号窗"
    assert data["queue_no"]
    assert data["diagnosis"] is not None
    assert len(data["items"]) == 1
    assert data["items"][0]["drug_name"] == drug["name"]
    assert data["items"][0]["usage"]
    assert data["signatures"]["dispenser"]
    assert "不等同于处方" in data["tips"][0]

    html = client.get(f"/print/dispense-slip/{encounter['id']}")
    assert html.status_code == 200
    assert "取药凭证" in html.text
    assert drug["name"] in html.text
    assert "3号窗" in html.text


def test_dispense_slip_rejects_unpaid_or_undispensed(client, auth):
    encounter, _drug = _make_paid_encounter(client, auth)
    # 已发药后凭证可打印；换一个未发药的就诊验证 404
    from datetime import date, timedelta

    patient = client.post(
        "/patients/",
        json={"name": "未发药患者", "id_number": "110101199001011235"},
        headers=auth["cashier"],
    ).json()
    department = client.post(
        "/departments/", json={"name": "未发药科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/",
        json={"name": "未发药医生", "department_id": department["id"]},
        headers=auth["admin"],
    ).json()
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    other = client.post(
        "/encounters/", json={"registration_id": reg["id"]}, headers=auth["doctor"]
    ).json()
    r = client.get(
        f"/pharmacy/dispense-slips/{other['id']}", headers=auth["pharmacist"]
    )
    assert r.status_code == 404
