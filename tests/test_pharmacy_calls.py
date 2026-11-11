"""药房叫号与发药核对。"""
from datetime import date, timedelta


def _paid_prescription(client, auth):
    drug = client.post(
        "/drugs/", json={"name": "叫号药品", "base_price": 10},
        headers=auth["admin"],
    ).json()
    client.post(
        "/pharmacy/stock-in",
        json={
            "drug_id": drug["id"],
            "batch_no": "CALL-B1",
            "expiry": (date.today() + timedelta(days=365)).isoformat(),
            "quantity": 50,
        },
        headers=auth["pharmacist"],
    )
    dept = client.post(
        "/departments/", json={"name": "叫号科"}, headers=auth["admin"]
    ).json()
    doctor = client.post(
        "/doctors/", json={"name": "叫号医生", "department_id": dept["id"]},
        headers=auth["admin"],
    ).json()
    patient = client.post(
        "/patients/",
        json={"name": "叫号患者", "id_number": "110101199901019999"},
        headers=auth["cashier"],
    ).json()
    reg = client.post(
        "/registrations/",
        json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    encounter = client.post(
        "/encounters/",
        json={"registration_id": reg["id"], "diagnosis": "叫号诊断"},
        headers=auth["doctor"],
    ).json()
    client.post(
        f"/encounters/{encounter['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 2},
        headers=auth["doctor"],
    )
    payment = client.post(
        "/payments/", json={"encounter_id": encounter["id"], "channel": "cash"},
        headers=auth["cashier"],
    )
    assert payment.status_code in (200, 201)
    return patient, encounter, drug


def test_pharmacy_call_and_verified_dispense(client, auth):
    patient, encounter, _ = _paid_prescription(client, auth)
    worklist = client.get("/pharmacy/worklist", headers=auth["pharmacist"])
    assert worklist.status_code == 200
    row = next(r for r in worklist.json() if r["encounter_id"] == encounter["id"])
    assert row["patient_name"] == "叫号患者"
    assert row["call_status"] == "waiting"

    called = client.post(
        f"/pharmacy/calls/{encounter['id']}",
        json={"window_no": "2号窗", "note": "请取药"},
        headers=auth["pharmacist"],
    )
    assert called.status_code == 200, called.text
    queue_no = called.json()["queue_no"]
    assert queue_no.startswith("Q")

    after_call = client.get("/pharmacy/worklist", headers=auth["pharmacist"]).json()
    called_row = next(r for r in after_call if r["encounter_id"] == encounter["id"])
    assert called_row["call_status"] == "called"
    assert called_row["window_no"] == "2号窗"

    dispensed = client.post(
        "/pharmacy/dispense",
        json={"encounter_id": encounter["id"], "note": "核对无误"},
        headers=auth["pharmacist"],
    )
    assert dispensed.status_code == 201, dispensed.text
    body = dispensed.json()
    assert body["verified_by"] == "pharmacist"
    assert body["verified_at"] is not None

    final = client.get("/pharmacy/worklist", headers=auth["pharmacist"]).json()
    assert all(r["encounter_id"] != encounter["id"] for r in final)

    duplicate = client.post(
        "/pharmacy/dispense",
        json={"encounter_id": encounter["id"]},
        headers=auth["pharmacist"],
    )
    assert duplicate.status_code == 400

    assert (
        client.get("/pharmacy/worklist", headers=auth["cashier"]).status_code == 403
    )


def test_pharmacy_pickup_code_and_signature(client, auth):
    from pathlib import Path

    _, encounter, _ = _paid_prescription(client, auth)
    worklist = client.get("/pharmacy/worklist", headers=auth["pharmacist"]).json()
    row = next(r for r in worklist if r["encounter_id"] == encounter["id"])
    code = row["pickup_code"]
    assert code.startswith("P")

    verified = client.get(
        f"/pharmacy/pickup-codes/{code}", headers=auth["pharmacist"]
    )
    assert verified.status_code == 200
    assert verified.json()["encounter_id"] == encounter["id"]

    wrong = client.post(
        "/pharmacy/dispense",
        json={
            "encounter_id": encounter["id"],
            "pickup_code": "P000000",
            "receiver_name": "张三",
        },
        headers=auth["pharmacist"],
    )
    assert wrong.status_code == 400

    dispensed = client.post(
        "/pharmacy/dispense",
        json={
            "encounter_id": encounter["id"],
            "pickup_code": code,
            "receiver_name": "张三",
            "receiver_relation": "本人",
            "note": "扫码核对",
        },
        headers=auth["pharmacist"],
    )
    assert dispensed.status_code == 201, dispensed.text
    body = dispensed.json()
    assert body["receiver_name"] == "张三"
    assert body["signed_at"] is not None

    signature = client.post(
        f"/pharmacy/dispense/{body['id']}/signature",
        files={"file": ("sign.png", b"fake-png", "image/png")},
        headers=auth["pharmacist"],
    )
    assert signature.status_code == 200, signature.text
    path = signature.json()["signature_path"]
    assert path.endswith(".png")

    used = client.get(
        f"/pharmacy/pickup-codes/{code}", headers=auth["pharmacist"]
    )
    assert used.status_code == 400
    Path(path).unlink(missing_ok=True)


def test_pickup_code_generated_at_payment(client, auth):
    _, encounter, _ = _paid_prescription(client, auth)
    payments = client.get(
        "/payments/", params={"encounter_id": encounter["id"]}, headers=auth["cashier"]
    ).json()
    receipt = client.get(f"/print/receipt/{payments[0]['id']}")
    assert receipt.status_code == 200
    assert "取药码" in receipt.text
    assert "P" in receipt.text


def test_dispense_label_contains_patient_and_usage(client, auth):
    patient, encounter, drug = _paid_prescription(client, auth)
    dispensed = client.post(
        "/pharmacy/dispense",
        json={"encounter_id": encounter["id"], "note": "标签测试"},
        headers=auth["pharmacist"],
    )
    assert dispensed.status_code == 201, dispensed.text
    label = client.get(f"/print/dispense-label/{dispensed.json()['id']}")
    assert label.status_code == 200
    assert "发药袋标签" in label.text
    assert "叫号患者" in label.text
    assert drug["name"] in label.text
    assert "请核对" in label.text


def test_nursing_label_contains_patient_and_route(client, auth):
    dept = client.post("/departments/", json={"name": "瓶签科"}, headers=auth["admin"]).json()
    doctor = client.post(
        "/doctors/", json={"name": "瓶签医生", "department_id": dept["id"]},
        headers=auth["admin"],
    ).json()
    patient = client.post(
        "/patients/", json={"name": "瓶签患者", "id_number": "110101199901018888"},
        headers=auth["cashier"],
    ).json()
    reg = client.post(
        "/registrations/", json={"patient_id": patient["id"], "doctor_id": doctor["id"]},
        headers=auth["cashier"],
    ).json()
    enc = client.post(
        "/encounters/", json={"registration_id": reg["id"]}, headers=auth["doctor"]
    ).json()
    drug = client.post(
        "/drugs/", json={"name": "瓶签药", "base_price": 1}, headers=auth["admin"]
    ).json()
    client.post(
        f"/encounters/{enc['id']}/prescriptions",
        json={"drug_id": drug["id"], "quantity": 1, "dosage": "1g", "route": "静滴", "frequency": "qd"},
        headers=auth["doctor"],
    )
    sync = client.post(f"/nursing/encounters/{enc['id']}/sync", headers=auth["nurse"])
    assert sync.status_code == 200, sync.text
    orders = client.get("/nursing/orders", params={"encounter_id": enc["id"]}, headers=auth["nurse"])
    assert orders.status_code == 200
    order = orders.json()[0]
    label = client.get(f"/print/nursing-label/{order['id']}")
    assert label.status_code == 200
    assert "瓶签患者" in label.text
    assert "瓶签药" in label.text
    assert "静滴" in label.text
